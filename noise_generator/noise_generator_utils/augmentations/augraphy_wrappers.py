"""Wrappers around pure-photometric augraphy augmentations.

Every augmentation here leaves pixel geometry untouched, so the pipeline can
feed them the current image without having to update bboxes afterwards. The
augmentations in augraphy's "Spatial level" category (BookBinding, Folding,
Geometric, PageBorder, ...) are intentionally NOT used — their non-linear
warps would desync the matrix-based bbox tracking.

If augraphy is not installed, importing this module succeeds but calling
`build_augraphy_augmentations` returns an empty list. That way the project
still runs with the pure OpenCV augmentations.
"""
from __future__ import annotations

import warnings
from typing import List

import numpy as np

from .base import AugResult, Augmentation

try:  # augraphy is an optional dependency at runtime.
    from augraphy import (  # type: ignore
        BadPhotoCopy,
        BleedThrough,
        BrightnessTexturize,
        DirtyDrum,
        DirtyRollers,
        InkBleed,
        Letterpress,
        LightingGradient,
        LowInkRandomLines,
        ShadowCast,
        SubtleNoise,
    )
    _AUGRAPHY_AVAILABLE = True
except Exception as exc:  # pragma: no cover - env-dependent
    warnings.warn(
        f"augraphy is not available ({exc!r}); photometric wrappers will be no-ops.",
        stacklevel=2,
    )
    _AUGRAPHY_AVAILABLE = False


class _AugraphyWrapper(Augmentation):
    """Adapt an augraphy `Augmentation` to our `Augmentation` interface.

    We always pass ``p=1`` to augraphy itself (so its internal dice roll never
    short-circuits) and control probability from our own base class.
    """

    name = "augraphy"

    def __init__(self, aug_factory, p: float = 0.5, name: str = "augraphy"):
        super().__init__(p=p)
        self._factory = aug_factory
        self.name = name

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        if not _AUGRAPHY_AVAILABLE:
            return AugResult(image=img, applied=False)

        # augraphy relies on numpy's global RNG; seed it from our rng so runs
        # are reproducible given a seed.
        seed = int(rng.integers(0, np.iinfo(np.int32).max))
        with _temporary_numpy_seed(seed):
            aug = self._factory()
            out = aug(img.copy())

        # Augraphy may return [image, mask, kps, bboxes] when extras are
        # supplied, but in our single-image call path it returns the image.
        if isinstance(out, list) and len(out) >= 1:
            out = out[0]
        if out is None:
            return AugResult(image=img, applied=False)
        return AugResult(image=np.asarray(out))


class _temporary_numpy_seed:
    """Context manager that pins np.random state, then restores it."""

    def __init__(self, seed: int):
        self.seed = int(seed)

    def __enter__(self):
        self._state = np.random.get_state()
        np.random.seed(self.seed)
        # Also pin `random` since some augraphy internals use it.
        import random as _random
        self._py_state = _random.getstate()
        _random.seed(self.seed)
        return self

    def __exit__(self, exc_type, exc, tb):
        np.random.set_state(self._state)
        import random as _random
        _random.setstate(self._py_state)
        return False


# ---------- catalogue ----------

def build_augraphy_augmentations(
    preset: str = "medium",
) -> List[Augmentation]:
    """Return a curated list of photometric augraphy wrappers for a preset.

    The presets tune per-augmentation probability; per-image only a subset of
    the list actually fires. All augmentations use augraphy defaults, which
    are already in a realistic range.
    """
    if not _AUGRAPHY_AVAILABLE:
        return []

    # (factory, default_probability, display_name)
    #
    # A few of these are intentionally constructed with explicit, gentler
    # parameters rather than augraphy's defaults:
    #
    # * ShadowCast — defaults paint a near-pitch-black band covering up to
    #   ~80% of the page (shadow_opacity up to 0.9, width/height up to 0.8,
    #   color (0,0,0)). At document scale that reads as "a large black bar".
    #   We keep it small and translucent so it looks like a soft shadow.
    # * DirtyDrum / DirtyRollers — defaults can stamp fairly wide horizontal
    #   or vertical streaks; we cap their line widths so they read as fine
    #   scanner streaks rather than bars.
    catalogue = [
        (lambda: InkBleed(), 0.35, "ink_bleed"),
        (lambda: LowInkRandomLines(), 0.2, "low_ink_random_lines"),
        (lambda: Letterpress(), 0.15, "letterpress"),
        (lambda: BleedThrough(), 0.25, "bleed_through"),
        (
            lambda: DirtyDrum(
                line_width_range=(1, 3),
                line_concentration=0.05,
                noise_intensity=0.3,
            ),
            0.25,
            "dirty_drum",
        ),
        (
            lambda: DirtyRollers(
                line_width_range=(3, 7),
            ),
            0.2,
            "dirty_rollers",
        ),
        (lambda: BadPhotoCopy(), 0.25, "bad_photocopy"),
        (lambda: LightingGradient(), 0.4, "lighting_gradient"),
        (
            lambda: ShadowCast(
                shadow_width_range=(0.05, 0.25),
                shadow_height_range=(0.05, 0.25),
                shadow_opacity_range=(0.1, 0.4),
            ),
            0.2,
            "shadow_cast",
        ),
        (lambda: BrightnessTexturize(), 0.25, "brightness_texturize"),
        (lambda: SubtleNoise(), 0.5, "subtle_noise"),
    ]

    # Scale probabilities by preset.
    multipliers = {
        "light": 0.4,
        "medium": 1.0,
        "heavy": 1.6,
        "scanner": 1.2,   # emphasizes scanner streaks
        "photocopy": 1.4,  # emphasizes photocopy noise
    }
    mult = multipliers.get(preset, 1.0)

    # Per-preset emphasis (multiplier per augmentation name).
    emphasis = {
        "scanner": {"dirty_drum": 1.8, "dirty_rollers": 1.8, "bad_photocopy": 1.2},
        "photocopy": {"bad_photocopy": 2.2, "letterpress": 1.6, "low_ink_random_lines": 1.6},
    }.get(preset, {})

    augs: List[Augmentation] = []
    for factory, prob, name in catalogue:
        p = min(1.0, prob * mult * emphasis.get(name, 1.0))
        augs.append(_AugraphyWrapper(factory, p=p, name=name))
    return augs
