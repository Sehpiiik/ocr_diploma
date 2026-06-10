# Document generator

[English](./README.md) | [Русский](./README_RU.md)

A synthetic document generator.
Given a text corpus, it produces:

- A specified number of page images (PNG).
- A JSON annotation per image containing, for every sentence, the text and its
  **per-line axis-aligned bounding boxes** in image pixel coordinates.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Use

```bash
python main.py --corpus sample_corpus.txt --num 10 --output out/ --seed 0
```

Useful flags:

| flag | default | meaning |
| --- | --- | --- |
| `--corpus / -n` | 10 | the corpus of text data to generate |
| `--num / -n` | 10 | number of documents |
| `--output / -o` | `out` | output directory |
| `--width`, `--height` | 1240, 1754 | page size in px |
| `--margin` | 100 | page margin |
| `--font-size` | 24 | font size in px |
| `--line-spacing` | 1.35 | line height multiplier |
| `--font` | auto | path to a `.ttf` font |
| `--min-sentences` / `--max-sentences` | 20 / 60 | sentences sampled per document |
| `--seed` | None | reproducibility |
| `--debug-boxes` | off | draw red outlines on bboxes |

## Output layout

```
out/
├── images/
│   ├── doc_00001.png
│   ├── doc_00002.png
│   └── ...
└── annotations/
    ├── doc_00001.json
    ├── doc_00002.json
    └── ...
```

## Annotation format

```json
{
  "image": "doc_00001.png",
  "width": 1240,
  "height": 1754,
  "sentences": [
    {
      "id": 0,
      "text": "Optical character recognition has long been a foundational task in document understanding.",
      "lines": [
        {
          "text": "Optical character recognition has long been a foundational",
          "bbox": [100, 100, 920, 33]
        },
        {
          "text": "task in document understanding.",
          "bbox": [100, 133, 470, 33]
        }
      ]
    }
  ]
}
```

`bbox` is `[x, y, width, height]` in pixels, top-left origin.
Each entry under `lines` is one visual line that the sentence occupies, so
multi-line sentences naturally produce multiple tight rectangles instead of one
loose union box.

## Use as a library

```python
from doc_generator import DocumentGenerator, PageConfig, load_sentences

sents = load_sentences("sample_corpus.txt")
gen = DocumentGenerator(PageConfig(font_size=22))
img, ann = gen.render(sents[:30], image_name="example.png", draw_debug_boxes=True)
img.save("example.png")
print(ann.to_dict())
```
