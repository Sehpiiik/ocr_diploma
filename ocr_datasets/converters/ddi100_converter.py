"""Convert DDI100 word-level pkl annotations to line-level xywh JSON.

Output layout under ``output/ddi100/``::

    output/ddi100/
    ├── images/
    │   └── ddi_<doc>_<page>.png   # hardlinked from datasets/DDI100_v1.3/<doc>/orig_texts/<page>.png
    └── annotations/
        └── ddi_<doc>_<page>.json  # references the .png by basename
"""
import pickle
from pathlib import Path

import numpy as np

from converters.common import (
    BBOX_XYWH,
    DOMAIN_DDI,
    Item,
    get_dataset_dirs,
    group_items_into_lines,
    link_or_copy_image,
    read_image_size,
    same_row_by_y_threshold,
    write_unified_output,
)

# DDI100 documents are typically multi-column scientific reports. Words on
# the same Y-row whose horizontal gap exceeds 1.0x their line height are
# treated as belonging to different columns and split into separate lines.
COLUMN_GAP_FACTOR = 1.0


def _load_pkl(path: Path) -> list[dict]:
    with open(path, "rb") as f:
        return pickle.load(f)


def _box4_to_xywh(box: np.ndarray) -> tuple[int, int, int, int]:
    xs = box[:, 1]
    ys = box[:, 0]
    x, y = int(xs.min()), int(ys.min())
    return x, y, int(xs.max()) - x, int(ys.max()) - y


def _words_to_items(words: list[dict]) -> list[Item]:
    items: list[Item] = []
    for w in words:
        x, y, bw, bh = _box4_to_xywh(w["box"])
        items.append({"text": w["text"], "x": x, "y": y, "w": bw, "h": bh})
    return items


def convert_ddi100(dataset_path: Path, output_path: Path) -> None:
    images_dir, annotations_dir = get_dataset_dirs(output_path)
    same_row = same_row_by_y_threshold()

    for doc_dir in sorted(dataset_path.iterdir()):
        if not doc_dir.is_dir() or doc_dir.name.startswith("."):
            continue

        boxes_dir = doc_dir / "orig_boxes"
        texts_dir = doc_dir / "orig_texts"
        if not boxes_dir.exists():
            continue

        for pkl_file in sorted(boxes_dir.glob("*.pkl")):
            page = pkl_file.stem
            base = f"ddi_{doc_dir.name}_{page}"
            src_image = texts_dir / f"{page}.png"
            dst_image = images_dir / f"{base}.png"

            link_or_copy_image(src_image, dst_image)
            width, height = read_image_size(dst_image)

            words = _load_pkl(pkl_file)
            objects = group_items_into_lines(
                _words_to_items(words),
                same_row,
                column_gap_factor=COLUMN_GAP_FACTOR,
            )

            write_unified_output(
                annotations_dir / f"{base}.json",
                image=f"{base}.png",
                domain=DOMAIN_DDI,
                width=width,
                height=height,
                bbox_format=BBOX_XYWH,
                objects=objects,
            )

    print(f"DDI100 conversion complete. Output: {output_path}")
