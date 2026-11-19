# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""A pasted PDF survives a send. Sarah sends ST, FT, and CT minutes apart with the same rows."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from doccon.match import MatchedRow
from doccon.register import DrawingRow

JOB = "2026-Tanzim"


def _row(key: str, drawing_id: str) -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} Drawing",
            drawing_id=drawing_id,
            title="Drawing",
            status="To Do",
            job_number=JOB,
            outgoing_rev="A",
            purpose="Info",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )


def _app(tmp_path: Path, monkeypatch, *, packed: set[str]):
    """A loaded console on the sandbox job, in a tmp folder. Usage is not recorded."""
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    folder = tmp_path / JOB
    (folder / "3.0 Doc Con").mkdir(parents=True, exist_ok=True)
    rows = [_row("P2024-1", "2026-Tanzim-1-1"), _row("P2024-2", "2026-Tanzim-1-2")]
    app._job_number = JOB
    app._job_folder = folder
    app._matches = {row.drawing.key: row for row in rows}
    app.board.set_rows(rows, checked=set(packed))
    app.board.focus_key("")
    messages: list[str] = []
    monkeypatch.setattr(app, "_refresh_cover_hint", lambda *_a, **_k: None)
    monkeypatch.setattr("doccon.gui.record_transmittal", lambda **_kw: None)
    for name in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(f"doccon.gui.messagebox.{name}", lambda _t, message, **_kw: messages.append(message))
    app._test_messages = messages
    return app


def _paste_and_assign(app, monkeypatch, tmp_path: Path, name: str, key: str) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir(exist_ok=True)
    source = inbox / name
    source.write_bytes(b"%PDF-1.4\nstub\n")
    monkeypatch.setattr("doccon.gui.clipboard_pdfs", lambda *_a, **_k: [source])
    app._paste_pdf()
    app.update()
    app.board.focus_key(key)
    app._new_pdf_list.selection_set(0)
    app._assign_new_pdf()
    app.update()
    extra = app._extra_item(key)
    if extra is not None:
        return Path(extra.path)
    return app._matches[key].pdf.path


def test_a_send_keeps_pasted_pdfs_and_packed_non_jira_rows(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch, packed={"P2024-1"})
    try:
        drawing_pdf = _paste_and_assign(app, monkeypatch, tmp_path, "2026-Tanzim-1-1 REV 0.pdf", "P2024-1")
        app._add_blank_extra()
        app.update()
        extra_id = app._current_extras()[0].id
        extra_pdf = _paste_and_assign(app, monkeypatch, tmp_path, "MID-2026-Tanzim-1.pdf", extra_id)
        assert "dropped" in drawing_pdf.parts and "dropped" in extra_pdf.parts

        rows = app._selected_rows()
        app._pack_issued("ST-2026-Tanzim-1", None, "", "", app._job_folder, JOB, rows, True, True, "shop")
        app.kind.set("field")
        app._kind_changed()
        app.update()

        assert drawing_pdf.is_file()
        assert app._matches["P2024-1"].pdf.path == drawing_pdf
        assert [row.drawing.key for row in app._selected_rows()] == ["P2024-1"]
        extras = app._current_extras()
        assert [(item.id, Path(item.path), item.packed) for item in extras] == [(extra_id, extra_pdf, True)]
        assert extra_pdf.is_file()

        app._both_issued(
            "ST-2026-Tanzim-2", None, "", "", True, "FT-2026-Tanzim-1", None, "", "", True,
            True, app._job_folder, JOB, rows,
        )
        assert drawing_pdf.is_file()
        assert extra_pdf.is_file()
        assert [item.id for item in app._current_extras() if item.packed] == [extra_id]
    finally:
        app.destroy()


@pytest.mark.parametrize("kind", ["client", "both"])
def test_create_transmittal_stops_when_a_packed_pdf_is_gone(tmp_path: Path, monkeypatch, kind: str) -> None:
    """The letter would list the drawing and the zip or folder copy would skip it."""
    app = _app(tmp_path, monkeypatch, packed={"P2024-1"})
    try:
        pasted = _paste_and_assign(app, monkeypatch, tmp_path, "2026-Tanzim-1-1 REV 0.pdf", "P2024-1")
        pasted.unlink()
        monkeypatch.setattr(
            "doccon.gui.prepare_book", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("book opened"))
        )
        app.kind.set(kind)
        app._issue_pack()
        assert app._test_messages[-1] == (
            "2026-Tanzim-1-1: 2026-Tanzim-1-1 REV 0.pdf is missing. Paste it again, or Locate it."
        )
    finally:
        app.destroy()


def test_locate_on_a_non_jira_row_keeps_its_typed_next_values(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path, monkeypatch, packed=set())
    try:
        app._add_blank_extra()
        app.update()
        current = app._current_extras()[0]
        block = app.board._blocks[current.id]
        block.nexts["client_document_number"].set("CLIENT-77")
        block.nexts["outgoing_rev"].set("B")
        current = app._extra_item(current.id)
        assert current.fields["client_document_number"] == "CLIENT-77"

        located = tmp_path / "MID-2026-Tanzim-1 REV 2.pdf"
        located.write_bytes(b"%PDF-1.4\nstub\n")
        app._replace_extra_file(current, located)

        item = app._extra_item(current.id)
        assert item.path == str(located)
        assert item.fields["client_document_number"] == "CLIENT-77"
        assert item.fields["outgoing_rev"] == "2"
        assert item.rev == "2"
        after = app.board._blocks[current.id]
        assert after.nexts["client_document_number"].get() == "CLIENT-77"
        assert after.nexts["outgoing_rev"].get() == "2"
    finally:
        app.destroy()
