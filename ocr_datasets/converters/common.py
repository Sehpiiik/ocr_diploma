from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Callable, Iterable, NotRequired, TypedDict

from PIL import Image

BBOX_XYWH = "xywh"
BBOX_POLYGON = "polygon"

DOMAIN_DDI = "ddi"
DOMAIN_RDTAG = "rdtag"
DOMAIN_SMARTDOC = "smartdoc"


class Item(TypedDict):
    """Normalized OCR item.
    """

    text: str
    x: int
    y: int
    w: int
    h: int
    polygon: NotRequired[list[list[int]]]


SameRowFn = Callable[[Item, Item], bool]
LineFormatter = Callable[[list[Item]], dict]

def same_row_by_y_threshold(y_threshold: float = 0.5) -> SameRowFn:
    """Return a same-row predicate based on Y-distance.

    Two items are on the same row when ``|item.y - first.y| < first.h * y_threshold``.
    Suitable for word-level boxes whose heights are not inflated (DDI100, RDTAG).
    """

    def predicate(first: Item, item: Item) -> bool:
        return abs(item["y"] - first["y"]) < first["h"] * y_threshold

    return predicate


def same_row_by_iou_no_overlap(iou_threshold: float = 0.5) -> SameRowFn:
    """Return a same-row predicate based on vertical IOU and absence of horizontal overlap.

    Two items are on the same row when:

    * Their vertical IOU is at least ``iou_threshold``, **and**
    * They do not overlap horizontally.

    Robust to OCR boxes whose heights extend beyond the actual glyph baseline
    (e.g. SmartDoc), where adjacent paragraph rows can have high vertical IOU.
    """

    def predicate(a: Item, b: Item) -> bool:
        a_y2, b_y2 = a["y"] + a["h"], b["y"] + b["h"]
        inter = max(0, min(a_y2, b_y2) - max(a["y"], b["y"]))
        union = max(a_y2, b_y2) - min(a["y"], b["y"])
        viou = inter / union if union else 0.0
        if viou < iou_threshold:
            return False
        a_x2, b_x2 = a["x"] + a["w"], b["x"] + b["w"]
        hov = max(0, min(a_x2, b_x2) - max(a["x"], b["x"]))
        return hov <= 0

    return predicate


def _join_text(items: list[Item]) -> str:
    return " ".join(i["text"] for i in items if i["text"])


def xywh_line(group: list[Item]) -> dict:
    """Emit a line dict with axis-aligned ``[x, y, w, h]`` bbox."""
    items = sorted(group, key=lambda i: i["x"])
    x_min = min(i["x"] for i in items)
    y_min = min(i["y"] for i in items)
    x_max = max(i["x"] + i["w"] for i in items)
    y_max = max(i["y"] + i["h"] for i in items)
    return {
        "text": _join_text(items),
        "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
        "type": "line",
    }


def polygon_line(group: list[Item]) -> dict:
    """Emit a line dict with a 4-point polygon bbox in ``[TL, TR, BR, BL]`` order.

    If every item carries a source ``polygon`` (4-point quad), the line polygon
    is constructed from the leftmost item's left edge (TL + BL) and the
    rightmost item's right edge (TR + BR). For a single-item group this
    reproduces the source polygon exactly. For a multi-item group it stitches
    together a wider quad that preserves any perspective tilt.

    Otherwise (e.g. RDTAG word boxes), the line polygon is the axis-aligned
    rectangle expressed as four corner points.
    """
    items = sorted(group, key=lambda i: i["x"])
    text = _join_text(items)

    if all("polygon" in i for i in items):
        leftmost = items[0]["polygon"]
        rightmost = items[-1]["polygon"]
        tl, _, _, bl = leftmost
        _, tr, br, _ = rightmost
        polygon = [list(tl), list(tr), list(br), list(bl)]
    else:
        x_min = min(i["x"] for i in items)
        y_min = min(i["y"] for i in items)
        x_max = max(i["x"] + i["w"] for i in items)
        y_max = max(i["y"] + i["h"] for i in items)
        polygon = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]

    return {"text": text, "bbox": polygon, "type": "line"}

