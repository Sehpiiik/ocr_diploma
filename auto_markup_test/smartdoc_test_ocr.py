#!/usr/bin/env python3

import os
import json
import argparse
from pathlib import Path

from jiwer import cer, wer
from rapidfuzz.distance import Levenshtein


def extract_text_from_json(json_path):
    """
    Extract and concatenate all OCR text lines from annotation JSON.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("objects", [])

    texts = []

    for obj in objects:
        text = obj.get("text", "").strip()

        if text:
            texts.append(text)

    return "\n".join(texts)


def read_groundtruth(txt_path):
    """
    Read ground truth text file.
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def normalized_edit_distance(reference, hypothesis):
    """
    Compute Normalized Edit Distance (NED).

    NED = LevenshteinDistance / max(len(reference), len(hypothesis))
    """

    if len(reference) == 0 and len(hypothesis) == 0:
        return 0.0

    dist = Levenshtein.distance(reference, hypothesis)

    return dist / max(len(reference), len(hypothesis))


def get_gt_filename(json_filename):
    """
    Convert:
        smartdoc_00001.json -> 00001.txt
    """

    stem = Path(json_filename).stem

    # split by "_"
    parts = stem.split("_")

    if len(parts) < 2:
        return None

    number = parts[-1]

    return f"{number}.txt"


def main():
    parser = argparse.ArgumentParser(
        description="Calculate CER, WER, and NED for OCR annotations."
    )

    parser.add_argument(
        "--annotations",
        required=True,
        help="Path to annotations folder containing JSON files",
    )

    parser.add_argument(
        "--groundtruth",
        required=True,
        help="Path to ground truth folder containing TXT files",
    )

    args = parser.parse_args()

    annotations_dir = Path(args.annotations)
    gt_dir = Path(args.groundtruth)

    json_files = sorted(annotations_dir.glob("*.json"))

    if not json_files:
        print("No JSON files found.")
        return
    else:
        print(f"Found {len(json_files)} JSON files to process.")

    total_cer = 0.0
    total_wer = 0.0
    total_ned = 0.0

    processed = 0

    for json_file in json_files:

        gt_filename = get_gt_filename(json_file.name)

        if gt_filename is None:
            print(f"Skipping invalid filename: {json_file.name}")
            continue

        gt_path = gt_dir / gt_filename

        if not gt_path.exists():
            print(f"Ground truth missing for: {json_file.name}")
            continue

        try:
            hypothesis = extract_text_from_json(json_file)
            reference = read_groundtruth(gt_path)
            #print(f"hypothesis: {hypothesis}")
            #print(f"reference: {reference}")
            #input(f"Press Enter to continue...")
            file_cer = cer(reference, hypothesis)
            file_wer = wer(reference, hypothesis)
            file_ned = normalized_edit_distance(reference, hypothesis)

            total_cer += file_cer
            total_wer += file_wer
            total_ned += file_ned

            processed += 1

            print(f"\nFile: {json_file.name}")
            print(f"GT:   {gt_filename}")
            print(f"CER:  {file_cer:.4f}")
            print(f"WER:  {file_wer:.4f}")
            print(f"NED:  {file_ned:.4f}")

        except Exception as e:
            print(f"Error processing {json_file.name}: {e}")

    if processed == 0:
        print("No valid file pairs processed.")
        return

    print("\n" + "=" * 50)
    print("AVERAGE METRICS")
    print("=" * 50)

    print(f"Files processed: {processed}")
    print(f"Average CER: {total_cer / processed:.4f}")
    print(f"Average WER: {total_wer / processed:.4f}")
    print(f"Average NED: {total_ned / processed:.4f}")


if __name__ == "__main__":
    raise SystemExit(main())