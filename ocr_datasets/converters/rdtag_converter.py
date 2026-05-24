"""Convert RDTAG word-level JSON annotations to line-level polygon JSON.

Expects the reorganized RDTAG-1.0 layout produced by
``datasets_utils/reorganize_rdtag.py``. Files may live directly under
``images/`` and ``orig_annotations/`` (flat layout) or inside
``Training_Set<N>/`` subdirectories (subset-grouped layout). The converter
walks ``orig_annotations/`` recursively and locates each image at the same
relative path under ``images/``.

Output layout::

    output/rdtag/
    ├── images/
    │   └── <original_name>.jpg     # name preserved
    └── annotations/
        └── <original_name>.json    # references the sibling image by basename

Output bbox format is ``polygon``: each line bbox is a 4-corner axis-aligned quad.
"""
import json
from pathlib import Path

from converters.common import (
    BBOX_POLYGON,
    DOMAIN_RDTAG,
    Item,
    get_dataset_dirs,
    group_items_into_lines,
    link_or_copy_image,
    polygon_line,
    read_image_size,
    same_row_by_y_threshold,
    write_unified_output,
)

IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def _find_image(stem: str, image_dir: Path) -> Path | None:
    for ext in IMAGE_EXTS:
        candidate = image_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _words_to_items(words: list[dict]) -> list[Item]:
    items: list[Item] = []
    for w in words:
        bb = w["bounding_box"]
        items.append({"text": w["text"], "x": bb["x"], "y": bb["y"], "w": bb["w"], "h": bb["h"]})
    return items


def convert_rdtag(dataset_path: Path, output_path: Path) -> None:
    """Convert RDTAG annotations (reorganized layout) to the unified format."""
    images_root = dataset_path / "images"
    annotations_root = dataset_path / "orig_annotations"

    if not annotations_root.is_dir() or not images_root.is_dir():
        raise FileNotFoundError(
            f"Expected reorganized RDTAG layout at {dataset_path}: "
            f"missing 'images/' and/or 'orig_annotations/' directories. "
            f"Run datasets_utils/reorganize_rdtag.py first."
        )

    images_dir, annotations_dir = get_dataset_dirs(output_path)
    same_row = same_row_by_y_threshold()

    for json_file in sorted(annotations_root.rglob("*.json")):
        rel_dir = json_file.parent.relative_to(annotations_root)
        # Mirror the relative directory inside images/ to find the matching image.
        image_dir = images_root / rel_dir
        stem = json_file.stem
        src_image = _find_image(stem, image_dir)

        if src_image is None:
            print(f"  warning: image for {json_file.name} not found in {image_dir}, skipping")
            continue

        # Preserve the original RDTAG file name for both the image and the
        # annotation file. Note: RDTAG file names are already globally unique
        # in practice (they encode the source book and page).
        image_name = src_image.name
        dst_image = images_dir / image_name
        link_or_copy_image(src_image, dst_image)
        width, height = read_image_size(dst_image)

        with open(json_file, "r", encoding="utf-8") as f:
            words = json.load(f)

        objects = group_items_into_lines(
            _words_to_items(words),
            same_row,
            line_formatter=polygon_line,
        )

        write_unified_output(
            annotations_dir / f"{src_image.stem}.json",
            image=image_name,
            domain=DOMAIN_RDTAG,
            width=width,
            height=height,
            bbox_format=BBOX_POLYGON,
            objects=objects,
        )

    print(f"RDTAG conversion complete. Output: {output_path}")
