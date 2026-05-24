"""Reorganize the RDTAG-1.0 dataset into a clean two-folder layout.

Original layout::

    RDTAG-1.0/
    ├── Training_Set1/
    │   ├── 2_Book6_46_in_close_3.jpg
    │   ├── 2_Book6_46_in_close_3.json
    │   ├── 2_Book6_46_in_close_3.txt
    │   └── ...
    ├── Training_Set2/
    └── ...

New layout::

    RDTAG-1.0/
    ├── images/
    │   ├── Training_Set1/
    │   │   └── 2_Book6_46_in_close_3.jpg
    │   └── ...
    └── orig_annotations/
        ├── Training_Set1/
        │   ├── 2_Book6_46_in_close_3.json
        │   └── 2_Book6_46_in_close_3.txt
        └── ...

"""
import argparse
import shutil
import sys
from pathlib import Path

TRAINING_SET_PREFIX = "Training_Set"


def is_subset_dir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith(TRAINING_SET_PREFIX)


def reorganize(dataset_path: Path, *, copy: bool = False, dry_run: bool = False) -> None:
    if not dataset_path.is_dir():
        raise FileNotFoundError(f"dataset path not found: {dataset_path}")

    images_root = dataset_path / "images"
    annotations_root = dataset_path / "orig_annotations"

    subset_dirs = sorted(p for p in dataset_path.iterdir() if is_subset_dir(p))
    if not subset_dirs:
        print(f"No '{TRAINING_SET_PREFIX}*' directories found in {dataset_path}.")
        print("Dataset may already be reorganized — nothing to do.")
        return

    transfer = shutil.copy2 if copy else shutil.move
    action = "copy" if copy else "move"

    moved_images = 0
    moved_annotations = 0

    for subset in subset_dirs:
        target_images = images_root / subset.name
        target_annotations = annotations_root / subset.name

        if not dry_run:
            target_images.mkdir(parents=True, exist_ok=True)
            target_annotations.mkdir(parents=True, exist_ok=True)

        for entry in sorted(subset.iterdir()):
            if not entry.is_file():
                continue
            if entry.name.startswith("."):
                continue

            if entry.suffix.lower() == ".jpg":
                target = target_images / entry.name
                moved_images += 1
            else:
                target = target_annotations / entry.name
                moved_annotations += 1

            if dry_run:
                print(f"[dry-run] {action} {entry} -> {target}")
            else:
                transfer(str(entry), str(target))

        if not copy and not dry_run:
            try:
                subset.rmdir()
            except OSError:
                pass

    print(
        f"Done. {action.title()}d {moved_images} image(s) into {images_root} "
        f"and {moved_annotations} annotation(s) into {annotations_root}."
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Reorganize RDTAG-1.0 into images/ and orig_annotations/ folders.",
    )
    p.add_argument(
        "--dataset", "-d", type=Path, required=True,
        help="Path to the RDTAG-1.0 dataset directory.",
    )
    p.add_argument(
        "--copy", action="store_true",
        help="Copy files instead of moving them (preserves the original layout).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without touching the filesystem.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reorganize(args.dataset, copy=args.copy, dry_run=args.dry_run)
    except FileNotFoundError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
