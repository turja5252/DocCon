# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Paste PDF pairs straight onto the selected row. No second Assign step."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from doccon.match import EMAIL_DROPPED_LABEL, MatchedRow, pdf_address_text
from doccon.register import DrawingRow

JOB = "2026-Tanzim"


def _row(*, key: str, drawing_id: str, title: str = "Drawing") -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} {title}".strip(),
            drawing_id=drawing_id,
            title=title,
            status="To Do",
            job_number=JOB,
            outgoing_rev="A",
            purpose="Info",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )


def _app_with_rows(tmp_path: Path, monkeypatch, rows: list[MatchedRow]):
    """A loaded console on the sandbox job. Never touches a live job folder."""
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()

    job_folder = tmp_path / JOB
    job_folder.mkdir(parents=True, exist_ok=True)
    app._job_number = JOB
    app._job_folder = job_folder
    app._matches = {row.drawing.key: row for row in rows}
    # checked=set() matches a real Load: Pack starts off on every row.
    app.board.set_rows(rows, checked=set())
    app.board.focus_key("")
    monkeypatch.setattr(app, "_save_pack", lambda **_kw: None)
    monkeypatch.setattr(app, "_refresh_cover_hint", lambda *_a, **_k: None)
    return app


def _clipboard_pdf(tmp_path: Path, name: str) -> Path:
    staged = tmp_path / "inbox"
    staged.mkdir(parents=True, exist_ok=True)
    path = staged / name
    path.write_bytes(b"%PDF-1.4\nstub\n")
    return path


def _paste(app, monkeypatch, path: Path, infos: list[str]) -> None:
    _paste_many(app, monkeypatch, [path], infos)


def _paste_many(app, monkeypatch, paths: list[Path], infos: list[str]) -> None:
    monkeypatch.setattr("doccon.gui.clipboard_pdfs", lambda *_a, **_k: list(paths))
    monkeypatch.setattr(
        "doccon.gui.messagebox.showinfo",
        lambda _title, message, **_kw: infos.append(message),
    )
    app._paste_pdf()
    app.update()


def test_selected_row_gets_the_paste_with_no_assign_step(tmp_path: Path, monkeypatch) -> None:
    """The 1.53 bug: paste staged into the watched inbox, so the watcher handed
    the operator's own file straight back to the New PDFs strip ~1.5s later."""
    from doccon.watch_inbox import InboxWatcher

    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        inbox = tmp_path / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        app._watcher = InboxWatcher([inbox], started=0.0, settle_s=0.0, now=lambda: 10_000.0)

        app.board.focus_key("P2024-2")
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "scan0042.pdf"), infos)

        paired = app._matches["P2024-2"]
        assert paired.pdf is not None, "selected row should have been paired by the paste"
        assert app._matches["P2024-1"].pdf is None
        assert app._new_pdfs == [], "nothing should land in the New PDFs strip"
        assert infos == []
        assert paired.pdf.email_dropped is True
        address = pdf_address_text(paired)
        assert EMAIL_DROPPED_LABEL in address
        assert address.startswith("scan0042.pdf"), "the operator must be able to see which file paired"
        # No REV in that Outlook name: leave Jira Now Outgoing Rev alone.
        assert app.board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "A"

        # The watcher must not re-report what the paste just staged.
        app._poll_watch()
        assert app._new_pdfs == [], "paste staging came back as a watched-folder arrival"

        # A genuine arrival in the same folder still fires.
        stray = inbox / "walk-in.pdf"
        stray.write_bytes(b"%PDF-1.4\nstub\n")
        app._poll_watch()
        assert [path.name for path in app._new_pdfs] == ["walk-in.pdf"]
    finally:
        app.destroy()


def test_paste_stamps_outgoing_rev_from_the_filename(tmp_path: Path, monkeypatch) -> None:
    rows = [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1")]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.focus_key("P2024-1")
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "2026-Tanzim-1-1 REV 0.pdf"), infos)
        box = app.board._blocks["P2024-1"].nexts["outgoing_rev"]
        assert box.get() == "0"
        assert box.cget("style") == "Pending.TCombobox"
        pending = {row.drawing.key: row.drawing.outgoing_rev for row in app.board.pending_rows()}
        assert pending["P2024-1"] == "0"
        assert app.board.explicit_focus_key() == "P2024-1"
    finally:
        app.destroy()


