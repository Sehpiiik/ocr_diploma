"""Prepare OCR datasets for PaddleOCR PP-OCRv3 training.

Run ``python dataset_split.py --help`` for CLI usage.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

IMAGE_SUFFIXES: Tuple[str, ...] = (".png", ".jpg", ".jpeg")


ANNOTATIONS_DIRNAME: str = "annotations"
IMAGES_DIRNAME: str = "images"


@dataclass(frozen=True)
class DatasetRule:
    """Per-dataset split and augmentation configuration."""

    name: str
    train_ratio: float
    augment_train: int = 0  # how many *train* docs to mark as augment=True
    augment_test: int = 0   # how many *test*  docs to mark as augment=True

    def __post_init__(self) -> None:
        if not 0.0 < self.train_ratio < 1.0:
            raise ValueError(
                f"{self.name}: train_ratio must be in (0, 1), got {self.train_ratio}"
            )
        if self.augment_train < 0 or self.augment_test < 0:
            raise ValueError(
                f"{self.name}: augment counts must be >= 0, got "
                f"train={self.augment_train}, test={self.augment_test}"
            )


#: Default rules as described in the task spec.
DEFAULT_RULES: Tuple[DatasetRule, ...] = (
    DatasetRule(name="synthdoc", train_ratio=0.90, augment_train=1000,  augment_test=100),
    DatasetRule(name="ddi100",   train_ratio=0.90, augment_train=1100, augment_test=200),
    DatasetRule(name="smartdoc", train_ratio=0.90, augment_train=800,  augment_test=200),
    DatasetRule(name="rdtag",    train_ratio=0.40, augment_train=0,    augment_test=0),
)


@dataclass(frozen=True)
class Document:
    """A single (image, annotation) pair belonging to a dataset."""

    dataset: str
    stem: str
    image_path: Path
    annotation_path: Path


@dataclass
class DatasetSplit:
    """Result of splitting one dataset."""

    rule: DatasetRule
    train: List[Document] = field(default_factory=list)
    test: List[Document] = field(default_factory=list)
    augment_train_stems: frozenset = field(default_factory=frozenset)
    augment_test_stems: frozenset = field(default_factory=frozenset)

    @property
    def total(self) -> int:
        return len(self.train) + len(self.test)

    def is_augmented(self, split: str, stem: str) -> bool:
        if split == "train":
            return stem in self.augment_train_stems
        if split == "test":
            return stem in self.augment_test_stems
        raise ValueError(f"unknown split: {split!r}")


def _find_image(images_dir: Path, stem: str) -> Optional[Path]:
    """Return the first image file in ``images_dir`` whose stem matches ``stem``.

    Searches the configured :data:`IMAGE_SUFFIXES` (case-insensitive).
    """
    for suffix in IMAGE_SUFFIXES:
        candidate = images_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
        # Try upper-case extension as well, just in case.
        candidate_upper = images_dir / f"{stem}{suffix.upper()}"
        if candidate_upper.is_file():
            return candidate_upper
    return None


def discover_dataset(
    dataset_root: Path,
    dataset_name: str,
    logger: logging.Logger,
) -> List[Document]:
    """Scan a single dataset folder and return the validated (image, json) pairs.

    Annotation files without a matching image (or vice versa) are reported and
    excluded from the result.
    """
    annotations_dir = dataset_root / ANNOTATIONS_DIRNAME
    images_dir = dataset_root / IMAGES_DIRNAME

    if not annotations_dir.is_dir():
        raise FileNotFoundError(
            f"{dataset_name}: annotations directory not found: {annotations_dir}"
        )
    if not images_dir.is_dir():
        raise FileNotFoundError(
            f"{dataset_name}: images directory not found: {images_dir}"
        )

    documents: List[Document] = []
    seen_stems: set[str] = set()
    missing_images: List[str] = []

    for annotation_path in sorted(annotations_dir.glob("*.json")):
        stem = annotation_path.stem
        if stem in seen_stems:
            logger.warning(
                "%s: duplicate annotation stem %r, skipping %s",
                dataset_name, stem, annotation_path,
            )
            continue
        image_path = _find_image(images_dir, stem)
        if image_path is None:
            missing_images.append(stem)
            continue
        seen_stems.add(stem)
        documents.append(
            Document(
                dataset=dataset_name,
                stem=stem,
                image_path=image_path,
                annotation_path=annotation_path,
            )
        )

    # Detect orphan images (image without matching JSON).
    orphan_images: List[str] = []
    for image_path in images_dir.iterdir():
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if image_path.stem not in seen_stems:
            orphan_images.append(image_path.name)

    if missing_images:
        logger.warning(
            "%s: %d annotation(s) without matching image (skipped). First few: %s",
            dataset_name,
            len(missing_images),
            ", ".join(missing_images[:5]),
        )
    if orphan_images:
        logger.warning(
            "%s: %d image(s) without matching annotation (skipped). First few: %s",
            dataset_name,
            len(orphan_images),
            ", ".join(orphan_images[:5]),
        )

    logger.info("%s: discovered %d valid pairs", dataset_name, len(documents))
    return documents


# ---------------------------------------------------------------------------
# Splitting & augmentation
# ---------------------------------------------------------------------------


def split_dataset(
    rule: DatasetRule,
    documents: Sequence[Document],
    seed: int,
    logger: logging.Logger,
) -> DatasetSplit:
    """Deterministically split ``documents`` into train/test for a single dataset."""
    if not documents:
        logger.warning("%s: no documents to split", rule.name)
        return DatasetSplit(rule=rule)

    # Sort by stem first so the input order is deterministic regardless of
    # filesystem traversal order — only then shuffle with the seeded RNG.
    ordered = sorted(documents, key=lambda d: d.stem)

    # Use a per-dataset RNG so adding/removing a dataset does not change the
    # split of the others. Mix the dataset name into the seed for stability.
    rng = random.Random(f"{seed}:{rule.name}:split")
    shuffled = ordered.copy()
    rng.shuffle(shuffled)

    n_total = len(shuffled)
    n_train = int(round(n_total * rule.train_ratio))
    # Guard against pathological edge cases on tiny datasets.
    n_train = max(0, min(n_total, n_train))

    train_docs = shuffled[:n_train]
    test_docs = shuffled[n_train:]

    # Augmentation is sampled independently for train and test, but only from
    # documents that actually live in that split (no leakage between splits).
    def _sample(pool: Sequence[Document], requested: int, label: str) -> frozenset[str]:
        if requested <= 0 or not pool:
            return frozenset()
        if requested > len(pool):
            logger.warning(
                "%s: augment_%s=%d exceeds %s size=%d, clamping",
                rule.name, label, requested, label, len(pool),
            )
            requested = len(pool)
        aug_rng = random.Random(f"{seed}:{rule.name}:augment:{label}")
        return frozenset(d.stem for d in aug_rng.sample(list(pool), k=requested))

    augment_train_stems = _sample(train_docs, rule.augment_train, "train")
    augment_test_stems = _sample(test_docs, rule.augment_test, "test")

    logger.info(
        "%s: total=%d train=%d (augment=%d) test=%d (augment=%d)",
        rule.name,
        n_total,
        len(train_docs), len(augment_train_stems),
        len(test_docs),  len(augment_test_stems),
    )
    return DatasetSplit(
        rule=rule,
        train=list(train_docs),
        test=list(test_docs),
        augment_train_stems=augment_train_stems,
        augment_test_stems=augment_test_stems,
    )


@dataclass
class OutputLayout:
    """Resolves the flat ``out/{split}/{images|annotations}/`` directory tree.

    Documents from all source datasets are merged into the same per-split
    folder; the originating dataset is no longer reflected in the directory
    structure (it is still available inside each annotation, e.g. as the
    ``domain`` field that ddi100, smartdoc and rdtag already carry).
    """

    root: Path

    def split_root(self, split: str) -> Path:
        return self.root / split

    def images_dir(self, split: str) -> Path:
        return self.split_root(split) / IMAGES_DIRNAME

    def annotations_dir(self, split: str) -> Path:
        return self.split_root(split) / ANNOTATIONS_DIRNAME


def _write_one(
    doc: Document,
    split: str,
    augment: bool,
    layout: OutputLayout,
    overwrite: bool,
) -> None:
    """Copy image and write updated annotation JSON for a single document."""
    images_dir = layout.images_dir(split)
    annotations_dir = layout.annotations_dir(split)
    images_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)

    # Image: copy preserving extension and metadata.
    out_image = images_dir / doc.image_path.name
    if overwrite or not out_image.exists():
        shutil.copy2(doc.image_path, out_image)

    # Annotation: load, mutate, write.
    with doc.annotation_path.open("r", encoding="utf-8") as f:
        annotation = json.load(f)
    if not isinstance(annotation, dict):
        raise ValueError(
            f"{doc.annotation_path}: expected top-level JSON object, "
            f"got {type(annotation).__name__}"
        )
    annotation["split"] = split
    annotation["augment"] = bool(augment)

    out_annotation = annotations_dir / doc.annotation_path.name
    if overwrite or not out_annotation.exists():
        # Write atomically via a tmp file to avoid half-written JSON on crashes.
        tmp_path = out_annotation.with_suffix(out_annotation.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(annotation, f, ensure_ascii=False, indent=2)
        tmp_path.replace(out_annotation)


def _check_collisions(
    splits: Sequence["DatasetSplit"],
    logger: logging.Logger,
) -> None:
    """Abort early if two source documents would land on the same output path."""
    for split_name in ("train", "test"):
        seen_images: Dict[str, str] = {}
        seen_annotations: Dict[str, str] = {}
        for ds_split in splits:
            docs = ds_split.train if split_name == "train" else ds_split.test
            for doc in docs:
                if doc.image_path.name in seen_images:
                    raise ValueError(
                        f"output filename collision in {split_name}/images: "
                        f"{doc.image_path.name!r} from {ds_split.rule.name!r} "
                        f"and {seen_images[doc.image_path.name]!r}"
                    )
                if doc.annotation_path.name in seen_annotations:
                    raise ValueError(
                        f"output filename collision in {split_name}/annotations: "
                        f"{doc.annotation_path.name!r} from "
                        f"{ds_split.rule.name!r} and "
                        f"{seen_annotations[doc.annotation_path.name]!r}"
                    )
                seen_images[doc.image_path.name] = ds_split.rule.name
                seen_annotations[doc.annotation_path.name] = ds_split.rule.name
        logger.info(
            "%s: no filename collisions across %d datasets",
            split_name, len(splits),
        )


def write_split(
    splits: Sequence[DatasetSplit],
    layout: OutputLayout,
    logger: logging.Logger,
    overwrite: bool = True,
) -> Dict[str, Dict[str, int]]:
    """Materialise ``splits`` to disk under ``layout.root``.

    The output uses a flat layout: ``out/{train|test}/{images|annotations}/``
    with documents from every source dataset merged into the same directories.
    Filename collisions across datasets are detected up front and aborted.

    Returns a per-dataset summary with train/test sizes and the number of
    augmented documents in each split.
    """
    _check_collisions(splits, logger)

    # Pre-create the four leaf directories so empty splits are still valid.
    for sp in ("train", "test"):
        layout.images_dir(sp).mkdir(parents=True, exist_ok=True)
        layout.annotations_dir(sp).mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Dict[str, int]] = {}
    for ds_split in splits:
        ds_name = ds_split.rule.name
        per = {
            "train": 0,
            "test": 0,
            "augment_train": len(ds_split.augment_train_stems),
            "augment_test": len(ds_split.augment_test_stems),
        }

        total = len(ds_split.train) + len(ds_split.test)
        logger.info("%s: writing %d documents...", ds_name, total)

        for idx, doc in enumerate(ds_split.train, start=1):
            _write_one(doc, "train", ds_split.is_augmented("train", doc.stem),
                       layout, overwrite)
            per["train"] += 1
            if idx % 500 == 0:
                logger.info("  %s/train progress: %d/%d", ds_name, idx, len(ds_split.train))

        for idx, doc in enumerate(ds_split.test, start=1):
            _write_one(doc, "test", ds_split.is_augmented("test", doc.stem),
                       layout, overwrite)
            per["test"] += 1
            if idx % 500 == 0:
                logger.info("  %s/test progress: %d/%d", ds_name, idx, len(ds_split.test))

        summary[ds_name] = per
        logger.info(
            "%s: wrote train=%d (augment=%d) test=%d (augment=%d)",
            ds_name,
            per["train"], per["augment_train"],
            per["test"],  per["augment_test"],
        )
    return summary


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    input_root: Path,
    output_root: Path,
    rules: Sequence[DatasetRule] = DEFAULT_RULES,
    seed: int = 42,
    dry_run: bool = False,
    overwrite: bool = True,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Dict[str, int]]:
    """End-to-end: discover -> split -> (write).

    Returns the per-dataset summary even in dry-run mode (no files are written
    when ``dry_run`` is true).
    """
    log = logger or logging.getLogger(__name__)

    if not input_root.is_dir():
        raise FileNotFoundError(f"input root not found: {input_root}")

    log.info("Input root:  %s", input_root)
    log.info("Output root: %s", output_root)
    log.info("Seed:        %d", seed)
    log.info("Dry run:     %s", dry_run)

    splits: List[DatasetSplit] = []
    for rule in rules:
        ds_root = input_root / rule.name
        if not ds_root.is_dir():
            log.warning("dataset folder missing, skipping: %s", ds_root)
            splits.append(DatasetSplit(rule=rule))
            continue
        docs = discover_dataset(
            dataset_root=ds_root,
            dataset_name=rule.name,
            logger=log,
        )
        splits.append(split_dataset(rule, docs, seed=seed, logger=log))

    if dry_run:
        summary = {
            s.rule.name: {
                "train": len(s.train),
                "test": len(s.test),
                "augment_train": len(s.augment_train_stems),
                "augment_test": len(s.augment_test_stems),
            }
            for s in splits
        }
        log.info("Dry run complete; no files written.")
        return summary

    layout = OutputLayout(root=output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    return write_split(splits, layout, logger=log, overwrite=overwrite)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Split OCR datasets (synthdoc, ddi100, smartdoc, rdtag) into "
            "train/test, mark augmentation candidates, update JSON annotations, "
            "and export the result for PaddleOCR PP-OCRv3."
        ),
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Root folder containing the four dataset sub-folders.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output root. ``train/`` and ``test/`` will be created here.",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and split, but do not copy files or write JSON.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip files that already exist in the output tree.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce log verbosity to warnings only.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("dataset_split")

    try:
        summary = run_pipeline(
            input_root=args.input,
            output_root=args.output,
            seed=args.seed,
            dry_run=args.dry_run,
            overwrite=not args.no_overwrite,
            logger=logger,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    # Final summary table — always printed (even when --quiet).
    totals = {"train": 0, "test": 0, "augment_train": 0, "augment_test": 0}
    print("\n=== Summary ===")
    print(
        f"{'dataset':<10} {'train':>8} {'test':>8} "
        f"{'aug_train':>10} {'aug_test':>10}"
    )
    for name, counts in summary.items():
        print(
            f"{name:<10} {counts['train']:>8} {counts['test']:>8} "
            f"{counts['augment_train']:>10} {counts['augment_test']:>10}"
        )
        for k in totals:
            totals[k] += counts[k]
    print(
        f"{'TOTAL':<10} {totals['train']:>8} {totals['test']:>8} "
        f"{totals['augment_train']:>10} {totals['augment_test']:>10}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
