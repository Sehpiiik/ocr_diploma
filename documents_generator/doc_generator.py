"""CLI for the synthetic document generator.

Example:
    python doc_generator.py --corpus sample_corpus.txt --num 150 --output out/  --debug-boxes --line-spacing 1.5 --margin 200 --min-sentences 20 --max-sentences 40 --seed 46 --font-size 50 --font /Users/shpkkk/python_projects/ocr_diploma/documents_generator/fonts/Courier_New.ttf    
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from doc_generator_utils import *


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate synthetic OCR documents "
                                            "with per-sentence per-line bbox annotations.")
    p.add_argument("--corpus", required=True, type=Path,
                   help="Path to a UTF-8 text file used as the sentence pool.")
    p.add_argument("--num", "-n", type=int, default=10,
                   help="Number of documents to generate (default: 10).")
    p.add_argument("--output", "-o", type=Path, default=Path("out"),
                   help="Output directory (default: ./out).")
    p.add_argument("--width", type=int, default=2480, help="Page width in px.")
    p.add_argument("--height", type=int, default=3508, help="Page height in px.")
    p.add_argument("--margin", type=int, default=100, help="Page margin in px.")
    p.add_argument("--font-size", type=int, default=50)
    p.add_argument("--line-spacing", type=float, default=1.35)
    p.add_argument("--font", type=str, default=None,
                   help="Path to a .ttf font. Auto-detected if omitted.")
    p.add_argument("--seed", type=int, default=None, help="Random seed.")
    p.add_argument("--min-sentences", type=int, default=20,
                   help="Minimum sentences sampled per document.")
    p.add_argument("--max-sentences", type=int, default=60,
                   help="Maximum sentences sampled per document.")
    p.add_argument("--debug-boxes", action="store_true",
                   help="Draw red bbox outlines on the rendered image.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.corpus.is_file():
        print(f"error: corpus file not found: {args.corpus}", file=sys.stderr)
        return 2

    sentences = load_sentences(args.corpus)
    if not sentences:
        print("error: corpus contains no sentences", file=sys.stderr)
        return 2
    print(f"Loaded {len(sentences)} sentences from {args.corpus}")

    rng = random.Random(args.seed)
    cfg = PageConfig(
        width=args.width,
        height=args.height,
        margin=args.margin,
        font_size=args.font_size,
        line_spacing=args.line_spacing,
        font_path=args.font,
    )
    gen = DocumentGenerator(config=cfg, rng=rng)
    results = gen.generate(
        sentence_pool=sentences,
        count=args.num,
        out_dir=args.output,
        sentences_per_doc=(args.min_sentences, args.max_sentences),
        draw_debug_boxes=args.debug_boxes,
    )
    print(f"Wrote {len(results)} documents to {args.output}/")
    print(f"  images:      {args.output}/images/")
    print(f"  annotations: {args.output}/annotations/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
