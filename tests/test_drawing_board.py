# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import contextlib
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

import pytest

from doccon.drawing_board import (
    BOARD_COLUMNS,
    CHAR_PX,
    DESC_COL_INDEX,
    DESC_COL_PX,
    DRAWING_COL_INDEX,
    FROZEN_COLS,
    FROZEN_SYNC_MAX,
    HEADER_TITLES,
    HEADING_PAD_PX,
    JIRA_ID_COL_PX,
    JIRA_ID_TITLE,
    MIN_COL_PX,
    PACK_COL_INDEX,
    PACK_COL_PX,
    PDF_COL_INDEX,
    PDF_COL_PX,
    PICK_ONLY_FIELDS,
    REV_VALUES,
    DrawingBoard,
    NextEntry,
    default_col_px,
    field_is_pick_only,
    header_pad_px,
    heading_floor_px,
    merge_col_px,
    next_outgoing_rev,
    row_key_for_y,
    row_matches_filter,
    with_now_option,
)
from doccon.match import EMAIL_DROPPED_LABEL, MatchedRow, PdfHit, pair_pdf
from doccon.register import DrawingRow
from doccon.settings import BOARD_LAYOUT_REV
from doccon.theme import BORDER, FOCUS_BG, FOCUS_RULE, PENDING_BG


def _row(
    *,
    key: str = "P2024-1",
    drawing_id: str = "2026-Tanzim-1-1",
    eddi_status: str = "",
    title: str = "Drawing",
    outgoing_rev: str = "A",
    return_request_date: str = "",
    submission_date: str = "",
) -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} Drawing",
            drawing_id=drawing_id,
            title=title,
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev=outgoing_rev,
            purpose="Info",
            parent_summary="Drawing Package",
            eddi_status=eddi_status,
            return_request_date=return_request_date,
            submission_date=submission_date,
        ),
        pdf=None,
        confidence="Missing",
    )


def test_option_now_uses_dropdown_value() -> None:
    from doccon.drawing_board import PURPOSE_VALUES, _option_now
    from doccon.register import EDDI_VALUES

    assert _option_now(PURPOSE_VALUES, "Info") == "Info"
    assert _option_now(EDDI_VALUES, "1 - Fabrication Drawings - EDDI") == "1 - Fabrication Drawings - EDDI"
    assert _option_now((), "2026-01-02") == "2026-01-02"
    assert _option_now(PURPOSE_VALUES, " leftover ") == "leftover"


def test_now_next_and_pack() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        assert board.pending_rows() == []
        assert board.selected_keys() == ("P2024-1",)
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("0")
        board._blocks["P2024-1"].nexts["purpose"].set("Approval")
        board._blocks["P2024-1"].nexts["client_document_number"].set("CNRL-T-101")
        board._blocks["P2024-1"].nexts["return_request_date"].set("2026-09-15")
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.outgoing_rev == "0"
        assert pending[0].drawing.purpose == "Approval"
        assert pending[0].drawing.client_document_number == "CNRL-T-101"
        assert pending[0].drawing.return_request_date == "2026-09-15"
        assert pending[0].drawing.due_date == "2026-09-15"
        assert "due_date" not in board._blocks["P2024-1"].nexts
        assert "due_date" not in board._batch_fields
        assert "Due Date (Jira)" not in board.header_titles()
        packed = board.selected_rows()
        assert packed[0].drawing.outgoing_rev == "0"
        board._blocks["P2024-1"].include.set(False)
        assert board.selected_rows() == []
        assert [row.drawing.key for row in board.current_rows()] == ["P2024-1"]
        assert board.pending_rows()
        board._blocks["P2024-1"].include.set(True)
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("A")
        board._blocks["P2024-1"].nexts["purpose"].set("Info")
        board._blocks["P2024-1"].status_next.set("IFI")
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.status == "IFI"
        assert pending[0].drawing.outgoing_rev == "A"
        board.revert_next()
        assert board.pending_rows() == []
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "A"
        assert board._blocks["P2024-1"].status_next.get() == "To Do"
    finally:
        root.destroy()


def test_edited_next_box_turns_yellow() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        box = board._blocks["P2024-1"].nexts["outgoing_rev"]
        status = board._blocks["P2024-1"].status_next
        assert "Pending" not in str(box.cget("style") or "")
        box.set("0")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TCombobox"
        cell = getattr(box, "_doccon_cell", None)
        assert cell is not None
        assert str(cell.cget("bg")).casefold() == "#fef3c7"
        status.set("IFI")
        root.update_idletasks()
        assert status.cget("style") == "Pending.TCombobox"
        box.set("A")
        root.update_idletasks()
        assert "Pending" not in str(box.cget("style") or "TCombobox")
        assert str(cell.cget("bg")).casefold() in {"#ffffff", "systembuttonface", "white"}
        board.revert_next()
        root.update_idletasks()
        assert "Pending" not in str(status.cget("style") or "TCombobox")
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_right_click_next_restores_now_and_clears_dirty() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        block = board._blocks["P2024-1"]
        other = board._blocks["P2024-2"]
        box = block.nexts["outgoing_rev"]
        purpose = block.nexts["purpose"]
        box.set("ZZ")
        purpose.set("Approval")
        other.nexts["outgoing_rev"].set("B")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TCombobox"
        assert purpose.cget("style") == "Pending.TCombobox"
        assert box.bind("<Button-3>")
        assert not box.bind("<<Paste>>")
        box.event_generate("<Button-3>")
        root.update_idletasks()
        if box.get() != "A":
            assert board._on_restore_next(SimpleNamespace(widget=box)) == "break"
            root.update_idletasks()
        assert box.get() == "A"
        assert "Pending" not in str(box.cget("style") or "TCombobox")
        cell = getattr(box, "_doccon_cell", None)
        assert cell is not None
        assert str(cell.cget("bg")).casefold() in {"#ffffff", "systembuttonface", "white"}
        assert purpose.get() == "Approval"
        assert purpose.cget("style") == "Pending.TCombobox"
        pending = board.pending_rows()
        assert len(pending) == 2
        first = next(row for row in pending if row.drawing.key == "P2024-1")
        assert first.drawing.outgoing_rev == "A"
        assert first.drawing.purpose == "Approval"
        assert other.nexts["outgoing_rev"].get() == "B"
        now_label = block.originals["outgoing_rev"]
        box.set("0")
        root.update_idletasks()
        now_label.event_generate("<Button-3>")
        root.update_idletasks()
        assert box.get() == "0"
        block.drawing_label.event_generate("<Button-3>")
        root.update_idletasks()
        assert box.get() == "0"
        cell_purpose = board._next_cell(purpose)
        assert cell_purpose is not None
        assert board._on_restore_next(SimpleNamespace(widget=cell_purpose)) == "break"
        root.update_idletasks()
        assert purpose.get() == "Info"
        assert "Pending" not in str(purpose.cget("style") or "TCombobox")
        still = next(row for row in board.pending_rows() if row.drawing.key == "P2024-1")
        assert still.drawing.outgoing_rev == "0"
        assert still.drawing.purpose == "Info"
    finally:
        root.destroy()


def test_right_click_restores_combobox_date_and_eddi() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        base = _row(eddi_status="1 - Fabrication Drawings - EDDI")
        row = replace(base, drawing=replace(base.drawing, submission_date="2026-01-02"))
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([row])
        block = board._blocks["P2024-1"]
        status = block.status_next
        date_box = block.nexts["submission_date"]
        eddi = block.nexts["eddi_status"]
        status.set("IFI")
        date_box.set("not-a-date")
        eddi.set("typed leftover")
        root.update_idletasks()
        assert board.restore_next_field("P2024-1", "status")
        assert board.restore_next_field("P2024-1", "submission_date")
        assert board.restore_next_field("P2024-1", "eddi_status")
        root.update_idletasks()
        assert status.get() == "To Do"
        assert date_box.get() == "2026-01-02"
        assert eddi.get() == "1 - Fabrication Drawings - EDDI"
        assert "Pending" not in str(status.cget("style") or "TCombobox")
        assert "Pending" not in str(date_box.cget("style") or "TCombobox")
        assert "Pending" not in str(eddi.cget("style") or "TCombobox")
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_right_click_next_does_not_write_jira(monkeypatch) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon import jira_client

        writes: list[str] = []

        def _bang(*_args, **_kwargs):
            writes.append("jira")
            raise AssertionError("restore Next must not write Jira")

        monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
        monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
        monkeypatch.setattr(jira_client, "transition_drawing", _bang)
        monkeypatch.setattr(jira_client, "apply_jira_updates", _bang)
        monkeypatch.setattr(jira_client, "run_jira_register_update", _bang)
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        box = board._blocks["P2024-1"].nexts["outgoing_rev"]
        box.set("0")
        root.update_idletasks()
        assert board._on_restore_next(SimpleNamespace(widget=box)) == "break"
        root.update_idletasks()
        assert box.get() == "A"
        assert writes == []
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_batch_applies_to_pack_only() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        count = board.apply_next_to_pack(status="In Progress", fields={"outgoing_rev": "0", "purpose": "Approval"})
        assert count == 1
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.key == "P2024-1"
        assert pending[0].drawing.status == "In Progress"
        assert pending[0].drawing.outgoing_rev == "0"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        board.set_pack(True)
        assert board.selected_keys() == ("P2024-1", "P2024-2")
        assert board.apply_next_to_pack() == 0
        assert not hasattr(board, "_batch_title")
        title_before = board._blocks["P2024-1"].title_next.get()
        board._batch_status.set("Done")
        board._apply_batch()
        assert board._blocks["P2024-1"].status_next.get() == "Done"
        assert board._blocks["P2024-1"].title_next.get() == title_before
    finally:
        root.destroy()


def test_batch_strip_starts_hidden() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        root.update_idletasks()
        assert board._batch_open is False
        assert board._batch_frame.winfo_manager() == ""
        assert str(board._batch_toggle.cget("text")) == "Batch Next…"
        board._set_batch_open(True)
        root.update_idletasks()
        assert board._batch_frame.winfo_manager() == "pack"
        assert str(board._batch_toggle.cget("text")) == "Hide batch"
        board.set_rows([_row()])
        root.update_idletasks()
        assert board._batch_open is False
        assert board._batch_frame.winfo_manager() == ""
        assert str(board._batch_toggle.cget("text")) == "Batch Next…"
    finally:
        root.destroy()


