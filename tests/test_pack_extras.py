# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

import pytest

from doccon.client_log import lines_from_extras
from doccon.kinds import CLIENT, FIELD, SHOP
from doccon.match import MatchedRow, PdfHit
from doccon.pack_mail import attach_pdfs
from doccon.pack_state import (
    ClientPack,
    PackExtra,
    blank_extra,
    document_no_for_file,
    extra_from_path,
    letter_status,
    load_client_pack,
    packed_issue_date,
    save_client_pack,
)
from doccon.register import DrawingRow


def test_extra_from_filename_rev_and_client_status(tmp_path: Path) -> None:
    path = tmp_path / "scan0042 REV 2.pdf"
    path.write_bytes(b"%PDF")
    item = extra_from_path(path, kind=CLIENT)
    assert item.document_no == "scan0042"
    assert item.rev == "2"
    assert item.description == ""
    assert item.status == "INFORMATION"
    assert item.email_dropped is False


def test_letter_status_falls_back_when_kind_changes() -> None:
    assert letter_status(SHOP, "APPROVAL") == "IFC"
    assert letter_status(FIELD, "INFORMATION") == "IFC"
    assert letter_status(SHOP, "PURCHASING ONLY") == "PURCHASING ONLY"


def test_lines_follow_packed_drawings() -> None:
    item = PackExtra(
        path="notes.pdf",
        document_no="Site photo",
        rev="",
        description="North side",
        status="INFORMATION",
        fields={"purpose": "Info"},
    )
    lines = lines_from_extras([item], CLIENT)
    assert lines[0].document_no == "Site photo"
    assert lines[0].description == "North side"
    assert lines[0].status == "INFORMATION"
    blank = lines_from_extras(
        [PackExtra(path="notes.pdf", document_no="Site photo", status="INFORMATION")],
        CLIENT,
    )
    assert blank[0].status == ""
    na = lines_from_extras(
        [PackExtra(path="notes.pdf", document_no="Site photo", fields={"purpose": "NA"})],
        CLIENT,
    )
    assert na[0].status == "N/A"
    assert lines[0].notes == ""
    noted = lines_from_extras(
        [PackExtra(path="notes.pdf", document_no="Site photo", notes="See markup")],
        CLIENT,
    )
    assert noted[0].notes == "See markup"
    shop = lines_from_extras(
        [
            PackExtra(
                path="calc.xlsx",
                document_no="TC-2026-070-1",
                rev="0",
                description="Tank Calculation Package",
                status="INFORMATION",
                fields={"shop_purpose": "IFC", "shop_ifc_date": "2026-10-15"},
            )
        ],
        SHOP,
    )
    assert shop[0].status == "IFC"
    assert shop[0].rev == "0"


def test_non_jira_issue_date_is_used_when_the_rows_agree() -> None:
    dated = PackExtra(
        path="calc.xlsx",
        document_no="TC-2026-070-1",
        fields={"shop_ifc_date": "2026-10-15"},
    )
    assert packed_issue_date([dated], "shop_ifc_date") == "2026-10-15"
    other = PackExtra(
        path="other.pdf",
        document_no="Other",
        fields={"shop_ifc_date": "2026-10-16"},
    )
    assert packed_issue_date([dated, other], "shop_ifc_date") == ""


def test_pack_extras_round_trip(tmp_path: Path) -> None:
    dropped = tmp_path / "3.0 Doc Con" / "DocCon" / "dropped" / "mail.pdf"
    item = PackExtra(
        path=str(dropped),
        document_no="mail",
        rev="0",
        description="From Sarah",
        status="INFORMATION",
        notes="See markup",
        note_color="Red",
        email_dropped=True,
        id="x:mail",
        fields={"shop_ifc_date": "2026-10-15", "shop_purpose": "IFC"},
    )
    save_client_pack(tmp_path, ClientPack(job_number="2026-Tanzim", pack_extras=(item,)))
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.pack_extras == (item,)


def test_attach_pdfs_adds_extra_after_drawings(tmp_path: Path) -> None:
    drawing = tmp_path / "drawing.pdf"
    extra = tmp_path / "loose.pdf"
    drawing.write_bytes(b"a")
    extra.write_bytes(b"b")
    row = MatchedRow(
        drawing=DrawingRow(
            key="P2024-1",
            summary="2026-Tanzim-1-1",
            drawing_id="2026-Tanzim-1-1",
            title="",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="0",
            purpose="Info",
            parent_summary="",
        ),
        pdf=PdfHit(path=drawing, drawing_id="2026-Tanzim-1-1", rev="0"),
        confidence="High",
    )
    files = attach_pdfs([row], [extra])
    assert [path.name for path in files] == ["drawing.pdf", "loose.pdf"]


def test_non_jira_row_is_its_own_group() -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.drawing_board import NON_JIRA_GROUP, DrawingBoard
        from doccon.log_layout import CLIENT_LAYOUT

        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([])
        item = extra_from_path(Path("notes REV 1.pdf"), kind="client")
        board.set_pack_extras([item], statuses=CLIENT_LAYOUT.statuses)
        painted = board.pack_extras()
        assert len(painted) == 1
        assert painted[0].document_no == "notes"
        assert painted[0].rev == "1"
        assert painted[0].status == "INFORMATION"
        assert painted[0].packed is True
        assert board._blocks[painted[0].id].group == NON_JIRA_GROUP
        doc_no = board._blocks[painted[0].id].nexts["client_document_number"]
        shop_date = board._blocks[painted[0].id].nexts["shop_ifc_date"]
        assert str(doc_no.cget("state")) != "disabled"
        assert str(shop_date.cget("state")) != "disabled"
        shop_date.set("2026-10-15")
        assert board.pack_extras()[0].fields["shop_ifc_date"] == "2026-10-15"
        assert board.pending_rows() == []
        board.focus_key(painted[0].id)
        assert board.explicit_focus_key() == painted[0].id
    finally:
        root.destroy()


def test_new_document_takes_the_pdf_name() -> None:
    assert document_no_for_file("New document", Path("scan0042.pdf")) == "scan0042"
    assert document_no_for_file("New document", Path("2026-Tanzim-1-9 REV 2.pdf")) == "2026-Tanzim-1-9"
    assert document_no_for_file("Cover letter", Path("scan0042.pdf")) == "Cover letter"


def test_blank_non_jira_row_has_no_pdf_until_one_is_added() -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.drawing_board import DrawingBoard
        from doccon.log_layout import CLIENT_LAYOUT

        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([])
        item = blank_extra(kind="client")
        board.set_pack_extras([item], statuses=CLIENT_LAYOUT.statuses)
        board.focus_key(item.id)
        board.reveal_key(item.id)
        root.update()
        painted = board.pack_extras()
        assert painted[0].path == ""
        assert painted[0].document_no == "New document"
        assert board.explicit_focus_key() == item.id
        assert str(board._blocks[item.id].pdf_label.cget("text")) == "No PDF"
    finally:
        root.destroy()
