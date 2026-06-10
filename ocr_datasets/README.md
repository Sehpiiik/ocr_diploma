# OCR Datasets — Unified Line-Level Annotations

[English](./README.md) | [Русский](./README_RU.md)

Python project that standardizes OCR datasets with heterogeneous annotation
formats into a single line-level JSON schema. Each input dataset uses its own
representation (per-word `.pkl`, per-word `.json`, per-line `.json`); this
project converts all of them into the same shape so downstream training /
evaluation pipelines can treat them uniformly.

## Unified output schema

Every produced file looks like this:

```json
{
  "image": "ddi_10_0.png",
  "domain": "ddi",
  "width": 2480,
  "height": 3508,
  "bbox_format": "xywh",
  "objects": [
    {
      "text": "Admission by consent of the instructor.",
      "bbox": [200, 200, 2030, 57],
      "type": "line"
    }
  ]
}
```

* ``domain`` is the source dataset: ``"ddi"``, ``"rdtag"``, or ``"smartdoc"``.
* ``image`` is the basename of an actual file living next to the annotation
  inside ``output/<dataset>/`` — every ``<name>.json`` has a sibling
  ``<name>.png/.jpg``. See [Output layout](#output-layout) for the naming.
* ``objects[*].type`` is always ``"line"`` — word-level inputs are merged into
  lines, line-level inputs are passed through.

Two ``bbox_format`` values are used:

* ``"xywh"`` — axis-aligned ``[x, y, w, h]`` rectangle, in pixels.
  Used for **DDI100**, whose source is a rendered (perfectly aligned) page.
* ``"polygon"`` — 4-point quadrilateral ``[[x, y], [x, y], [x, y], [x, y]]``
  in ``[TL, TR, BR, BL]`` order, in pixels. Used for **RDTAG** (axis-aligned
  rectangles expressed as quads, for schema uniformity) and **SmartDoc**
  (genuine perspective quads from photographed pages).

## Output layout

Each conversion run materialises a self-contained per-dataset folder split
into ``images/`` and ``annotations/`` subdirectories. Source images are
hardlinked under their final filenames (regular copies are used as a fallback
when hardlinks are unsupported), so no source data is mutated and there is no
on-disk duplication on the typical case.

```
output/
├── ddi100/
│   ├── images/
│   │   └── ddi_<doc>_<page>.png        # e.g. ddi_10_0.png
│   └── annotations/
│       └── ddi_<doc>_<page>.json       # references the .png by basename
├── rdtag/
│   ├── images/
│   │   └── <original_name>.jpg         # e.g. 5_Book7_120_in_ni_y_4.jpg (kept as-is)
│   └── annotations/
│       └── <original_name>.json
└── smartdoc/
    ├── images/
    │   └── smartdoc_<id>.jpg           # e.g. smartdoc_00001.jpg
    └── annotations/
        └── smartdoc_<id>.json
```

Naming rules:

* **DDI100**: image and annotation are named ``ddi_<doc_folder>_<page>``
  (e.g. ``ddi_10_0``). The original PNGs live inside per-document
  ``orig_texts/`` directories with bare numeric stems; the converter renames
  them while hardlinking into ``output/ddi100/images/``.
* **RDTAG**: the original RDTAG file name is kept verbatim — both for the
  image (``5_Book7_120_in_ni_y_4.jpg``) and the matching ``.json`` annotation.
* **SmartDoc**: source images use bare numeric stems (``00001.jpg``); the
  converter renames them to ``smartdoc_00001.jpg`` and emits
  ``smartdoc_00001.json`` alongside.

The annotation's ``image`` field is always a basename — to load an image,
join it with the sibling ``images/`` directory of its annotation file.

## Project layout

```
ocr_datasets/
├── convert.py                       # CLI entry point (orchestrates converters)
├── converters/
│   ├── __init__.py
│   ├── ddi100_converter.py          # DDI100 .pkl  → unified JSON
│   ├── rdtag_converter.py           # RDTAG .json  → unified JSON
│   └── smartdoc_converter.py        # SmartDoc2015 .json → unified JSON
├── datasets_utils/
│   ├── images_rotation.py           # Rotate + edge-crop a folder of images
│   └── reorganize_rdtag.py          # Split RDTAG-1.0 into images/ and orig_annotations/
├── datasets/                        # Source datasets (not committed)
│   ├── DDI100_v1.3/
│   ├── RDTAG-1.0/
│   └── SmartDoc2015_Challenge_2/
└── output/                          # Generated unified JSON (created on first run)
    ├── ddi100/
    ├── rdtag/
    └── smartdoc/
```

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install numpy Pillow
```

The project targets Python 3.11+ and depends only on `numpy` (for unpickling
DDI100 box arrays) and `Pillow` (for reading image dimensions).

## Datasets

### DDI100 v1.3

Original layout:

```
DDI100_v1.3/
└── <doc_id>/
    ├── orig_texts/<page>.png        # rendered document pages
    └── orig_boxes/<page>.pkl        # word-level annotations (pickled list of dicts)
```

Each `.pkl` is a `list[dict]` with `text`, `box`, and `chars`. `box` is a
4-point `numpy.int32` array in `(row, col)` order — i.e. each row is `(y, x)`.
The converter extracts axis-aligned `xywh` bounds from the four corner points,
then groups words into lines by vertical proximity.

### RDTAG-1.0

Distributed with everything mixed inside each subset:

```
RDTAG-1.0/
└── Training_Set<N>/
    ├── <name>.jpg
    ├── <name>.json     # word-level: list of {text, bounding_box: {x,y,w,h}, order}
    └── <name>.txt      # plain-text transcription
```

The converter expects the reorganized layout produced by
`datasets_utils/reorganize_rdtag.py`:

```
RDTAG-1.0/
├── images/
│   └── Training_Set<N>/<name>.jpg
└── orig_annotations/
    └── Training_Set<N>/
        ├── <name>.json
        └── <name>.txt
```

Run the reorganization step before invoking the converter (see
[Utilities](#utilities)). If the expected `images/` and `orig_annotations/`
directories are missing, `convert_rdtag` raises a `FileNotFoundError` pointing
you at the script.

### SmartDoc2015_Challenge_2

```
SmartDoc2015_Challenge_2/
├── images/<id>.jpg
├── ocr_boxes/<id>.json              # already line-level, polygon bbox + confidence
└── input_sample_groundtruth/<id>.txt
```

Each `ocr_boxes/<id>.json` looks like:

```json
{
  "image": "00040.jpg",
  "detections": [
    {"bbox": {"polygon": [[311, 338], [1456, 323], [1457, 370], [311, 386]]},
     "text": "...", "confidence": 0.94}
  ]
}
```

Each polygon is a 4-point quadrilateral in `[TL, TR, BR, BL]` order — the
non-rectangular shape captures the perspective tilt of the photographed page.

Annotations are mostly line-level, but the OCR engine occasionally emits
single-word boxes (e.g. a section number next to its heading). The converter
groups detections into lines using a vertical-IOU + no-horizontal-overlap
predicate, then emits each line as a 4-point polygon. For same-row merges the
output polygon is stitched from the leftmost item's left edge and the
rightmost item's right edge so the source tilt is preserved.

## Usage

### Convert all datasets

```bash
python convert.py                  # writes output/{ddi100,rdtag,smartdoc}/
```

### Convert one dataset

```bash
python convert.py --dataset ddi100
python convert.py --dataset rdtag
python convert.py --dataset smartdoc
```

### Custom output directory

```bash
python convert.py --output /path/to/out
```

## Utilities

### `datasets_utils/reorganize_rdtag.py`

Splits RDTAG-1.0 into a clean two-folder layout
(`images/` + `orig_annotations/`), preserving the `Training_Set<N>`
subdirectory structure inside each. Filename collisions are avoided this way
and the train-split grouping is kept intact.

```bash
# Preview without touching the filesystem
python datasets_utils/reorganize_rdtag.py -d datasets/RDTAG-1.0 --dry-run

# Move files (default — frees disk space)
python datasets_utils/reorganize_rdtag.py -d datasets/RDTAG-1.0

# Copy instead of move (keep the original layout intact)
python datasets_utils/reorganize_rdtag.py -d datasets/RDTAG-1.0 --copy
```

The script is idempotent: if `Training_Set*/` directories are already gone, it
prints a notice and exits cleanly.

### `datasets_utils/images_rotation.py`

Rotates every image in a folder by a fixed angle and optionally crops a
constant margin from each edge. Handy for normalizing scanned datasets where
all pages were captured rotated.

```bash
python datasets_utils/images_rotation.py \
    --input  datasets/RDTAG-1.0/images/Training_Set1 \
    --output rotated/Training_Set1 \
    --format jpg \
    --angle 270 \
    --crop 0
```

## Implementation notes

* **Word → line grouping.** For DDI100 and RDTAG, words are grouped into a
  single line when the absolute Y-difference between their top edges is less
  than 50 % of the reference word's height. Within a line, words are sorted
  by X and joined with a single space; the line bbox is the axis-aligned
  union of word bboxes.
* **Multi-column documents (DDI100).** After Y-grouping, each line is split
  again wherever consecutive words have a horizontal gap larger than 1.5 ×
  their height. This prevents words from neighbouring columns (e.g. table
  cells, side-by-side paragraph blocks) from being merged into a single line.
* **Image lookup.** Width/height are read directly from the image file with
  Pillow. If the image is missing, `width` and `height` are written as `0` and
  conversion still succeeds.
* **Image placement.** Source images are hardlinked into
  ``output/<dataset>/`` under their unified names; on filesystems that do not
  support hardlinks the converter falls back to a regular copy. Existing
  destination files are left untouched (idempotent).
* **Idempotent output.** Each run overwrites the destination JSON files;
  partial runs are safe to resume.