def test_board_groups_by_eddi_with_headers(tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.match import pair_pdf

        pdf = tmp_path / "2026-Tanzim-1-2 REV 0.pdf"
        pdf.write_bytes(b"%PDF")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                pair_pdf(
                    _row(
                        key="P2024-2",
                        drawing_id="2026-Tanzim-1-2",
                        eddi_status="1 - Fabrication Drawings - EDDI",
                    ),
                    pdf,
                ),
                _row(key="P2024-1", drawing_id="2026-Tanzim-ITP", eddi_status="0 - Generic Task"),
                _row(key="P2024-3", drawing_id="2026-Tanzim-RFI", eddi_status=""),
            ]
        )
        assert list(board._blocks) == ["P2024-2", "P2024-3"]
        labels = [
            child.cget("text")
            for child in board._inner.winfo_children()
            if isinstance(child, ttk.Label) and str(child.cget("style")) == "Group.TLabel"
        ]
        assert labels[0].startswith("1 -")
        assert labels[-1] == "Ungrouped"
        assert board._blocks["P2024-2"].pack_mark.cget("text") == "✓"
        assert str(board._blocks["P2024-2"].pack_mark.cget("width")) == "2"
        assert "nsew" not in str(board._blocks["P2024-2"].pack_mark.grid_info().get("sticky", ""))
        board._blocks["P2024-2"].include.set(False)
        assert board._blocks["P2024-2"].pack_mark.cget("text") == ""
        assert board._blocks["P2024-2"].locate_btn.winfo_manager() in {"grid", "pack"}
        assert board._blocks["P2024-3"].locate_btn.winfo_manager() in {"grid", "pack"}
        matched_block = board._blocks["P2024-2"]
        missing_block = board._blocks["P2024-3"]
        assert str(matched_block.open_btn.cget("text")) == "Open"
        assert str(matched_block.preview_btn.cget("text")) == "Preview"
        assert matched_block.open_btn.master is matched_block.locate_btn.master
        cluster = list(matched_block.locate_btn.master.pack_slaves())
        assert cluster[:3] == [matched_block.locate_btn, matched_block.open_btn, matched_block.preview_btn]
        assert "disabled" not in str(matched_block.open_btn.cget("state"))
        assert "disabled" not in str(matched_block.preview_btn.cget("state"))
        assert "disabled" in str(missing_block.open_btn.cget("state"))
        assert "disabled" in str(missing_block.preview_btn.cget("state"))
        board.apply_row(pair_pdf(_row(key="P2024-3", drawing_id="2026-Tanzim-RFI"), pdf))
        assert "disabled" not in str(board._blocks["P2024-3"].open_btn.cget("state"))
        assert "disabled" not in str(board._blocks["P2024-3"].preview_btn.cget("state"))
        header_text = board.header_titles()
        assert JIRA_ID_TITLE in header_text
        assert "Drawing" not in header_text
        assert "Description" in header_text
        assert "Submitted to Client For" in header_text
        assert "Due Date (Jira)" not in header_text
        inner_headers = [
            child.cget("text")
            for child in board._inner.winfo_children()
            if isinstance(child, ttk.Label) and str(child.cget("style")) == "Header.TLabel"
        ]
        assert inner_headers == []
    finally:
        root.destroy()


def test_locate_button_browses_instead_of_opening(tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.match import pair_pdf

        opened: list[str] = []
        located: list[str] = []
        previewed: list[str] = []
        pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
        pdf.write_bytes(b"%PDF")
        board = DrawingBoard(
            root,
            on_open_pdf=opened.append,
            on_locate_pdf=located.append,
            on_preview_pdf=previewed.append,
        )
        board.set_rows(
            [
                pair_pdf(
                    _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                    pdf,
                )
            ]
        )
        board._blocks["P2024-1"].locate_btn.invoke()
        assert located == ["P2024-1"]
        assert opened == []
        board._blocks["P2024-1"].open_btn.invoke()
        assert opened == ["P2024-1"]
        assert located == ["P2024-1"]
        board._blocks["P2024-1"].preview_btn.invoke()
        assert previewed == ["P2024-1"]
        assert opened == ["P2024-1"]
        assert located == ["P2024-1"]
        assert str(board._blocks["P2024-1"].pdf_label.cget("text")) == pdf.name
        assert EMAIL_DROPPED_LABEL not in str(board._blocks["P2024-1"].pdf_label.cget("text"))
    finally:
        root.destroy()


def test_email_dropped_pdf_address_is_yellow(tmp_path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.drop_pdfs import apply_row_drop, copy_into_dropped
        from doccon.match import EMAIL_DROPPED_LABEL, EMAIL_DROPPED_SUFFIX, pair_pdf
        from doccon.theme import BG, PENDING_BG

        job = tmp_path / "2026-Tanzim"
        src = tmp_path / "inbox" / "2026-Tanzim-1-1 REV 0.pdf"
        src.parent.mkdir()
        src.write_bytes(b"%PDF-fake")
        copied = copy_into_dropped(job, src)
        dropped_row, _leftover = apply_row_drop(
            _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
            [copied],
            "2026-Tanzim",
        )
        opened: list[str] = []
        board = DrawingBoard(root, on_open_pdf=opened.append)
        board.set_rows([dropped_row])
        block = board._blocks["P2024-1"]
        assert str(block.pdf_label.cget("text")) == f"{copied.name}{EMAIL_DROPPED_SUFFIX}"
        assert str(block.pdf_label.cget("text")).startswith(copied.name)
        assert board._pdf_tip_text("P2024-1") == f"{copied.name}{EMAIL_DROPPED_SUFFIX}\n{copied}"
        assert str(block.pdf_cell.cget("bg")).casefold() == PENDING_BG.casefold()
        assert str(block.pdf_label.cget("style")) == "Pending.TLabel"
        assert str(block.match_label.cget("text")) == "High"
        assert str(block.pack_mark.cget("bg")).casefold() != PENDING_BG.casefold()
        assert board.next_edits() == {}
        board._blocks["P2024-1"].open_btn.invoke()
        assert opened == ["P2024-1"]
        assert dropped_row.pdf is not None and dropped_row.pdf.path == copied

        real = tmp_path / "Current PDF" / "2026-Tanzim-1-1 REV 0.pdf"
        real.parent.mkdir()
        real.write_bytes(b"%PDF-real")
        board.apply_row(pair_pdf(dropped_row, real))
        block = board._blocks["P2024-1"]
        assert str(block.pdf_label.cget("text")) == real.name
        assert EMAIL_DROPPED_LABEL not in str(block.pdf_label.cget("text"))
        assert board._pdf_tip_text("P2024-1") == real.name
        assert str(block.pdf_cell.cget("bg")).casefold() == BG.casefold()
        assert str(block.pdf_label.cget("style")) == "Board.TLabel"
        assert board.next_edits() == {}
    finally:
        root.destroy()


def test_email_dropped_address_puts_the_filename_before_the_marker(tmp_path) -> None:
    from doccon.match import EMAIL_DROPPED_SUFFIX, pdf_address_text, pdf_address_tip

    long_name = "2026-Tanzim-1-14 SPIRAL STAIRWAY INSIDE HANDRAIL DETAIL REV 0.pdf"
    staged = tmp_path / "2026-Tanzim" / "3.0 Doc Con" / "DocCon" / "dropped" / long_name
    row = replace(
        _row(key="P2024-1"),
        pdf=PdfHit(path=staged, drawing_id="", rev="", email_dropped=True),
        confidence="High",
    )
    address = pdf_address_text(row)
    assert address == f"{long_name}{EMAIL_DROPPED_SUFFIX}"
    # The cell clips from the right, so a long name spends the column on itself, not on the marker.
    assert address.startswith(long_name)
    assert address.endswith(EMAIL_DROPPED_LABEL)
    assert PDF_COL_PX == 272, "Preview sits beside Open; the email-dropped marker still clips from the right"
    # Whatever the column eats, the hover still carries the full wording and where the copy is staged.
    tip = pdf_address_tip(row)
    assert tip == f"{address}\n{staged}"
    assert EMAIL_DROPPED_LABEL in tip
    assert str(staged) in tip


def test_locate_inside_dropped_keeps_yellow_and_shows_that_filename(tmp_path) -> None:
    from doccon.drop_pdfs import replace_paired_pdf, write_pdf_bytes_into_dropped
    from doccon.match import EMAIL_DROPPED_SUFFIX, pair_pdf
    from doccon.theme import PENDING_BG

    root = _board_root()
    try:
        job = tmp_path / "2026-Tanzim"
        first = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-first")
        second = write_pdf_bytes_into_dropped(job, "scan0043.pdf", b"%PDF-second")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([pair_pdf(_row(key="P2024-1"), first)])
        block = board._blocks["P2024-1"]
        assert str(block.pdf_label.cget("text")) == f"scan0042.pdf{EMAIL_DROPPED_SUFFIX}"

        relocated = replace_paired_pdf(board._matches["P2024-1"], second)
        board.apply_row(relocated)
        block = board._blocks["P2024-1"]
        assert str(block.pdf_label.cget("text")) == f"scan0043.pdf{EMAIL_DROPPED_SUFFIX}"
        assert str(block.pdf_label.cget("style")) == "Pending.TLabel"
        assert str(block.pdf_cell.cget("bg")).casefold() == PENDING_BG.casefold()
        assert second.is_file(), "a Locate inside dropped keeps that copy"
    finally:
        root.destroy()


def test_long_description_is_kept() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        title = "Main Steel: Intermediate Shell Platform Detail — north stair and landing"
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title=title)])
        block = board._blocks["P2024-1"]
        assert block.title_label.cget("text") == title
        assert block.title_next.get() == title
        assert int(str(block.title_label.cget("wraplength") or 0)) > 24
    finally:
        root.destroy()


def test_now_next_has_full_width_rules() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        rules = [
            child
            for child in board._inner.winfo_children()
            if isinstance(child, tk.Frame) and str(child.cget("height")) == "1"
        ]
        assert len(rules) == 2
        assert all(int(child.grid_info()["columnspan"]) == BOARD_COLUMNS for child in rules)
    finally:
        root.destroy()


def test_start_rows_paints_one_by_one() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        finished: list[bool] = []
        board.start_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            on_done=lambda: finished.append(True),
        )
        for _ in range(80):
            if finished:
                break
            root.update()
        assert finished
        assert set(board._blocks) == {"P2024-1", "P2024-2"}
        assert not board._paint_queue
    finally:
        root.destroy()


def test_header_and_body_share_resizable_columns() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from doccon.drawing_board import default_col_px

        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        header_px = board.column_minsizes()
        body_px = [
            int(board._inner.grid_columnconfigure(col)["minsize"] or 0) for col in range(BOARD_COLUMNS)
        ]
        assert header_px == body_px
        assert len(header_px) == BOARD_COLUMNS
        purpose_col = next(i for i, (title, _) in enumerate(HEADER_TITLES) if title == "Submitted to Client For")
        assert default_col_px()[purpose_col] == heading_floor_px()[purpose_col]
        assert default_col_px()[purpose_col] == len("Submitted to Client For") * 10 + header_pad_px(purpose_col)
        assert int(str(board._header_labels[purpose_col].cget("wraplength") or 0)) == 0
        board.resize_column(purpose_col, 280)
        assert board.column_minsizes()[purpose_col] == 280
        assert int(board._inner.grid_columnconfigure(purpose_col)["minsize"]) == 280
        desc_col = next(i for i, (title, _) in enumerate(HEADER_TITLES) if title == "Description")
        board.resize_column(desc_col, 96)
        assert str(board._blocks["P2024-1"].title_label.cget("width")) == "1"
        assert int(board._inner.grid_columnconfigure(desc_col)["minsize"]) == 96
        assert board.column_minsizes()[desc_col] == 96
        assert int(str(board._blocks["P2024-1"].title_label.cget("wraplength") or 0)) > 0
        assert int(str(board._blocks["P2024-1"].drawing_label.cget("wraplength") or 0)) > 0
        assert int(str(board._blocks["P2024-1"].title_label.cget("wraplength"))) <= 96
    finally:
        root.destroy()


