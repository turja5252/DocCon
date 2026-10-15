# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from doccon.pdf_grab import (
    canvas_box_to_page_rect,
    clean_grabbed_text,
    append_grabbed_id,
    grab_target_accepts,
    grabbed_text_is_usable,
    tessdata_dir,
    text_from_page_clip,
    words_to_text,
)


def test_clean_grabbed_text_collapses_whitespace() -> None:
    assert clean_grabbed_text("FLOOR\nREPAIR   DETAIL") == "FLOOR REPAIR DETAIL"
    assert grabbed_text_is_usable("FLOOR REPAIR DETAIL")
    assert grabbed_text_is_usable("IFC")
    assert not grabbed_text_is_usable("1")
    assert not grabbed_text_is_usable("")


def test_words_to_text_reads_left_to_right_top_to_bottom() -> None:
    words = [
        (200, 40, 260, 52, "DETAIL"),
        (80, 40, 140, 52, "FLOOR"),
        (150, 40, 190, 52, "REPAIR"),
        (80, 60, 140, 72, "CNRL"),
    ]
    assert words_to_text(words) == "FLOOR REPAIR DETAIL CNRL"


def test_text_from_page_clip_reads_boxed_title() -> None:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 120), "FLOOR REPAIR DETAIL", fontsize=16)
        page.insert_text((72, 400), "Unrelated footer", fontsize=10)
        grabbed = text_from_page_clip(page, pymupdf.Rect(60, 90, 360, 150))
        assert grabbed == "FLOOR REPAIR DETAIL"
    finally:
        doc.close()


def test_append_grabbed_id_joins_a_later_box() -> None:
    assert append_grabbed_id("2026-118-1-1", "TJ") == "2026-118-1-1 TJ"
    assert append_grabbed_id("2026-118-1-1 TJ", "TJ") == "2026-118-1-1 TJ"
    assert append_grabbed_id("", "2026-118-1-1") == "2026-118-1-1"
    assert append_grabbed_id("2026-118-1-1", "") == "2026-118-1-1"


def test_text_from_page_clip_ocrs_an_image_with_no_text_layer() -> None:
    if tessdata_dir() is None:
        pytest.skip("eng.traineddata is not in vendor/tesseract/tessdata")
    src = pymupdf.open()
    try:
        page = src.new_page(width=612, height=792)
        page.insert_text((72, 140), "FLOOR REPAIR DETAIL", fontsize=28)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    finally:
        src.close()
    doc = pymupdf.open()
    try:
        image_page = doc.new_page(width=612, height=792)
        image_page.insert_image(image_page.rect, pixmap=pix)
        assert not image_page.get_text("text").strip()
        grabbed = text_from_page_clip(image_page, pymupdf.Rect(40, 70, 520, 200))
        assert "FLOOR" in grabbed
        assert "REPAIR" in grabbed
        assert grab_target_accepts(grabbed, "description")
        assert grab_target_accepts("2026-118-1-1", "id")
        assert not grab_target_accepts("2026-118-1-1", "description")
    finally:
        doc.close()


def test_canvas_box_to_page_rect_maps_fit_image() -> None:
    box = canvas_box_to_page_rect(
        100,
        80,
        300,
        140,
        center=(306.0, 396.0),
        pix_size=(612, 792),
        zoom=1.0,
        page_size=(612.0, 792.0),
    )
    assert box is not None
    x0, y0, x1, y1 = box
    assert x0 < x1
    assert y0 < y1
    assert canvas_box_to_page_rect(
        10,
        10,
        12,
        12,
        center=(306.0, 396.0),
        pix_size=(612, 792),
        zoom=1.0,
        page_size=(612.0, 792.0),
    ) is None


def test_text_from_page_clip_writes_a_real_pdf(tmp_path: Path) -> None:
    path = tmp_path / "title.pdf"
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 120), "FLOOR REPAIR DETAIL", fontsize=16)
        doc.save(path)
    finally:
        doc.close()
    handle = pymupdf.open(path)
    try:
        grabbed = text_from_page_clip(handle[0], pymupdf.Rect(60, 90, 360, 150))
        assert grabbed == "FLOOR REPAIR DETAIL"
    finally:
        handle.close()
