# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Read words inside a preview box. Native PDF text first; OCR only if the clip is empty."""
from __future__ import annotations

import re
from collections.abc import Iterable

import pymupdf

MAX_GRAB_CHARS = 240


def clean_grabbed_text(text: str) -> str:
    """One Description line: collapse whitespace, keep the drawing's own capitals."""
    cleaned = re.sub(r"\s+", " ", (text or "").replace("\n", " ").replace("\r", " ")).strip()
    if len(cleaned) > MAX_GRAB_CHARS:
        return cleaned[:MAX_GRAB_CHARS].rstrip()
    return cleaned


def grabbed_text_is_usable(text: str) -> bool:
    """True when the box looks like a title, not a stray dimension or scan speck."""
    cleaned = clean_grabbed_text(text)
    return sum(1 for char in cleaned if char.isalpha()) >= 2


def words_to_text(words: Iterable[object]) -> str:
    """Join pymupdf ``get_text('words')`` rows left-to-right, top-to-bottom."""
    rows: dict[int, list[tuple[float, str]]] = {}
    for word in words:
        if not isinstance(word, (list, tuple)) or len(word) < 5:
            continue
        token = str(word[4]).strip()
        if not token:
            continue
        y_mid = (float(word[1]) + float(word[3])) / 2.0
        key = int(round(y_mid / 6.0))
        rows.setdefault(key, []).append((float(word[0]), token))
    lines: list[str] = []
    for key in sorted(rows):
        line = " ".join(token for _x, token in sorted(rows[key], key=lambda item: item[0]))
        if line:
            lines.append(line)
    return " ".join(lines)


def canvas_box_to_page_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    center: tuple[float, float],
    pix_size: tuple[int, int],
    zoom: float,
    page_size: tuple[float, float],
    rotation: int = 0,
) -> tuple[float, float, float, float] | None:
    """Map a preview drag box back onto the page. Returns ``(x0, y0, x1, y1)`` or None."""
    if min(abs(x1 - x0), abs(y1 - y0)) < 8:
        return None
    matrix = pymupdf.Matrix(float(zoom), float(zoom)).prerotate(int(rotation) % 360)
    cx, cy = center
    pix_w, pix_h = pix_size
    left = cx - pix_w / 2.0
    top = cy - pix_h / 2.0
    inv = ~matrix
    xs = (min(x0, x1) - left, max(x0, x1) - left)
    ys = (min(y0, y1) - top, max(y0, y1) - top)
    pts = [pymupdf.Point(x, y) * inv for x in xs for y in ys]
    clip = pymupdf.Rect(pts[0], pts[0])
    for point in pts[1:]:
        clip.include_point(point)
    page = pymupdf.Rect(0, 0, max(page_size[0], 1), max(page_size[1], 1))
    clip = clip & page
    if clip.is_empty or clip.width < 2 or clip.height < 2:
        return None
    return (float(clip.x0), float(clip.y0), float(clip.x1), float(clip.y1))


def ocr_page_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> str:
    """OCR the clip when Tesseract is on this PC. Empty string if it is not."""
    area = page.rect & clip
    if area.is_empty or area.width < 2 or area.height < 2:
        return ""
    try:
        textpage = page.get_textpage_ocr(language="eng", dpi=200, full=False)
    except Exception:
        return ""
    try:
        raw = page.get_text("words", clip=area, textpage=textpage) or []
    except TypeError:
        return ""
    return clean_grabbed_text(words_to_text(raw))


def text_from_page_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> str:
    """Read the words inside a preview box. OCR the clip when the PDF has no real text."""
    area = page.rect & clip
    if area.is_empty or area.width < 2 or area.height < 2:
        return ""
    picked = clean_grabbed_text(words_to_text(page.get_text("words", clip=area) or []))
    if grabbed_text_is_usable(picked):
        return picked
    ocrd = ocr_page_clip(page, area)
    if grabbed_text_is_usable(ocrd):
        return ocrd
    return picked
