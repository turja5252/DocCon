# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import contextlib
import threading
import time
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import ttk

import pytest

from doccon.match import MatchedRow, PdfHit, pair_pdf
from doccon.register import DrawingRow, JobProject
from doccon.theme import FOLDER, IDENTITY_MISSING, JIRA


def _pack_row(
    *,
    key: str = "P2024-1",
    title: str = "Drawing",
    outgoing_rev: str = "A",
    submission_date: str = "",
    return_request_date: str = "",
) -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary="2026-Tanzim-1-1 Drawing",
            drawing_id="2026-Tanzim-1-1",
            title=title,
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev=outgoing_rev,
            purpose="Info",
            parent_summary="Drawing Package",
            submission_date=submission_date,
            return_request_date=return_request_date,
        ),
        pdf=None,
        confidence="Missing",
    )


def test_job_identity_labels_and_colors(tmp_path: Path, monkeypatch) -> None:
    try:
        from doccon.gui import NO_ROW_PDF, DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    opened: list[Path] = []
    infos: list[str] = []
    errors: list[str] = []
    located: list[str] = []

    def _info(_title: str, message: str, **_kw: object) -> None:
        infos.append(message)

    def _error(_title: str, message: str, **_kw: object) -> None:
        errors.append(message)

    monkeypatch.setattr("doccon.gui.messagebox.showinfo", _info)
    monkeypatch.setattr("doccon.gui.messagebox.showerror", _error)
    app._open_path = opened.append
    app._locate_pdf = lambda key="": located.append(key)  # type: ignore[method-assign]
    try:
        folder = Path("dummy") / "2.1 Current Jobs" / "2026-Tanzim"
        app._set_job_identity(JobProject(key="P2024-15553", summary="2026-Tanzim Test"), folder)
        assert "P2024-15553" in app._jira_value.cget("text")
        assert "2026-Tanzim Test" in app._jira_value.cget("text")
        assert "2.1 Current Jobs" in app._folder_value.cget("text")
        assert "2026-Tanzim" in app._folder_value.cget("text")
        assert app._jira_title.cget("fg") == JIRA
        assert app._folder_title.cget("fg") == FOLDER
        assert app._jira_title.cget("fg") != app._folder_title.cget("fg")
        assert app._jira_bar.cget("bg") == JIRA
        assert app._folder_bar.cget("bg") == FOLDER
        assert app._jira_bar.cget("bg") != app._folder_bar.cget("bg")
        assert app._jira_value.cget("fg") != IDENTITY_MISSING
        assert app._folder_value.cget("fg") != IDENTITY_MISSING

        app._set_job_identity(None, None)
        assert "No Jira Project for this Job Number" in app._jira_value.cget("text")
        assert "No Dropbox folder for this Job Number" in app._folder_value.cget("text")
        assert app._jira_value.cget("fg") == IDENTITY_MISSING
        assert app._folder_value.cget("fg") == IDENTITY_MISSING
        assert app._jira_title.cget("fg") == JIRA
        assert app._folder_title.cget("fg") == FOLDER

        missing_row = _pack_row()
        app._matches[missing_row.drawing.key] = missing_row
        app._open_pdf_key("P2024-1")
        assert opened == []
        assert located == []
        assert infos == [NO_ROW_PDF]
        assert errors == []

        pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
        pdf.write_bytes(b"%PDF")
        matched = pair_pdf(missing_row, pdf)
        app._matches[matched.drawing.key] = matched
        app._open_pdf_key("P2024-1")
        assert opened == [pdf]
        assert located == []

        opened.clear()
        infos.clear()
        gone = tmp_path / "gone.pdf"
        app._matches["P2024-1"] = MatchedRow(
            drawing=missing_row.drawing,
            pdf=PdfHit(path=gone, drawing_id="2026-Tanzim-1-1", rev="0"),
            confidence="High",
        )
        app._open_pdf_key("P2024-1")
        assert opened == []
        assert located == []
        assert errors
        assert "gone.pdf" in errors[-1]
    finally:
        app.destroy()


