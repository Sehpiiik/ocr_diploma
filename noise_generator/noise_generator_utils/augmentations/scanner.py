"""Custom pixel-level augmentations that simulate sensor / optics artifacts.

All augmentations preserve image dimensions and so the input xywh bboxes pass
through unchanged. Implemented with OpenCV + NumPy only.
"""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from .base import AugResult, Augmentation


# ---------- helpers ----------

def _ensure_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def _clip_uint8(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0, 255).astype(np.uint8)


# ---------- vignette / glare ----------

class Vignette(Augmentation):
    """Radial darkening toward the corners (camera / scanner lid edges)."""

    name = "vignette"

    def __init__(self, strength: Tuple[float, float] = (0.25, 0.55), p: float = 0.5):
        super().__init__(p=p)
        self.strength = strength

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img)
        h, w = img.shape[:2]
        strength = float(rng.uniform(*self.strength))

        # Separable Gaussian kernel in x/y → cheap radial-ish mask.
        kx = cv2.getGaussianKernel(w, w * 0.55)
        ky = cv2.getGaussianKernel(h, h * 0.55)
        mask = (ky @ kx.T)
        mask = mask / mask.max()           # 0..1, center=1
        mask = 1.0 - strength * (1.0 - mask)  # darken corners by `strength`
        mask = mask[..., None]

        out = img.astype(np.float32) * mask
        return AugResult(image=_clip_uint8(out))


class ScannerHighlight(Augmentation):
    """Single soft bright spot — e.g. a glare off the scanner lid."""

    name = "scanner_highlight"

    def __init__(
        self,
        intensity: Tuple[float, float] = (0.15, 0.4),
        radius_frac: Tuple[float, float] = (0.15, 0.35),
        p: float = 0.35,
    ):
        super().__init__(p=p)
        self.intensity = intensity
        self.radius_frac = radius_frac

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img)
        h, w = img.shape[:2]
        cx = rng.uniform(0.2 * w, 0.8 * w)
        cy = rng.uniform(0.2 * h, 0.8 * h)
        r = rng.uniform(*self.radius_frac) * min(h, w)
        intensity = float(rng.uniform(*self.intensity))

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dist2 = (xx - cx) ** 2 + (yy - cy) ** 2
        mask = np.exp(-dist2 / (2.0 * r * r))
        mask = (mask * intensity)[..., None]

        out = img.astype(np.float32) + mask * 255.0
        return AugResult(image=_clip_uint8(out))


# ---------- dust / scratches / streaks ----------

class DustAndScratches(Augmentation):
    """Small dark specks (dust) plus thin diagonal scratches."""

    name = "dust_scratches"

    def __init__(
        self,
        dust_density: Tuple[float, float] = (2e-5, 1e-4),
        scratch_count: Tuple[int, int] = (0, 4),
        p: float = 0.5,
    ):
        super().__init__(p=p)
        self.dust_density = dust_density
        self.scratch_count = scratch_count

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img).copy()
        h, w = img.shape[:2]

        # Dust: random dark pixels + tiny blobs.
        density = float(rng.uniform(*self.dust_density))
        n_dust = int(density * h * w)
        if n_dust > 0:
            ys = rng.integers(0, h, size=n_dust)
            xs = rng.integers(0, w, size=n_dust)
            for x, y in zip(xs, ys):
                radius = int(rng.integers(0, 2))
                color = int(rng.integers(0, 60))
                cv2.circle(img, (int(x), int(y)), radius, (color, color, color), -1)

        # Scratches: thin nearly-horizontal/vertical lines.
        n_scratch = int(rng.integers(self.scratch_count[0], self.scratch_count[1] + 1))
        for _ in range(n_scratch):
            x1 = int(rng.integers(0, w))
            y1 = int(rng.integers(0, h))
            length = int(rng.integers(min(w, h) // 20, min(w, h) // 4))
            angle = float(rng.uniform(-10.0, 10.0)) if rng.random() < 0.5 else float(
                rng.uniform(80.0, 100.0)
            )
            theta = np.deg2rad(angle)
            x2 = int(x1 + length * np.cos(theta))
            y2 = int(y1 + length * np.sin(theta))
            shade = int(rng.integers(40, 140))
            cv2.line(img, (x1, y1), (x2, y2), (shade, shade, shade), 1, cv2.LINE_AA)

        return AugResult(image=img)


class ScanlineStreaks(Augmentation):
    """Thin horizontal (or vertical) tone streaks — scanner memory bands."""

    name = "scanline_streaks"

    def __init__(
        self,
        count: Tuple[int, int] = (2, 10),
        opacity: Tuple[float, float] = (0.04, 0.14),
        vertical_prob: float = 0.2,
        p: float = 0.5,
    ):
        super().__init__(p=p)
        self.count = count
        self.opacity = opacity
        self.vertical_prob = float(vertical_prob)

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img).astype(np.float32)
        h, w = img.shape[:2]
        vertical = rng.random() < self.vertical_prob
        n = int(rng.integers(self.count[0], self.count[1] + 1))

        for _ in range(n):
            thickness = int(rng.integers(1, 4))
            opacity = float(rng.uniform(*self.opacity))
            darken = rng.random() < 0.65  # most streaks are slightly darker
            delta = (-1.0 if darken else 1.0) * opacity * 255.0
            if vertical:
                x = int(rng.integers(0, w))
                img[:, max(0, x):min(w, x + thickness), :] += delta
            else:
                y = int(rng.integers(0, h))
                img[max(0, y):min(h, y + thickness), :, :] += delta

        return AugResult(image=_clip_uint8(img))


# ---------- noise / compression / resampling ----------

class GaussianSensorNoise(Augmentation):
    """Additive Gaussian noise with per-channel correlation."""

    name = "gaussian_noise"

    def __init__(self, sigma: Tuple[float, float] = (2.0, 7.0), p: float = 0.7):
        super().__init__(p=p)
        self.sigma = sigma

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img).astype(np.float32)
        sigma = float(rng.uniform(*self.sigma))
        # Grayscale-correlated noise: single channel broadcast across BGR,
        # plus a small uncorrelated component for chromatic grain.
        luma = rng.normal(0.0, sigma, size=img.shape[:2] + (1,)).astype(np.float32)
        chroma = rng.normal(0.0, sigma * 0.35, size=img.shape).astype(np.float32)
        out = img + luma + chroma
        return AugResult(image=_clip_uint8(out))


