# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk

import pytest

from doccon.theme import (
    ACCENT,
    BG,
    FOLDER,
    JIRA,
    NAVY,
    SCROLL_THUMB,
    SCROLL_TROUGH,
    ThemeProgress,
    apply_theme,
    match_style,
)


def test_apply_theme_and_match_styles() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        style = apply_theme(root)
        assert style.lookup("Accent.TButton", "background") == ACCENT
        assert JIRA != FOLDER
        assert style.lookup("BrandJira.TLabel", "foreground") == JIRA
        assert style.lookup("BrandFolder.TLabel", "foreground") == FOLDER
        assert style.lookup("BrandJira.TLabel", "foreground") != style.lookup(
            "BrandFolder.TLabel", "foreground"
        )
        assert SCROLL_THUMB != SCROLL_TROUGH
        assert SCROLL_THUMB != NAVY
        assert SCROLL_THUMB != BG
        assert SCROLL_TROUGH != NAVY
        assert style.lookup("TScrollbar", "background") == SCROLL_THUMB
        assert style.lookup("TScrollbar", "troughcolor") == SCROLL_TROUGH
        assert style.lookup("Horizontal.TScrollbar", "background") == SCROLL_THUMB
        assert style.lookup("Horizontal.TScrollbar", "troughcolor") == SCROLL_TROUGH
        assert style.lookup("Vertical.TScrollbar", "background") == SCROLL_THUMB
        assert style.lookup("Vertical.TScrollbar", "troughcolor") == SCROLL_TROUGH
        assert style.lookup("Pending.TCombobox", "fieldbackground") == "#FEF3C7"
        assert style.lookup("Pending.TEntry", "fieldbackground") == "#FEF3C7"
        assert match_style("High") == "Ok.TLabel"
        assert match_style("Missing") == "Bad.TLabel"
        assert match_style("Review") == "Board.TLabel"
        bar = ThemeProgress(root)
        bar.set_determinate(3, 10)
        assert bar.fraction() == 0.3
        assert bar.mode() == "determinate"
        assert ThemeProgress.FILL != ThemeProgress.TRACK
        assert ThemeProgress.TRACK != NAVY
        assert ThemeProgress.FILL != NAVY
        assert ThemeProgress.BAR_H >= 8
        bar.stop()
        assert bar.mode() == "idle"
        assert not bar.winfo_ismapped()
    finally:
        root.destroy()


def test_scrollbar_thumb_contrasts_trough_and_navy() -> None:
    assert SCROLL_THUMB != SCROLL_TROUGH
    assert SCROLL_THUMB != NAVY
    assert SCROLL_THUMB != BG
    assert SCROLL_TROUGH != BG