def test_sash_drag_does_not_relayout_body_until_release() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        from types import SimpleNamespace

        from doccon.drawing_board import MAX_COL_PX

        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        desc_col = next(i for i, (title, _) in enumerate(HEADER_TITLES) if title == "Description")
        start = board.column_minsizes()[desc_col]
        body_start = int(board._inner.grid_columnconfigure(desc_col)["minsize"])
        press = SimpleNamespace(x_root=100)
        board._sash_press(desc_col, press)
        board._sash_move(SimpleNamespace(x_root=180))
        header_now = board.column_minsizes()[desc_col]
        assert header_now == min(start + 80, MAX_COL_PX)
        assert int(board._inner.grid_columnconfigure(desc_col)["minsize"]) == body_start
        board._sash_release(SimpleNamespace(x_root=180))
        assert int(board._inner.grid_columnconfigure(desc_col)["minsize"]) == header_now
        assert board.column_minsizes()[desc_col] == header_now
    finally:
        root.destroy()


def test_row_matches_filter_id_and_description() -> None:
    row = _row(drawing_id="2026-Tanzim-1-STWD", title="SPIRAL STAIRWAY: INSIDE HANDRAIL")
    assert row_matches_filter(row, "")
    assert row_matches_filter(row, "stwd")
    assert row_matches_filter(row, "handrail")
    assert row_matches_filter(row, "STWD stair")
    assert row_matches_filter(row, "P2024-1")
    assert not row_matches_filter(row, "ITP")
    assert row_matches_filter(row, "stair", extra="roof plan")
    assert row_matches_filter(row, "roof", extra="roof plan")


def test_filter_hides_non_matching_rows_and_keeps_edits() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    key="P2024-1",
                    drawing_id="2026-Tanzim-1-STWD",
                    title="SPIRAL STAIRWAY",
                    eddi_status="1 - Fabrication Drawings - EDDI",
                ),
                _row(
                    key="P2024-2",
                    drawing_id="2026-Tanzim-ITP-1-1",
                    title="Inspection and Testing Plan",
                    eddi_status="",
                ),
            ]
        )
        board._blocks["P2024-2"].nexts["outgoing_rev"].set("B")
        board.apply_filter("stair")
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == ""
        assert board._filter_note.cget("text") == "1 of 2"
        groups = {title: label.winfo_manager() for title, label in board._group_headers}
        assert groups["1 - Fabrication Drawings"] == "grid"
        assert groups["Ungrouped"] == ""
        assert board.selected_keys() == ("P2024-1", "P2024-2")
        board.set_pack(False)
        assert board.selected_keys() == ("P2024-2",)
        board.apply_filter("ITP")
        root.update_idletasks()
        board.set_pack(False)
        board.set_pack(True)
        assert board.selected_keys() == ("P2024-2",)
        board.apply_filter("")
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "B"
        assert board._filter_note.cget("text") == "Type, then Find"
    finally:
        root.destroy()


def test_drawing_column_stays_put_when_scrolled_sideways() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.master is board._freeze_inner
        assert board._blocks["P2024-1"].pack_mark.master is board._freeze_inner
        assert board._blocks["P2024-1"].title_label.master is board._inner
        board._xview("moveto", "1.0")
        root.update_idletasks()
        pinned = board._canvas.coords(board._freeze_window)
        assert abs(float(pinned[0]) - float(board._canvas.canvasx(0))) < 2
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
    finally:
        root.destroy()


def test_frozen_rows_follow_wrapped_description_height() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    title=(
                        "SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL AND LONG "
                        "DESCRIPTION THAT MUST WRAP ONTO SEVERAL LINES"
                    )
                )
            ]
        )
        board.resize_column(DESC_COL_INDEX, 72, persist=False)
        root.update()
        for _ in range(8):
            root.update_idletasks()
        block = board._blocks["P2024-1"]
        now_row = int(block.title_label.grid_info()["row"])
        inner_min = int(board._inner.grid_rowconfigure(now_row)["minsize"] or 0)
        freeze_min = int(board._freeze_inner.grid_rowconfigure(now_row)["minsize"] or 0)
        assert inner_min == freeze_min
        assert inner_min >= int(block.title_label.winfo_reqheight())
        assert abs(block.drawing_label.winfo_y() - block.title_label.winfo_y()) <= 2
        title_next = block.title_next
        title_next.focus_set()
        root.update()
        title_next.event_generate("<Return>")
        root.update()
        for _ in range(8):
            root.update_idletasks()
        assert int(board._inner.grid_rowconfigure(now_row)["minsize"] or 0) == int(
            board._freeze_inner.grid_rowconfigure(now_row)["minsize"] or 0
        )
        assert abs(block.drawing_label.winfo_y() - block.title_label.winfo_y()) <= 2
        assert root.focus_get() is not title_next
    finally:
        root.destroy()


def test_frozen_sync_stops_after_many_wrapped_rows() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)

        def _bang(*_a, **_k):
            raise AssertionError("update_idletasks nested in frozen sync freezes Load")

        board.update_idletasks = _bang  # type: ignore[method-assign]
        runs = {"n": 0}
        original = board._run_frozen_row_sync

        def _counted() -> None:
            runs["n"] += 1
            if runs["n"] > FROZEN_SYNC_MAX + 2:
                raise AssertionError("frozen row sync loop")
            original()

        board._run_frozen_row_sync = _counted  # type: ignore[method-assign]
        long_title = "SPIRAL STAIRWAY INSIDE HANDRAIL DETAIL " * 6
        rows = [
            _row(
                key=f"P2024-{index}",
                drawing_id=f"2026-Tanzim-1-{index}",
                title=long_title,
            )
            for index in range(1, 13)
        ]
        finished: list[bool] = []
        board.start_rows(rows, on_done=lambda: finished.append(True))
        for _ in range(400):
            if finished and not board._paint_after:
                break
            root.update()
        assert finished
        for _ in range(12):
            root.update()
        assert runs["n"] <= FROZEN_SYNC_MAX + 2
        assert board._frozen_passes <= FROZEN_SYNC_MAX
        assert board._frozen_syncing is False
        assert not board._paint_queue
    finally:
        root.destroy()


def test_next_outgoing_rev_steps_letters_numbers_and_blank() -> None:
    # Blank Now → 0: Elite IFC / numeric jobs (2026-075) already use 0, not A.
    assert next_outgoing_rev("") == "0"
    assert next_outgoing_rev("   ") == "0"
    assert next_outgoing_rev("A") == "B"
    assert next_outgoing_rev("C") == "D"
    assert next_outgoing_rev("0") == "1"
    assert next_outgoing_rev("15") == "16"
    assert next_outgoing_rev("N/A") == "N/A"
    assert next_outgoing_rev("0A") == "0B"
    assert next_outgoing_rev("a") == "b"


def _board_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    return root


def test_scroll_builds_locate_on_rows_below_the_first_screen() -> None:
    root = _board_root()
    try:
        root.geometry("900x400")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.pack(fill="both", expand=True)
        rows = [_row(key=f"P2024-{n}", drawing_id=f"2026-Tanzim-1-{n}") for n in range(1, 28)]
        board.start_rows(rows)
        for _ in range(400):
            if not board._paint_queue:
                break
            root.update()
        root.update_idletasks()
        shells = [block for block in board._blocks.values() if not block.mounted]
        assert shells
        target = max(shells, key=lambda block: block.drawing_label.winfo_y())
        assert target.locate_btn is None
        total = max(int(board._inner.winfo_reqheight()), 1)
        y = int(target.drawing_label.winfo_y())
        board._canvas.yview_moveto(min(y / total, 1))
        board._mount_visible()
        fresh = board._blocks[target.key]
        assert fresh.mounted
        assert fresh.locate_btn is not None
        assert fresh.open_btn is not None
        assert fresh.preview_btn is not None
    finally:
        root.destroy()


def test_bump_packed_revs_from_now_leaves_unpacked() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="0"),
                _row(key="P2024-3", drawing_id="2026-Tanzim-1-3", outgoing_rev=""),
                _row(key="P2024-4", drawing_id="2026-Tanzim-1-4", outgoing_rev="C"),
            ]
        )
        board._blocks["P2024-4"].include.set(False)
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("Z")
        assert str(board._packed_only_btn.cget("text")) == "Packed only"
        assert not hasattr(board, "_bump_packed_btn")
        assert "OFA" in board._pack_status.cget("values")
        assert "readonly" in str(board._pack_status.cget("state"))
        count = board.bump_packed_revs()
        assert count == 3
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "B"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "1"
        assert board._blocks["P2024-3"].nexts["outgoing_rev"].get() == "0"
        assert board._blocks["P2024-4"].nexts["outgoing_rev"].get() == "C"
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].cget("style") == "Pending.TCombobox"
        pending = {row.drawing.key: row.drawing.outgoing_rev for row in board.pending_rows()}
        assert pending["P2024-1"] == "B"
        assert pending["P2024-2"] == "1"
        assert pending["P2024-3"] == "0"
        assert "P2024-4" not in pending
        assert board.restore_next_field("P2024-1", "outgoing_rev")
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "A"
        assert "Pending" not in str(board._blocks["P2024-1"].nexts["outgoing_rev"].cget("style") or "")
    finally:
        root.destroy()


def test_set_packed_rev_stamps_zero_from_letters() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="C"),
                _row(key="P2024-3", drawing_id="2026-Tanzim-1-3", outgoing_rev="B"),
            ]
        )
        board._blocks["P2024-3"].include.set(False)
        count = board.set_packed_rev("0")
        assert count == 2
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "0"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "0"
        assert board._blocks["P2024-3"].nexts["outgoing_rev"].get() == "B"
        pending = {row.drawing.key: row.drawing.outgoing_rev for row in board.pending_rows()}
        assert pending == {"P2024-1": "0", "P2024-2": "0"}
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].cget("style") == "Pending.TCombobox"
        assert board.set_packed_rev("") == 0
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "0"
    finally:
        root.destroy()