def _split_by_column_gap(line: list[Item], gap_factor: float) -> list[list[Item]]:
    """Split a line wherever consecutive items have a horizontal gap greater
    than ``gap_factor * max(item_h)``. Useful for multi-column documents where
    words from different columns would otherwise share the same Y-row.
    """
    if len(line) < 2:
        return [line]
    sorted_line = sorted(line, key=lambda i: i["x"])
    chunks: list[list[Item]] = [[sorted_line[0]]]
    for prev, curr in zip(sorted_line, sorted_line[1:]):
        prev_right = prev["x"] + prev["w"]
        gap = curr["x"] - prev_right
        threshold = max(prev["h"], curr["h"]) * gap_factor
        if gap > threshold:
            chunks.append([curr])
        else:
            chunks[-1].append(curr)
    return chunks


def group_items_into_lines(
    items: Iterable[Item],
    same_row: SameRowFn,
    *,
    line_formatter: LineFormatter = xywh_line,
    compare_to_all_members: bool = False,
    column_gap_factor: float | None = None,
) -> list[dict]:
    """Group OCR items into lines and emit them via ``line_formatter``.

    ``items`` are sorted top-to-bottom then left-to-right. Each item is
    attached to an existing line, or a new line is started, based on the
    ``same_row`` predicate.

    * When ``compare_to_all_members`` is ``False`` (default), the candidate is
      compared only against the first item placed in the line.
    * When ``True``, the candidate matches if **any** existing line member
      satisfies the predicate. Used by SmartDoc.

    When ``column_gap_factor`` is set, each Y-row is then split into multiple
    lines wherever consecutive items have a horizontal gap exceeding
    ``column_gap_factor * max(item_h)`` — a heuristic for multi-column
    documents where two columns share the same Y-row.

    Each resulting group is formatted via ``line_formatter`` (defaults to
    ``xywh_line``; pass ``polygon_line`` for polygon output).
    """
    sorted_items = sorted(items, key=lambda i: (i["y"], i["x"]))
    if not sorted_items:
        return []

    lines: list[list[Item]] = []
    for item in sorted_items:
        merged = False
        for line in lines:
            matches = (
                any(same_row(member, item) for member in line)
                if compare_to_all_members
                else same_row(line[0], item)
            )
            if matches:
                line.append(item)
                merged = True
                break
        if not merged:
            lines.append([item])

    if column_gap_factor is not None:
        split_lines: list[list[Item]] = []
        for line in lines:
            split_lines.extend(_split_by_column_gap(line, column_gap_factor))
        lines = split_lines

    return [line_formatter(group) for group in lines]

def read_image_size(path: Path) -> tuple[int, int]:
    """Return ``(width, height)`` for an image, or ``(0, 0)`` if missing/unreadable."""
    if not path.exists():
        return 0, 0
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return 0, 0


def link_or_copy_image(src: Path, dst: Path) -> bool:
    """Place ``src`` at ``dst`` using a hardlink (fast, no data duplication)
    or a regular copy as a fallback. Idempotent: skips when ``dst`` exists.

    Returns ``True`` if the destination is now in place, ``False`` if the
    source was missing.
    """
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return True
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return True


def get_dataset_dirs(output_path: Path) -> tuple[Path, Path]:
    """Return ``(images_dir, annotations_dir)`` under ``output_path``,
    creating them if necessary.

    Each conversion run materialises a per-dataset folder with this layout::

        <output_path>/
        ├── images/
        │   └── <name>.png|jpg
        └── annotations/
            └── <name>.json
    """
    images = output_path / "images"
    annotations = output_path / "annotations"
    images.mkdir(parents=True, exist_ok=True)
    annotations.mkdir(parents=True, exist_ok=True)
    return images, annotations


def write_unified_output(
    out_file: Path,
    *,
    image: str,
    domain: str,
    width: int,
    height: int,
    bbox_format: str,
    objects: list[dict],
) -> None:
    """Write a single unified line-level annotation file."""
    payload = {
        "image": image,
        "domain": domain,
        "width": width,
        "height": height,
        "bbox_format": bbox_format,
        "objects": objects,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
