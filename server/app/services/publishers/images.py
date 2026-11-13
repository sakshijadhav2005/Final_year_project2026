"""Images for image-first platforms (Instagram).

Instagram only publishes JPEG images with an aspect ratio between 4:5 and 1.91:1, up to
8 MB. :func:`render_card` draws a 1080x1350 (4:5) recap card from the flyer copy;
:func:`normalize_upload` makes a user's own picture fit those rules.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.services.publishers import PublishError

CARD_SIZE = (1080, 1350)
MIN_RATIO, MAX_RATIO = 4 / 5, 1.91
MAX_SIDE = 1440
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_JPEG_BYTES = 8 * 1024 * 1024

BG_TOP, BG_BOTTOM = (24, 16, 38), (58, 22, 52)  # velvet stage palette
ACCENT = (251, 191, 36)  # amber
INK = (245, 240, 250)
INK_DIM = (200, 190, 215)

# Emoji and pictographs: the bundled fonts have no glyphs for them (they'd print as boxes).
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0000fe0f\U0000200d\U00002300-\U000023ff"
    "\U00002b00-\U00002bff\U0001f1e6-\U0001f1ff]"
)


@dataclass
class CardContent:
    headline: str
    subhead: str = ""
    bullets: list[str] = field(default_factory=list)
    footer: str = ""


def _clean(text: str) -> str:
    text = _EMOJI.sub("", text or "")
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf")
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)  # Pillow's bundled scalable font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and " ".join(lines) != text:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def render_card(content: CardContent) -> bytes:
    width, height = CARD_SIZE
    image = Image.new("RGB", CARD_SIZE, BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(height):  # vertical gradient
        t = y / (height - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM, strict=True))
        draw.line([(0, y), (width, y)], fill=color)

    margin = 96
    text_width = width - 2 * margin
    y = 140
    draw.rectangle([margin, y, margin + 120, y + 10], fill=ACCENT)
    y += 60

    headline_font = _font(84, bold=True)
    for line in _wrap(draw, _clean(content.headline) or "Event Recap", headline_font, text_width, 4):
        draw.text((margin, y), line, font=headline_font, fill=INK)
        y += 100
    y += 20

    subhead = _clean(content.subhead)
    if subhead:
        sub_font = _font(42)
        for line in _wrap(draw, subhead, sub_font, text_width, 3):
            draw.text((margin, y), line, font=sub_font, fill=ACCENT)
            y += 56
        y += 40

    bullet_font = _font(38)
    for bullet in [b for b in (_clean(x) for x in content.bullets) if b][:5]:
        lines = _wrap(draw, bullet, bullet_font, text_width - 50, 2)
        if y + 52 * len(lines) > height - 220:
            break
        draw.ellipse([margin, y + 14, margin + 18, y + 32], fill=ACCENT)
        for line in lines:
            draw.text((margin + 50, y), line, font=bullet_font, fill=INK_DIM)
            y += 52
        y += 22

    footer = _clean(content.footer)
    if footer:
        footer_font = _font(34, bold=True)
        draw.line([(margin, height - 190), (width - margin, height - 190)], fill=(110, 90, 125), width=2)
        line = _wrap(draw, footer, footer_font, text_width, 1)[0]
        draw.text((margin, height - 150), line, font=footer_font, fill=INK)

    return _to_jpeg(image)


def _to_jpeg(image: Image.Image) -> bytes:
    for quality in (90, 80, 70, 60):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_JPEG_BYTES:
            return buf.getvalue()
    raise PublishError("The image is too large for Instagram (8 MB).", "image_too_large")


def normalize_upload(data: bytes) -> bytes:
    """Any common image -> RGB JPEG within Instagram's size and aspect-ratio limits.

    Too tall or too wide pictures are padded (not cropped) so nothing is cut off.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise PublishError("Images must be 10 MB or smaller.", "image_too_large")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PublishError("That file is not an image Instagram can use.", "invalid_image") from exc
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))

    w, h = image.size
    ratio = w / h
    if ratio < MIN_RATIO:  # too tall: widen the canvas
        canvas = Image.new("RGB", (round(h * MIN_RATIO), h), BG_TOP)
        canvas.paste(image, ((canvas.width - w) // 2, 0))
        image = canvas
    elif ratio > MAX_RATIO:  # too wide: make the canvas taller
        canvas = Image.new("RGB", (w, round(w / MAX_RATIO)), BG_TOP)
        canvas.paste(image, (0, (canvas.height - h) // 2))
        image = canvas
    return _to_jpeg(image)