def test_no_return_and_ifc_clear_return_request() -> None:
    root = _board_root()
    try:
        marked: list[str] = []
        board = DrawingBoard(root, on_open_pdf=lambda _key: None, on_no_return=lambda: marked.append("na"))
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", return_request_date="2026-09-20"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", return_request_date="2026-09-21"),
            ]
        )
        board.set_pack(False)
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board.stamp_packed_no_return() == 1
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "N/A"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == "2026-09-21"
        assert board._blocks["P2024-1"].nexts["return_request_date"].cget("style") == "Pending.TEntry"
        assert marked == ["na"]
        pending = board.pending_rows()
        assert pending[0].drawing.return_request_date == "N/A"
        assert pending[0].drawing.due_date == "N/A"
        board.set_pack_status("IFC")
        assert board._blocks["P2024-1"].status_next.get() == "IFC"
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "N/A"
        board._blocks["P2024-2"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-2"].status_next.get() == "IFC"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == "N/A"
    finally:
        root.destroy()


def test_set_packed_status_stamps_like_cover_dates() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        board.set_pack(False)
        board.set_pack_status("OFA", stamp=False)
        assert board.pack_status() == "OFA"
        assert board._blocks["P2024-1"].status_next.get() == "To Do"
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].status_next.get() == "OFA"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        assert board._blocks["P2024-1"].status_next.cget("style") == "Pending.TCombobox"
        pending = {row.drawing.key: row.drawing.status for row in board.pending_rows()}
        assert pending == {"P2024-1": "OFA"}
        board.set_pack_status("IFI")
        assert board._blocks["P2024-1"].status_next.get() == "IFI"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        board._blocks["P2024-2"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-2"].status_next.get() == "IFI"
        board.set_pack_status("")
        assert board._blocks["P2024-1"].status_next.get() == "To Do"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        board.set_pack(False)
        board._blocks["P2024-1"].status_next.set("Done")
        board.set_pack_status("", stamp=False)
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].status_next.get() == "Done"
        assert not hasattr(board, "_set_packed_btn")
        assert not hasattr(board, "_packed_rev")
    finally:
        root.destroy()


def test_submitted_to_client_for_stamps_packed_rows() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        board.set_pack(False)
        board.set_pack_purpose("Approval", stamp=False)
        assert board.pack_purpose() == "Approval"
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Info"
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Approval"
        assert board._blocks["P2024-2"].nexts["purpose"].get() == "Info"
        board.set_pack_purpose("Planned")
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Planned"
        assert board._blocks["P2024-2"].nexts["purpose"].get() == "Info"
        board._blocks["P2024-2"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-2"].nexts["purpose"].get() == "Planned"
        board.set_pack_purpose("")
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Info"
        assert board._blocks["P2024-2"].nexts["purpose"].get() == "Info"
        board.set_pack(False)
        board._blocks["P2024-1"].nexts["purpose"].set("NA")
        board.set_pack_purpose("", stamp=False)
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "NA"
    finally:
        root.destroy()


def test_filter_purpose_follows_transmittal_kind() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(key="P2024-1", drawing_id="2026-Tanzim-1-1")])
        board.set_pack(False)
        board.set_pack_purpose("Approval", stamp=False)
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Approval"
        board.set_transmittal_kind("shop")
        assert board._pack_purpose_label.cget("text") == "Submitted to Shop For"
        assert "IFC" in board._pack_purpose.cget("values")
        assert "Purchasing Only" in board._pack_purpose.cget("values")
        assert board.pack_purpose() == ""
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Approval"
        board.set_pack_purpose("IFU")
        assert board._blocks["P2024-1"].nexts["shop_purpose"].get() == "IFU"
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Approval"
        board.set_transmittal_kind("field")
        assert board._pack_purpose_label.cget("text") == "Submitted to Field For"
        assert "IFI" in board._pack_purpose.cget("values")
        assert board._blocks["P2024-1"].nexts["shop_purpose"].get() == "IFU"
        board.set_pack_purpose("IFI")
        assert board._blocks["P2024-1"].nexts["field_purpose"].get() == "IFI"
        board.set_transmittal_kind("client")
        assert board._pack_purpose_label.cget("text") == "Submitted to Client For"
        assert "Approval" in board._pack_purpose.cget("values")
    finally:
        root.destroy()


def test_bump_and_set_packed_zero_packed_does_not_crash() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="0"),
            ]
        )
        board.set_pack(False)
        assert board.selected_keys() == ()
        assert board.bump_packed_revs() == 0
        assert board.set_packed_rev("0") == 0
        assert board.set_packed_status("OFA") == 0
        board.set_pack_status("OFA")
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "A"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "0"
        assert board._blocks["P2024-1"].status_next.get() == "To Do"
        assert board.pending_rows() == []
        note = str(board._batch_note.cget("text"))
        assert "Pack" in note
    finally:
        root.destroy()


def test_packed_only_hides_unpacked_and_empty_eddi_headers() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    key="P2024-1",
                    drawing_id="2026-Tanzim-1-STWD",
                    title="SPIRAL STAIRWAY",
                    eddi_status="1 - Fabrication Drawings - EDDI",
                    outgoing_rev="A",
                ),
                _row(
                    key="P2024-2",
                    drawing_id="2026-Tanzim-ITP-1-1",
                    title="Inspection and Testing Plan",
                    eddi_status="",
                    outgoing_rev="C",
                ),
                _row(
                    key="P2024-3",
                    drawing_id="2026-Tanzim-RFI-1",
                    title="RFI",
                    eddi_status="4 - Engineering - EDDI",
                    outgoing_rev="0",
                ),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        board._blocks["P2024-3"].include.set(False)
        assert not board.packed_only()
        board._packed_only_btn.invoke()
        root.update_idletasks()
        assert board.packed_only()
        assert board._packed_only_btn.cget("style") == "Brand.TButton"
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == ""
        assert board._blocks["P2024-3"].drawing_label.winfo_manager() == ""
        groups = {title: label.winfo_manager() for title, label in board._group_headers}
        assert groups["1 - Fabrication Drawings"] == "grid"
        assert groups["Ungrouped"] == ""
        assert groups["4 - Engineering"] == ""
        assert board._filter_note.cget("text") == "1 packed"
        board.set_packed_only(False)
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-3"].drawing_label.winfo_manager() == "grid"
        groups = {title: label.winfo_manager() for title, label in board._group_headers}
        assert groups["1 - Fabrication Drawings"] == "grid"
        assert groups["Ungrouped"] == "grid"
        assert groups["4 - Engineering"] == "grid"
        assert board._filter_note.cget("text") == "Type, then Find"
        assert board._packed_only_btn.cget("style") == "TButton"
    finally:
        root.destroy()


def test_packed_only_stacks_packed_rows_together() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    key="P2024-1",
                    drawing_id="2026-Tanzim-1-1",
                    title="First packed",
                    eddi_status="1 - Fabrication Drawings - EDDI",
                ),
                _row(
                    key="P2024-2",
                    drawing_id="2026-Tanzim-1-2",
                    title="Unpacked hole",
                    eddi_status="1 - Fabrication Drawings - EDDI",
                ),
                _row(
                    key="P2024-3",
                    drawing_id="2026-Tanzim-1-3",
                    title="Second packed",
                    eddi_status="4 - Engineering - EDDI",
                ),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        root.update_idletasks()
        y1_full = int(board._blocks["P2024-1"].drawing_label.winfo_y())
        y3_full = int(board._blocks["P2024-3"].drawing_label.winfo_y())
        hole_row = int(board._blocks["P2024-2"].drawing_label.grid_info()["row"])
        gap_full = y3_full - y1_full
        board.set_packed_only(True)
        root.update_idletasks()
        hole_minsize = int(board._inner.grid_rowconfigure(hole_row).get("minsize") or 0)
        assert hole_minsize == 0
        y1 = int(board._blocks["P2024-1"].drawing_label.winfo_y())
        y3 = int(board._blocks["P2024-3"].drawing_label.winfo_y())
        assert y3 - y1 < gap_full
        if gap_full > 20:
            assert y3 - y1 <= gap_full * 3 // 4
        board.set_packed_only(False)
        root.update_idletasks()
        restored = int(board._inner.grid_rowconfigure(hole_row).get("minsize") or 0)
        assert restored > 0
        assert int(board._blocks["P2024-3"].drawing_label.winfo_y()) == y3_full
    finally:
        root.destroy()


def test_packed_only_intersects_text_filter() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    key="P2024-1",
                    drawing_id="2026-Tanzim-1-STWD",
                    title="SPIRAL STAIRWAY",
                    eddi_status="1 - Fabrication Drawings - EDDI",
                ),
                _row(
                    key="P2024-2",
                    drawing_id="2026-Tanzim-ITP-1-1",
                    title="Inspection and Testing Plan",
                    eddi_status="",
                ),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        board.set_packed_only(True)
        board.apply_filter("ITP")
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == ""
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == ""
        assert board._filter_note.cget("text") == "No matches"
        board.apply_filter("stair")
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == ""
        assert board._filter_note.cget("text") == "1 of 1 packed"
        board.set_packed_only(False)
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_label.winfo_manager() == "grid"
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == ""
        board.apply_filter("")
        root.update_idletasks()
        assert board._blocks["P2024-2"].drawing_label.winfo_manager() == "grid"
        board._blocks["P2024-2"].include.set(True)
        board.apply_filter("stair")
        root.update_idletasks()
        assert board.bump_packed_revs() == 2
        board.apply_filter("")
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "B"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "B"
    finally:
        root.destroy()


def test_bump_and_set_packed_do_not_write_jira(monkeypatch) -> None:
    root = _board_root()
    try:
        from doccon import jira_client

        writes: list[str] = []

        def _bang(*_args, **_kwargs):
            writes.append("jira")
            raise AssertionError("rev batch must not write Jira")

        monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
        monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
        monkeypatch.setattr(jira_client, "transition_drawing", _bang)
        monkeypatch.setattr(jira_client, "apply_jira_updates", _bang)
        monkeypatch.setattr(jira_client, "run_jira_register_update", _bang)
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="C"),
            ]
        )
        board._blocks["P2024-2"].include.set(False)
        board.bump_packed_revs()
        board.set_packed_rev("0")
        board.set_packed_status("OFA")
        assert writes == []
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "0"
        assert board._blocks["P2024-1"].status_next.get() == "OFA"
        assert board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "C"
        assert board._blocks["P2024-2"].status_next.get() == "To Do"
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.outgoing_rev == "0"
    finally:
        root.destroy()


def test_next_widget_kinds_split_dropdown_text_and_calendar() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY")])
        block = board._blocks["P2024-1"]
        assert isinstance(block.title_next, NextEntry)
        assert not isinstance(block.title_next, ttk.Combobox)
        assert isinstance(block.nexts["client_document_number"], NextEntry)
        assert not isinstance(block.nexts["client_document_number"], ttk.Combobox)
        assert isinstance(block.status_next, ttk.Combobox)
        assert tuple(block.status_next.cget("values"))
        for field in ("outgoing_rev", "incoming_rev", "shop_ifc_rev", "field_ifc_rev"):
            box = block.nexts[field]
            assert isinstance(box, ttk.Combobox)
            assert "A" in box.cget("values")
            assert "0" in box.cget("values")
        assert isinstance(block.nexts["purpose"], ttk.Combobox)
        assert "Approval" in block.nexts["purpose"].cget("values")
        assert isinstance(block.nexts["approval"], ttk.Combobox)
        assert "Void" in block.nexts["approval"].cget("values")
        assert isinstance(block.nexts["eddi_status"], ttk.Combobox)
        assert any(str(item).startswith("1 -") for item in block.nexts["eddi_status"].cget("values"))
        for field in (
            "submission_date",
            "return_request_date",
            "return_date",
            "shop_ifc_date",
            "field_ifc_date",
        ):
            box = block.nexts[field]
            assert isinstance(box, NextEntry)
            assert not isinstance(box, ttk.Combobox)
            assert getattr(box, "_doccon_calendar", None) is not None
        assert isinstance(board._batch_fields["client_document_number"], NextEntry)
        assert isinstance(board._batch_fields["outgoing_rev"], ttk.Combobox)
        assert isinstance(board._batch_fields["submission_date"], NextEntry)
    finally:
        root.destroy()


