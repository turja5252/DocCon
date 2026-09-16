# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Explorer / Adobe file drags in the GUI process, via OLE IDropTarget.

CF_HDROP only. This module never asks for FileGroupDescriptorW, never asks for
FileContents, and never touches an IStream, so it cannot repeat the 1.49/1.50
native crashes. Outlook attachment streams stay in the drop_host child.

Why OLE here and not DragAcceptFiles:

* WM_DROPFILES has no DragEnter and no DragOver, so it cannot show a copy
  cursor or highlight the row under the pointer while the drag is moving. The
  operator gets no feedback at all until the file is already dropped.
* The two mechanisms conflict. An OLE target registered on a window takes
  precedence and WS_EX_ACCEPTFILES is bypassed, so a window must use one or the
  other - never both. HdropHost must be detached from any HWND registered here.

OLE walks up the parent chain to find a target, so registering the toplevel
covers every widget on the board. The drop point is a screen coordinate, which
is what the row hit-test wants anyway.
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from ctypes import (
    POINTER,
    WINFUNCTYPE,
    Structure,
    Union,
    byref,
    c_byte,
    c_int32,
    c_int64,
    c_long,
    c_ulong,
    c_void_p,
    cast,
    create_unicode_buffer,
    pointer,
    sizeof,
    wintypes,
)
from pathlib import Path

try:
    from ctypes import windll
except ImportError:  # non-Windows
    windll = None  # type: ignore[assignment]

CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1
S_OK = 0
S_FALSE = 1
E_NOINTERFACE = 0x80004002
RPC_E_CHANGED_MODE = 0x80010106
DRAGDROP_E_ALREADYREGISTERED = 0x80040101

IID_IDROPTARGET_DATA1 = 0x00000122
IID_IUNKNOWN_DATA1 = 0x00000000

# x64 passes POINTL (8 bytes) in one register; a ctypes Structure by value in a
# COM callback is unreliable there and can silently leave the effect at NONE.
IS_WIN64 = sizeof(c_void_p) == 8

HdropCallback = Callable[[list[str], int, int], None]
HoverCallback = Callable[[int, int], None]
LeaveCallback = Callable[[], None]
ScheduleCallback = Callable[[Callable[[], None]], None]

_ole_ready = False
_KEEP: list = []


def ole_available() -> bool:
    return os.name == "nt" and windll is not None


def _in_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not os.environ.get("DOCCON_TEST_HDROP")


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "drop", message)
    except Exception:
        return


def _hresult(value: int) -> int:
    return c_int32(value).value


class GUID(Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", c_byte * 8),
    ]


class POINTL(Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


PointArg = c_int64 if IS_WIN64 else POINTL


def unpack_pointl(pt) -> tuple[int, int]:
    """Screen x, y from an IDropTarget POINTL (packed int64 on x64)."""
    if isinstance(pt, POINTL):
        return int(pt.x), int(pt.y)
    packed = int(pt) & 0xFFFFFFFFFFFFFFFF
    x = c_int32(packed & 0xFFFFFFFF).value
    y = c_int32((packed >> 32) & 0xFFFFFFFF).value
    return x, y


class FORMATETC(Structure):
    _fields_ = [
        ("cfFormat", wintypes.WORD),
        ("ptd", c_void_p),
        ("dwAspect", wintypes.DWORD),
        ("lindex", c_long),
        ("tymed", wintypes.DWORD),
    ]


class _StgUnion(Union):
    _fields_ = [
        ("hGlobal", c_void_p),
        ("pstm", c_void_p),
        ("pstg", c_void_p),
        ("lpszFileName", c_void_p),
    ]


class STGMEDIUM(Structure):
    _fields_ = [
        ("tymed", wintypes.DWORD),
        ("u", _StgUnion),
        ("pUnkForRelease", c_void_p),
    ]


QI = WINFUNCTYPE(c_int32, c_void_p, POINTER(GUID), POINTER(c_void_p))
ADDREF = WINFUNCTYPE(c_ulong, c_void_p)
RELEASE = WINFUNCTYPE(c_ulong, c_void_p)
DRAGENTER = WINFUNCTYPE(
    c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)
)
DRAGOVER = WINFUNCTYPE(c_int32, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD))
DRAGLEAVE = WINFUNCTYPE(c_int32, c_void_p)
DROP = WINFUNCTYPE(c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD))


