# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.match import MatchedRow, PdfHit
from doccon.pack_mail import (
    cover_pdf_for_book,
    draft_subject,
    normalize_recipients,
    pack_files,
    write_pack_zip,
)
from doccon.register import DrawingRow


def _row(name: str, pdf: Path | None) -> MatchedRow:
    drawing = DrawingRow(
        key="P2024-1",
        summary=f"{name} Drawing",
        drawing_id=name,
        title="Drawing",
        status="To Do",
        job_number="2026-Tanzim",
        outgoing_rev="0",
        purpose="Info",
        parent_summary="Drawing Package",
    )
    hit = PdfHit(path=pdf, drawing_id=name, rev="0") if pdf else None
    return MatchedRow(drawing=drawing, pdf=hit, confidence="High" if pdf else "Missing")


def test_normalize_recipients() -> None:
    assert normalize_recipients("a@x.com\nb@y.com, c@z.com") == "a@x.com; b@y.com; c@z.com"
    assert (
        normalize_recipients("Elite: Client Contact (PM) ; Blake Rancier; extra@x.com")
        == "extra@x.com"
    )


def test_cover_pdf_prefers_next_then_previous(tmp_path: Path) -> None:
    book = tmp_path / "CT-2026-Tanzim.xlsm"
    book.write_bytes(b"x")
    cover_id, found = cover_pdf_for_book(book, "2026-Tanzim", 3)
    assert cover_id == "CT-2026-Tanzim-3"
    assert found is None
    prev = tmp_path / "CT-2026-Tanzim-2.pdf"
    prev.write_bytes(b"%PDF")
    cover_id, found = cover_pdf_for_book(book, "2026-Tanzim", 3)
    assert cover_id == "CT-2026-Tanzim-2"
    assert found == prev


def test_write_pack_zip(tmp_path: Path) -> None:
    drawing = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
    drawing.write_bytes(b"%PDF")
    cover = tmp_path / "CT-2026-Tanzim-1.pdf"
    cover.write_bytes(b"%PDF-cover")
    files = pack_files([_row("2026-Tanzim-1-1", drawing)], cover)
    dest = write_pack_zip(tmp_path / "CT-2026-Tanzim-1.zip", files)
    assert dest.is_file()
    assert dest.stat().st_size > 0
    assert draft_subject("CT-2026-Tanzim-1", "2026-Tanzim") == "CT-2026-Tanzim-1  2026-Tanzim"