def test_right_click_description_next_restores_now() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY")])
        title = board._blocks["P2024-1"].title_next
        title.set("changed wording")
        root.update_idletasks()
        assert title.cget("style") == "Pending.TEntry"
        assert board._on_restore_next(SimpleNamespace(widget=title)) == "break"
        root.update_idletasks()
        assert title.get() == "SPIRAL STAIRWAY"
        assert "Pending" not in str(title.cget("style") or "TEntry")
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_text_next_turns_yellow() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        box = board._blocks["P2024-1"].nexts["client_document_number"]
        box.set("CNRL-T-101")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TEntry"
        cell = getattr(box, "_doccon_cell", None)
        assert cell is not None
        assert str(cell.cget("bg")).casefold() == "#fef3c7"
        box.set("")
        root.update_idletasks()
        assert "Pending" not in str(box.cget("style") or "TEntry")
    finally:
        root.destroy()


def test_rev_combobox_uses_jira_allowed_values() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rev_options({"outgoing_rev": ("", "0", "A", "Q")})
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="Z"),
            ]
        )
        first = board._blocks["P2024-1"].nexts["outgoing_rev"]
        second = board._blocks["P2024-2"].nexts["outgoing_rev"]
        assert isinstance(first, ttk.Combobox)
        first_vals = [str(v) for v in first.cget("values")]
        assert "0" in first_vals and "A" in first_vals and "Q" in first_vals
        assert "B" not in first_vals
        assert "Z" in [str(v) for v in second.cget("values")]
        batch_vals = [str(v) for v in board._batch_fields["outgoing_rev"].cget("values")]
        assert "Q" in batch_vals and "B" not in batch_vals
        incoming = board._blocks["P2024-1"].nexts["incoming_rev"]
        incoming_vals = [str(v) for v in incoming.cget("values")]
        assert "A" in incoming_vals and "0A" in incoming_vals
        assert set(incoming_vals) == set(REV_VALUES)
    finally:
        root.destroy()


def test_with_now_option_appends_missing_now() -> None:
    assert with_now_option(("", "A", "B"), "A") == ("", "A", "B")
    assert with_now_option(("", "A", "B"), "Z") == ("", "A", "B", "Z")
    assert with_now_option(("", "A"), "") == ("", "A")


def test_header_column_is_jira_id() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        titles = board.header_titles()
        assert HEADER_TITLES[DRAWING_COL_INDEX][0] == JIRA_ID_TITLE
        assert titles[DRAWING_COL_INDEX] == JIRA_ID_TITLE
        assert "Drawing" not in titles
        assert titles[DESC_COL_INDEX] == "Description"
        freeze_texts = [
            label.cget("text")
            for child in board._freeze_header.winfo_children()
            if isinstance(child, tk.Frame)
            for label in child.winfo_children()
            if isinstance(label, ttk.Label)
        ]
        assert JIRA_ID_TITLE in freeze_texts
        assert "Drawing" not in freeze_texts
        assert "Now" not in freeze_texts
        assert "Next" not in freeze_texts
        assert freeze_texts == ["Pack", JIRA_ID_TITLE]
    finally:
        root.destroy()


def test_default_column_widths_save_horizontal_space() -> None:
    defaults = default_col_px()
    floors = heading_floor_px()
    old_pack = 94
    old_desc = 52 * CHAR_PX + 44
    old_id = 32 * CHAR_PX + 44
    assert PACK_COL_PX == 48
    assert DESC_COL_PX == 240
    assert DESC_COL_PX != 564
    assert JIRA_ID_COL_PX == 180
    assert PDF_COL_PX == 272
    assert defaults[PACK_COL_INDEX] == PACK_COL_PX
    assert old_pack > PACK_COL_PX
    assert defaults[DESC_COL_INDEX] == DESC_COL_PX
    assert old_desc > DESC_COL_PX
    assert defaults[DRAWING_COL_INDEX] == JIRA_ID_COL_PX
    assert old_id > JIRA_ID_COL_PX
    for sample in ("2026-075-1-STWD", "2026-Tanzim-1-1"):
        assert defaults[DRAWING_COL_INDEX] >= len(sample) * CHAR_PX
    assert defaults[PDF_COL_INDEX] == PDF_COL_PX
    assert len("PDF") * CHAR_PX + HEADING_PAD_PX < PDF_COL_PX
    assert PDF_COL_PX >= (8 + 5 + 7) * CHAR_PX
    assert HEADER_TITLES[0][0] == "Pack"
    assert HEADER_TITLES[1][0] == JIRA_ID_TITLE
    assert all(title for title, _chars in HEADER_TITLES)
    assert FROZEN_COLS == 2
    assert DRAWING_COL_INDEX == 1
    assert DESC_COL_INDEX == 2
    for index, (title, _) in enumerate(HEADER_TITLES):
        if index in (PACK_COL_INDEX, DRAWING_COL_INDEX, DESC_COL_INDEX, PDF_COL_INDEX):
            continue
        assert defaults[index] == floors[index]
        assert floors[index] == max(MIN_COL_PX, len(title) * CHAR_PX + header_pad_px(index))
    assert merge_col_px([80] * 20) == defaults
    assert merge_col_px(defaults) == defaults


def test_layout_revision_invalidates_stale_saved_widths() -> None:
    defaults = default_col_px()
    fat = list(defaults)
    fat[DESC_COL_INDEX] = 564
    fat[PACK_COL_INDEX] = 94
    assert merge_col_px(fat) == defaults
    assert merge_col_px(fat, 0) == defaults
    assert merge_col_px(fat, 135) == defaults
    kept = merge_col_px(fat, BOARD_LAYOUT_REV)
    assert kept[DESC_COL_INDEX] == 564
    assert kept[PACK_COL_INDEX] == 94
    assert BOARD_LAYOUT_REV == 137


def test_no_now_next_label_column() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        block = board._blocks["P2024-1"]
        freeze_texts = [
            str(child.cget("text"))
            for child in board._freeze_inner.winfo_children()
            if isinstance(child, ttk.Label)
        ]
        assert "Now" not in freeze_texts
        assert "Next" not in freeze_texts
        assert "" not in board.header_titles()
        assert int(block.pack_mark.grid_info()["column"]) == PACK_COL_INDEX
        assert int(block.drawing_label.grid_info()["column"]) == DRAWING_COL_INDEX
        assert int(block.title_label.grid_info()["column"]) == DESC_COL_INDEX
        now_row = int(block.title_label.grid_info()["row"])
        next_row = int(block.title_next._doccon_cell.grid_info()["row"])
        assert next_row == now_row + 1
    finally:
        root.destroy()


def _tk_toplevels(root: tk.Misc) -> list[tk.Toplevel]:
    found: list[tk.Toplevel] = []
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            children = widget.winfo_children()
        except tk.TclError:
            continue
        for child in children:
            if isinstance(child, tk.Toplevel):
                found.append(child)
            stack.append(child)
    return found


def _click_twice(widget: tk.Misc) -> None:
    """Tk will not synthesize <Double-1>; two presses are what a double-click is."""
    for _ in range(2):
        widget.event_generate("<ButtonPress-1>", x=4, y=4)
        widget.event_generate("<ButtonRelease-1>", x=4, y=4)


def test_double_click_text_next_does_not_open_toplevel() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL")])
        block = board._blocks["P2024-1"]
        title = block.title_next
        client = block.nexts["client_document_number"]
        client.set("CNRL-T-101")
        root.update_idletasks()
        before = {id(win) for win in _tk_toplevels(root)}
        _click_twice(title)
        _click_twice(client)
        _click_twice(block.title_label)
        root.update()
        after = {id(win) for win in _tk_toplevels(root)}
        assert after == before
        assert not hasattr(board, "_read_full")
        assert title.bind("<Double-1>")
        assert client.bind("<Double-1>")
        assert not block.title_label.bind("<Double-1>")
        title.set("Roof stair wording")
        assert title.get() == "Roof stair wording"
        assert client.get() == "CNRL-T-101"
        pending = {row.drawing.key: row.drawing for row in board.pending_rows()}
        assert pending["P2024-1"].title == "Roof stair wording"
        assert pending["P2024-1"].client_document_number == "CNRL-T-101"
    finally:
        root.destroy()


def test_entry_return_commits_and_leaves_editor() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        box = board._blocks["P2024-1"].nexts["client_document_number"]
        other = board._blocks["P2024-2"].nexts["client_document_number"]
        box.focus_set()
        root.update()
        box.set("CNRL-T-101")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TEntry"
        box.event_generate("<Return>")
        root.update()
        assert box.get() == "CNRL-T-101"
        assert root.focus_get() is not box
        assert root.focus_get() is not other
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.client_document_number == "CNRL-T-101"
        assert board._active_next is None
    finally:
        root.destroy()


def test_combobox_return_leaves_editor_and_dropdown_still_sets() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        box = board._blocks["P2024-1"].status_next
        box.focus_set()
        root.update()
        box.set("IFI")
        box.event_generate("<<ComboboxSelected>>")
        root.update_idletasks()
        assert box.get() == "IFI"
        box.event_generate("<Return>")
        root.update()
        assert box.get() == "IFI"
        assert root.focus_get() is not box
        pending = board.pending_rows()
        assert len(pending) == 1
        assert pending[0].drawing.status == "IFI"
    finally:
        root.destroy()


def test_entry_focus_out_and_click_outside_commit() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        box = board._blocks["P2024-1"].nexts["client_document_number"]
        box.focus_set()
        root.update()
        box.set("CNRL-T-101")
        root.update_idletasks()
        box.event_generate("<FocusOut>")
        board._canvas.focus_set()
        root.update()
        assert box.get() == "CNRL-T-101"
        assert board.pending_rows()
        assert str(box._doccon_cell.cget("bg")).casefold() == "#fef3c7"

        box.focus_set()
        root.update()
        box.set("CNRL-T-202")
        root.update_idletasks()
        board._on_global_press(SimpleNamespace(widget=board._canvas))
        root.update()
        assert box.get() == "CNRL-T-202"
        assert root.focus_get() is not box
        assert board.pending_rows()[0].drawing.client_document_number == "CNRL-T-202"

        board._active_next = box
        board._on_global_press(SimpleNamespace(widget=box))
        root.update()
        assert board._active_next is box
    finally:
        root.destroy()


def test_escape_restores_now_and_leaves_editor() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY", outgoing_rev="A")])
        box = board._blocks["P2024-1"].nexts["outgoing_rev"]
        box.set("0")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TCombobox"
        assert board._on_next_escape(SimpleNamespace(widget=box)) == "break"
        root.update()
        assert box.get() == "A"
        assert "Pending" not in str(box.cget("style") or "TCombobox")
        assert root.focus_get() is not box
        assert board._active_next is None
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_pack_stamps_return_request_from_cover() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(
            root, on_open_pdf=lambda _key: None, cover_return_stamp=lambda: "2026-09-22"
        )
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            checked=set(),
        )
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == ""
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        assert board._blocks["P2024-1"].nexts["return_request_date"].cget("style") == "Pending.TEntry"
        board._blocks["P2024-1"].nexts["return_request_date"].set("2026-09-30")
        board._blocks["P2024-2"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-30"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == "2026-09-22"
        board._blocks["P2024-1"].include.set(False)
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-30"
        assert board.restore_next_field("P2024-1", "return_request_date")
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == ""
    finally:
        root.destroy()


def test_cover_expected_change_restamps_packed_only() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            checked={"P2024-1"},
        )
        assert board.stamp_packed_return_request("2026-09-22") == 1
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        assert board.stamp_packed_return_request("2026-10-01") == 1
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-10-01"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        assert board.stamp_packed_return_request("") == 0
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-10-01"
    finally:
        root.destroy()