class DropTargetVtbl(Structure):
    _fields_ = [
        ("QueryInterface", QI),
        ("AddRef", ADDREF),
        ("Release", RELEASE),
        ("DragEnter", DRAGENTER),
        ("DragOver", DRAGOVER),
        ("DragLeave", DRAGLEAVE),
        ("Drop", DROP),
    ]


class ComObj(Structure):
    _fields_ = [("lpVtbl", c_void_p)]


def ensure_ole() -> bool:
    global _ole_ready
    if not ole_available():
        return False
    if _ole_ready:
        return True
    ole32 = windll.ole32
    ole32.OleInitialize.argtypes = [c_void_p]
    ole32.OleInitialize.restype = c_int32
    hr = int(ole32.OleInitialize(None))
    _ole_ready = hr in (S_OK, S_FALSE, _hresult(RPC_E_CHANGED_MODE))
    _log(f"OleInitialize (gui) hr={hr:#x} ready={_ole_ready}")
    return _ole_ready


def _set_effect(pdw_effect, value: int) -> None:
    with contextlib.suppress(Exception):
        pdw_effect[0] = wintypes.DWORD(value).value


def data_object_has_hdrop(pdataobj: int) -> bool:
    """QueryGetData(CF_HDROP). Never enumerates or fetches any other format."""
    if not pdataobj:
        return False
    try:
        vtbl = cast(cast(pdataobj, POINTER(c_void_p)).contents, POINTER(c_void_p))
        query = WINFUNCTYPE(c_int32, c_void_p, POINTER(FORMATETC))(vtbl[5])
        fmt = FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL)
        return int(query(pdataobj, byref(fmt))) == S_OK
    except Exception as exc:
        _log(f"QueryGetData(CF_HDROP) {exc}", level="WARN")
        return False


def hdrop_paths_from_data_object(pdataobj: int) -> list[str]:
    """GetData(CF_HDROP) then DragQueryFileW. HGLOBAL only, no IStream."""
    if not pdataobj:
        return []
    medium = STGMEDIUM()
    try:
        vtbl = cast(cast(pdataobj, POINTER(c_void_p)).contents, POINTER(c_void_p))
        get_data = WINFUNCTYPE(c_int32, c_void_p, POINTER(FORMATETC), POINTER(STGMEDIUM))(vtbl[3])
        fmt = FORMATETC(CF_HDROP, None, DVASPECT_CONTENT, -1, TYMED_HGLOBAL)
        hr = int(get_data(pdataobj, byref(fmt), byref(medium)))
        if hr != S_OK:
            _log(f"GetData(CF_HDROP) hr={hr:#x}", level="WARN")
            return []
        handle = medium.u.hGlobal
        if not handle:
            return []
        shell32 = windll.shell32
        shell32.DragQueryFileW.argtypes = [c_void_p, wintypes.UINT, c_void_p, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        count = int(shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0))
        buf = create_unicode_buffer(32768)
        paths: list[str] = []
        for index in range(count):
            if int(shell32.DragQueryFileW(handle, index, buf, 32768)):
                paths.append(buf.value)
        return paths
    except Exception as exc:
        _log(f"CF_HDROP extract {exc}", level="WARN")
        return []
    finally:
        with contextlib.suppress(Exception):
            ole32 = windll.ole32
            ole32.ReleaseStgMedium.argtypes = [POINTER(STGMEDIUM)]
            ole32.ReleaseStgMedium(byref(medium))


