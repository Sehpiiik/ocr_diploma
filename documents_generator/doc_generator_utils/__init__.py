"""Synthetic document generator."""
from .generator import DocumentGenerator, PageConfig
from .text_source import load_sentences

__all__ = ["DocumentGenerator", "PageConfig", "load_sentences"]
