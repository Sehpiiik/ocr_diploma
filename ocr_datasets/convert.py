"""Main script to convert all datasets to unified line-level annotation format."""
import argparse
from pathlib import Path

from converters.ddi100_converter import convert_ddi100
from converters.rdtag_converter import convert_rdtag
from converters.smartdoc_converter import convert_smartdoc

BASE_DIR = Path(__file__).parent
DATASETS_DIR = BASE_DIR / "datasets"
OUTPUT_DIR = BASE_DIR / "output"


def main():
    parser = argparse.ArgumentParser(description="Convert OCR datasets to unified line-level format.")
    parser.add_argument("--dataset", choices=["ddi100", "rdtag", "smartdoc", "all"], default="all",
                        help="Which dataset to convert (default: all)")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_DIR,
                        help="Output directory (default: ./output)")
    args = parser.parse_args()

    if args.dataset in ("ddi100", "all"):
        convert_ddi100(DATASETS_DIR / "DDI100_v1.3", args.output / "ddi100")

    if args.dataset in ("rdtag", "all"):
        convert_rdtag(DATASETS_DIR / "RDTAG-1.0", args.output / "rdtag")

    if args.dataset in ("smartdoc", "all"):
        convert_smartdoc(DATASETS_DIR / "SmartDoc2015_Challenge_2", args.output / "smartdoc")


if __name__ == "__main__":
    main()