def test_blank_expected_pack_does_not_clear_return_request() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None, cover_return_stamp=lambda: "")
        board.set_rows(
            [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", return_request_date="2026-08-01")],
            checked=set(),
        )
        box = board._blocks["P2024-1"].nexts["return_request_date"]
        box.set("2026-09-15")
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert box.get() == "2026-09-15"
        assert board.stamp_packed_return_request("") == 0
        assert box.get() == "2026-09-15"
    finally:
        root.destroy()


def test_pack_stamps_submission_date_from_cover() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(
            root,
            on_open_pdf=lambda _key: None,
            cover_issued_stamp=lambda: "2026-09-11",
            cover_return_stamp=lambda: "2026-09-22",
        )
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            checked=set(),
        )
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == ""
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == ""
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-11"
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert board._blocks["P2024-2"].nexts["submission_date"].get() == ""
        assert board._blocks["P2024-1"].nexts["submission_date"].cget("style") == "Pending.TEntry"
        board._blocks["P2024-1"].nexts["submission_date"].set("2026-09-18")
        board._blocks["P2024-2"].include.set(True)
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-18"
        assert board._blocks["P2024-2"].nexts["submission_date"].get() == "2026-09-11"
        board._blocks["P2024-1"].include.set(False)
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-18"
        assert board.restore_next_field("P2024-1", "submission_date")
        root.update_idletasks()
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == ""
    finally:
        root.destroy()


def test_cover_issued_change_restamps_packed_only() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            checked={"P2024-1"},
        )
        assert board.stamp_packed_submission_date("2026-09-11") == 1
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-11"
        assert board._blocks["P2024-2"].nexts["submission_date"].get() == ""
        assert board.stamp_packed_date("submission_date", "2026-09-15") == 1
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-15"
        assert board._blocks["P2024-2"].nexts["submission_date"].get() == ""
        assert board.stamp_packed_submission_date("") == 0
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-15"
        assert board.stamp_packed_return_request("2026-09-22") == 1
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-15"
    finally:
        root.destroy()


def test_blank_issued_pack_does_not_clear_submission_date() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None, cover_issued_stamp=lambda: "")
        board.set_rows(
            [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", submission_date="2026-08-01")],
            checked=set(),
        )
        box = board._blocks["P2024-1"].nexts["submission_date"]
        box.set("2026-09-15")
        board._blocks["P2024-1"].include.set(True)
        root.update_idletasks()
        assert box.get() == "2026-09-15"
        assert board.stamp_packed_cover_dates() == 0
        assert box.get() == "2026-09-15"
    finally:
        root.destroy()


def test_pack_stamp_does_not_write_jira(monkeypatch) -> None:
    root = _board_root()
    try:
        from doccon import jira_client

        writes: list[str] = []

        def _bang(*_args, **_kwargs):
            writes.append("jira")
            raise AssertionError("pack stamp must not write Jira")

        monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
        monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
        monkeypatch.setattr(jira_client, "transition_drawing", _bang)
        monkeypatch.setattr(jira_client, "apply_jira_updates", _bang)
        monkeypatch.setattr(jira_client, "run_jira_register_update", _bang)
        board = DrawingBoard(
            root, on_open_pdf=lambda _key: None, cover_return_stamp=lambda: "2026-09-22"
        )
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ],
            checked=set(),
        )
        board._blocks["P2024-1"].include.set(True)
        board.stamp_packed_return_request("2026-10-01")
        assert writes == []
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-10-01"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
    finally:
        root.destroy()


def test_pick_only_next_fields_are_readonly() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()])
        block = board._blocks["P2024-1"]
        assert field_is_pick_only("status")
        assert {
            "purpose",
            "shop_purpose",
            "field_purpose",
            "approval",
            "shop_ifc_rev",
            "field_ifc_rev",
            "eddi_status",
        } == PICK_ONLY_FIELDS
        assert str(block.status_next.cget("state")) == "readonly"
        before_status = block.status_next.get()
        with contextlib.suppress(tk.TclError):
            block.status_next.insert("end", "typed")
        assert block.status_next.get() == before_status
        for field in (
            "purpose",
            "shop_purpose",
            "field_purpose",
            "approval",
            "shop_ifc_rev",
            "field_ifc_rev",
            "eddi_status",
        ):
            box = block.nexts[field]
            assert isinstance(box, ttk.Combobox)
            assert str(box.cget("state")) == "readonly"
            before = box.get()
            with contextlib.suppress(tk.TclError):
                box.insert("end", "typed")
            assert box.get() == before
            assert str(board._batch_fields[field].cget("state")) == "readonly"
        outgoing = block.nexts["outgoing_rev"]
        incoming = block.nexts["incoming_rev"]
        assert str(outgoing.cget("state")) == "readonly"
        assert str(incoming.cget("state")) == "readonly"
        board.enter_next_editor(outgoing)
        board.enter_next_editor(incoming)
        assert str(outgoing.cget("state")) == "normal"
        assert str(incoming.cget("state")) == "normal"
        outgoing.insert("end", "X")
        assert outgoing.get().endswith("X")
        incoming.insert("end", "Y")
        assert incoming.get().endswith("Y")
        board.leave_next_editor(outgoing)
        board.leave_next_editor(incoming)
        assert str(outgoing.cget("state")) == "readonly"
        assert str(incoming.cget("state")) == "readonly"
        assert str(board._batch_fields["outgoing_rev"].cget("state")) == "normal"
        assert str(board._batch_fields["incoming_rev"].cget("state")) == "normal"
        assert isinstance(block.title_next, NextEntry)
        assert isinstance(block.nexts["client_document_number"], NextEntry)
        assert isinstance(block.nexts["return_request_date"], NextEntry)
    finally:
        root.destroy()


def test_apply_to_pack_pick_only_rejects_off_list() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row()], checked={"P2024-1"})
        count = board.apply_next_to_pack(fields={"purpose": "not-a-purpose", "outgoing_rev": "0"})
        assert count == 1
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Info"
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "0"
        assert board.apply_next_to_pack(fields={"purpose": "Approval"}) == 1
        assert board._blocks["P2024-1"].nexts["purpose"].get() == "Approval"
    finally:
        root.destroy()


def test_cover_na_reverts_packed_dates_to_now() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(
                    key="P2024-1",
                    submission_date="2026-08-01",
                    return_request_date="2026-08-10",
                ),
                _row(
                    key="P2024-2",
                    drawing_id="2026-Tanzim-1-2",
                    submission_date="2026-08-02",
                    return_request_date="2026-08-11",
                ),
            ],
            checked={"P2024-1"},
        )
        assert board.stamp_packed_submission_date("2026-09-11") == 1
        assert board.stamp_packed_return_request("2026-09-22") == 1
        assert board.apply_cover_date_change("return_request_date", "N/A") == 1
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-08-10"
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-11"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == "2026-08-11"
        assert board.apply_cover_date_change("submission_date", "") == 1
        assert board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-08-01"
        assert board._blocks["P2024-2"].nexts["submission_date"].get() == "2026-08-02"
    finally:
        root.destroy()


def test_cancel_next_restores_every_listed_row() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", title="First", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", title="Second", outgoing_rev="B"),
            ],
            checked={"P2024-1"},
        )
        packed = board._blocks["P2024-1"]
        loose = board._blocks["P2024-2"]
        packed.status_next.set("IFI")
        packed.nexts["outgoing_rev"].set("C")
        packed.nexts["submission_date"].set("2026-09-11")
        loose.title_next.set("Changed")
        loose.nexts["client_document_number"].set("CNRL-T-101")
        root.update_idletasks()
        assert board.pending_rows()
        count = board.revert_next()
        assert count == 2
        assert packed.status_next.get() == "To Do"
        assert packed.nexts["outgoing_rev"].get() == "A"
        assert packed.nexts["submission_date"].get() == ""
        assert loose.title_next.get() == "Second"
        assert loose.nexts["client_document_number"].get() == ""
        assert board.selected_keys() == ("P2024-1",)
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_cancel_next_button_restores_without_jira(monkeypatch) -> None:
    root = _board_root()
    try:
        from doccon import jira_client

        writes: list[str] = []

        def _bang(*_args, **_kwargs):
            writes.append("jira")
            raise AssertionError("Cancel Next must not write Jira")

        monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
        monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
        monkeypatch.setattr("doccon.drawing_board.messagebox.askyesno", lambda *_a, **_k: True)
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", title="First"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", title="Second"),
            ],
            checked={"P2024-1"},
        )
        board._blocks["P2024-1"].status_next.set("IFI")
        board._blocks["P2024-2"].title_next.set("Changed")
        root.update_idletasks()
        board._cancel_next()
        assert board._blocks["P2024-1"].status_next.get() == "To Do"
        assert board._blocks["P2024-2"].title_next.get() == "Second"
        assert board.selected_keys() == ("P2024-1",)
        assert board.pending_rows() == []
        assert writes == []
    finally:
        root.destroy()


def test_single_click_entry_does_not_take_edit_focus() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY")])
        box = board._blocks["P2024-1"].title_next
        date_box = board._blocks["P2024-1"].nexts["submission_date"]
        board._canvas.focus_set()
        root.update()
        assert str(box.cget("state")) == "readonly"
        box.event_generate("<Button-1>", x=4, y=4)
        root.update()
        assert root.focus_get() is not box
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is not box
        date_box.event_generate("<Button-1>", x=4, y=4)
        root.update()
        assert root.focus_get() is not date_box
        assert str(date_box.cget("state")) == "readonly"
    finally:
        root.destroy()


def test_double_click_entry_takes_edit_focus() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY")])
        box = board._blocks["P2024-1"].title_next
        assert box.bind("<Double-1>")
        before = {id(win) for win in _tk_toplevels(root)}
        board._on_next_double1(SimpleNamespace(widget=box))
        root.update()
        after = {id(win) for win in _tk_toplevels(root)}
        assert after == before
        assert str(box.cget("state")) == "normal"
        assert board._active_next is box
        box.insert("end", " X")
        assert box.get().endswith(" X")
        board.leave_next_editor(box)
        root.update()
        assert root.focus_get() is not box
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is None
    finally:
        root.destroy()