class _HdropDropTarget:
    """One IDropTarget shared by every registered board HWND."""

    def __init__(
        self,
        callback: HdropCallback,
        hover: HoverCallback | None,
        leave: LeaveCallback | None,
        schedule: ScheduleCallback,
    ) -> None:
        self.callback = callback
        self.hover = hover
        self.leave = leave
        self._schedule = schedule
        self._has_hdrop = False
        self._hover_xy: tuple[int, int] | None = None
        self._hover_pending = False
        self._vtbl = DropTargetVtbl(
            QI(self._qi),
            ADDREF(lambda _this: 2),
            RELEASE(lambda _this: 1),
            DRAGENTER(self._drag_enter),
            DRAGOVER(self._drag_over),
            DRAGLEAVE(self._drag_leave),
            DROP(self._drop),
        )
        self._obj = ComObj(cast(pointer(self._vtbl), c_void_p))
        _KEEP.append(self)

    def as_punk(self) -> int:
        return cast(pointer(self._obj), c_void_p).value or 0

    def _qi(self, this, riid, ppv) -> int:
        try:
            data1 = int(riid.contents.Data1)
        except (ValueError, AttributeError):
            data1 = -1
        if data1 in (IID_IDROPTARGET_DATA1, IID_IUNKNOWN_DATA1):
            with contextlib.suppress(Exception):
                ppv[0] = this
            return S_OK
        with contextlib.suppress(Exception):
            ppv[0] = None
        return _hresult(E_NOINTERFACE)

    def _drag_enter(self, _this, pdataobj, _keys, pt, pdw_effect) -> int:
        try:
            self._has_hdrop = data_object_has_hdrop(pdataobj)
            x, y = unpack_pointl(pt)
            _set_effect(pdw_effect, DROPEFFECT_COPY if self._has_hdrop else DROPEFFECT_NONE)
            _log(
                f"DragEnter pt={x},{y} CF_HDROP={int(self._has_hdrop)} "
                f"effect={'COPY' if self._has_hdrop else 'NONE'}"
            )
            if self._has_hdrop:
                self._queue_hover(x, y)
            return S_OK
        except Exception as exc:
            _log(f"DragEnter {exc}", level="WARN")
            _set_effect(pdw_effect, DROPEFFECT_NONE)
            return S_OK

    def _drag_over(self, _this, _keys, pt, pdw_effect) -> int:
        try:
            _set_effect(pdw_effect, DROPEFFECT_COPY if self._has_hdrop else DROPEFFECT_NONE)
            if self._has_hdrop:
                x, y = unpack_pointl(pt)
                self._queue_hover(x, y)
            return S_OK
        except Exception as exc:
            _log(f"DragOver {exc}", level="WARN")
            _set_effect(pdw_effect, DROPEFFECT_NONE)
            return S_OK

    def _drag_leave(self, _this) -> int:
        try:
            self._has_hdrop = False
            self._hover_xy = None
            if self.leave is not None:
                self._schedule(self.leave)
            return S_OK
        except Exception as exc:
            _log(f"DragLeave {exc}", level="WARN")
            return S_OK

    def _queue_hover(self, x: int, y: int) -> None:
        if self.hover is None:
            return
        self._hover_xy = (x, y)
        if self._hover_pending:
            return
        self._hover_pending = True

        def run() -> None:
            self._hover_pending = False
            xy = self._hover_xy
            if self.hover is not None and xy is not None:
                self.hover(xy[0], xy[1])

        self._schedule(run)

    def _drop(self, _this, pdataobj, _keys, pt, pdw_effect) -> int:
        try:
            x, y = unpack_pointl(pt)
            paths = hdrop_paths_from_data_object(pdataobj) if pdataobj else []
            self._has_hdrop = False
            self._hover_xy = None
            _set_effect(pdw_effect, DROPEFFECT_COPY if paths else DROPEFFECT_NONE)
            names = ",".join(Path(p).name[:80] for p in paths[:6]) or "none"
            _log(f"Drop (gui CF_HDROP) pt={x},{y} count={len(paths)} names={names}")
            items = list(paths)
            px, py = x, y

            def deliver() -> None:
                if self.leave is not None:
                    with contextlib.suppress(Exception):
                        self.leave()
                if items:
                    self.callback(items, px, py)

            self._schedule(deliver)
            return S_OK
        except Exception as exc:
            _log(f"Drop {exc}", level="WARN")
            _set_effect(pdw_effect, DROPEFFECT_NONE)
            return S_OK


