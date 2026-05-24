"""CLI
Example:
    python noise_generator.py --input ../documents_generator/out --variants 3 --seed 0
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import List, Tuple

from noise_generator_utils import (
    NoisePipeline,
    build_renamed_annotation,
    draw_annotation_bboxes,
    find_pairs,
    make_rngs,
    read_image_bgr,
    should_augment,
    write_annotation,
    write_image,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "In-place augmentation of clean document pairs. Each annotation "
            "JSON whose top-level field has \"augment\": true is replaced by "
            "N augmented variants named <stem>_au_NN.{png,json}; the "
            "original image and annotation are then deleted. Annotations "
            "are copied verbatim except the \"image\" field is updated to "
            "the new variant filename."
        )
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Folder containing images/ and annotations/.")
    p.add_argument("--seed", type=int, default=None, help="Random seed.")
    p.add_argument("--variants", type=int, default=1,
                   help="Number of augmented variants per flagged pair "
                        "(default: 1).")
    p.add_argument(
        "--preset",
        choices=["light", "medium", "heavy", "scanner", "photocopy"],
        default="medium",
        help="Distortion preset (default: medium).",
    )
    p.add_argument("--debug-boxes", action="store_true",
                   help="Draw the (unchanged) xywh bboxes on each saved "
                        "augmented image.")
    p.add_argument("--limit", type=int, default=None,
                   help="Process only the first N flagged pairs.")
    p.add_argument("--workers", type=int, default=1,
                   help="Number of parallel worker processes (default: 1).")
    p.add_argument("--keep-originals", action="store_true",
                   help="Do not delete the source image / annotation after "
                        "writing the augmented variants.")
    p.add_argument("--augment", action="store_true", help="check augment flag")
    return p


def _variant_seed(base_seed: int, stem: str, variant_idx: int) -> int:
    """Deterministic per-(stem, variant) sub-seed derived from ``base_seed``.

    Python's built-in ``hash()`` is randomized per interpreter via
    ``PYTHONHASHSEED``, so mixing it into a seed makes runs non-reproducible
    both across invocations and (with ``spawn`` workers) across processes
    inside a single run. Using a stable hash function fixes both.
    """
    digest = hashlib.blake2b(
        f"{stem}|{variant_idx}".encode("utf-8"), digest_size=4
    ).digest()
    return (int(base_seed) + int.from_bytes(digest, "big")) & 0x7FFFFFFF


def _process_one(args_dict: dict) -> Tuple[str, List[str]]:
    """Worker: augment one flagged pair in place.

    Returns ``(stem, written_filenames)`` so the parent process can log which
    pair just finished — important when running with ``--workers > 1`` where
    ``imap_unordered`` does not preserve input order.
    """
    pair_info = args_dict["pair"]
    args = args_dict["args"]
    base_seed = args_dict["seed"]

    pipeline = NoisePipeline.default(preset=args["preset"])

    image_path = Path(pair_info["image_path"])
    ann_path = Path(pair_info["annotation_path"])
    annotation = pair_info["annotation"]
    stem = pair_info["stem"]
    img_ext = image_path.suffix or ".png"
    variants = max(int(args["variants"]), 0)
    debug_boxes = bool(args["debug_boxes"])
    keep_originals = bool(args["keep_originals"])

    if variants == 0:
        return stem, []

    image = read_image_bgr(image_path)

    written: List[str] = []
    for v in range(variants):
        suffix = f"_au_{v + 1:02d}"
        out_img_name = f"{stem}{suffix}{img_ext}"
        out_ann_name = f"{stem}{suffix}.json"
        out_img_path = image_path.parent / out_img_name
        out_ann_path = ann_path.parent / out_ann_name

        # Per-variant seed so each variant differs but the run is reproducible
        # — see _variant_seed for why we don't use Python's hash() here.
        seed = (
            None
            if base_seed is None
            else _variant_seed(base_seed, stem, v)
        )
        np_rng, _ = make_rngs(seed)

        noisy = pipeline.run(image, rng=np_rng)
        ann_out = build_renamed_annotation(annotation, out_img_name)

        img_to_save = noisy.image
        if debug_boxes:
            img_to_save = draw_annotation_bboxes(img_to_save, ann_out)

        write_image(out_img_path, img_to_save)
        write_annotation(out_ann_path, ann_out)
        written.append(out_img_name)

   
    if written and not keep_originals:
        for path in (image_path, ann_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    return stem, written


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.input.is_dir():
        print(f"error: input dir not found: {args.input}", file=sys.stderr)
        return 2

    all_pairs = find_pairs(args.input)
    if args.augment:
        pairs = [p for p in all_pairs if should_augment(p.annotation)]
    else:
        pairs = all_pairs

    if not all_pairs:
        print(f"error: no annotation/image pairs under {args.input}",
              file=sys.stderr)
        return 2
    if not pairs:
        print(
            f"No pairs flagged with \"augment\": true under {args.input} "
            f"(scanned {len(all_pairs)} pair(s)). Nothing to do."
        )
        return 0
    if args.limit is not None:
        pairs = pairs[: args.limit]

    print(
        f"Augmenting {len(pairs)}/{len(all_pairs)} flagged pair(s) under "
        f"{args.input} ({args.variants} variant(s) each)."
    )

    shared = {
        "preset": args.preset,
        "variants": args.variants,
        "debug_boxes": args.debug_boxes,
        "keep_originals": args.keep_originals,
    }

    total_written = 0
    t0 = time.time()

    if args.workers <= 1:
        for i, pair in enumerate(pairs, 1):
            payload = {
                "pair": {
                    "image_path": str(pair.image_path),
                    "annotation_path": str(pair.annotation_path),
                    "annotation": pair.annotation,
                    "stem": pair.stem,
                },
                "args": shared,
                "seed": args.seed,
            }
            written = _process_one(payload)[1]
            total_written += len(written)
            print(
                f"[{i:>4d}/{len(pairs)}] {pair.stem} -> {len(written)} variant(s)"
            )
    else:
        import multiprocessing as mp
        payloads = [
            {
                "pair": {
                    "image_path": str(p.image_path),
                    "annotation_path": str(p.annotation_path),
                    "annotation": p.annotation,
                    "stem": p.stem,
                },
                "args": shared,
                "seed": args.seed,
            }
            for p in pairs
        ]
        with mp.get_context("spawn").Pool(args.workers) as pool:
            for i, (stem_done, written) in enumerate(
                pool.imap_unordered(_process_one, payloads), 1
            ):
                total_written += len(written)
                print(
                    f"[{i:>4d}/{len(pairs)}] {stem_done} ->  {len(written)} variant(s)",
                )

    dt = time.time() - t0
    action = "kept" if args.keep_originals else "replaced"
    print(
        f"Done. Wrote {total_written} augmented document(s) in {dt:.1f}s; "
        f"originals were {action}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