def test_next_edits_round_trip_and_skips_stale() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(key="P2024-1", outgoing_rev="A"), _row(key="P2024-2", outgoing_rev="A")])
        board._blocks["P2024-1"].nexts["outgoing_rev"].set("C")
        board._blocks["P2024-1"].status_next.set("IFI")
        edits = board.next_edits()
        assert edits["P2024-1"]["outgoing_rev"] == "C"
        assert edits["P2024-1"]["status"] == "IFI"
        assert "P2024-2" not in edits
        board.set_rows([_row(key="P2024-1", outgoing_rev="A")])
        applied = board.apply_next_edits({**edits, "P2024-gone": {"outgoing_rev": "Z"}})
        assert applied == 1
        assert board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "C"
        assert board._blocks["P2024-1"].status_next.get() == "IFI"
    finally:
        root.destroy()


def test_jira_id_next_is_a_plain_entry_in_the_frozen_column() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(drawing_id="2026-Tanzim-1-1", title="SPIRAL STAIRWAY")])
        block = board._blocks["P2024-1"]
        box = block.drawing_id_next
        assert isinstance(box, NextEntry)
        assert not isinstance(box, ttk.Combobox)
        assert box.get() == "2026-Tanzim-1-1"
        assert box.master.master is board._freeze_inner
        cell = board._next_cell(box)
        assert cell is not None
        assert int(cell.grid_info()["column"]) == DRAWING_COL_INDEX
        assert int(cell.grid_info()["row"]) == int(block.drawing_label.grid_info()["row"]) + 1
        assert board.header_titles()[DRAWING_COL_INDEX] == JIRA_ID_TITLE
        assert "drawing_id" not in board._batch_fields
    finally:
        root.destroy()


def test_jira_id_next_single_click_selects_double_click_edits() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(drawing_id="2026-Tanzim-1-1")])
        box = board._blocks["P2024-1"].drawing_id_next
        board._canvas.focus_set()
        root.update()
        assert str(box.cget("state")) == "readonly"
        box.event_generate("<Button-1>", x=4, y=4)
        root.update()
        assert root.focus_get() is not box
        assert str(box.cget("state")) == "readonly"
        before = {id(win) for win in _tk_toplevels(root)}
        assert box.bind("<Double-1>")
        board._on_next_double1(SimpleNamespace(widget=box))
        root.update()
        assert {id(win) for win in _tk_toplevels(root)} == before
        assert str(box.cget("state")) == "normal"
        assert board._active_next is box
        box.insert("end", "-B")
        assert box.get() == "2026-Tanzim-1-1-B"
        assert board._on_next_return(SimpleNamespace(widget=box)) == "break"
        root.update()
        assert box.get() == "2026-Tanzim-1-1-B"
        assert root.focus_get() is not box
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is None
        assert board.pending_rows()[0].drawing.drawing_id == "2026-Tanzim-1-1-B"

        board._on_next_double1(SimpleNamespace(widget=box))
        board._on_global_press(SimpleNamespace(widget=board._canvas))
        root.update()
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is None
    finally:
        root.destroy()


def test_jira_id_next_turns_yellow_and_restores_now() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(drawing_id="2026-Tanzim-1-1", title="Drawing")])
        block = board._blocks["P2024-1"]
        box = block.drawing_id_next
        assert "Pending" not in str(box.cget("style") or "")
        box.set("2026-Tanzim-1-STWD")
        root.update_idletasks()
        assert box.cget("style") == "Pending.TEntry"
        assert str(board._next_cell(box).cget("bg")).casefold() == "#fef3c7"
        assert "Pending" not in str(block.title_next.cget("style") or "TEntry")
        assert board._on_restore_next(SimpleNamespace(widget=box)) == "break"
        root.update_idletasks()
        assert box.get() == "2026-Tanzim-1-1"
        assert "Pending" not in str(box.cget("style") or "TEntry")
        assert board.pending_rows() == []

        box.set("2026-Tanzim-1-STWD")
        root.update_idletasks()
        assert board._on_next_escape(SimpleNamespace(widget=box)) == "break"
        root.update()
        assert box.get() == "2026-Tanzim-1-1"
        assert board._active_next is None
    finally:
        root.destroy()


def test_cancel_next_restores_jira_id() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(drawing_id="2026-Tanzim-1-1", title="Drawing")])
        block = board._blocks["P2024-1"]
        block.drawing_id_next.set("2026-Tanzim-9-9")
        block.title_next.set("Changed")
        root.update_idletasks()
        assert board.pending_rows()
        assert board.revert_next() == 1
        assert block.drawing_id_next.get() == "2026-Tanzim-1-1"
        assert block.title_next.get() == "Drawing"
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_jira_id_next_composes_one_summary() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-ITP-1-1", title=""),
            ]
        )
        board._blocks["P2024-1"].drawing_id_next.set("2026-Tanzim-1-STWD")
        board._blocks["P2024-2"].drawing_id_next.set("2026-Tanzim-ITP-1-2")
        rows = {row.drawing.key: row.drawing for row in board.pending_rows()}
        assert rows["P2024-1"].drawing_id == "2026-Tanzim-1-STWD"
        assert rows["P2024-1"].title == "Drawing-1"
        assert rows["P2024-1"].summary == "2026-Tanzim-1-STWD Drawing-1"
        assert rows["P2024-2"].summary == "2026-Tanzim-ITP-1-2"
        assert not rows["P2024-2"].summary.endswith(" ")
        board._blocks["P2024-1"].title_next.set("SPIRAL STAIRWAY")
        both = {row.drawing.key: row.drawing for row in board.pending_rows()}
        assert both["P2024-1"].summary == "2026-Tanzim-1-STWD SPIRAL STAIRWAY"
    finally:
        root.destroy()


def test_jira_id_next_round_trips_through_next_edits() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", title="Drawing")])
        board._blocks["P2024-1"].drawing_id_next.set("2026-Tanzim-1-STWD")
        edits = board.next_edits()
        assert edits == {"P2024-1": {"drawing_id": "2026-Tanzim-1-STWD"}}
        board.set_rows([_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", title="Drawing")])
        assert board._blocks["P2024-1"].drawing_id_next.get() == "2026-Tanzim-1-1"
        assert board.apply_next_edits(edits) == 1
        root.update_idletasks()
        assert board._blocks["P2024-1"].drawing_id_next.get() == "2026-Tanzim-1-STWD"
        assert board._blocks["P2024-1"].drawing_id_next.cget("style") == "Pending.TEntry"
        assert board._blocks["P2024-1"].title_next.get() == "Drawing"
    finally:
        root.destroy()


def test_paired_pdf_survives_a_jira_id_edit(tmp_path) -> None:
    root = _board_root()
    try:
        from doccon.match import pair_pdf

        pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
        pdf.write_bytes(b"%PDF")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([pair_pdf(_row(key="P2024-1", drawing_id="2026-Tanzim-1-1"), pdf)])
        block = board._blocks["P2024-1"]
        block.drawing_id_next.set("2026-Tanzim-1-STWD")
        root.update_idletasks()
        assert str(block.pdf_label.cget("text")) == pdf.name
        assert "disabled" not in str(block.open_btn.cget("state"))
        row = board.pending_rows()[0]
        assert row.pdf is not None and row.pdf.path == pdf
        assert row.confidence == "High"
        assert board.current_rows()[0].pdf is not None
        assert board.selected_rows()[0].pdf is not None
    finally:
        root.destroy()


def test_letter_and_eddi_print_the_effective_jira_id(tmp_path) -> None:
    root = _board_root()
    try:
        from doccon.client_log import lines_from_rows
        from doccon.eddi import eddi_print_drawings, item_values
        from doccon.match import pair_pdf

        pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
        pdf.write_bytes(b"%PDF")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                pair_pdf(
                    _row(
                        key="P2024-1",
                        drawing_id="2026-Tanzim-1-1",
                        title="Drawing",
                        eddi_status="1 - Fabrication Drawings - EDDI",
                    ),
                    pdf,
                )
            ]
        )
        board._blocks["P2024-1"].drawing_id_next.set("2026-Tanzim-1-STWD")
        assert [line.document_no for line in lines_from_rows(board.selected_rows())] == [
            "2026-Tanzim-1-STWD"
        ]
        printed = eddi_print_drawings(board.current_rows())
        assert [item_values(drawing)[0] for drawing in printed] == ["2026-Tanzim-1-STWD"]
    finally:
        root.destroy()


def test_row_key_for_y_maps_band() -> None:
    bands = [("P2024-1", 100, 180), ("P2024-2", 180, 260)]
    assert row_key_for_y(bands, 100) == "P2024-1"
    assert row_key_for_y(bands, 179) == "P2024-1"
    assert row_key_for_y(bands, 180) == "P2024-2"
    assert row_key_for_y(bands, 259) == "P2024-2"
    assert row_key_for_y(bands, 99) is None
    assert row_key_for_y(bands, 260) is None
    assert row_key_for_y([], 120) is None


def test_row_key_at_y_on_stub_board(tmp_path) -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
            ]
        )
        root.update_idletasks()
        first = board._blocks["P2024-1"].drawing_label
        second = board._blocks["P2024-2"].drawing_label
        x = int(first.winfo_rootx()) + 2
        y1 = int(first.winfo_rooty()) + max(int(first.winfo_height()) // 2, 1)
        y2 = int(second.winfo_rooty()) + max(int(second.winfo_height()) // 2, 1)
        assert board.row_key_at(x, y1) == "P2024-1"
        assert board.row_key_at(x, y2) == "P2024-2"
        assert row_key_for_y(board.row_bands(), y1) == "P2024-1"
        assert row_key_for_y(board.row_bands(), y2) == "P2024-2"
        widgets = board.drop_target_widgets()
        assert board._inner in widgets
        assert board._freeze_inner in widgets
        dest = tmp_path / "2026-Tanzim"
        dest.mkdir()
        assert dest.name == "2026-Tanzim"
    finally:
        root.destroy()


def test_eddi_picker_offers_only_that_rows_own_options() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        sub_task = ("", "1 - Fabrication Drawings - EDDI", "4 - Engineering - EDDI")
        task = ("", "8 - Document Control - EDDI", "4 - Engineering - EDDI")
        board.set_eddi_options({"P2024-1": sub_task, "P2024-9": task})
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
                _row(key="P2024-9", drawing_id="2026-Tanzim-ITP-1"),
                _row(key="P2024-3", drawing_id="2026-Tanzim-1-3"),
            ]
        )
        first = [str(item) for item in board._blocks["P2024-1"].nexts["eddi_status"].cget("values")]
        other = [str(item) for item in board._blocks["P2024-9"].nexts["eddi_status"].cget("values")]
        assert first == list(sub_task)
        assert "8 - Document Control - EDDI" not in first
        assert "1 - Fabrication Drawings - EDDI" not in other
        # No context for this row: the Elite convenience list stays.
        unmapped = [str(item) for item in board._blocks["P2024-3"].nexts["eddi_status"].cget("values")]
        assert "0 - Generic Task" in unmapped
        # Batch stamp only offers what every listed issue's context has.
        batch = [str(item) for item in board._batch_fields["eddi_status"].cget("values")]
        assert batch == ["", "4 - Engineering - EDDI"]
        board._apply_next_to_block(
            board._blocks["P2024-9"], fields={"eddi_status": "1 - Fabrication Drawings - EDDI"}
        )
        assert board._blocks["P2024-9"].nexts["eddi_status"].get() == ""
    finally:
        root.destroy()


