# Generator PP-OCR valid dataset

[English](./README.md) | [Русский](./README_RU.md)

Convert a document OCR dataset to a PaddleOCR PP-OCRv3 recognition (REC) dataset.

## Input layout

### Source layout (per split):

```
    src/
    ├── train
    │   ├── images/
    │       │   ├── doc_00001.png
    │       │   ├── doc_00002.png
    │       │   └── ...
    │       └── annotations/
    │           ├── doc_00001.json
    │           ├── doc_00002.json
    │           └── ...
    ├── test
    │   ├── images/
    │       │   ├── test_doc_00001.png
    │       │   ├── test_doc_00002.png
    │       │   └── ...
    │       └── annotations/
    │           ├── test_doc_00001.json
    │           ├── test_doc_00002.json
    │           └── ...
```

### Source annotation format

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

## Output layout (PP-OCRv3 REC):

```
    dst/
    ├── train
    │   ├── images/
    │       │   ├── <orig>_line_<idx>.jpg
    │       │   └── ...
    ├── test
    │   ├── images/
    │       │   ├── <orig>_line_<idx>.jpg
    │       │   └── ...
    |── rec_gt_train.txt
    |── rec_gt_test.txt
```

### GT file format (UTF-8, TAB separator, one record per line):

```
    train/images/doc_00001_line_000.jpg\tExample text
    test/images/doc_00001_line_000.jpg\tExample text
```
