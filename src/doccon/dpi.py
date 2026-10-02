# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Per-monitor DPI so a 125% or 150% laptop is sharp, and 100% stays the same size."""
from __future__ import annotations

import sys
import tkinter as tk


def enable_process_dpi() -> None:
    """Call before any Tk window. A DPI-unaware exe is bitmap-stretched on the other screen."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # PROCESS_PER_MONITOR_DPI_AWARE = 2. A second call fails once awareness is set.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            return


def apply_window_dpi(root: tk.Misc) -> float:
    """Match Tk's point size to this window. Returns 1.0 at 96 DPI."""
    scale = 1.0
    if sys.platform == "win32":
        try:
            import ctypes

            dpi = int(ctypes.windll.user32.GetDpiForWindow(int(root.winfo_id())))
            if dpi > 0:
                root.tk.call("tk", "scaling", dpi / 72.0)
                scale = dpi / 96.0
        except (AttributeError, OSError, tk.TclError, ValueError):
            scale = 1.0
    return max(1.0, scale)


def pixel_scale(widget: tk.Misc) -> float:
    """1.0 when Tk is at the 96 DPI point size (scaling 96/72)."""
    try:
        scaling = float(widget.tk.call("tk", "scaling"))
    except (tk.TclError, TypeError, ValueError):
        return 1.0
    return max(1.0, scaling / (96 / 72))
