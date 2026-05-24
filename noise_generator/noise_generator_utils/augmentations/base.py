"""Base classes for image augmentations.

Every augmentation is a callable that takes a BGR image and a numpy Generator
and returns an :class:`AugResult`. All augmentations in this project are
pixel-only (no geometric change), so bboxes pass through untouched.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class AugResult:
    """Output of an augmentation step."""

    image: np.ndarray     # BGR uint8
    applied: bool = True  # False if the augmentation was a no-op


class Augmentation(ABC):
    """Stateless augmentation with an independent probability of firing."""

    name: str = "augmentation"

    def __init__(self, p: float = 1.0):
        self.p = float(p)

    @abstractmethod
    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        """Do the actual work (no probability check)."""

    def __call__(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        if self.p < 1.0 and rng.random() >= self.p:
            return AugResult(image=img, applied=False)
        return self._apply(img, rng)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.__class__.__name__}(p={self.p})"
