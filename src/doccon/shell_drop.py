# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Explorer HDROP via DragAcceptFiles + WM_DROPFILES. No Outlook attachment streams."""
from __future__ import annotations

import contextlib
import os
import struct
from collections.abc import Callable
from ctypes import WINFUNCTYPE, Structure, byref, c_int, c_int64, c_long, c_void_p, sizeof, wintypes
from pathlib import Path

try:
    from ctypes import windll
except ImportError:
    windll = None  # type: ignore[assignment]

WM_DROPFILES = 0x0233
WM_NCDESTROY = 0x0082
GWLP_WNDPROC = -4
DROPFILES_HEADER = 20

HdropCallback = Callable[[list[str], int, int], None]
LRESULT = c_int64 if sizeof(c_void_p) == 8 else c_long
WNDPROC = WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class POINT(Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def hdrop_available() -> bool:
    return os.name == "nt" and windll is not None


def _in_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not os.environ.get("DOCCON_TEST_HDROP")


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "drop", message)
    except Exception:
        return


def _hwnd_from_token(token: object) -> int:
    text = str(token or "").strip()
    if not text:
        return 0
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return 0


def child_hwnds(parent: int) -> list[int]:
    """Descendants of one HWND. Used for DragAcceptFiles, never OLE on the parent."""
    found: list[int] = []
    if not parent or not hdrop_available() or windll is None:
        return found
    try:
        WNDENUMPROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @WNDENUMPROC
        def _enum(hwnd, _lparam):
            found.append(int(hwnd))
            return True

        windll.user32.EnumChildWindows(int(parent), _enum, 0)
    except Exception as exc:
        _log(f"EnumChildWindows {exc}", level="WARN")
    return found


def drop_hwnds(widget, extras=None, *, children: bool = False) -> list[int]:
    """Toplevel + optional board/dock surfaces. Row children only when children=True (HDROP)."""
    seen: set[int] = set()
    hwnds: list[int] = []

    def add(hwnd: int) -> None:
        if hwnd and hwnd not in seen:
            seen.add(hwnd)
            hwnds.append(hwnd)

    with contextlib.suppress(Exception):
        add(int(widget.winfo_toplevel().winfo_id()))
    with contextlib.suppress(Exception):
        add(int(widget.winfo_id()))
    with contextlib.suppress(Exception):
        add(_hwnd_from_token(widget.winfo_toplevel().wm_frame()))
    extra_hwnds: list[int] = []
    for extra in extras or ():
        if extra is None:
            continue
        with contextlib.suppress(Exception):
            hwnd = int(extra.winfo_id())
            add(hwnd)
            extra_hwnds.append(hwnd)
    if children:
        for hwnd in extra_hwnds:
            for child in child_hwnds(hwnd):
                add(child)
    return hwnds


def parse_dropfiles_blob(blob: bytes) -> tuple[list[str], int, int]:
    """Parse a DROPFILES buffer (HDROP contents). Wide or ANSI path list."""
    if len(blob) < DROPFILES_HEADER:
        return [], 0, 0
    p_files = int.from_bytes(blob[0:4], "little")
    x = struct.unpack_from("<i", blob, 4)[0]
    y = struct.unpack_from("<i", blob, 8)[0]
    f_wide = int.from_bytes(blob[16:20], "little") != 0
    if p_files < DROPFILES_HEADER or p_files > len(blob):
        return [], x, y
    rest = blob[p_files:]
    text = rest.decode("utf-16-le", errors="ignore") if f_wide else rest.decode("mbcs", errors="ignore")
    names: list[str] = []
    for part in text.split("\0"):
        if not part:
            break
        names.append(part)
    return names, x, y


def make_dropfiles_blob(paths: list[str], x: int = 0, y: int = 0) -> bytes:
    body = b"".join(path.encode("utf-16-le") + b"\x00\x00" for path in paths) + b"\x00\x00"
    header = (DROPFILES_HEADER).to_bytes(4, "little")
    header += struct.pack("<ii", int(x), int(y))
    header += (0).to_bytes(4, "little")
    header += (1).to_bytes(4, "little")
    return header + body


def hdrop_paths(hdrop: int) -> list[str]:
    if not hdrop or not hdrop_available():
        return []
    try:
        from ctypes import create_unicode_buffer

        shell32 = windll.shell32
        shell32.DragQueryFileW.argtypes = [c_void_p, wintypes.UINT, c_void_p, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        count = int(shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0))
        paths: list[str] = []
        buf = create_unicode_buffer(32768)
        for index in range(count):
            n = int(shell32.DragQueryFileW(hdrop, index, buf, 32768))
            if n:
                paths.append(buf.value)
        return paths
    except Exception as exc:
        _log(f"DragQueryFile {exc}", level="WARN")
        return []


