Convert a document OCR dataset to a PaddleOCR PP-OCRv3 recognition (REC) dataset.

Source layout (per split):
    <src>/train/images/<name>.{png,jpg,jpeg,...}
    <src>/train/annotations/<name>.json
    <src>/test/images/<name>.{png,jpg,jpeg,...}
    <src>/test/annotations/<name>.json

Annotation schema (relevant fields):
    {
        "image": "<filename>",
        "width": int, "height": int,
        "bbox_format": "xywh",
        "objects": [
            {"text": "...", "bbox": [x, y, w, h], "type": "line"},
            ...
        ]
    }

Output layout (PP-OCRv3 REC):
    <dst>/train/images/<orig>_line_<idx>.jpg
    <dst>/test/images/<orig>_line_<idx>.jpg
    <dst>/rec_gt_train.txt
    <dst>/rec_gt_test.txt

GT file format (UTF-8, TAB separator, one record per line):
    train/images/doc_00001_line_000.jpg\tExample text
    test/images/doc_00001_line_000.jpg\tExample text