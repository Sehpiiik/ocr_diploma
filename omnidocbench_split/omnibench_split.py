import json
import shutil
import argparse
from pathlib import Path

# Categories to skip entirely
SKIP_CATEGORIES = {
    "abandon",
    "text_mask",
    "unknown_mask",
    "chart_mask",
    "algorithm_mask",
    "table_mask",
    "need_mask",
    "figure",
    "code_txt",
    "table",
    "equation_isolated",
    "equation_semantic",
    "equation_explanation",

}

def polygon_to_xywh(poly):
    """
    Convert polygon into axis-aligned xywh bbox.

    Returns:
    [x, y, w, h]
    """

    xs = poly[0::2]
    ys = poly[1::2]

    x_min = min(xs)
    y_min = min(ys)

    x_max = max(xs)
    y_max = max(ys)

    width = x_max - x_min
    height = y_max - y_min

    return [
        int(round(x_min)),
        int(round(y_min)),
        int(round(width)),
        int(round(height))
    ]


def calculate_page_statistics(sample):

    layout_dets = sample.get("layout_dets", [])

    text_boxes = 0
    total_text_length = 0
    total_objects = 0
    bad_boxes = 0

    for obj in layout_dets:

        category = obj.get("category_type", "")

        if category in SKIP_CATEGORIES:
            continue

        total_objects += 1

        text = ""

        if obj.get("text"):
            text = obj["text"]

        elif obj.get("latex"):
            text = obj["latex"]

        text = text.strip()

        total_text_length += len(text)

        if category in {
            "text_block",
            "header",
            "title",
            "reference",
            "caption"
        }:
            text_boxes += 1

        # Penalize formula-heavy pages
        if category in SKIP_CATEGORIES:
            bad_boxes += 1

    return {
        "text_boxes": text_boxes,
        "total_text_length": total_text_length,
        "total_objects": total_objects,
        "bad_boxes": bad_boxes
    }


def calculate_page_score(stats):

    score = (
        stats["text_boxes"] * 10 +
        stats["total_text_length"] * 0.2 +
        stats["total_objects"] * 3 -
        stats["bad_boxes"] * 5
    )

    return score

def convert_annotation(sample):

    page_info = sample["page_info"]

    converted = {
        "image": page_info["image_path"],
        "domain": "omnidocbench",
        "width": page_info["width"],
        "height": page_info["height"],

        # Global bbox format
        "bbox_format": "xywh",

        "objects": []
    }

    for obj in sample["layout_dets"]:

        category = obj.get("category_type", "unknown")

        if category in SKIP_CATEGORIES:
            continue

        poly = obj.get("poly")

        if poly is None or len(poly) < 8:
            continue

        text = ""

        if obj.get("text") is not None:
            text = obj["text"]

        elif obj.get("latex") is not None:
            text = obj["latex"]

        text = text.strip()

        if text == "":
            continue

        xywh_bbox = polygon_to_xywh(poly)

        converted_obj = {
            "text": text,
            "bbox": xywh_bbox,
            "type": category,
        }

        converted["objects"].append(converted_obj)

    return converted



def main():

    parser = argparse.ArgumentParser(
        description="Prepare high-quality OmniDocBench OCR subset"
    )

    parser.add_argument(
        "--annotations",
        required=True,
        help="Path to OmniDocBench.json"
    )

    parser.add_argument(
        "--images",
        required=True,
        help="Path to images folder"
    )

    parser.add_argument(
        "--output",
        default="output",
        help="Output directory"
    )

    parser.add_argument(
        "--num_samples",
        type=int,
        default=200,
        help="Number of selected samples"
    )

    parser.add_argument(
        "--min_text_boxes",
        type=int,
        default=10,
        help="Minimum number of text boxes"
    )

    parser.add_argument(
        "--min_text_length",
        type=int,
        default=100,
        help="Minimum total text length"
    )
    args = parser.parse_args()

    annotations_path = Path(args.annotations)
    images_dir = Path(args.images)

    output_dir = Path(args.output)
    output_images_dir = output_dir / "images"
    output_annotations_dir = output_dir / "annotations"

    output_images_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_annotations_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Loading annotations...")

    with open(
        annotations_path,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    print(f"Total pages in dataset: {len(data)}")

    english_samples = []

    for sample in data:

        language = (
            sample.get("page_info", {})
            .get("page_attribute", {})
            .get("language", "")
            .lower()
        )

        if language == "english":
            english_samples.append(sample)

    print(f"English pages found: {len(english_samples)}")

    filtered_samples = []

    for sample in english_samples:

        stats = calculate_page_statistics(sample)

        if (
            stats["text_boxes"] >= args.min_text_boxes
            and
            stats["total_text_length"] >= args.min_text_length
        ):

            filtered_samples.append(
                (sample, stats)
            )

    print(
        f"Pages after quality filtering: "
        f"{len(filtered_samples)}"
    )

    if len(filtered_samples) < args.num_samples:

        raise ValueError(
            f"Not enough high-quality samples.\n"
            f"Requested: {args.num_samples}\n"
            f"Available: {len(filtered_samples)}"
        )

    scored_samples = []

    for sample, stats in filtered_samples:

        score = calculate_page_score(stats)

        scored_samples.append({
            "sample": sample,
            "stats": stats,
            "score": score
        })

    scored_samples.sort(
        key=lambda x: x["score"],
        reverse=True
    )


    selected = scored_samples[:args.num_samples]

    print(
        f"Selected {len(selected)} "
        f"high-quality samples"
    )

    selected_metadata = []

    for idx, item in enumerate(selected):

        sample = item["sample"]
        stats = item["stats"]
        score = item["score"]

        page_info = sample["page_info"]

        image_name = page_info["image_path"]

        source_image = images_dir / image_name
        destination_image = output_images_dir / image_name

        if not source_image.exists():

            print(
                f"WARNING: Missing image: "
                f"{source_image}"
            )

            continue

        # Copy image
        shutil.copy2(
            source_image,
            destination_image
        )

        # Convert annotation
        converted_annotation = convert_annotation(sample)

        annotation_name = (
            Path(image_name).stem + ".json"
        )

        annotation_path = (
            output_annotations_dir /
            annotation_name
        )

        with open(
            annotation_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                converted_annotation,
                f,
                ensure_ascii=False,
                indent=4
            )

        selected_metadata.append({
            "image": image_name,
            "annotation": annotation_name,
            "score": score,
            "statistics": stats
        })

        if (idx + 1) % 25 == 0:

            print(
                f"Processed "
                f"{idx + 1}/{args.num_samples}"
            )


    selection_file = (
        output_dir /
        "selected_samples.json"
    )

    with open(
        selection_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            selected_metadata,
            f,
            ensure_ascii=False,
            indent=4
        )

    print("\nDone!")

    print(f"Images saved to: {output_images_dir}")

    print(
        f"Annotations saved to: "
        f"{output_annotations_dir}"
    )

    print(
        f"Selection metadata saved to: "
        f"{selection_file}"
    )

if __name__ == "__main__":
    raise SystemExit(main())