def hdrop_point_screen(hwnd: int, hdrop: int) -> tuple[int, int]:
    if not hdrop_available():
        return 0, 0
    pt = POINT(0, 0)
    try:
        windll.shell32.DragQueryPoint.argtypes = [c_void_p, c_void_p]
        windll.shell32.DragQueryPoint.restype = wintypes.BOOL
        windll.shell32.DragQueryPoint(hdrop, byref(pt))
        if hwnd:
            windll.user32.ClientToScreen.argtypes = [wintypes.HWND, c_void_p]
            windll.user32.ClientToScreen.restype = wintypes.BOOL
            windll.user32.ClientToScreen(hwnd, byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return int(pt.x), int(pt.y)


def _set_window_long_ptr():
    user32 = windll.user32
    fn = user32.SetWindowLongPtrW if sizeof(c_void_p) == 8 else user32.SetWindowLongW
    fn.restype = c_void_p
    fn.argtypes = [wintypes.HWND, c_int, c_void_p]
    return fn


class HdropHost:
    """Subclass the Tk HWND and accept CF_HDROP. Never IDataObject extract."""

    def __init__(self, callback: HdropCallback) -> None:
        self._callback = callback
        self._widget = None
        self._hwnds: list[int] = []
        self._old: dict[int, int] = {}
        self._proc = None
        self._wanted: list[int] = []

    def attach(self, widget, extras=None) -> None:
        self._widget = widget
        if not hdrop_available():
            return
        if _in_pytest():
            _log("hdrop attach skipped under pytest")
            return
        hwnds = drop_hwnds(widget, extras=extras, children=True)
        if self._hwnds and self._wanted == hwnds:
            return
        self.detach()
        self._widget = widget
        self._wanted = list(hwnds)
        self._proc = WNDPROC(self._wndproc)
        set_long = _set_window_long_ptr()
        shell32 = windll.shell32
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragAcceptFiles.restype = None
        for hwnd in hwnds:
            try:
                _log(f"DragAcceptFiles hwnd={hwnd:#x}")
                shell32.DragAcceptFiles(hwnd, True)
                old = set_long(hwnd, GWLP_WNDPROC, self._proc)
                if old:
                    self._old[hwnd] = int(old)
                    self._hwnds.append(hwnd)
            except Exception as exc:
                _log(f"DragAcceptFiles hwnd={hwnd:#x} {exc}", level="WARN")
        if not self._hwnds:
            _log("DragAcceptFiles attached 0 windows", level="WARN")

    def detach(self) -> None:
        if not hdrop_available() or windll is None:
            self._hwnds = []
            self._old = {}
            self._wanted = []
            return
        set_long = _set_window_long_ptr()
        shell32 = getattr(windll, "shell32", None)
        for hwnd in list(self._hwnds):
            old = self._old.get(hwnd)
            if old:
                with contextlib.suppress(Exception):
                    set_long(hwnd, GWLP_WNDPROC, old)
            if shell32 is not None:
                with contextlib.suppress(Exception):
                    shell32.DragAcceptFiles(hwnd, False)
        self._hwnds = []
        self._old = {}
        self._wanted = []
        self._widget = None

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if int(msg) == WM_DROPFILES:
                self._on_wm_dropfiles(int(hwnd), int(wparam))
                return 0
            if int(msg) == WM_NCDESTROY:
                self._old.pop(int(hwnd), None)
                if int(hwnd) in self._hwnds:
                    self._hwnds.remove(int(hwnd))
        except Exception as exc:
            _log(f"WM_DROPFILES {exc}", level="WARN")
        old = self._old.get(int(hwnd))
        user32 = windll.user32
        if old:
            user32.CallWindowProcW.restype = LRESULT
            user32.CallWindowProcW.argtypes = [
                c_void_p,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            return user32.CallWindowProcW(old, hwnd, msg, wparam, lparam)
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _on_wm_dropfiles(self, hwnd: int, hdrop: int) -> None:
        try:
            paths = hdrop_paths(hdrop)
            x, y = hdrop_point_screen(hwnd, hdrop)
            names = ",".join(Path(p).name[:80] for p in paths[:6]) or "none"
            _log(f"WM_DROPFILES hwnd={hwnd:#x} count={len(paths)} pt={x},{y} names={names}")
            self._callback(paths, x, y)
        except Exception as exc:
            _log(f"WM_DROPFILES deliver {exc}", level="WARN")
        finally:
            with contextlib.suppress(Exception):
                windll.shell32.DragFinish.argtypes = [c_void_p]
                windll.shell32.DragFinish.restype = None
                windll.shell32.DragFinish(hdrop)
