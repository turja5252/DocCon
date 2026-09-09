# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk

import pytest

from doccon.theme import ACCENT, apply_theme, match_style


def test_apply_theme_and_match_styles() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        style = apply_theme(root)
        assert style.lookup("Accent.TButton", "background") == ACCENT
        assert match_style("High") == "Ok.TLabel"
        assert match_style("Missing") == "Bad.TLabel"
        assert match_style("Review") == "Board.TLabel"
    finally:
        root.destroy()
