# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Read words inside a preview box. Native PDF text first; OCR the pixels when that is empty."""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import pymupdf

from doccon.paths import install_dir

MAX_GRAB_CHARS = 240
OCR_DPI = 220
OCR_MAX_EDGE = 2000


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


def append_grabbed_text(existing: str, addition: str) -> str:
    """Join a later box onto the ID or Description already grabbed, with a space.

    The same words boxed again are left as they are.
    """
    current = clean_grabbed_text(existing)
    extra = clean_grabbed_text(addition)
    if not extra:
        return current
    if not current:
        return extra
    current_fold = f" {current.casefold()} "
    extra_fold = extra.casefold()
    if f" {extra_fold} " in current_fold:
        return current
    return clean_grabbed_text(f"{current} {extra}")


append_grabbed_id = append_grabbed_text


def grab_has_token(text: str) -> bool:
    """True when OCR or a text layer returned at least one letter or digit."""
    return any(char.isalnum() for char in clean_grabbed_text(text))


def grab_target_accepts(text: str, target: str) -> bool:
    """Description needs a title. An ID can be a drawing number with no letters."""
    if (target or "").strip().lower() == "id":
        return grab_has_token(text)
    return grabbed_text_is_usable(text)


def tessdata_dir() -> Path | None:
    """Folder with eng.traineddata. Frozen exe, the suite folder, or beside this file."""
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        roots.append(Path(meipass))
    roots.append(install_dir())
    roots.append(Path(__file__).resolve().parents[2])
    seen: set[str] = set()
    for root in roots:
        candidate = (root / "vendor" / "tesseract" / "tessdata").resolve()
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if (candidate / "eng.traineddata").is_file():
            return candidate
    return None


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


def canvas_box_to_pix_irect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    center: tuple[float, float],
    pix_size: tuple[int, int],
    pad: int = 4,
) -> tuple[int, int, int, int] | None:
    """Map a preview drag box onto the displayed pixmap."""
    if min(abs(x1 - x0), abs(y1 - y0)) < 8 or pix_size[0] < 2 or pix_size[1] < 2:
        return None
    left = center[0] - pix_size[0] / 2.0
    top = center[1] - pix_size[1] / 2.0
    ix0 = max(0, min(int(min(x0, x1) - left) - pad, pix_size[0] - 1))
    iy0 = max(0, min(int(min(y0, y1) - top) - pad, pix_size[1] - 1))
    ix1 = max(ix0 + 1, min(int(max(x0, x1) - left) + pad, pix_size[0]))
    iy1 = max(iy0 + 1, min(int(max(y0, y1) - top) + pad, pix_size[1]))
    if min(ix1 - ix0, iy1 - iy0) < 8:
        return None
    return (ix0, iy0, ix1, iy1)


def _ocr_matrix(width: float, height: float, dpi: float = OCR_DPI) -> pymupdf.Matrix:
    scale = float(dpi) / 72.0
    edge = max(width, height, 1.0) * scale
    if edge > OCR_MAX_EDGE:
        scale *= OCR_MAX_EDGE / edge
    return pymupdf.Matrix(scale, scale)


def _text_from_ocr_pixmap(pix: pymupdf.Pixmap, tessdata: Path) -> str:
    if pix.width < 8 or pix.height < 8:
        return ""
    os.environ["TESSDATA_PREFIX"] = str(tessdata)
    try:
        payload = pix.pdfocr_tobytes(compress=True, language="eng", tessdata=str(tessdata))
    except Exception:
        return ""
    doc = pymupdf.open(stream=payload, filetype="pdf")
    try:
        if doc.page_count < 1:
            return ""
        return clean_grabbed_text(words_to_text(doc[0].get_text("words") or []))
    finally:
        doc.close()


def ocr_page_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> str:
    """OCR the boxed pixels with the bundled Tesseract. Empty when it is missing."""
    tessdata = tessdata_dir()
    if tessdata is None:
        return ""
    area = page.rect & clip
    area.x0 = max(page.rect.x0, area.x0 - 4)
    area.y0 = max(page.rect.y0, area.y0 - 4)
    area.x1 = min(page.rect.x1, area.x1 + 4)
    area.y1 = min(page.rect.y1, area.y1 + 4)
    if area.is_empty or area.width < 2 or area.height < 2:
        return ""
    pix = page.get_pixmap(matrix=_ocr_matrix(area.width, area.height), clip=area, alpha=False)
    return _text_from_ocr_pixmap(pix, tessdata)


def ocr_pixmap_box(pix: pymupdf.Pixmap, box: tuple[int, int, int, int]) -> str:
    """OCR the pixels the operator boxed on screen."""
    x0, y0, x1, y1 = (int(value) for value in box)
    if min(x1 - x0, y1 - y0) < 8 or pix.width < 8 or pix.height < 8:
        return ""
    holder = pymupdf.open()
    try:
        page = holder.new_page(width=float(pix.width), height=float(pix.height))
        page.insert_image(page.rect, pixmap=pix)
        return ocr_page_clip(page, pymupdf.Rect(x0, y0, x1, y1))
    finally:
        holder.close()


def text_from_page_clip(page: pymupdf.Page, clip: pymupdf.Rect) -> str:
    """Read the words inside a preview box. OCR the clip when the PDF has no real text."""
    area = page.rect & clip
    if area.is_empty or area.width < 2 or area.height < 2:
        return ""
    picked = clean_grabbed_text(words_to_text(page.get_text("words", clip=area) or []))
    if grabbed_text_is_usable(picked):
        return picked
    ocrd = ocr_page_clip(page, area)
    if grab_has_token(ocrd):
        return ocrd
    return picked
