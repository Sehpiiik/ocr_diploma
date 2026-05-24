"""Render synthetic documents with per-sentence, per-line bbox annotations."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _resolve_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = [font_path] if font_path else _FONT_CANDIDATES
    for c in candidates:
        if c and Path(c).exists():
            return ImageFont.truetype(c, size=size)
    raise FileNotFoundError(
        "No TrueType font found. Pass --font /path/to/font.ttf "
        f"(searched: {candidates})"
    )

@dataclass
class PageConfig:
    width: int = 2480            # ~A4 @ 300 DPI
    height: int = 3508
    margin: int = 100
    font_size: int = 50
    line_spacing: float = 1.35
    font_path: str | None = None
    background: Tuple[int, int, int] = (255, 255, 255)
    text_color: Tuple[int, int, int] = (20, 20, 20)
    paragraph_spacing: float = 0.6   # extra blank-line fraction between paragraphs
    sentences_per_paragraph: Tuple[int, int] = (2, 5)


@dataclass
class LineAnno:
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h (axis-aligned, pixels)
    type: str = "line"



@dataclass
class PageAnnotation:
    image: str
    width: int
    height: int
    font: str
    font_size: int
    line_spacing: float
    margin: int
    bbox_format: str = "xywh"
    objects: List[LineAnno] = field(default_factory=list)
 
    def to_dict(self) -> dict:
        return {
            "image": self.image,
            "width": self.width,
            "height": self.height,
            "font": self.font,
            "font_size": self.font_size,
            "line_spacing": self.line_spacing,
            "margin": self.margin,
            "bbox_format": self.bbox_format,
            "objects": [asdict(obj) for obj in self.objects],
         }


@dataclass
class _PlacedWord:
    text: str
    x: int
    y: int
    w: int
    h: int
    sentence_idx: int
    line_idx: int


class DocumentGenerator:
    def __init__(self, config: PageConfig | None = None, rng: random.Random | None = None):
        self.cfg = config or PageConfig()
        self.rng = rng or random.Random()
        self.font = _resolve_font(self.cfg.font_path, self.cfg.font_size)
        # ascent + descent is the total height of the symbol
        ascent, descent = self.font.getmetrics()
        self.text_height = ascent + descent
        # line advance is the vertical step between lines, which may be larger than text height due to line spacing > 1
        self.line_advance = int(round(self.text_height * self.cfg.line_spacing))

    def _word_width(self, word: str) -> int:
        return int(round(self.font.getlength(word)))

    def _space_width(self) -> int:
        return int(round(self.font.getlength(" ")))
    
    def _get_count_of_existing(self, out_dir: Path) -> int:
        """Find the next available index based on existing files."""
        images_dir = out_dir / "images"
        # Just count existing files 
        existing = list(images_dir.glob("synth_doc_*.png"))
        return len(existing)

    def _layout(self, sentences: Sequence[str]) -> Tuple[List[_PlacedWord], List[str]]:
        """Place as many sentences as fit on the page.

        Returns (placed_words, used_sentence_texts).
        """
        cfg = self.cfg
        x_left = cfg.margin
        x_right = cfg.width - cfg.margin
        y_bottom = cfg.height - cfg.margin
        max_line_w = x_right - x_left

        space_w = self._space_width()
        placed: List[_PlacedWord] = []
        used_sentences: List[str] = []

        cur_x = x_left
        cur_y = cfg.margin
        cur_line_idx = 0
        line_has_content = False

        sent_min, sent_max = cfg.sentences_per_paragraph
        para_break_after: set[int] = set()
        i = 0
        while i < len(sentences):
            step = self.rng.randint(sent_min, sent_max)
            j = min(i + step, len(sentences)) - 1
            para_break_after.add(j)
            i = j + 1

        for s_idx, sentence in enumerate(sentences):
            words = sentence.split()
            if not words:
                continue
            if cur_y + self.text_height > y_bottom:
                break

            sentence_placed_any = False
            for w_pos, word in enumerate(words):
                w_width = self._word_width(word)
                needs_space = line_has_content
                advance = (space_w if needs_space else 0) + w_width

                if cur_x + advance > x_right and line_has_content:
                    # wrap
                    cur_x = x_left
                    cur_y += self.line_advance
                    cur_line_idx += 1
                    line_has_content = False
                    needs_space = False
                    advance = w_width
                    if cur_y + self.text_height > y_bottom:
                        break  # out of vertical space

                if needs_space:
                    cur_x += space_w

                # Bbox h = glyph height (tight); line_advance is only used for y stepping.
                placed.append(
                    _PlacedWord(
                        text=word,
                        x=cur_x,
                        y=cur_y,
                        w=w_width,
                        h=self.text_height,
                        sentence_idx=s_idx,
                        line_idx=cur_line_idx,
                    )
                )
                cur_x += w_width
                line_has_content = True
                sentence_placed_any = True

            else:
                if sentence_placed_any:
                    used_sentences.append(sentence)
                if s_idx in para_break_after:
                    cur_x = x_left
                    cur_y += int(self.line_advance * (1 + cfg.paragraph_spacing))
                    cur_line_idx += 1
                    line_has_content = False
                continue

            if sentence_placed_any:
                used_sentences.append(sentence)
            break

        return placed, used_sentences

    @staticmethod
    def _line_bbox(words: List[_PlacedWord]) -> Tuple[int, int, int, int]:
        x0 = min(w.x for w in words)
        y0 = min(w.y for w in words)
        x1 = max(w.x + w.w for w in words)
        y1 = max(w.y + w.h for w in words)
        return (x0, y0, x1 - x0, y1 - y0)

    def _build_annotations(self, placed: List[_PlacedWord], image_name: str) -> PageAnnotation:
        cfg = self.cfg
        ann = PageAnnotation(image=image_name, width=cfg.width, height=cfg.height, font=self.font.font.family, font_size=cfg.font_size, line_spacing=cfg.line_spacing, margin=cfg.margin)

        lines_dict: dict[int, List[_PlacedWord]] = {}
        for w in placed:
            lines_dict.setdefault(w.line_idx, []).append(w)

        for line_idx in sorted(lines_dict.keys()):
            line_words = lines_dict[line_idx]
            bbox = self._line_bbox(line_words)
            text = " ".join(w.text for w in line_words)
        
            ann.objects.append(LineAnno(
                type="line",
                bbox=bbox,
                text=text
            ))

        return ann

    def render(self, sentences: Sequence[str], image_name: str = "doc.png",
               draw_debug_boxes: bool = False) -> Tuple[Image.Image, PageAnnotation]:
        cfg = self.cfg
        img = Image.new("RGB", (cfg.width, cfg.height), cfg.background)
        draw = ImageDraw.Draw(img)

        placed, _ = self._layout(sentences)
        for w in placed:
            draw.text((w.x, w.y), w.text, font=self.font, fill=cfg.text_color)

        ann = self._build_annotations(placed, image_name)

        if draw_debug_boxes:
            for obj in ann.objects:
                x, y, w, h = obj.bbox
                draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0), width=1)

        return img, ann

    def generate(self, sentence_pool: Sequence[str], count: int, out_dir: str | Path,
                 sentences_per_doc: Tuple[int, int] = (20, 60),
                 draw_debug_boxes: bool = False) -> List[Path]:
        """Generate `count` documents into `out_dir`.

        Each document samples a contiguous random slice from the pool (or shuffles
        if the pool is small) until the page fills.

        Returns the list of annotation JSON paths written.
        """
        out = Path(out_dir)
        (out / "images").mkdir(parents=True, exist_ok=True)
        (out / "annotations").mkdir(parents=True, exist_ok=True)

        ann_paths: List[Path] = []
        n_pool = len(sentence_pool)
        if n_pool == 0:
            raise ValueError("sentence_pool is empty")

        low, high = sentences_per_doc
        count_of_existing = self._get_count_of_existing(out)
        for i in range(count):
            k = self.rng.randint(low, high)
            if n_pool <= k:
                # Use whole pool, shuffled.
                doc_sents = list(sentence_pool)
                self.rng.shuffle(doc_sents)
            else:
                start = self.rng.randrange(0, n_pool - k)
                doc_sents = list(sentence_pool[start:start + k])

            name = f"synth_doc_{i + count_of_existing + 1:05d}"
            img_name = f"{name}.png"
            img, ann = self.render(doc_sents, image_name=img_name,
                                   draw_debug_boxes=draw_debug_boxes)
            img.save(out / "images" / img_name)
            ann_path = out / "annotations" / f"{name}.json"
            ann_path.write_text(json.dumps(ann.to_dict(), ensure_ascii=False, indent=2),
                                encoding="utf-8")
            ann_paths.append(ann_path)
        return ann_paths
