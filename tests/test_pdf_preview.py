# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pymupdf
import pytest

from doccon.pdf_preview import close_pdf_preview, open_pdf_preview


def _sample_pdf(folder: Path) -> Path:
    path = folder / "2026-Tanzim-1-1 REV 0.pdf"
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 120), "FLOOR REPAIR DETAIL", fontsize=16)
        doc.save(path)
    finally:
        doc.close()
    return path


def test_preview_window_opens_and_closes(tmp_path: Path) -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    grabbed: list[str] = []
    try:
        pdf = _sample_pdf(tmp_path)
        dialog = open_pdf_preview(
            root,
            pdf,
            heading="2026-Tanzim-1-1",
            on_grab=lambda text: grabbed.append(text) or True,
        )
        root.update_idletasks()
        assert dialog.winfo_exists()
        assert "2026-Tanzim-1-1" in str(dialog._heading.cget("text"))
        again = open_pdf_preview(root, pdf, heading="retarget", on_grab=lambda _text: True)
        assert again is dialog
        close_pdf_preview()
        root.update_idletasks()
        assert not dialog.winfo_exists()
        assert grabbed == []
    finally:
        close_pdf_preview()
        root.destroy()
