from __future__ import annotations

import argparse
import json
import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageFile
from tqdm import tqdm
import cv2

import numpy as np
from math import atan2, degrees, radians, cos, sin

# Be tolerant to slightly truncated images instead of failing the whole run.
ImageFile.LOAD_TRUNCATED_IMAGES = True
# Disable PIL's decompression bomb guard for very large document scans.
Image.MAX_IMAGE_PIXELS = None

LOG = logging.getLogger("ppocr_rec_builder")

IMG_EXTS = (".png", ".jpg", ".jpeg")

@dataclass(frozen=True)
class SplitConfig:
    """How a source split maps to an output split."""

    src_name: str  # subfolder name in the source dataset (e.g. "train", "test")
    dst_name: str  # subfolder name in the output dataset (e.g. "train", "test")
    gt_filename: str  # e.g. "rec_gt_train.txt"


@dataclass
class CropResult:
    """Result of processing a single annotation file."""

    crops_written: int = 0
    crops_skipped: int = 0
    gt_lines: List[str] = None  # type: ignore[assignment]
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.gt_lines is None:
            self.gt_lines = []
        if self.errors is None:
            self.errors = []


def _find_image_path(images_dir: Path, declared_name: str, stem: str) -> Optional[Path]:
    """Return the actual image path for an annotation.

    Tries the filename declared inside the JSON first, then falls back to the
    annotation stem with any of the known image extensions.
    """
    if declared_name:
        candidate = images_dir / declared_name
        if candidate.is_file():
            return candidate
    for ext in IMG_EXTS:
        candidate = images_dir / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _normalise_text(text: str) -> str:
    """Make the text safe for a TAB-separated GT line.

    - Replaces tabs/newlines with a single space (TAB is the column separator).
    - Strips leading/trailing whitespace.
    - Preserves all other Unicode characters.
    """
    if text is None or not isinstance(text, str):
        return ""
    # Replace control characters that would break a single-line TSV record.
    cleaned = (
        text.replace("\r\n", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )
    # Collapse runs of spaces lightly while keeping intentional inner spacing.
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def _order_points(pts):
    """Order 4 points as [TL, TR, BR, BL] (clockwise from top-left)."""
    y_sorted = pts[np.argsort(pts[:, 1])]
    top_pts = y_sorted[:2]  
    bottom_pts = y_sorted[2:]  
    
    tl = top_pts[np.argmin(top_pts[:, 0])]
    tr = top_pts[np.argmax(top_pts[:, 0])]
    
    bl = bottom_pts[np.argmin(bottom_pts[:, 0])]
    br = bottom_pts[np.argmax(bottom_pts[:, 0])]
    
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _crop_polygon_rotated(img, points, pad_h: int, pad_v: int):
    """Crop rotated rectangle using perspective transform (FIXED dimensions)."""
    points = np.array(points, dtype=np.float32)
    
    src_pts = _order_points(points)
    
    
    width_top = np.linalg.norm(src_pts[0] - src_pts[1])
    width_bottom = np.linalg.norm(src_pts[3] - src_pts[2])
    width = int(round((width_top + width_bottom) / 2))
    
    height_left = np.linalg.norm(src_pts[0] - src_pts[3])
    height_right = np.linalg.norm(src_pts[1] - src_pts[2])
    height = int(round((height_left + height_right) / 2))
    
    width_padded = width + pad_h * 2
    height_padded = height + pad_v * 2
    
    dst_pts = np.array([
        [0, 0],  # TL
        [width_padded - 1, 0],  # TR
        [width_padded - 1, height_padded - 1],  # BR
        [0, height_padded - 1],  # BL
    ], dtype=np.float32)
    
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    img_cv = np.array(img.convert("RGB"))
    cropped = cv2.warpPerspective(
        img_cv, M, 
        (width_padded, height_padded),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    
    return Image.fromarray(cropped)

def _crop_from_bbox(
    img, 
    bbox: Sequence, 
    bbox_format: str,
    pad_h: int, 
    pad_v: int,
    img_w: int, 
    img_h: int
):
    """Crop image using original bbox format."""
    
    fmt = bbox_format.lower()
    
    # For polygon with 4 points (rotated rectangle)
    if fmt == "polygon":
        if not bbox or len(bbox) != 4:
            raise ValueError(f"Expected 4 points for polygon, got {len(bbox) if bbox else 0}")
        
        # Check if we have 4 points with x,y coordinates
        if not all(hasattr(p, "__len__") and len(p) == 2 for p in bbox):
            raise ValueError(f"Invalid polygon points: {bbox}")
        
        # Crop the rotated rectangle
        crop = _crop_polygon_rotated(img, bbox, pad_h, pad_v)
        
        # Get bounding box coordinates for reference (not used for actual crop)
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]
        bbox_coords = (min(xs), min(ys), max(xs), max(ys))
        
        return crop, bbox_coords
    
    # For standard axis-aligned bboxes
    if len(bbox) != 4:
        raise ValueError(f"Expected bbox of length 4 for {fmt}, got {len(bbox)}")
    
    if fmt == "xywh":
        x, y, w, h = bbox
        x1, y1, x2, y2 = x, y, x + w, y + h
    elif fmt in ("xyxy", "x1y1x2y2"):
        x1, y1, x2, y2 = bbox
    else:
        raise ValueError(f"Unsupported bbox_format: {fmt}")
    
    # Convert to int and apply padding
    x1 = int(round(max(0, x1 - pad_h)))
    y1 = int(round(max(0, y1 - pad_v)))
    x2 = int(round(min(img_w, x2 + pad_h)))
    y2 = int(round(min(img_h, y2 + pad_v)))
    
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Degenerate crop region: ({x1},{y1},{x2},{y2})")
    
    crop = img.crop((x1, y1, x2, y2))
    return crop, (x1, y1, x2, y2)


def process_annotation(
    ann_path: Path,
    images_dir: Path,
    out_images_dir: Path,
    dst_split_name: str,
    pad_h: int,
    pad_v: int,
    jpeg_quality: int,
) -> CropResult:
    """Process a single annotation JSON file and emit cropped JPGs + GT lines."""
    result = CropResult()
    try:
        with ann_path.open("r", encoding="utf-8") as fh:
            ann = json.load(fh)
    except Exception as exc: 
        result.errors.append(f"{ann_path.name}: failed to parse JSON: {exc}")
        return result

    declared_name = ann.get("image", "")
    bbox_format = ann.get("bbox_format", "")
    objects = ann.get("objects") or []
    if not objects:
        return result

    img_path = _find_image_path(images_dir, declared_name, ann_path.stem)
    if img_path is None:
        result.errors.append(
            f"{ann_path.name}: image not found "
            f"(declared={declared_name!r}, stem={ann_path.stem!r})"
        )
        return result

    try:
        with Image.open(img_path) as img:
            img.load()
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            elif img.mode == "L":
                # JPEG supports L, but recognition models expect RGB; convert.
                img = img.convert("RGB")
            img_w, img_h = img.size

            # Allow JSON-provided dims to override if mismatch (rare).
            ann_w = int(ann.get("width") or img_w)
            ann_h = int(ann.get("height") or img_h)
            if (ann_w, ann_h) != (img_w, img_h):
                LOG.debug(
                    "Dim mismatch for %s: ann=%sx%s img=%sx%s — using image dims.",
                    ann_path.name, ann_w, ann_h, img_w, img_h,
                )

            stem = img_path.stem  # original filename without extension
            for idx, obj in enumerate(objects):
                text = _normalise_text(obj.get("text", ""))
                # Skip crops whose annotation text is empty or a single
                # character — they're not useful for REC training/eval.
                if len(text) < 5:
                    result.crops_skipped += 1
                    LOG.debug(
                        f"Skipping crop {stem}_line_{idx:03d} in {ann_path.name}: "
                        f"text too short (len={len(text)}, text={text!r})"
                    )
                    continue
                bbox = obj.get("bbox")
                if not bbox:
                    result.crops_skipped += 1
                    LOG.debug(
                        f"Skipping crop {stem}_line_{idx:03d} in {ann_path.name}: "
                        f"no bbox provided"
                    )
                    continue
                crop, _ = _crop_from_bbox(img, bbox, bbox_format, pad_h, pad_v, img_w, img_h)
                crop_name = f"{stem}_line_{idx:03d}.jpg"
                crop_path = out_images_dir / crop_name
                # High-quality JPEG: quality + chroma subsampling off + optimize.
                crop.save(
                    crop_path,
                    format="JPEG",
                    quality=jpeg_quality,
                    subsampling=0,
                    optimize=True,
                    progressive=False,
                )
                rel_path = f"{dst_split_name}/images/{crop_name}"
                result.gt_lines.append(f"{rel_path}\t{text}")
                result.crops_written += 1
    except Exception as exc:
        result.errors.append(f"{ann_path.name}: failed to process image: {exc}")
        return result

    return result


# --------------------------------------------------------------------------- #
# Worker entrypoint (must be top-level for multiprocessing)
# --------------------------------------------------------------------------- #


def _worker(args: tuple) -> CropResult:
    (
        ann_path_str,
        images_dir_str,
        out_images_dir_str,
        dst_split_name,
        pad_h,
        pad_v,
        jpeg_quality,
    ) = args
    return process_annotation(
        Path(ann_path_str),
        Path(images_dir_str),
        Path(out_images_dir_str),
        dst_split_name,
        pad_h,
        pad_v,
        jpeg_quality,
    )



def _iter_annotations(annotations_dir: Path, limit: Optional[int]) -> List[Path]:
    files = sorted(p for p in annotations_dir.iterdir() if p.suffix.lower() == ".json")
    if limit is not None and limit > 0:
        files = files[:limit]
    return files


def run_split(
    src_root: Path,
    dst_root: Path,
    split: SplitConfig,
    pad_h: int,
    pad_v: int,
    jpeg_quality: int,
    workers: int,
    limit: Optional[int],
) -> Tuple[int, int, int, int]:
    """Process a single split. Returns (n_anns, n_crops, n_skipped, n_errors)."""
    images_dir = src_root / split.src_name / "images"
    annotations_dir = src_root / split.src_name / "annotations"

    if not annotations_dir.is_dir():
        LOG.warning("Skipping split %r: %s does not exist.", split.src_name, annotations_dir)
        return 0, 0, 0, 0
    if not images_dir.is_dir():
        LOG.warning("Skipping split %r: %s does not exist.", split.src_name, images_dir)
        return 0, 0, 0, 0

    out_images_dir = dst_root / split.dst_name / "images"
    out_images_dir.mkdir(parents=True, exist_ok=True)
    gt_path = dst_root / split.gt_filename

    ann_files = _iter_annotations(annotations_dir, limit)
    if not ann_files:
        LOG.warning("No annotation files in %s", annotations_dir)
        # still create an empty GT file for downstream tooling
        gt_path.write_text("", encoding="utf-8")
        return 0, 0, 0, 0

    LOG.info(
        "Split %r: %d annotations, output dir=%s",
        split.src_name, len(ann_files), out_images_dir,
    )

    work_items = [
        (
            str(p),
            str(images_dir),
            str(out_images_dir),
            split.dst_name,
            pad_h,
            pad_v,
            jpeg_quality,
        )
        for p in ann_files
    ]

    total_crops = 0
    total_skipped = 0
    total_errors = 0
    error_log: List[str] = []

    # Open GT file once and stream lines as they come in.
    with gt_path.open("w", encoding="utf-8", newline="\n") as gt_fh:
        if workers <= 1:
            iterator: Iterable[CropResult] = (
                _worker(item) for item in work_items
            )
            for res in tqdm(iterator, total=len(work_items), desc=f"{split.src_name}->{split.dst_name}"):
                if res.gt_lines:
                    gt_fh.write("\n".join(res.gt_lines))
                    gt_fh.write("\n")
                total_crops += res.crops_written
                total_skipped += res.crops_skipped
                if res.errors:
                    total_errors += len(res.errors)
                    error_log.extend(res.errors)
        else:
            ctx = mp.get_context("spawn")
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
                futures = [ex.submit(_worker, item) for item in work_items]
                for fut in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc=f"{split.src_name}->{split.dst_name}",
                ):
                    res = fut.result()
                    if res.gt_lines:
                        gt_fh.write("\n".join(res.gt_lines))
                        gt_fh.write("\n")
                    total_crops += res.crops_written
                    total_skipped += res.crops_skipped
                    if res.errors:
                        total_errors += len(res.errors)
                        error_log.extend(res.errors)

    if error_log:
        LOG.warning("Encountered %d errors during split %r. First 10:", total_errors, split.src_name)
        for msg in error_log[:10]:
            LOG.warning("  %s", msg)

    LOG.info(
        "Split %r done: anns=%d crops=%d skipped=%d errors=%d gt=%s",
        split.src_name, len(ann_files), total_crops, total_skipped, total_errors, gt_path,
    )
    return len(ann_files), total_crops, total_skipped, total_errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a document OCR dataset (per-image JSON annotations + bboxes) "
            "into a PaddleOCR PP-OCRv3 recognition (REC) dataset."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("/Users/shpkkk/python_projects/ocr_diploma/ocr_datasets/split_dataset"),
        help="Path to the source dataset root containing train/ and test/ subfolders.",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        default=Path("ppocr_rec_dataset"),
        help="Path where the PP-OCRv3 REC dataset will be created.",
    )
    parser.add_argument(
        "--pad-h",
        type=int,
        default=4,
        help="Horizontal padding (pixels) added to each bbox before cropping.",
    )
    parser.add_argument(
        "--pad-v",
        type=int,
        default=4,
        help="Vertical padding (pixels) added to each bbox before cropping.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        help="JPEG quality (1-100) used for crop images.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
        help="Number of parallel worker processes.",
    )
    parser.add_argument(
        "--train-src",
        default="train",
        help="Source split folder name that maps to output 'train'.",
    )
    parser.add_argument(
        "--test-src",
        default="test",
        help="Source split folder name that maps to output 'val'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If set, process at most N annotation files per split (useful for smoke tests).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    src_root: Path = args.src.expanduser().resolve()
    dst_root: Path = args.dst.expanduser().resolve()

    if not src_root.is_dir():
        LOG.error("Source path does not exist or is not a directory: %s", src_root)
        return 2

    if args.quality < 1 or args.quality > 100:
        LOG.error("--quality must be between 1 and 100 (got %d)", args.quality)
        return 2
    if args.pad_h < 0 or args.pad_v < 0:
        LOG.error("Padding must be non-negative (h=%d, v=%d)", args.pad_h, args.pad_v)
        return 2

    dst_root.mkdir(parents=True, exist_ok=True)

    splits = [
        SplitConfig(src_name=args.train_src, dst_name="train", gt_filename="rec_gt_train.txt"),
        SplitConfig(src_name=args.test_src, dst_name="test", gt_filename="rec_gt_test.txt"),
    ]

    LOG.info("Source: %s", src_root)
    LOG.info("Destination: %s", dst_root)
    LOG.info(
        "Padding: h=%d, v=%d | JPEG quality: %d | Workers: %d",
        args.pad_h, args.pad_v, args.quality, args.workers,
    )

    grand_anns = grand_crops = grand_skipped = grand_errors = 0
    for split in splits:
        n_ann, n_crops, n_skipped, n_err = run_split(
            src_root=src_root,
            dst_root=dst_root,
            split=split,
            pad_h=args.pad_h,
            pad_v=args.pad_v,
            jpeg_quality=args.quality,
            workers=max(1, args.workers),
            limit=args.limit,
        )
        grand_anns += n_ann
        grand_crops += n_crops
        grand_skipped += n_skipped
        grand_errors += n_err

    LOG.info(
        "All done. annotations=%d crops=%d skipped=%d errors=%d -> %s",
        grand_anns, grand_crops, grand_skipped, grand_errors, dst_root,
    )
    return 0 if grand_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())