def test_selected_row_beats_a_filename_that_matches_another_row(tmp_path: Path, monkeypatch) -> None:
    """Explicit selection always wins over the filename guess."""
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.focus_key("P2024-2")
        infos: list[str] = []
        # This filename matches row 1, but row 2 is the one the operator selected.
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "2026-Tanzim-1-1 REV A.pdf"), infos)

        assert app._matches["P2024-2"].pdf is not None
        assert app._matches["P2024-1"].pdf is None
        assert app._new_pdfs == []
    finally:
        app.destroy()


def test_no_selection_falls_back_to_the_filename_match(tmp_path: Path, monkeypatch) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "2026-Tanzim-1-2 REV A.pdf"), infos)

        assert app._matches["P2024-2"].pdf is not None
        assert app._matches["P2024-1"].pdf is None
        assert app._new_pdfs == []
    finally:
        app.destroy()


def test_many_packed_rows_are_not_a_selection(tmp_path: Path, monkeypatch) -> None:
    """'First of several packed rows' is a guess — fall through to the filename match."""
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.set_pack(True)
        assert len(app.board.selected_keys()) == 2
        assert app._paste_target_key() == ""

        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "some-invoice.pdf"), infos)

        assert app._matches["P2024-1"].pdf is None
        assert app._matches["P2024-2"].pdf is None
        assert len(app._new_pdfs) == 1
    finally:
        app.destroy()


def test_a_single_pack_tick_counts_as_the_selection(tmp_path: Path, monkeypatch) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board._blocks["P2024-2"].include.set(True)
        assert app.board.selected_keys() == ("P2024-2",)
        assert app._paste_target_key() == "P2024-2"

        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "scan0042.pdf"), infos)

        assert app._matches["P2024-2"].pdf is not None
        assert app._matches["P2024-1"].pdf is None
        assert app._new_pdfs == []
    finally:
        app.destroy()


def test_no_selection_and_no_match_parks_it_and_says_select_a_row(tmp_path: Path, monkeypatch) -> None:
    rows = [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1")]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "some-invoice.pdf"), infos)

        assert app._matches["P2024-1"].pdf is None
        assert len(app._new_pdfs) == 1
        assert app._new_pdfs[0].name == "some-invoice.pdf"
        assert infos, "operator should be told to select a row first"
        assert "select" in infos[0].casefold()
        assert "some-invoice.pdf" in app.status.cget("text")
    finally:
        app.destroy()


def test_status_names_the_jira_id_and_the_filename(tmp_path: Path, monkeypatch) -> None:
    rows = [_row(key="P2024-7", drawing_id="2026-Tanzim-1-7")]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.focus_key("P2024-7")
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "scan0042.pdf"), infos)

        status = app.status.cget("text")
        assert "2026-Tanzim-1-7" in status, f"JIRA ID missing from status: {status!r}"
        assert "scan0042.pdf" in status, f"filename missing from status: {status!r}"
    finally:
        app.destroy()


def test_watched_folder_still_leads_with_the_filename_match(tmp_path: Path) -> None:
    """A file appearing in Downloads is not an explicit gesture, so it must not
    hijack whatever row happens to be selected."""
    from doccon.watch_inbox import InboxWatcher, plan_watch_hits

    watched = tmp_path / "Downloads"
    watched.mkdir()
    watcher = InboxWatcher([watched], started=0.0, settle_s=0.0, now=lambda: 10_000.0)
    hit = watched / "2026-Tanzim-1-2 REV A.pdf"
    hit.write_bytes(b"%PDF-1.4\nstub\n")

    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    pairs, unmatched = plan_watch_hits(rows, watcher.poll(), JOB)
    assert pairs == [("P2024-2", hit)], "watcher pairs by filename, not by selection"
    assert unmatched == []


