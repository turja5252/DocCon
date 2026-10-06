# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Keep dialogs on the monitor where the console is, not the primary screen."""
from __future__ import annotations

import contextlib
import tkinter as tk

_INSTALLED = False
_CONSOLE: tk.Misc | None = None


def bind_console(window: tk.Misc) -> None:
    """Remember the DocCon window so a message with no parent still uses its screen."""
    global _CONSOLE
    _CONSOLE = window


def fit_on_monitor(
    x: int,
    y: int,
    width: int,
    height: int,
    work: tuple[int, int, int, int],
) -> tuple[int, int]:
    """Keep the popup inside the parent monitor. Do not pull it back to the primary screen."""
    left, top, right, bottom = work
    if x + width > right:
        x = right - width
    if x < left:
        x = left
    if y + height > bottom:
        y = bottom - height
    if y < top:
        y = top
    return x, y


def _monitor_work(host: tk.Misc) -> tuple[int, int, int, int] | None:
    if str(host.tk.call("tk", "windowingsystem")) != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        hwnd = int(host.winfo_id())
        monitor = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        area = info.rcWork
        return int(area.left), int(area.top), int(area.right), int(area.bottom)
    except (AttributeError, OSError, tk.TclError, ValueError):
        return None


def center_origin(
    parent_x: int,
    parent_y: int,
    parent_w: int,
    parent_h: int,
    child_w: int,
    child_h: int,
) -> tuple[int, int]:
    """Center a popup on the parent window. Do not use the primary monitor size."""
    return (
        int(parent_x) + (max(int(parent_w), 1) - max(int(child_w), 1)) // 2,
        int(parent_y) + (max(int(parent_h), 1) - max(int(child_h), 1)) // 2,
    )


def _alive(window: tk.Misc | None) -> tk.Misc | None:
    if window is None:
        return None
    try:
        if int(window.winfo_exists()):
            return window.winfo_toplevel()
    except tk.TclError:
        return None
    return None


def _host(parent: tk.Misc | None) -> tk.Misc | None:
    found = _alive(parent)
    if found is not None:
        return found
    found = _alive(_CONSOLE)
    if found is not None:
        return found
    return _alive(getattr(tk, "_default_root", None))


def _child_size(window: tk.Misc) -> tuple[int, int]:
    window.update_idletasks()
    stated = str(window.geometry() or "")
    width = height = 0
    if "x" in stated:
        try:
            width = int(stated.split("x", 1)[0])
            height = int(stated.split("x", 1)[1].split("+", 1)[0].split("-", 1)[0])
        except (TypeError, ValueError):
            width = height = 0
    req_w = max(int(window.winfo_reqwidth()), 1)
    req_h = max(int(window.winfo_reqheight()), 1)
    if width <= 1:
        width = req_w
    if height <= 1:
        height = req_h
    return width, height


def place_on_parent(window: tk.Misc) -> None:
    """Move a Tk window onto the parent window's monitor."""
    host = _host(window.master if isinstance(window, tk.Misc) else None)
    if host is None or host is window:
        return
    try:
        host.update_idletasks()
        width, height = _child_size(window)
        x, y = center_origin(
            int(host.winfo_rootx()),
            int(host.winfo_rooty()),
            max(int(host.winfo_width()), 1),
            max(int(host.winfo_height()), 1),
            width,
            height,
        )
        work = _monitor_work(host)
        if work is not None:
            x, y = fit_on_monitor(x, y, width, height, work)
        if width > 1 and height > 1 and "x" in str(window.geometry()):
            window.geometry(f"{width}x{height}+{x}+{y}")
        else:
            window.geometry(f"+{x}+{y}")
    except tk.TclError:
        return


def reveal_on_parent(window: tk.Toplevel) -> None:
    """Show a dialog that was withdrawn, centered on its parent."""
    place_on_parent(window)
    with contextlib.suppress(tk.TclError):
        window.deiconify()
        window.lift()


def _pin(parent: tk.Misc | None) -> tk.Toplevel | None:
    """A mapped 1px owner on the console's monitor.

    Windows centers a message on its owner. An unmapped or see-through owner
    still counts as the primary screen, so the pin is placed and drawn first.
    """
    host = _host(parent)
    if host is None:
        return None
    try:
        host.update_idletasks()
        pin = tk.Toplevel(host)
        pin.overrideredirect(True)
        pin.transient(host)
        x = int(host.winfo_rootx()) + max(int(host.winfo_width()), 1) // 2
        y = int(host.winfo_rooty()) + max(int(host.winfo_height()), 1) // 2
        pin.geometry(f"1x1+{x}+{y}")
        pin.update()
        return pin
    except tk.TclError:
        return None


def _wrap(fn):
    def inner(*args, **kwargs):
        parent = kwargs.get("parent")
        pin = _pin(parent if isinstance(parent, tk.Misc) else None)
        if pin is not None:
            kwargs["parent"] = pin
        try:
            return fn(*args, **kwargs)
        finally:
            if pin is not None:
                with contextlib.suppress(tk.TclError):
                    pin.destroy()

    return inner


def install() -> None:
    """Point Tk's message and file dialogs at the console's monitor."""
    global _INSTALLED
    if _INSTALLED:
        return
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox

    for name in (
        "showinfo",
        "showwarning",
        "showerror",
        "askyesno",
        "askokcancel",
        "askquestion",
        "askretrycancel",
    ):
        original = getattr(messagebox, name, None)
        if callable(original):
            setattr(messagebox, name, _wrap(original))
    for name in ("askopenfilename", "askopenfilenames", "asksaveasfilename", "askdirectory"):
        original = getattr(filedialog, name, None)
        if callable(original):
            setattr(filedialog, name, _wrap(original))
    _INSTALLED = True