def test_open_row_pdf_calls_opener(tmp_path: Path) -> None:
    from doccon.gui import NO_ROW_PDF, open_row_pdf

    pdf = tmp_path / "2026-Tanzim-1-1 REV 0.pdf"
    pdf.write_bytes(b"%PDF")
    opened: list[Path] = []
    assert open_row_pdf(pdf, opener=opened.append) is None
    assert opened == [pdf]

    opened.clear()
    assert open_row_pdf(None, opener=opened.append) == NO_ROW_PDF
    assert opened == []

    gone = tmp_path / "missing.pdf"
    opened.clear()
    missing = open_row_pdf(gone, opener=opened.append)
    assert opened == []
    assert missing is not None
    assert "not on disk" in missing
    assert "missing.pdf" in missing

    def boom(_path: Path) -> None:
        raise OSError("reader failed")

    assert open_row_pdf(pdf, opener=boom) == "reader failed"


def test_expected_return_stamps_packed_return_request(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client

    writes: list[str] = []

    def _bang(*_args, **_kwargs):
        writes.append("jira")
        raise AssertionError("expected-return stamp must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
    monkeypatch.setattr(jira_client, "transition_drawing", _bang)
    monkeypatch.setattr(jira_client, "apply_jira_updates", _bang)
    monkeypatch.setattr(jira_client, "run_jira_register_update", _bang)
    try:
        app.board.set_rows(
            [_pack_row(key="P2024-1"), _pack_row(key="P2024-2")],
            checked=set(),
        )
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-09-22")
        app.board._blocks["P2024-1"].include.set(True)
        app.update_idletasks()
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert app.board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-10-01")
        app._on_expected_return_change()
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-10-01"
        assert app.board._blocks["P2024-2"].nexts["return_request_date"].get() == ""
        app.expected.delete(0, "end")
        app._on_expected_return_change()
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == ""
        assert writes == []
    finally:
        app.destroy()


def test_date_issued_stamps_packed_submission(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client

    writes: list[str] = []

    def _bang(*_args, **_kwargs):
        writes.append("jira")
        raise AssertionError("date-issued stamp must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
    monkeypatch.setattr(jira_client, "transition_drawing", _bang)
    monkeypatch.setattr(jira_client, "apply_jira_updates", _bang)
    monkeypatch.setattr(jira_client, "run_jira_register_update", _bang)
    try:
        app.board.set_rows(
            [_pack_row(key="P2024-1"), _pack_row(key="P2024-2")],
            checked=set(),
        )
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-11")
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-09-22")
        app.board._blocks["P2024-1"].include.set(True)
        app.update_idletasks()
        assert app.board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-11"
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        assert app.board._blocks["P2024-2"].nexts["submission_date"].get() == ""
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-15")
        app._on_issued_change()
        assert app.board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-09-15"
        assert app.board._blocks["P2024-2"].nexts["submission_date"].get() == ""
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-22"
        app.issued.delete(0, "end")
        app._on_issued_change()
        assert app.board._blocks["P2024-1"].nexts["submission_date"].get() == ""
        assert writes == []
    finally:
        app.destroy()


def test_open_and_pack_use_today_as_date_issued(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client

    def _bang(*_args, **_kwargs):
        raise AssertionError("cover date stamp must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    today = date.today().isoformat()
    try:
        assert app.issued.get() == today
        assert app.expected.get() == "N/A"
        app.board.set_rows(
            [_pack_row(key="P2024-1", submission_date=""), _pack_row(key="P2024-2")],
            checked=set(),
        )
        app.board._blocks["P2024-1"].include.set(True)
        app.update_idletasks()
        assert app.board._blocks["P2024-1"].nexts["submission_date"].get() == today
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == ""
        assert app.board._blocks["P2024-2"].nexts["submission_date"].get() == ""
    finally:
        app.destroy()


def test_expected_return_presets_use_issued_and_stamp_packed(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client

    def _bang(*_args, **_kwargs):
        raise AssertionError("expected-return preset must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    try:
        labels = _button_texts(app)
        assert "Urgent same day" in labels
        assert "Urgent +1" in labels
        assert "7 days" in labels
        assert "14 days" in labels
        app.board.set_rows([_pack_row(key="P2024-1")], checked={"P2024-1"})
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-16")
        app._apply_expected_preset(0)
        assert app.expected.get() == "2026-09-16"
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-16"
        app._apply_expected_preset(1)
        assert app.expected.get() == "2026-09-17"
        assert app.board._blocks["P2024-1"].nexts["return_request_date"].get() == "2026-09-17"
        app._apply_expected_preset(7)
        assert app.expected.get() == "2026-09-23"
        app._apply_expected_preset(14)
        assert app.expected.get() == "2026-09-30"
        app.issued.delete(0, "end")
        app.issued.insert(0, "N/A")
        app._apply_expected_preset(0)
        assert app.expected.get() == date.today().isoformat()
        app.issued.delete(0, "end")
        app._apply_expected_preset(1)
        assert app.expected.get() == (date.today() + timedelta(days=1)).isoformat()
    finally:
        app.destroy()


def test_load_starts_cover_na_and_unpacked(tmp_path: Path) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon.pack_state import ClientPack, save_client_pack

    save_client_pack(
        tmp_path,
        ClientPack(
            job_number="2026-Tanzim",
            issued="2026-09-11",
            expected="2026-09-22",
            selected_keys=("P2024-1",),
        ),
    )
    try:
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-11")
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-09-22")
        rows = [
            _pack_row(key="P2024-1", submission_date="2026-08-01"),
            _pack_row(key="P2024-2", submission_date="2026-08-02"),
        ]
        app.board.set_rows(rows, checked={"P2024-1"})
        assert app.board.selected_keys() == ("P2024-1",)
        app._job_folder = tmp_path
        app._job_number = "2026-Tanzim"
        app.board.set_rows(rows, checked=set())
        app._restore_pack(tmp_path, "2026-Tanzim", None)
        assert app.issued.get() == date.today().isoformat()
        assert app.expected.get() == "N/A"
        assert app.board.selected_keys() == ()
        assert app.board._blocks["P2024-1"].nexts["submission_date"].get() == "2026-08-01"
    finally:
        app.destroy()


def test_cancel_next_restores_next_and_cover_na(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client

    writes: list[str] = []

    def _bang(*_args, **_kwargs):
        writes.append("jira")
        raise AssertionError("Cancel Next must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
    monkeypatch.setattr("doccon.drawing_board.messagebox.askyesno", lambda *_a, **_k: True)
    try:
        app.board.set_rows(
            [
                _pack_row(key="P2024-1", title="First", outgoing_rev="A"),
                _pack_row(key="P2024-2", title="Second", outgoing_rev="B"),
            ],
            checked={"P2024-1"},
        )
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-11")
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-09-22")
        packed = app.board._blocks["P2024-1"]
        loose = app.board._blocks["P2024-2"]
        packed.status_next.set("IFI")
        packed.nexts["outgoing_rev"].set("C")
        packed.nexts["submission_date"].set("2026-09-11")
        loose.title_next.set("Changed")
        loose.nexts["client_document_number"].set("CNRL-T-101")
        app.update_idletasks()
        app.board._cancel_next()
        assert packed.status_next.get() == "To Do"
        assert packed.nexts["outgoing_rev"].get() == "A"
        assert packed.nexts["submission_date"].get() == ""
        assert loose.title_next.get() == "Second"
        assert loose.nexts["client_document_number"].get() == ""
        assert app.issued.get() == date.today().isoformat()
        assert app.expected.get() == "N/A"
        assert app.board.selected_keys() == ("P2024-1",)
        assert app.board.pending_rows() == []
        assert writes == []
    finally:
        app.destroy()


def test_load_shows_progress_before_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    try:
        import doccon.gui as gui_mod
        from doccon.gui import DocConApp
        from doccon.register import JobProject
        from doccon.settings import AppSettings
    except tk.TclError:
        pytest.skip("Tk is not available")
    infos: list[str] = []
    monkeypatch.setattr(gui_mod, "_session", lambda: (AppSettings(email="sarah@example.com"), "token"))
    monkeypatch.setattr(gui_mod.messagebox, "showinfo", lambda _t, message, **_k: infos.append(message))
    monkeypatch.setattr(gui_mod.messagebox, "showerror", lambda _t, message, **_k: infos.append(message))
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    drawing = _pack_row().drawing
    started = threading.Event()
    release = threading.Event()
    statuses: list[str] = []
    original_status = app._set_status

    def _status(text: str) -> None:
        statuses.append(text)
        original_status(text)

    def _fetch(*_args, **_kwargs):
        started.set()
        assert release.wait(4)
        return [drawing], JobProject(key="P2024-15553", summary="2026-Tanzim Test")

    monkeypatch.setattr(app, "_set_status", _status)
    monkeypatch.setattr(app, "_settings", lambda: None)
    monkeypatch.setattr(gui_mod, "fetch_job_pack", _fetch)
    monkeypatch.setattr(gui_mod, "fetch_rev_option_lists", lambda *_a, **_k: {})
    monkeypatch.setattr(gui_mod, "resolve_job_folder", lambda _job: tmp_path)
    monkeypatch.setattr(gui_mod, "scan_current_pdfs", lambda _folder: [])
    monkeypatch.setattr(gui_mod, "adopt_transmittal_books", lambda *_a, **_k: [])
    monkeypatch.setattr(gui_mod, "find_pep", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "load_client_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "save_client_pack", lambda *_a, **_k: None)
    try:
        app.job.delete(0, "end")
        app.job.insert(0, "2026-Tanzim")
        app.update_idletasks()
        assert app.job.get().strip() == "2026-Tanzim"
        app._load()
        assert infos == []
        assert app._work == "load"
        assert app._progress.mode() == "indeterminate"
        assert app._load_meter.winfo_manager() == "pack"
        for _ in range(80):
            app.update()
            if started.wait(0.05):
                break
        assert started.is_set()
        assert any("Loading" in text or "Jira" in text or "Finding" in text for text in statuses)
        assert app.board._blocks == {}
        release.set()
        deadline = time.time() + 5
        while time.time() < deadline:
            app.update()
            if "P2024-1" in app.board._blocks and app._progress.mode() == "idle":
                break
            time.sleep(0.02)
        assert "P2024-1" in app.board._blocks
        assert any("Drawing" in text or "Painting" in text or "Matching" in text for text in statuses)
        assert app.issued.get() == date.today().isoformat()
        assert app.expected.get() == "N/A"
        assert app.board.selected_keys() == ()
        assert app._progress.mode() == "idle"
        assert app._load_meter.winfo_manager() == ""
    finally:
        release.set()
        app.destroy()


def test_restore_next_keeps_pack_off_and_cover_na(tmp_path: Path, monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client
    from doccon.pack_state import ClientPack, save_client_pack

    writes: list[str] = []

    def _bang(*_args, **_kwargs):
        writes.append("jira")
        raise AssertionError("Load restore must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
    monkeypatch.setattr(jira_client, "update_eddi_status", _bang)
    save_client_pack(
        tmp_path,
        ClientPack(
            job_number="2026-Tanzim",
            issued="2026-09-11",
            expected="2026-09-22",
            to_line="client@example.com",
            selected_keys=("P2024-1",),
            next_edits={
                "P2024-1": {"outgoing_rev": "C", "status": "IFI"},
                "P2024-gone": {"outgoing_rev": "Z"},
            },
        ),
    )
    try:
        rows = [_pack_row(key="P2024-1", outgoing_rev="A"), _pack_row(key="P2024-2")]
        app.board.set_rows(rows, checked={"P2024-1"})
        app._job_folder = tmp_path
        app._job_number = "2026-Tanzim"
        app.board.set_rows(rows, checked=set())
        app._restore_pack(tmp_path, "2026-Tanzim", None)
        assert app.board._blocks["P2024-1"].nexts["outgoing_rev"].get() == "C"
        assert app.board._blocks["P2024-1"].status_next.get() == "IFI"
        assert app.board._blocks["P2024-2"].nexts["outgoing_rev"].get() == "A"
        assert app.issued.get() == date.today().isoformat()
        assert app.expected.get() == "N/A"
        assert app.board.selected_keys() == ()
        assert app._email_value(app.to_box) == "client@example.com"
        assert writes == []
    finally:
        app.destroy()


def test_jira_id_next_survives_save_and_load(tmp_path: Path, monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import jira_client
    from doccon.pack_state import load_client_pack

    def _bang(*_args, **_kwargs):
        raise AssertionError("saving or restoring a JIRA ID must not write Jira")

    monkeypatch.setattr(jira_client, "apply_drawing_update", _bang)
    monkeypatch.setattr(jira_client, "update_drawing_fields", _bang)
    try:
        rows = [_pack_row(key="P2024-1", title="Drawing"), _pack_row(key="P2024-2")]
        app._job_folder = tmp_path
        app._job_number = "2026-Tanzim"
        app.board.set_rows(rows, checked={"P2024-1"})
        app.board._blocks["P2024-1"].drawing_id_next.set("2026-Tanzim-1-STWD")
        app.issued.delete(0, "end")
        app.issued.insert(0, "2026-09-11")
        app.expected.delete(0, "end")
        app.expected.insert(0, "2026-09-22")
        assert app._save_pack(quiet=True, force=True)
        saved = load_client_pack(tmp_path, "2026-Tanzim")
        assert saved is not None
        assert saved.next_edits["P2024-1"]["drawing_id"] == "2026-Tanzim-1-STWD"
        assert "P2024-2" not in saved.next_edits

        app.board.set_rows(rows, checked=set())
        app._restore_pack(tmp_path, "2026-Tanzim", None)
        assert app.board._blocks["P2024-1"].drawing_id_next.get() == "2026-Tanzim-1-STWD"
        assert app.board._blocks["P2024-1"].title_next.get() == "Drawing"
        assert app.board._blocks["P2024-2"].drawing_id_next.get() == "2026-Tanzim-1-1"
        assert app.board.selected_keys() == ()
        assert app.issued.get() == date.today().isoformat()
        assert app.expected.get() == "N/A"
        restored = app.board.pending_rows()
        assert [row.drawing.summary for row in restored] == ["2026-Tanzim-1-STWD Drawing"]
    finally:
        app.destroy()


def test_load_saves_current_job_before_switch(tmp_path: Path, monkeypatch) -> None:
    try:
        import doccon.gui as gui_mod
        from doccon.gui import DocConApp
        from doccon.register import JobProject
        from doccon.settings import AppSettings
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    saved: list[str] = []

    def _save(quiet: bool = False, *, force: bool = False) -> bool:
        saved.append(app._job_number)
        return True

    monkeypatch.setattr(gui_mod, "_session", lambda: (AppSettings(email="sarah@example.com"), "token"))
    monkeypatch.setattr(app, "_save_pack", _save)
    monkeypatch.setattr(gui_mod, "fetch_job_pack", lambda *_a, **_k: ([], JobProject(key="P2024-1", summary="Other")))
    monkeypatch.setattr(gui_mod, "fetch_rev_option_lists", lambda *_a, **_k: {})
    monkeypatch.setattr(gui_mod, "resolve_job_folder", lambda _job: tmp_path)
    monkeypatch.setattr(gui_mod, "scan_current_pdfs", lambda _folder: [])
    monkeypatch.setattr(gui_mod, "adopt_transmittal_books", lambda *_a, **_k: [])
    monkeypatch.setattr(gui_mod, "find_pep", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "load_client_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "save_client_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(app, "_settings", lambda: None)
    try:
        app._job_number = "2026-Tanzim"
        app._job_folder = tmp_path
        app.job.delete(0, "end")
        app.job.insert(0, "2026-Other")
        app._load()
        assert saved
        assert saved[0] == "2026-Tanzim"
        assert app._job_number == "2026-Other"
    finally:
        app.destroy()


def test_eddi_fixer_writes_one_value_and_reloads(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import gui as gui_mod
    from doccon.settings import AppSettings

    writes: list[tuple[str, str]] = []
    reloads: list[str] = []

    monkeypatch.setattr(gui_mod, "_session", lambda: (AppSettings(email="sarah@example.com"), "token"))
    monkeypatch.setattr(
        gui_mod,
        "update_eddi_status",
        lambda _site, _email, _token, key, status, _options=(): writes.append((key, status)),
    )
    monkeypatch.setattr(
        app,
        "_ask_eddi_fixes",
        lambda conflicts: {conflicts[0].key: "1 - Fabrication Drawings - EDDI"},
    )
    monkeypatch.setattr(app, "_load", lambda: reloads.append("reload"))
    monkeypatch.setattr(app, "_stop_progress", lambda: None)
    row = _pack_row().drawing
    row = DrawingRow(
        key=row.key,
        summary=row.summary,
        drawing_id=row.drawing_id,
        title=row.title,
        status=row.status,
        job_number=row.job_number,
        outgoing_rev=row.outgoing_rev,
        purpose=row.purpose,
        parent_summary=row.parent_summary,
        eddi_status="1 - Fabrication Drawings - EDDI; 4 - Engineering - EDDI",
    )
    try:
        assert app._resolve_eddi_conflicts([row]) is True
        assert writes == [("P2024-1", "1 - Fabrication Drawings - EDDI")]
        app.update()
        assert reloads == ["reload"]
        assert app._reloading_after_eddi_fix is True
    finally:
        app.destroy()


def test_eddi_fixer_skip_does_not_write(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import gui as gui_mod

    writes: list[str] = []
    reloads: list[str] = []
    monkeypatch.setattr(gui_mod, "update_eddi_status", lambda *_a, **_k: writes.append("jira"))
    monkeypatch.setattr(app, "_ask_eddi_fixes", lambda _conflicts: {})
    monkeypatch.setattr(app, "_load", lambda: reloads.append("reload"))
    row = _pack_row().drawing
    row = DrawingRow(
        key=row.key,
        summary=row.summary,
        drawing_id=row.drawing_id,
        title=row.title,
        status=row.status,
        job_number=row.job_number,
        outgoing_rev=row.outgoing_rev,
        purpose=row.purpose,
        parent_summary=row.parent_summary,
        eddi_status="1 - Fabrication Drawings - EDDI; 4 - Engineering - EDDI",
    )
    try:
        assert app._resolve_eddi_conflicts([row]) is False
        assert writes == []
        assert reloads == []
    finally:
        app.destroy()


def test_eddi_fixer_offers_only_that_issues_options(monkeypatch) -> None:
    try:
        from doccon.gui import DocConApp, EddiConflictDialog
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    from doccon import gui as gui_mod
    from doccon.register import FieldOption
    from doccon.settings import AppSettings

    writes: list[tuple[str, str, tuple]] = []
    monkeypatch.setattr(gui_mod, "_session", lambda: (AppSettings(email="sarah@example.com"), "token"))
    monkeypatch.setattr(
        gui_mod,
        "update_eddi_status",
        lambda _site, _email, _token, key, status, options=(): writes.append((key, status, options)),
    )
    monkeypatch.setattr(app, "_load", lambda: None)
    monkeypatch.setattr(app, "_stop_progress", lambda: None)
    options = (
        FieldOption(label="0 - Generic Task", option_id="10400"),
        FieldOption(label="1 - Fabrication Drawings - EDDI", option_id="10401"),
        FieldOption(label="8 - Document Control - EDDI", option_id="10408"),
    )
    app._eddi_contexts = {"P2024-1": options}
    row = _pack_row().drawing
    row = DrawingRow(
        key=row.key,
        summary=row.summary,
        drawing_id=row.drawing_id,
        title=row.title,
        status=row.status,
        job_number=row.job_number,
        outgoing_rev=row.outgoing_rev,
        purpose=row.purpose,
        parent_summary=row.parent_summary,
        eddi_status="1 - Fabrication Drawings - EDDI; 8 - Document Control - EDDI",
    )
    try:
        conflicts = gui_mod.eddi_conflicts([row], app._eddi_contexts)
        assert conflicts[0].allowed == (
            "1 - Fabrication Drawings - EDDI",
            "8 - Document Control - EDDI",
        )
        dialog = EddiConflictDialog(app, conflicts)
        offered = [str(item) for item in dialog._picks["P2024-1"].cget("values")]
        assert offered == ["", "1 - Fabrication Drawings - EDDI", "8 - Document Control - EDDI"]
        assert "4 - Engineering - EDDI" not in offered
        assert "0 - Generic Task" not in offered
        dialog._skip()
        monkeypatch.setattr(
            app,
            "_ask_eddi_fixes",
            lambda _conflicts: {"P2024-1": "8 - Document Control - EDDI"},
        )
        assert app._resolve_eddi_conflicts([row]) is True
        assert writes == [("P2024-1", "8 - Document Control - EDDI", options)]
    finally:
        app.destroy()


def test_load_many_rows_finishes_without_per_row_drop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    try:
        import doccon.gui as gui_mod
        from doccon.gui import DocConApp
        from doccon.register import JobProject
        from doccon.settings import AppSettings
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    drawings = [
        _pack_row(key=f"P2024-{index}", title=f"Drawing {index}").drawing for index in range(1, 21)
    ]
    sweep_threads: list[str] = []
    original_sweep = gui_mod.sweep_replaced_dropped_copies

    def _sweep(*args, **kwargs):
        sweep_threads.append(threading.current_thread().name)
        return original_sweep(*args, **kwargs)

    monkeypatch.setattr(gui_mod, "_session", lambda: (AppSettings(email="sarah@example.com"), "token"))
    monkeypatch.setattr(gui_mod.messagebox, "showinfo", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod.messagebox, "showerror", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "sweep_replaced_dropped_copies", _sweep)
    monkeypatch.setattr(
        gui_mod,
        "fetch_job_pack",
        lambda *_a, **_k: (drawings, JobProject(key="P2024-15553", summary="2026-Tanzim Test")),
    )
    monkeypatch.setattr(gui_mod, "fetch_rev_option_lists", lambda *_a, **_k: {})
    monkeypatch.setattr(gui_mod, "resolve_job_folder", lambda _job: tmp_path)
    monkeypatch.setattr(gui_mod, "scan_current_pdfs", lambda _folder: [])
    monkeypatch.setattr(gui_mod, "adopt_transmittal_books", lambda *_a, **_k: [])
    monkeypatch.setattr(gui_mod, "find_pep", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "load_client_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_mod, "save_client_pack", lambda *_a, **_k: None)
    monkeypatch.setattr(app, "_settings", lambda: None)
    try:
        app.job.delete(0, "end")
        app.job.insert(0, "2026-Tanzim")
        app._load()
        deadline = time.time() + 20
        while time.time() < deadline:
            app.update()
            if len(app.board._blocks) == 20 and app._progress.mode() == "idle":
                break
            time.sleep(0.02)
        assert len(app.board._blocks) == 20
        assert app._progress.mode() == "idle"
        assert app._work == ""
        assert sweep_threads
        assert all(name != "MainThread" for name in sweep_threads)
        assert not hasattr(app, "_drop_dock")
        assert not hasattr(gui_mod, "DropHost")
        assert not hasattr(gui_mod, "DropBridge")
        assert not hasattr(gui_mod, "HdropHost")
    finally:
        app.destroy()


def _button_texts(widget) -> list[str]:
    texts: list[str] = []
    stack = [widget]
    while stack:
        current = stack.pop()
        with contextlib.suppress(tk.TclError):
            if isinstance(current, ttk.Button | tk.Button):
                texts.append(str(current.cget("text")))
        with contextlib.suppress(tk.TclError):
            stack.extend(current.winfo_children())
    return texts


def test_console_has_paste_pdf_and_no_pdf_from_outlook_button() -> None:
    try:
        from doccon.gui import DocConApp
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        app = DocConApp()
    except tk.TclError:
        pytest.skip("Tk is not available")
    app.withdraw()
    try:
        labels = _button_texts(app)
        assert "Paste PDF" in labels
        assert "PDF from Outlook" not in labels
        assert "Urgent same day" in labels
        assert "Urgent +1" in labels
        assert "7 days" in labels
        assert "14 days" in labels
        assert not hasattr(app, "_pdf_from_outlook")
        assert not hasattr(app, "_outlook_hunt")
    finally:
        app.destroy()