def hdrop_ole_hwnds(widget, extras=None) -> list[int]:
    """Toplevel first. OLE resolves a child to the nearest registered ancestor."""
    seen: set[int] = set()
    hwnds: list[int] = []

    def add(hwnd: int) -> None:
        if hwnd and hwnd not in seen:
            seen.add(hwnd)
            hwnds.append(hwnd)

    with contextlib.suppress(Exception):
        add(int(widget.winfo_toplevel().winfo_id()))
    for extra in extras or ():
        if extra is None:
            continue
        with contextlib.suppress(Exception):
            add(int(extra.winfo_id()))
    return hwnds


class HdropOleHost:
    """RegisterDragDrop for CF_HDROP in the GUI process.

    Any HWND registered here must NOT also have DragAcceptFiles: OLE wins and
    the legacy path is dead weight that only confuses the next reader.
    """

    def __init__(
        self,
        callback: HdropCallback,
        hover: HoverCallback | None = None,
        leave: LeaveCallback | None = None,
    ) -> None:
        self._callback = callback
        self._hover = hover
        self._leave = leave
        self._widget = None
        self._target: _HdropDropTarget | None = None
        self._hwnds: list[int] = []
        self._wanted: list[int] = []

    @property
    def hwnds(self) -> list[int]:
        return list(self._hwnds)

    def _schedule(self, fn: Callable[[], None]) -> None:
        widget = self._widget
        if widget is None:
            return

        def run(job=fn) -> None:
            try:
                job()
            except Exception as exc:
                _log(f"scheduled {exc}", level="WARN")

        try:
            widget.after(0, run)
        except Exception:
            run()

    def attach(self, widget, extras=None) -> bool:
        self._widget = widget
        if _in_pytest():
            _log("hdrop ole attach skipped under pytest")
            return False
        if not ole_available() or not ensure_ole():
            return False
        hwnds = hdrop_ole_hwnds(widget, extras=extras)
        if self._hwnds and self._wanted == hwnds:
            return True
        self.detach()
        self._widget = widget
        self._wanted = list(hwnds)
        self._target = _HdropDropTarget(
            self._callback, self._hover, self._leave, self._schedule
        )
        punk = self._target.as_punk()
        ole32 = windll.ole32
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            ole32.RegisterDragDrop.argtypes = [wintypes.HWND, c_void_p]
            ole32.RegisterDragDrop.restype = c_int32
        for hwnd in hwnds:
            try:
                hr = int(ole32.RegisterDragDrop(hwnd, punk))
            except Exception as exc:
                _log(f"RegisterDragDrop hwnd={hwnd:#x} {exc}", level="WARN")
                continue
            if hr == S_OK:
                self._hwnds.append(hwnd)
                _log(f"RegisterDragDrop hwnd={hwnd:#x} hr=0 (gui CF_HDROP)")
            elif hr == _hresult(DRAGDROP_E_ALREADYREGISTERED):
                self._hwnds.append(hwnd)
                _log(f"RegisterDragDrop hwnd={hwnd:#x} already (gui)")
            else:
                _log(f"RegisterDragDrop hwnd={hwnd:#x} hr={hr:#x}", level="WARN")
        if not self._hwnds:
            _log("RegisterDragDrop (gui) attached 0 windows", level="WARN")
            return False
        return True

    def detach(self) -> None:
        if ole_available() and self._hwnds:
            ole32 = getattr(windll, "ole32", None)
            if ole32 is not None:
                with contextlib.suppress(AttributeError, TypeError, ValueError):
                    ole32.RevokeDragDrop.argtypes = [wintypes.HWND]
                    ole32.RevokeDragDrop.restype = c_int32
                for hwnd in self._hwnds:
                    with contextlib.suppress(Exception):
                        ole32.RevokeDragDrop(hwnd)
        self._hwnds = []
        self._wanted = []
        self._target = None
