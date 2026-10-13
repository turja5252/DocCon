# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Keep dialogs on the monitor where the console is, not the primary screen."""
from __future__ import annotations

import contextlib
import sys
import tkinter as tk

_INSTALLED = False
_CONSOLE: tk.Misc | None = None

# A borderless Tk window is WS_EX_TOOLWINDOW. Windows then centers MessageBox
# on the primary screen even when that window sits on the console's monitor.
_WS_EX_TOOLWINDOW = 0x00000080
_GWL_EXSTYLE = -20
_GA_ROOT = 2
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040
_SWP_FRAMECHANGED = 0x0020


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


def _user32():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    long_ptr = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongPtrW.restype = long_ptr
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
    user32.SetWindowLongPtrW.restype = long_ptr
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32, wintypes, ctypes


def root_hwnd(host: tk.Misc) -> int:
    """The real top-level window. Tk's own id can be an inner child."""
    hwnd = int(host.winfo_id())
    if sys.platform != "win32" or hwnd <= 0:
        return hwnd
    try:
        user32, _wintypes, _ctypes = _user32()
        root = user32.GetAncestor(hwnd, _GA_ROOT)
        return int(root or hwnd)
    except (AttributeError, OSError, tk.TclError, ValueError):
        return hwnd


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Screen rectangle of a window, in pixels. None when Windows cannot see it."""
    if sys.platform != "win32" or hwnd <= 0:
        return None
    try:
        user32, wintypes, ctypes = _user32()

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        area = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(area)):
            return None
        return int(area.left), int(area.top), int(area.right), int(area.bottom)
    except (AttributeError, OSError, ValueError):
        return None


def host_span(host: tk.Misc) -> tuple[int, int, int, int]:
    """Left, top, width, height of the console in screen pixels."""
    rect = window_rect(root_hwnd(host))
    if rect is not None:
        left, top, right, bottom = rect
        if right > left and bottom > top:
            return left, top, right - left, bottom - top
    return (
        int(host.winfo_rootx()),
        int(host.winfo_rooty()),
        max(int(host.winfo_width()), 1),
        max(int(host.winfo_height()), 1),
    )


def seat_owner(window: tk.Misc, x: int, y: int) -> None:
    """Move a dialog owner onto the console and drop the tool-window style.

    Windows centers a message on the primary screen while the owner still
    has WS_EX_TOOLWINDOW, which is what a borderless Tk window carries.
    """
    if sys.platform != "win32":
        return
    try:
        raw = int(window.winfo_id())
        hwnd = root_hwnd(window)
        if hwnd <= 0 and raw <= 0:
            return
        user32, _wintypes, _ctypes = _user32()
        for handle in dict.fromkeys((raw, hwnd)):
            if handle <= 0:
                continue
            style = int(user32.GetWindowLongPtrW(handle, _GWL_EXSTYLE))
            if style & _WS_EX_TOOLWINDOW:
                user32.SetWindowLongPtrW(handle, _GWL_EXSTYLE, style & ~_WS_EX_TOOLWINDOW)
        user32.SetWindowPos(
            hwnd or raw,
            0,
            int(x),
            int(y),
            1,
            1,
            _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_SHOWWINDOW | _SWP_FRAMECHANGED,
        )
    except (AttributeError, OSError, tk.TclError, ValueError):
        return


def owner_is_tool_window(window: tk.Misc) -> bool:
    if sys.platform != "win32":
        return False
    try:
        user32, _wintypes, _ctypes = _user32()
        style = int(user32.GetWindowLongPtrW(root_hwnd(window), _GWL_EXSTYLE))
    except (AttributeError, OSError, tk.TclError, ValueError):
        return False
    return bool(style & _WS_EX_TOOLWINDOW)


def _monitor_work(host: tk.Misc) -> tuple[int, int, int, int] | None:
    if str(host.tk.call("tk", "windowingsystem")) != "win32":
        return None
    try:
        user32, wintypes, ctypes = _user32()

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

        monitor = user32.MonitorFromWindow(root_hwnd(host), 2)
        if not monitor:
            return None
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
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
        left, top, host_w, host_h = host_span(host)
        x, y = center_origin(left, top, host_w, host_h, width, height)
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
    """A mapped owner on the console's monitor.

    Windows centers a message on its owner. A borderless Tk window is a tool
    window, and Windows then uses the primary screen, so the tool style is
    cleared and the owner is moved to the console's real window rectangle.
    """
    host = _host(parent)
    if host is None:
        return None
    try:
        host.update_idletasks()
        pin = tk.Toplevel(host)
        pin.overrideredirect(True)
        left, top, width, height = host_span(host)
        x = left + max(width, 1) // 2
        y = top + max(height, 1) // 2
        pin.geometry(f"1x1+{x}+{y}")
        pin.update()
        seat_owner(pin, x, y)
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
