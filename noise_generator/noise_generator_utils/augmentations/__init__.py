"""Pixel-only augmentation building blocks.

All augmentations preserve image dimensions, so input xywh bboxes pass through
the pipeline unchanged.
"""
from .base import AugResult, Augmentation
from .scanner import (
    DustAndScratches,
    GaussianSensorNoise,
    JpegArtifacts,
    LowResResample,
    MotionBlur,
    ScannerHighlight,
    ScanlineStreaks,
    Vignette,
)
from .augraphy_wrappers import build_augraphy_augmentations

__all__ = [
    "AugResult",
    "Augmentation",
    "Vignette",
    "ScannerHighlight",
    "DustAndScratches",
    "ScanlineStreaks",
    "GaussianSensorNoise",
    "JpegArtifacts",
    "MotionBlur",
    "LowResResample",
    "build_augraphy_augmentations",
]
