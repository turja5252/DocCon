# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk

import pytest

from doccon.theme import (
    ACCENT,
    BG,
    BORDER,
    FOCUS_BG,
    FOCUS_RULE,
    SELECT_BG,
    SELECT_RULE,
    FOLDER,
    JIRA,
    NAVY,
    PENDING_BG,
    SCROLL_THUMB,
    SCROLL_TROUGH,
    SURFACE,
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


def test_focused_row_band_is_palette_and_never_the_pending_amber() -> None:
    # Selected row is a darker orange. Dirty Next stays the pale yellow.
    assert SELECT_BG != BORDER
    assert SELECT_BG != PENDING_BG
    assert SELECT_RULE != ACCENT
    assert FOCUS_BG not in {BG, SURFACE, PENDING_BG, BORDER, SELECT_BG}
    assert FOCUS_RULE == ACCENT
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        style = apply_theme(root)
        for name in ("Focus.TLabel", "FocusOk.TLabel", "FocusBad.TLabel"):
            assert style.lookup(name, "background") == SELECT_BG
        assert style.lookup("Focus.TLabel", "background") != style.lookup("Board.TLabel", "background")
        assert style.lookup("FocusOk.TLabel", "foreground") == style.lookup("Ok.TLabel", "foreground")
        assert style.lookup("FocusBad.TLabel", "foreground") == style.lookup("Bad.TLabel", "foreground")
        assert style.lookup("TEntry", "fieldbackground", ["focus"]) == FOCUS_BG
        assert style.lookup("TCombobox", "fieldbackground", ["focus"]) == FOCUS_BG
        assert style.lookup("Pending.TEntry", "fieldbackground", ["focus"]) == PENDING_BG
        assert style.lookup("Pending.TCombobox", "fieldbackground", ["focus"]) == PENDING_BG
        assert match_style("High", focused=True) == "FocusOk.TLabel"
        assert match_style("Missing", focused=True) == "FocusBad.TLabel"
        assert match_style("Review", focused=True) == "Focus.TLabel"
        assert match_style("High") == "Ok.TLabel"
    finally:
        root.destroy()


def test_scrollbar_thumb_contrasts_trough_and_navy() -> None:
    assert SCROLL_THUMB != SCROLL_TROUGH
    assert SCROLL_THUMB != NAVY
    assert SCROLL_THUMB != BG
    assert SCROLL_TROUGH != BG
