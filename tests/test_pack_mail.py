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
    load_mail_formats,
    mail_attachments,
    mail_facts,
    normalize_recipients,
    pick_outlook_send_account,
    save_mail_formats,
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
    assert "Good Day," in body
    assert "doc.control@eliteintegrityservices.com" in body
    assert "Rows 1.1" not in body
    assert "Kind Regards," in body


def test_itp_signoff_note_is_only_on_a_client_pack_that_includes_an_itp(tmp_path: Path) -> None:
    drawing = tmp_path / "2026-011-ITP-1-1 REV 0.pdf"
    plain = draft_body(
        cover_id="CT-2026-011-1",
        project="",
        rows=[_row("2026-011-1-1", drawing)],
    )
    assert "Rows 1.1" not in plain
    included = draft_body(
        cover_id="CT-2026-011-1",
        project="",
        rows=[_row("2026-011-1-1", drawing), _row("2026-011-ITP-1-1", drawing)],
    )
    assert "Rows 1.1, 1.2, 1.3, 1.4 under client column on ITP" in included
    shop = draft_body(
        cover_id="ST-2026-011-1",
        project="",
        rows=[_row("2026-011-ITP-1-1", drawing)],
    )
    assert "Rows 1.1" not in shop
    assert draft_subject("CT-2026-Tanzim-1", "2026-Tanzim") == (
        "Trans. # CT-2026-Tanzim-1 | ISSUED FOR N/A | N/A | "
        "Loc: N/A | Ref. Tag: N/A | PO#: N/A | WO#: N/A | MOC#: N/A"
    )
    assert draft_subject("CT-2026-Tanzim-1", "2026-Tanzim", facts=mail_facts(urgent="same")).startswith(
        "URGENT Trans. #"
    )
    shop = draft_body(cover_id="ST-2026-Tanzim-1", project="", rows=[_row("EIS-1", drawing)])
    assert "1.0 Current IFC Drawings folder" in shop
    assert draft_subject("ST-2026-Tanzim-1", "2026-Tanzim") == (
        "Trans. # ST-2026-Tanzim-1 | N/A | N/A | Loc: N/A | Ref. Tag: N/A"
    )
    field = draft_body(cover_id="FT-2026-Tanzim-1", project="", rows=[_row("EIS-1", drawing)])
    assert "Field Construction folder" in field
    assert draft_subject("FT-2026-Tanzim-1", "2026-Tanzim") == (
        "Trans. # FT-2026-Tanzim-1 | N/A | N/A | Loc: N/A | Ref. Tag: N/A"
    )


def test_custom_wording_replaces_markers(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "mail-formats.json"
    monkeypatch.setattr("doccon.paths.mail_formats_path", lambda: dest)
    save_mail_formats(
        {
            "client": ("{job} {cover}", "Hello {project}\n{documents}\n"),
            "shop": ("", ""),
        }
    )
    loaded = load_mail_formats()
    assert loaded["client"] == ("{job} {cover}", "Hello {project}\n{documents}\n")
    assert "shop" not in loaded
    from doccon.pack_mail import load_cc_permanent, save_cc_permanent

    save_cc_permanent("perm@eliteintegrityservices.com")
    assert load_cc_permanent() == ("perm@eliteintegrityservices.com",)
    from doccon.pack_mail import permanent_line, save_permanent

    save_permanent(
        {
            "client": {"to": "client-to@eliteintegrityservices.com", "cc": "client-cc@eliteintegrityservices.com"},
            "shop": {"to": "shop-to@eliteintegrityservices.com", "cc": "shop-cc@eliteintegrityservices.com"},
            "field": {"to": "field-to@eliteintegrityservices.com", "cc": ""},
        }
    )
    assert permanent_line("client", "to") == "client-to@eliteintegrityservices.com"
    assert permanent_line("shop", "cc") == "shop-cc@eliteintegrityservices.com"
    assert permanent_line("field", "cc") == ""
    assert load_mail_formats()["client"][0] == "{job} {cover}"
    drawing = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
    body = draft_body(
        cover_id="CT-2026-Tanzim-1",
        project="Tank 9",
        rows=[_row("2026-Tanzim-1-1", drawing)],
        job="2026-Tanzim",
        template=loaded["client"][1],
    )
    assert "Hello Tank 9" in body
    assert "2026-Tanzim-1-1" in body
    assert draft_subject("CT-2026-Tanzim-1", "2026-Tanzim", template=loaded["client"][0]) == (
        "2026-Tanzim CT-2026-Tanzim-1"
    )


def test_mail_tokens_fill_urgent_issued_for_and_pep_fields() -> None:
    from doccon.pack_mail import issued_for_text, mail_facts, split_wo_moc
    from doccon.register import DrawingRow

    assert split_wo_moc("WO-14 / MOC-9") == ("WO-14", "MOC-9")
    assert split_wo_moc("WO-14") == ("WO-14", "")
    drawing = DrawingRow(
        key="P2024-1",
        summary="2026-011-1-1 Gate",
        drawing_id="2026-011-1-1",
        title="Gate",
        status="OFA",
        job_number="2026-011",
        outgoing_rev="0",
        purpose="Approval",
        parent_summary="",
    )
    row = MatchedRow(drawing=drawing, pdf=None, confidence="Missing")
    facts = mail_facts(
        urgent="same",
        issued_for=issued_for_text([row], "client"),
        client="Gibson",
        location="Hardisty",
        tag="TK12",
        po="4500123",
        wo_moc="WO-14 / MOC-9",
    )
    subject = draft_subject(
        "CT-2026-011-3",
        "2026-011",
        template="{urgent} {transmittal} {client} {location} {tag} {po} {wo} {moc} {issued_for}",
        facts=facts,
    )
    assert subject == "URGENT CT-2026-011-3 Gibson Hardisty TK12 4500123 WO-14 MOC-9 Approval"
    quiet = draft_subject(
        "CT-2026-011-3",
        "2026-011",
        template="{urgent} {transmittal}",
        facts=mail_facts(),
    )
    assert quiet == "CT-2026-011-3"


def test_missing_job_field_is_na_until_a_real_value_is_saved() -> None:
    from doccon.pack_mail import value_or_na

    assert value_or_na("", "") == "N/A"
    assert value_or_na("N/A", "") == "N/A"
    assert value_or_na("N/A", "Gibson") == "Gibson"
    assert value_or_na("Gibson", "Other") == "Gibson"


def test_pick_outlook_send_account_prefers_doc_control() -> None:
    from doccon.pep import DOC_CONTROL_FROM

    assert (
        pick_outlook_send_account(
            ["sarah.chan@eliteintegrityservices.com", DOC_CONTROL_FROM]
        )
        == DOC_CONTROL_FROM
    )
    assert pick_outlook_send_account(["chris.samm@eliteintegrityservices.com"]) == ""


def test_pick_list_includes_the_saved_address_book(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("doccon.paths.mail_formats_path", lambda: tmp_path / "mail-formats.json")
    from doccon.pack_mail import pick_address_lists, save_permanent, save_saved_addresses

    save_permanent({"shop": {"to": "shop-to@eliteintegrityservices.com", "cc": ""}})
    save_saved_addresses(("book@eliteintegrityservices.com", "shop-to@eliteintegrityservices.com"))
    standing, saved = pick_address_lists("shop", "to")
    assert standing == ("shop-to@eliteintegrityservices.com",)
    assert saved == ("book@eliteintegrityservices.com",)
