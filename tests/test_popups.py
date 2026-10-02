# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk
from tkinter import ttk

import pytest

from doccon.popups import center_origin, fit_on_monitor, place_on_parent


def test_fit_keeps_a_tall_dialog_on_the_parent_monitor() -> None:
    x, y = fit_on_monitor(2700, -40, 400, 800, (1920, 0, 3840, 1080))
    assert (x, y) == (2700, 0)
    assert fit_on_monitor(-20, 40, 200, 100, (1920, 0, 3840, 1080))[0] == 1920
    x, y = center_origin(2400, 80, 800, 600, 200, 100)
    assert (x, y) == (2700, 330)


def test_dialog_is_placed_on_the_parent_not_at_the_origin() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.geometry("400x300+140+90")
    try:
        root.update()
        dialog = tk.Toplevel(root)
        dialog.withdraw()
        ttk.Label(dialog, text="On this screen").pack(padx=16, pady=16)
        place_on_parent(dialog)
        dialog.update_idletasks()
        parts = str(dialog.geometry()).split("+")
        assert len(parts) >= 3
        placed_x = int(parts[1])
        parent_x = int(root.winfo_rootx())
        assert abs(placed_x - parent_x) < 400
        assert placed_x != 0 or parent_x == 0
    finally:
        root.destroy()
