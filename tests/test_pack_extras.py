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
    extra_from_path,
    letter_status,
    load_client_pack,
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
    assert letter_status(SHOP, "APPROVAL") == "INFORMATION"
    assert letter_status(FIELD, "INFORMATION") == "INFORMATION"
    assert letter_status(SHOP, "PURCHASING ONLY") == "PURCHASING ONLY"


def test_lines_follow_packed_drawings() -> None:
    item = PackExtra(
        path="notes.pdf",
        document_no="Site photo",
        rev="",
        description="North side",
        status="INFORMATION",
    )
    lines = lines_from_extras([item], CLIENT)
    assert lines[0].document_no == "Site photo"
    assert lines[0].description == "North side"
    assert lines[0].status == "INFORMATION"


def test_pack_extras_round_trip(tmp_path: Path) -> None:
    dropped = tmp_path / "3.0 Doc Con" / "DocCon" / "dropped" / "mail.pdf"
    item = PackExtra(
        path=str(dropped),
        document_no="mail",
        rev="0",
        description="From Sarah",
        status="INFORMATION",
        email_dropped=True,
        id="x:mail",
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
        assert str(board._blocks[painted[0].id].nexts["client_document_number"].cget("state")) == "disabled"
        assert board.pending_rows() == []
    finally:
        root.destroy()
