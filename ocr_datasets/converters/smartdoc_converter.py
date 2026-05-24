"""Convert SmartDoc2015_Challenge_2 OCR JSON to unified line-level polygon JSON.

Each ``ocr_boxes/<id>.json`` looks like::

    {"image": "<id>.jpg", "detections": [
        {"bbox": {"polygon": [[x, y]*4]}, "text": "...", "confidence": ...},
        ...
    ]}

Each polygon is a 4-point quadrilateral in ``[TL, TR, BR, BL]`` order; the
non-rectangular shape captures the perspective tilt of the photographed page.

Output layout::

    output/smartdoc/
    ├── images/
    │   └── smartdoc_<id>.jpg       # hardlinked under the new name
    └── annotations/
        └── smartdoc_<id>.json      # references the sibling image by basename

Most detections already cover a full line; same-row splits (e.g. a section
number next to its heading) are merged using a vertical-IOU + no-horizontal-
overlap predicate, with the merged polygon stitched from the leftmost item's
left edge and the rightmost item's right edge to preserve the source quads'
tilt.
"""
import json
from pathlib import Path

from converters.common import (
    BBOX_POLYGON,
    DOMAIN_SMARTDOC,
    Item,
    get_dataset_dirs,
    group_items_into_lines,
    link_or_copy_image,
    polygon_line,
    read_image_size,
    same_row_by_iou_no_overlap,
    write_unified_output,
)


def _polygon_bounds(polygon: list[list[int]]) -> tuple[int, int, int, int]:
    """Return the axis-aligned ``(x, y, w, h)`` for a polygon's points."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_min, y_min = min(xs), min(ys)
    return x_min, y_min, max(xs) - x_min, max(ys) - y_min


def _detections_to_items(detections: list[dict]) -> list[Item]:
    items: list[Item] = []
    for det in detections:
        polygon = (det.get("bbox") or {}).get("polygon")
        if not polygon or len(polygon) != 4:
            continue
        x, y, w, h = _polygon_bounds(polygon)
        items.append(
            {
                "text": det.get("text", ""),
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "polygon": polygon,
            }
        )
    return items


def convert_smartdoc(dataset_path: Path, output_path: Path) -> None:
    """Convert all SmartDoc2015 ocr_boxes JSON annotations to the unified format."""
    boxes_dir = dataset_path / "ocr_boxes"
    images_dir_src = dataset_path / "images"

    if not boxes_dir.exists():
        raise FileNotFoundError(f"ocr_boxes directory not found: {boxes_dir}")

    images_dir, annotations_dir = get_dataset_dirs(output_path)
    same_row = same_row_by_iou_no_overlap()

    for json_file in sorted(boxes_dir.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        original_image_name = data.get("image", f"{json_file.stem}.jpg")
        src_image = images_dir_src / original_image_name

        # Rename image and annotation to the unified ``smartdoc_<id>.<ext>`` form.
        new_image_name = f"smartdoc_{original_image_name}"
        new_stem = Path(new_image_name).stem
        dst_image = images_dir / new_image_name

        link_or_copy_image(src_image, dst_image)
        width, height = read_image_size(dst_image)

        objects = group_items_into_lines(
            _detections_to_items(data.get("detections", [])),
            same_row,
            line_formatter=polygon_line,
            compare_to_all_members=True,
        )

        write_unified_output(
            annotations_dir / f"{new_stem}.json",
            image=new_image_name,
            domain=DOMAIN_SMARTDOC,
            width=width,
            height=height,
            bbox_format=BBOX_POLYGON,
            objects=objects,
        )

    print(f"SmartDoc2015 conversion complete. Output: {output_path}")