def _click(widget: tk.Misc) -> None:
    widget.event_generate("<Button-1>", x=4, y=4)


def _two_rows() -> list[MatchedRow]:
    return [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]


def test_clicking_a_row_bands_it_and_clears_the_one_it_left() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(_two_rows())
        first = board._blocks["P2024-1"]
        second = board._blocks["P2024-2"]
        assert board.explicit_focus_key() == ""
        assert not first.focused and not second.focused

        _click(first.drawing_label)
        root.update_idletasks()
        assert board.explicit_focus_key() == "P2024-1"
        assert first.focused and not second.focused
        assert str(first.drawing_label.cget("style")) == "Focus.TLabel"
        assert str(second.drawing_label.cget("style")) == "Board.TLabel"

        _click(second.title_label)
        root.update_idletasks()
        assert board.explicit_focus_key() == "P2024-2"
        assert second.focused and not first.focused
        assert str(second.drawing_label.cget("style")) == "Focus.TLabel"
        # The row it left goes all the way back, not just the cell that was clicked.
        assert str(first.drawing_label.cget("style")) == "Board.TLabel"
        assert str(first.title_label.cget("style")) == "Board.TLabel"
        assert all(str(line.cget("background")) == BORDER for line in first.rules)
    finally:
        root.destroy()


def test_focus_band_covers_the_frozen_and_the_scrolling_pane() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(_two_rows())
        block = board._blocks["P2024-1"]
        board.focus_key("P2024-1")
        root.update_idletasks()
        # Frozen pane (Pack / JIRA ID) and scrolling pane are two separate grids.
        assert block.drawing_label.master is board._freeze_inner
        assert block.title_label.master is board._inner
        assert str(block.drawing_label.cget("style")) == "Focus.TLabel"
        for label in (block.title_label, block.status_label, *block.originals.values()):
            assert str(label.cget("style")) == "Focus.TLabel"
        assert str(block.match_label.cget("style")) == "FocusBad.TLabel"
        # The rules bracket the block in both panes, so a sideways scroll cannot split it.
        assert {line.master for line in block.rules} == {board._inner, board._freeze_inner}
        assert all(str(line.cget("background")) == FOCUS_RULE for line in block.rules)
    finally:
        root.destroy()


def test_pack_tick_does_not_band_a_row_even_when_it_stamps_a_cover_date() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(
            root,
            on_open_pdf=lambda _key: None,
            cover_return_stamp=lambda: "2026-09-15",
        )
        board.set_rows(_two_rows(), checked=set())
        for key in ("P2024-1", "P2024-2"):
            board._blocks[key].include.set(True)
        root.update_idletasks()
        # The tick really did stamp Next, so this is not passing by doing nothing.
        assert board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-15"
        assert board._blocks["P2024-2"].nexts["return_request_date"].get() == "2026-09-15"
        # A Pack tick is not a cursor: nothing is banded and a paste still has no target.
        assert board.explicit_focus_key() == ""
        assert not any(block.focused for block in board._blocks.values())
        assert str(board._blocks["P2024-2"].drawing_label.cget("style")) == "Board.TLabel"
    finally:
        root.destroy()


def test_batch_apply_does_not_band_a_row() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(_two_rows())
        assert board.apply_next_to_pack(status="IFI") == 2
        assert board.bump_packed_revs() == 2
        root.update_idletasks()
        assert board._blocks["P2024-1"].status_next.get() == "IFI"
        assert board.explicit_focus_key() == ""
        assert not any(block.focused for block in board._blocks.values())
    finally:
        root.destroy()


def test_dirty_next_stays_yellow_on_a_banded_row() -> None:
    root = _board_root()
    try:
        assert FOCUS_BG != PENDING_BG
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(_two_rows())
        block = board._blocks["P2024-1"]
        board.focus_key("P2024-1")
        box = block.nexts["client_document_number"]
        box.set("CNRL-T-101")
        root.update_idletasks()
        assert block.focused
        assert box.cget("style") == "Pending.TEntry"
        cell = board._next_cell(box)
        assert cell is not None
        # The band never reaches into a Next cell, so yellow is still the only amber.
        assert str(cell.cget("bg")).casefold() == PENDING_BG.casefold()
        assert str(block.drawing_label.cget("style")) == "Focus.TLabel"
    finally:
        root.destroy()


def test_stamp_outgoing_rev_from_filename_does_not_move_focus() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(
            [
                _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                _row(key="P2024-2", drawing_id="2026-Tanzim-1-2", outgoing_rev="A"),
            ]
        )
        board.focus_key("P2024-2")
        assert board.stamp_outgoing_rev("P2024-1", "0")
        assert board.explicit_focus_key() == "P2024-2"
        box = board._blocks["P2024-1"].nexts["outgoing_rev"]
        assert box.get() == "0"
        assert box.cget("style") == "Pending.TCombobox"
        pending = {row.drawing.key: row.drawing.outgoing_rev for row in board.pending_rows()}
        assert pending["P2024-1"] == "0"
        assert not board.stamp_outgoing_rev("P2024-1", "")
        assert box.get() == "0"
        assert board.stamp_outgoing_rev("P2024-2", "A")
        same = board._blocks["P2024-2"].nexts["outgoing_rev"]
        assert same.get() == "A"
        assert "Pending" not in str(same.cget("style") or "")
    finally:
        root.destroy()


def test_set_rows_does_not_stamp_outgoing_rev_from_a_pdf_filename() -> None:
    """Load hunt paints the match; it must not yellow Next Outgoing Rev."""
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        hit = PdfHit(
            path=Path("2026-Tanzim-1-1 REV 0.pdf"),
            drawing_id="2026-Tanzim-1-1",
            rev="0",
        )
        board.set_rows(
            [
                replace(
                    _row(key="P2024-1", drawing_id="2026-Tanzim-1-1", outgoing_rev="A"),
                    pdf=hit,
                    confidence="High",
                )
            ]
        )
        box = board._blocks["P2024-1"].nexts["outgoing_rev"]
        assert box.get() == "A"
        assert "Pending" not in str(box.cget("style") or "")
        assert board.pending_rows() == []
    finally:
        root.destroy()


def test_email_dropped_pdf_keeps_its_yellow_on_a_banded_row(tmp_path) -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        dropped = replace(
            _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
            pdf=PdfHit(path=tmp_path / "scan0042.pdf", drawing_id="", rev="", email_dropped=True),
            confidence="High",
        )
        board.set_rows([dropped])
        block = board._blocks["P2024-1"]
        board.focus_key("P2024-1")
        root.update_idletasks()
        assert block.focused
        assert str(block.pdf_label.cget("text")) == "scan0042.pdf — email dropped"
        assert EMAIL_DROPPED_LABEL in str(block.pdf_label.cget("text"))
        assert str(block.pdf_label.cget("style")) == "Pending.TLabel"
        assert str(block.pdf_cell.cget("bg")).casefold() == PENDING_BG.casefold()
    finally:
        root.destroy()


def test_rename_button_only_for_email_dropped_in_dropped(tmp_path) -> None:
    root = _board_root()
    try:
        from doccon.drop_pdfs import write_pdf_bytes_into_dropped

        job = tmp_path / "2026-Tanzim"
        staged = write_pdf_bytes_into_dropped(job, "scan0042.pdf", b"%PDF-drop")
        current = tmp_path / "Current PDF" / "2026-Tanzim-1-2 REV 0.pdf"
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(b"%PDF")
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        dropped = replace(
            _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
            pdf=PdfHit(path=staged, drawing_id="", rev="", email_dropped=True),
            confidence="High",
        )
        located = pair_pdf(_row(key="P2024-2", drawing_id="2026-Tanzim-1-2"), current)
        board.set_rows([dropped, located])
        root.update_idletasks()
        email_block = board._blocks["P2024-1"]
        locate_block = board._blocks["P2024-2"]
        assert str(email_block.rename_btn.winfo_manager()) == "pack"
        cluster = list(email_block.locate_btn.master.pack_slaves())
        assert cluster == [
            email_block.locate_btn,
            email_block.rename_btn,
            email_block.open_btn,
            email_block.preview_btn,
        ]
        assert str(locate_block.rename_btn.winfo_manager()) != "pack"
        locate_cluster = list(locate_block.locate_btn.master.pack_slaves())
        assert locate_cluster == [
            locate_block.locate_btn,
            locate_block.open_btn,
            locate_block.preview_btn,
        ]
        assert board.suggested_dropped_name("P2024-1") == "2026-Tanzim-1-1 REV A.pdf"
    finally:
        root.destroy()


def test_load_repaint_clears_a_stale_focus() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows(_two_rows())
        board.focus_key("P2024-2")
        root.update_idletasks()
        assert board.explicit_focus_key() == "P2024-2"

        board.set_rows(_two_rows())
        root.update_idletasks()
        assert board.explicit_focus_key() == ""
        assert not any(block.focused for block in board._blocks.values())
        block = board._blocks["P2024-2"]
        assert str(block.drawing_label.cget("style")) == "Board.TLabel"
        assert all(str(line.cget("background")) == BORDER for line in block.rules)
    finally:
        root.destroy()


def test_banding_a_row_leaves_the_next_editor_gestures_alone() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(title="SPIRAL STAIRWAY")])
        block = board._blocks["P2024-1"]
        box = block.title_next
        board._canvas.focus_set()
        root.update()

        # Single click bands the row and leaves the editor shut (1.34 gesture).
        _click(box)
        root.update()
        assert block.focused
        assert board.explicit_focus_key() == "P2024-1"
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is not box

        before = {id(win) for win in _tk_toplevels(root)}
        board._on_next_double1(SimpleNamespace(widget=box))
        root.update()
        assert {id(win) for win in _tk_toplevels(root)} == before
        assert str(box.cget("state")) == "normal"
        assert board._active_next is box
        box.insert("end", " X")
        board._on_next_escape(SimpleNamespace(widget=box))
        root.update()
        assert box.get() == "SPIRAL STAIRWAY"
        assert str(box.cget("state")) == "readonly"
        assert board._active_next is None
        # Leaving the editor does not clear the band: the row is still the paste target.
        assert block.focused
        assert board.explicit_focus_key() == "P2024-1"
    finally:
        root.destroy()


def test_preview_grab_writes_yellow_next_description() -> None:
    root = _board_root()
    try:
        board = DrawingBoard(root, on_open_pdf=lambda _key: None)
        board.set_rows([_row(key="P2024-1", title="Drawing")])
        root.update_idletasks()
        assert board.set_next_description("P2024-1", "FLOOR REPAIR DETAIL") is True
        root.update_idletasks()
        block = board._blocks["P2024-1"]
        assert block.title_next.get() == "FLOOR REPAIR DETAIL"
        assert block.title_next.cget("style") == "Pending.TEntry"
        assert board.next_edits() == {"P2024-1": {"title": "FLOOR REPAIR DETAIL"}}
        assert board.set_next_description("P2024-1", "1") is False
        assert block.title_next.get() == "FLOOR REPAIR DETAIL"
        assert board.set_next_description("missing", "FLOOR REPAIR DETAIL") is False
    finally:
        root.destroy()
