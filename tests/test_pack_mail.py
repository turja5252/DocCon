# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path
from zipfile import ZipFile

from doccon.match import MatchedRow, PdfHit
from doccon.pack_mail import (
    attachment_note,
    cover_pdf_for_book,
    draft_body,
    draft_subject,
    drawing_pdfs,
    mail_attachments,
    normalize_recipients,
    pick_outlook_send_account,
    write_drawings_zip,
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


def test_drawings_zip_excludes_transmittal_form(tmp_path: Path) -> None:
    drawing = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
    drawing.write_bytes(b"%PDF")
    cover = tmp_path / "CT-2026-Tanzim-1.pdf"
    cover.write_bytes(b"%PDF-cover")
    dest = tmp_path / "CT-2026-Tanzim-1.zip"
    assert drawing_pdfs([_row("2026-Tanzim-1-1", drawing)]) == [drawing.resolve()]
    write_drawings_zip(dest, [drawing, cover], exclude=cover)
    with ZipFile(dest) as zipped:
        names = zipped.namelist()
    assert names == ["2026-Tanzim-1-1 REV 0.pdf"]
    assert "CT-2026-Tanzim-1.pdf" not in names
    files = mail_attachments(cover, dest)
    assert [path.name for path in files] == ["CT-2026-Tanzim-1.pdf", "CT-2026-Tanzim-1.zip"]
    assert attachment_note(files).startswith("Attached: CT-2026-Tanzim-1.pdf")
    body = draft_body(cover_id="CT-2026-Tanzim-1", project="Job", rows=[_row("2026-Tanzim-1-1", drawing)])
    assert "zip" in body.casefold()
    assert "transmittal form" in body.casefold()
    assert draft_subject("CT-2026-Tanzim-1", "2026-Tanzim") == "CT-2026-Tanzim-1  2026-Tanzim"
    shop = draft_body(cover_id="ST-2026-Tanzim-1", project="", rows=[_row("EIS-1", drawing)])
    assert "shop transmittal" in shop
    field = draft_body(cover_id="FT-2026-Tanzim-1", project="", rows=[_row("EIS-1", drawing)])
    assert "field transmittal" in field


def test_pick_outlook_send_account_prefers_doc_control() -> None:
    from doccon.pep import DOC_CONTROL_FROM

    assert (
        pick_outlook_send_account(
            ["sarah.chan@eliteintegrityservices.com", DOC_CONTROL_FROM]
        )
        == DOC_CONTROL_FROM
    )
    assert pick_outlook_send_account(["chris.samm@eliteintegrityservices.com"]) == ""
