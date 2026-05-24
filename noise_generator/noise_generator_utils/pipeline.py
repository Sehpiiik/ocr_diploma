"""End-to-end noising pipeline (photometric only).

All augmentations in this project preserve image dimensions, so the input
``xywh`` bboxes pass through untouched. The pipeline's only job is to run a
stochastic sequence of pixel-level effects on the image.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .augmentations import (
    Augmentation,
    DustAndScratches,
    GaussianSensorNoise,
    JpegArtifacts,
    LowResResample,
    MotionBlur,
    ScannerHighlight,
    ScanlineStreaks,
    Vignette,
    build_augraphy_augmentations,
)


@dataclass
class NoisyDocument:
    """Result of running the pipeline on one document."""

    image: np.ndarray                           # BGR uint8, same WxH as input
    width: int
    height: int
    applied: List[str] = field(default_factory=list)  # augmentations that fired


class NoisePipeline:
    """A stochastic sequence of pixel-level augmentations.

    Per-image the augmentations are visited in a shuffled order and each
    decides independently (by its ``p``) whether to fire. Image geometry is
    never changed, so bboxes in the annotation are copied through unchanged.
    """

    def __init__(self, augmentations: Optional[Sequence[Augmentation]] = None):
        self.augmentations: List[Augmentation] = list(augmentations or [])

    @classmethod
    def default(cls, preset: str = "medium") -> "NoisePipeline":
        """Build the default pipeline for the given preset."""
        augs: List[Augmentation] = []
        # Augraphy paper / ink / lighting effects first.
        augs.extend(build_augraphy_augmentations(preset=preset))
        # Custom optics / sensor effects.
        augs.extend(
            [
                Vignette(p=0.45),
                ScannerHighlight(p=0.3),
                ScanlineStreaks(p=0.35),
                DustAndScratches(p=0.4),
                MotionBlur(p=0.2),
                LowResResample(p=0.4),
                GaussianSensorNoise(p=0.7),
                JpegArtifacts(p=0.6),
            ]
        )
        return cls(augmentations=augs)

    def run(
        self,
        image: np.ndarray,
        rng: Optional[np.random.Generator] = None,
    ) -> NoisyDocument:
        """Apply the pipeline to ``image``. Returns a :class:`NoisyDocument`."""
        if rng is None:
            rng = np.random.default_rng()

        img = image
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        order = list(self.augmentations)
        rng.shuffle(order)

        applied: List[str] = []
        for aug in order:
            result = aug(img, rng)
            if not result.applied:
                continue
            applied.append(aug.name)
            img = result.image

        h, w = img.shape[:2]
        return NoisyDocument(
            image=img,
            width=int(w),
            height=int(h),
            applied=applied,
        )


# ---------- seeding helpers ----------

def make_rngs(seed: Optional[int]) -> Tuple[np.random.Generator, random.Random]:
    """Return a (numpy Generator, python Random) pair derived from ``seed``."""
    if seed is None:
        seed = random.SystemRandom().randrange(1 << 31)
    return np.random.default_rng(seed), random.Random(seed)
