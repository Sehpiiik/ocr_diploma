"""noise_generator: realistic photometric document noise with xywh bboxes."""
from .io_utils import (
    InputPair,
    build_output_annotation,
    build_renamed_annotation,
    ensure_output_dirs,
    find_pairs,
    read_image_bgr,
    should_augment,
    write_annotation,
    write_image,
)
from .pipeline import NoisePipeline, NoisyDocument, make_rngs
from .visualize import draw_annotation_bboxes, draw_xywh_bboxes

__all__ = [
    "InputPair",
    "NoisePipeline",
    "NoisyDocument",
    "make_rngs",
    "find_pairs",
    "read_image_bgr",
    "write_image",
    "write_annotation",
    "build_output_annotation",
    "build_renamed_annotation",
    "should_augment",
    "ensure_output_dirs",
    "draw_annotation_bboxes",
    "draw_xywh_bboxes",
]
