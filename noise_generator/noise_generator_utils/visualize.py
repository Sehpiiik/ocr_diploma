"""Debug overlay: draw xywh bboxes from an annotation on the noisy image."""
from __future__ import annotations

from typing import Iterable, Sequence

import cv2
import numpy as np


def draw_xywh_bboxes(
    image: np.ndarray,
    bboxes: Iterable[Sequence[float]],
    color: tuple = (0, 0, 255),
    thickness: int = 1,
) -> np.ndarray:
    """Return a copy of ``image`` with each xywh bbox outlined.

    Parameters
    ----------
    image : np.ndarray
        BGR uint8 image.
    bboxes : iterable of [x, y, w, h]
        Axis-aligned bounding boxes.
    """
    out = image.copy()
    for bbox in bboxes:
        x, y, w, h = bbox
        cv2.rectangle(
            out,
            (int(round(x)), int(round(y))),
            (int(round(x + w)), int(round(y + h))),
            color,
            thickness,
            cv2.LINE_AA,
        )
    return out


def draw_annotation_bboxes(
    image: np.ndarray,
    annotation: dict,
    color: tuple = (0, 0, 255),
    thickness: int = 1,
) -> np.ndarray:
    """Draw every ``objects[i].bbox`` from an annotation dict on the image."""
    bboxes = [o["bbox"] for o in annotation.get("objects", []) if "bbox" in o]
    return draw_xywh_bboxes(image, bboxes, color=color, thickness=thickness)
