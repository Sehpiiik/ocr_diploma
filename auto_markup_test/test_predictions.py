import argparse
from pathlib import Path

from jiwer import process_words, process_characters
from rapidfuzz.distance import Levenshtein


def read_tsv_file(file_path):
    """
    Reads file with format:
        filename<TAB>text

    Returns:
        dict[str, str]
    """

    data = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip("\n")

            if not line.strip():
                continue

            parts = line.split("\t", 1)

            if len(parts) != 2:
                print(
                    f"[WARNING] Invalid line {line_num} "
                    f"in {file_path}: {line[:100]}"
                )
                continue

            filename, text = parts

            data[filename.strip()] = text.strip()

    return data


def normalized_similarity(reference, hypothesis):
    """
    ANLS / 1-NED style similarity metric.

    Returns:
        1.0 = perfect match
        0.0 = completely different
    """

    if len(reference) == 0 and len(hypothesis) == 0:
        return 1.0

    distance = Levenshtein.distance(reference, hypothesis)

    return 1.0 - (
        distance / max(len(reference), len(hypothesis))
    )


def main():
    parser = argparse.ArgumentParser(
        description="OCR evaluation script (CER/WER/1-NED)"
    )

    parser.add_argument(
        "--groundtruth",
        required=True,
        help="Path to GT file"
    )

    parser.add_argument(
        "--predictions",
        required=True,
        help="Path to prediction file"
    )

    parser.add_argument(
        "--verbose",
        action="store_true"
    )
    parser.add_argument(
    "--ignore_space",
    action="store_true",
    help="Ignore spaces like PaddleOCR RecMetric"
    )

    args = parser.parse_args()

    gt_path = Path(args.groundtruth)
    pred_path = Path(args.predictions)

    if not gt_path.exists():
        print(f"[ERROR] GT file not found: {gt_path}")
        return 1

    if not pred_path.exists():
        print(f"[ERROR] Prediction file not found: {pred_path}")
        return 1

    print(f"Reading GT: {gt_path}")
    gt_dict = read_tsv_file(gt_path)

    print(f"Reading predictions: {pred_path}")
    pred_dict = read_tsv_file(pred_path)

    common_files = sorted(
        set(gt_dict.keys()) & set(pred_dict.keys())
    )
    if len(common_files) == 0:
        print("[ERROR] No matching filenames found")
        return 1

    print(f"Matched files: {len(common_files)}")

  
    total_char_subs = 0
    total_char_dels = 0
    total_char_ins = 0
    total_char_hits = 0

    total_word_subs = 0
    total_word_dels = 0
    total_word_ins = 0
    total_word_hits = 0

   
    mean_cer_sum = 0.0
    mean_wer_sum = 0.0
    mean_anls_sum = 0.0

    exact_matches = 0

    results = []

    for filename in common_files:

        gt = gt_dict[filename]
        pred = pred_dict[filename]
        if args.ignore_space:
            gt = gt.replace(" ", "")
            pred = pred.replace(" ", "")
        #print(f"GT:{gt},PRED:{pred}")
     
        char_output = process_characters(
            gt,
            pred
        )

        total_char_subs += char_output.substitutions
        total_char_dels += char_output.deletions
        total_char_ins += char_output.insertions
        total_char_hits += char_output.hits

        file_cer = (
            char_output.substitutions
            + char_output.deletions
            + char_output.insertions
        ) / max(
            1,
            (
                char_output.substitutions
                + char_output.deletions
                + char_output.hits
            )
        )

        word_output = process_words(
            gt,
            pred
        )

        total_word_subs += word_output.substitutions
        total_word_dels += word_output.deletions
        total_word_ins += word_output.insertions
        total_word_hits += word_output.hits

        file_wer = (
            word_output.substitutions
            + word_output.deletions
            + word_output.insertions
        ) / max(
            1,
            (
                word_output.substitutions
                + word_output.deletions
                + word_output.hits
            )
        )

        file_anls = normalized_similarity(gt, pred)

        if gt == pred:
            exact_matches += 1

        mean_cer_sum += file_cer
        mean_wer_sum += file_wer
        mean_anls_sum += file_anls

        results.append({
            "filename": filename,
            "cer": file_cer,
            "wer": file_wer,
            "anls": file_anls,
        })

   
        if args.verbose:
            print("\n" + "=" * 80)
            print(f"FILE: {filename}")

            print(f"GT   : {gt[:120]}")
            print(f"PRED : {pred[:120]}")

            print(f"CER  : {file_cer:.4f}")
            print(f"WER  : {file_wer:.4f}")
            print(f"1-NED: {file_anls:.4f}")


    global_cer = (
        total_char_subs
        + total_char_dels
        + total_char_ins
    ) / max(
        1,
        (
            total_char_subs
            + total_char_dels
            + total_char_hits
        )
    )

    global_wer = (
        total_word_subs
        + total_word_dels
        + total_word_ins
    ) / max(
        1,
        (
            total_word_subs
            + total_word_dels
            + total_word_hits
        )
    )

   
    n = len(common_files)

    mean_cer = mean_cer_sum / n
    mean_wer = mean_wer_sum / n
    mean_anls = mean_anls_sum / n

    exact_match_acc = exact_matches / n

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    print(f"Files processed        : {n}")

    print("\n--- GLOBAL METRICS (recommended) ---")

    print(f"Global CER             : {global_cer:.4f} ({global_cer*100:.2f}%)")
    print(f"Global WER             : {global_wer:.4f} ({global_wer*100:.2f}%)")

    print("\n--- MEAN METRICS ---")

    print(f"Mean CER               : {mean_cer:.4f}")
    print(f"Mean WER               : {mean_wer:.4f}")

    print("\n--- OCR PAPER METRICS ---")

    print(f"1-NED / ANLS           : {mean_anls:.4f}")
    print(f"Exact Match Accuracy   : {exact_match_acc:.4f}")

    print("\n--- CHARACTER STATS ---")

    print(f"Substitutions          : {total_char_subs}")
    print(f"Deletions              : {total_char_dels}")
    print(f"Insertions             : {total_char_ins}")

    print("\n--- WORD STATS ---")

    print(f"Substitutions          : {total_word_subs}")
    print(f"Deletions              : {total_word_dels}")
    print(f"Insertions             : {total_word_ins}")

    best = min(results, key=lambda x: x["cer"])
    worst = max(results, key=lambda x: x["cer"])

    print("\n--- BEST / WORST ---")

    print(f"Best CER file          : {best['filename']} ({best['cer']:.4f})")
    print(f"Worst CER file         : {worst['filename']} ({worst['cer']:.4f})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())