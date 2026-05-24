"""Read / write helpers for the (image, annotation) pair."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .pipeline import NoisyDocument


# ---------- loading ----------

@dataclass
class InputPair:
    image_path: Path
    annotation_path: Path
    annotation: dict

    @property
    def stem(self) -> str:
        return self.annotation_path.stem


def find_pairs(input_dir: Path) -> List[InputPair]:
    """Find matching (image, annotation) pairs under ``input_dir``.

    Expects ``input_dir/images`` and ``input_dir/annotations`` subfolders.
    Annotations drive the matching: for each ``*.json`` we look for an image
    with the same stem (or the name listed in the annotation's ``image``
    field).
    """
    img_dir = input_dir / "images"
    ann_dir = input_dir / "annotations"
    if not img_dir.is_dir():
        raise FileNotFoundError(f"missing images dir: {img_dir}")
    if not ann_dir.is_dir():
        raise FileNotFoundError(f"missing annotations dir: {ann_dir}")

    exts = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
    pairs: List[InputPair] = []
    for ann_path in sorted(ann_dir.glob("*.json")):
        try:
            ann = json.loads(ann_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"cannot parse {ann_path}: {exc}") from exc

        img_path: Optional[Path] = None
        ref = ann.get("image")
        if ref:
            cand = img_dir / Path(ref).name
            if cand.is_file():
                img_path = cand
        if img_path is None:
            for ext in exts:
                cand = img_dir / (ann_path.stem + ext)
                if cand.is_file():
                    img_path = cand
                    break
        if img_path is None:
            raise FileNotFoundError(
                f"no image found for annotation {ann_path.name} in {img_dir}"
            )
        pairs.append(InputPair(img_path, ann_path, ann))
    return pairs


def read_image_bgr(path: Path) -> np.ndarray:
    """Read an image as BGR uint8 (ignoring alpha)."""
    arr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if arr is None:
        raise IOError(f"cannot read image: {path}")
    return arr


# ---------- writing ----------

def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), image)
    if not ok:
        raise IOError(f"cv2.imwrite failed: {path}")


def build_output_annotation(
    original_annotation: dict,
    noisy: NoisyDocument,
    image_name: str,
) -> dict:
    """Produce the JSON dict describing the noisy document.

    The output keeps the input ``xywh`` schema exactly — every object is
    copied verbatim from the input. Only the ``image`` field is rewritten
    to the noisy filename and a top-level ``augmentations`` field is added
    listing the effects that fired.
    """
    out = copy.deepcopy(original_annotation)
    out["image"] = image_name
    out["width"] = noisy.width
    out["height"] = noisy.height
    out.setdefault("bbox_format", "xywh")
    out["augmentations"] = list(noisy.applied)
    return out


def should_augment(annotation: dict) -> bool:
    """Whether this annotation requested augmentation via ``"augment": true``.

    Anything other than a literal truthy ``augment`` flag is treated as
    "leave alone" — missing key, ``false``, ``null``, ``0`` etc.
    """
    return bool(annotation.get("augment", False))


def build_renamed_annotation(
    original_annotation: dict,
    new_image_name: str,
) -> dict:
    """Deep copy of ``original_annotation`` with only the ``image`` field
    rewritten to ``new_image_name``.

    Used by the in-place augmentation CLI: each augmented variant gets its
    own annotation that is otherwise byte-equivalent to the source.
    """
    out = copy.deepcopy(original_annotation)
    out["image"] = new_image_name
    return out


def write_annotation(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ensure_output_dirs(output_dir: Path) -> Tuple[Path, Path]:
    img_dir = output_dir / "images"
    ann_dir = output_dir / "annotations"
    img_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)
    return img_dir, ann_dir
