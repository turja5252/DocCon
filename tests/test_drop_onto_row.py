# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""A drop on a drawing row is the pair. Filename matching does not override it."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from doccon.drop_pdfs import sources_from_paths
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
    app.board.set_rows(rows, checked=set())
    app.board.focus_key("")
    monkeypatch.setattr(app, "_save_pack", lambda **_kw: None)
    monkeypatch.setattr(app, "_refresh_cover_hint", lambda *_a, **_k: None)
    return app


def _drop_pdf(app, path: Path, x: int, y: int) -> None:
    app._apply_drop(sources_from_paths([path]), x, y)
    app.update()


def test_drop_on_a_row_beats_a_filename_that_matches_another_row(
    tmp_path: Path, monkeypatch
) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        monkeypatch.setattr(app.board, "row_key_at", lambda _x, _y: "P2024-2")
        pdf = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
        pdf.write_bytes(b"%PDF-1.4\nstub\n")
        _drop_pdf(app, pdf, 40, 80)
        assert app._matches["P2024-2"].pdf is not None
        assert app._matches["P2024-1"].pdf is None
        address = pdf_address_text(app._matches["P2024-2"])
        assert EMAIL_DROPPED_LABEL in address
        assert address.startswith("2026-Tanzim-1-1 REV A.pdf")
    finally:
        app.destroy()


def test_drop_on_empty_board_pairs_by_filename(tmp_path: Path, monkeypatch) -> None:
    rows = [
        _row(key="P2024-1", drawing_id="2026-Tanzim-1-1"),
        _row(key="P2024-2", drawing_id="2026-Tanzim-1-2"),
    ]
    app = _app_with_rows(tmp_path, monkeypatch, rows)
    try:
        monkeypatch.setattr(app.board, "row_key_at", lambda _x, _y: None)
        pdf = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
        pdf.write_bytes(b"%PDF-1.4\nstub\n")
        _drop_pdf(app, pdf, 40, 80)
        assert app._matches["P2024-1"].pdf is not None
        assert app._matches["P2024-2"].pdf is None
    finally:
        app.destroy()