class JpegArtifacts(Augmentation):
    """Lossy JPEG re-encoding (quality 30..75)."""

    name = "jpeg"

    def __init__(self, quality: Tuple[int, int] = (30, 75), p: float = 0.6):
        super().__init__(p=p)
        self.quality = quality

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img)
        q = int(rng.integers(self.quality[0], self.quality[1] + 1))
        ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if not ok:
            return AugResult(image=img, applied=False)
        dec = cv2.imdecode(enc, cv2.IMREAD_COLOR)
        return AugResult(image=dec)


class MotionBlur(Augmentation):
    """Linear motion blur, simulating a moving scanner bar."""

    name = "motion_blur"

    def __init__(self, ksize: Tuple[int, int] = (3, 7), p: float = 0.25):
        super().__init__(p=p)
        self.ksize = ksize

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        k = int(rng.integers(self.ksize[0], self.ksize[1] + 1))
        if k < 3:
            return AugResult(image=img, applied=False)
        if k % 2 == 0:
            k += 1
        angle = float(rng.uniform(0.0, 180.0))

        kernel = np.zeros((k, k), dtype=np.float32)
        kernel[k // 2, :] = 1.0 / k
        m = cv2.getRotationMatrix2D((k / 2.0, k / 2.0), angle, 1.0)
        kernel = cv2.warpAffine(kernel, m, (k, k))
        kernel /= max(kernel.sum(), 1e-6)

        out = cv2.filter2D(_ensure_bgr(img), -1, kernel)
        return AugResult(image=out)


class LowResResample(Augmentation):
    """Simulate a low-DPI scan: downsample then upsample to original size.

    The output image keeps the input dimensions, so bbox coordinates stay
    valid. Only image sharpness is reduced.
    """

    name = "lowres_resample"

    def __init__(
        self,
        scale_range: Tuple[float, float] = (0.75, 0.95),
        p: float = 0.4,
    ):
        super().__init__(p=p)
        lo, hi = scale_range
        if not (0 < lo <= hi <= 1):
            raise ValueError("scale_range must satisfy 0 < lo <= hi <= 1")
        self.scale_range = (float(lo), float(hi))

    def _apply(self, img: np.ndarray, rng: np.random.Generator) -> AugResult:
        img = _ensure_bgr(img)
        h, w = img.shape[:2]
        s = float(rng.uniform(*self.scale_range))
        down_w = max(1, int(round(w * s)))
        down_h = max(1, int(round(h * s)))
        small = cv2.resize(img, (down_w, down_h), interpolation=cv2.INTER_AREA)
        restored = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
        return AugResult(image=restored)