def test_two_pasted_pdfs_wait_in_new_pdfs_even_with_a_selected_row(tmp_path: Path, monkeypatch) -> None:
    """A multi Copy is not a pair — every file waits for Assign."""
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.focus_key("P2024-2")
        infos: list[str] = []
        one = _clipboard_pdf(tmp_path, "scan0042.pdf")
        two = _clipboard_pdf(tmp_path, "scan0043.pdf")
        _paste_many(app, monkeypatch, [one, two], infos)

        assert app._matches["P2024-1"].pdf is None
        assert app._matches["P2024-2"].pdf is None
        assert [path.name for path in app._new_pdfs] == ["scan0042.pdf", "scan0043.pdf"]
        assert infos == []
        status = app.status.cget("text")
        assert "New PDFs" in status
        assert "Assign" in status
    finally:
        app.destroy()


def test_assign_from_new_pdfs_uses_the_clicked_row(tmp_path: Path, monkeypatch) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        infos: list[str] = []
        one = _clipboard_pdf(tmp_path, "scan0042.pdf")
        two = _clipboard_pdf(tmp_path, "scan0043.pdf")
        _paste_many(app, monkeypatch, [one, two], infos)
        app.board.focus_key("P2024-2")
        app._new_pdf_list.selection_clear(0, "end")
        app._new_pdf_list.selection_set(0)
        app._assign_new_pdf()

        paired = app._matches["P2024-2"]
        assert paired.pdf is not None
        assert Path(paired.pdf.path).name == "scan0042.pdf"
        assert paired.pdf.email_dropped is True
        assert app._matches["P2024-1"].pdf is None
        assert [path.name for path in app._new_pdfs] == ["scan0043.pdf"]
    finally:
        app.destroy()


def test_assign_with_several_packed_rows_needs_a_click(tmp_path: Path, monkeypatch) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        infos: list[str] = []
        one = _clipboard_pdf(tmp_path, "scan0042.pdf")
        two = _clipboard_pdf(tmp_path, "scan0043.pdf")
        _paste_many(app, monkeypatch, [one, two], infos)
        app.board.set_pack(True)
        monkeypatch.setattr(
            "doccon.gui.messagebox.showinfo",
            lambda _title, message, **_kw: infos.append(message),
        )
        app._assign_new_pdf()
        assert app._matches["P2024-1"].pdf is None
        assert app._matches["P2024-2"].pdf is None
        assert len(app._new_pdfs) == 2
        assert any("click" in msg.casefold() for msg in infos)
    finally:
        app.destroy()


def test_rename_email_dropped_pdf_not_a_locate_file(tmp_path: Path, monkeypatch) -> None:
    rows = [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1")]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        app.board.focus_key("P2024-1")
        infos: list[str] = []
        _paste(app, monkeypatch, _clipboard_pdf(tmp_path, "scan0042.pdf"), infos)
        paired = app._matches["P2024-1"]
        assert paired.pdf is not None
        old = paired.pdf.path
        monkeypatch.setattr(app, "_ask_rename_pdf", lambda **_k: "2026-Tanzim-1-1 REV 0.pdf")
        app._rename_pdf("P2024-1")
        updated = app._matches["P2024-1"]
        assert updated.pdf is not None
        assert updated.pdf.path.name == "2026-Tanzim-1-1 REV 0.pdf"
        assert updated.pdf.email_dropped is True
        assert EMAIL_DROPPED_LABEL in pdf_address_text(updated)
        assert not old.exists()
        assert updated.pdf.path.is_file()
        assert app.board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "0"
        assert app.board._blocks["P2024-1"].nexts["outgoing_rev"].cget("style") == "Pending.TCombobox"
        cluster = list(app.board._blocks["P2024-1"].locate_btn.master.pack_slaves())
        assert app.board._blocks["P2024-1"].rename_btn in cluster

        real = tmp_path / "Current PDF" / "job.pdf"
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_bytes(b"%PDF-job")
        from doccon.drop_pdfs import replace_paired_pdf

        located = replace_paired_pdf(updated, real)
        app._pair_located(located, remember_folder=False, save=False)
        app.update_idletasks()
        assert not pdf_address_text(app._matches["P2024-1"]).endswith("email dropped")
        assert str(app.board._blocks["P2024-1"].rename_btn.winfo_manager()) != "pack"
    finally:
        app.destroy()
