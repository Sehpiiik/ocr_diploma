"""Load sentences from a local corpus file."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

# Sentence terminators: ., !, ?, plus their multi-char and unicode variants.
_SENT_SPLIT = re.compile(r"(?<=[.!?\u2026])[\"')\]]*\s+(?=[\"'(\[A-ZА-ЯЁ0-9])")


def load_sentences(corpus_path: str | Path) -> List[str]:
    """Read a UTF-8 text file and split it into a flat list of sentences.

    Empty lines act as paragraph separators but are otherwise ignored.
    """
    text = Path(corpus_path).read_text(encoding="utf-8")
    # Normalize whitespace inside paragraphs.
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in text.split("\n\n")]
    sentences: List[str] = []
    for para in paragraphs:
        if not para:
            continue
        parts = _SENT_SPLIT.split(para)
        sentences.extend(s.strip() for s in parts if s.strip())
    return sentences
