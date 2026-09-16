# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Windows OLE drop for the drop_host **child process** only.

Never import this module from gui.py. FileContents / IStream / QueryGetData can AV
and kill the process that owns IDropTarget. The parent uses WM_DROPFILES (Explorer)
and a localhost protocol from this helper (Outlook).
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
    addressof,
    byref,
    c_byte,
    c_int32,
    c_int64,
    c_long,
    c_ulong,
    c_ulonglong,
    c_void_p,
    cast,
    create_unicode_buffer,
    pointer,
    sizeof,
    wintypes,
)
from pathlib import Path

from doccon.drop_pdfs import DropSource, is_pdf_filename

try:
    from ctypes import windll
except ImportError:  # non-Windows
    windll = None  # type: ignore[assignment]

CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
TYMED_FILE = 2
TYMED_ISTREAM = 4
TYMED_ISTORAGE = 8
DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1
DROPEFFECT_LINK = 4
S_OK = 0
S_FALSE = 1
E_NOINTERFACE = 0x80004002
E_UNEXPECTED = 0x8000FFFF
RPC_E_CHANGED_MODE = 0x80010106
DRAGDROP_E_ALREADYREGISTERED = 0x80040101
FILEDESCRIPTORW_SIZE = 592
FILEDESCRIPTORA_SIZE = 332
FD_NAME_OFFSET = 72
MAX_PATH_WCHARS = 260
# x64: POINTL (8 bytes) is one register. ctypes Structure-by-value in a COM
# callback is unreliable and can leave pdwEffect as NONE — drop looks like nothing.
IS_WIN64 = sizeof(c_void_p) == 8

IID_IUNKNOWN_DATA1 = 0x00000000
IID_IDROPTARGET_DATA1 = 0x00000122
IID_COM_DATA4 = b"\xc0\x00\x00\x00\x00\x00\x00\x46"
MK_LBUTTON = 1
CLSCTX_INPROC_SERVER = 1
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400
FOFX_DONTDISPLAYSOURCEPATH = 0x04000000
FOFX_DONTDISPLAYDESTPATH = 0x08000000
# IFileOperation::CopyItems is what Explorer uses when you paste into a folder.
_FO_FLAGS = (
    FOF_SILENT
    | FOF_NOCONFIRMATION
    | FOF_NOERRORUI
    | FOF_NOCONFIRMMKDIR
    | FOFX_DONTDISPLAYSOURCEPATH
    | FOFX_DONTDISPLAYDESTPATH
)

DropCallback = Callable[[list[DropSource], int, int], None]
HoverCallback = Callable[[int, int], None]
LeaveCallback = Callable[[], None]
ScheduleCallback = Callable[[Callable[[], None]], None]
DropGate = Callable[[bool], None]

_ole_ready = False
_hosts: list[DropHost] = []
# Tests pass pdataobj=1. Real IUnknown* values live well above this.
_MIN_LIVE_COM = 0x10000
_last_get_hr = 1
_last_here_hr = 1


def _hresult(value: int) -> int:
    return c_int32(value).value


def ole_available() -> bool:
    return os.name == "nt" and windll is not None


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
    """Screen x, y from IDropTarget POINTL (packed int64 on x64, struct on x86)."""
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


class IDropTargetVtbl(Structure):
    pass


class DropTargetObj(Structure):
    _fields_ = [("lpVtbl", POINTER(IDropTargetVtbl))]


IDropTargetVtbl._fields_ = [
    (
        "QueryInterface",
        WINFUNCTYPE(c_int32, c_void_p, POINTER(GUID), POINTER(c_void_p)),
    ),
    ("AddRef", WINFUNCTYPE(c_ulong, c_void_p)),
    ("Release", WINFUNCTYPE(c_ulong, c_void_p)),
    (
        "DragEnter",
        WINFUNCTYPE(c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)),
    ),
    (
        "DragOver",
        WINFUNCTYPE(c_int32, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)),
    ),
    ("DragLeave", WINFUNCTYPE(c_int32, c_void_p)),
    (
        "Drop",
        WINFUNCTYPE(c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)),
    ),
]


def parse_file_group_descriptor_w(blob: bytes) -> list[str]:
    """Parse FILEGROUPDESCRIPTORW. Names only; contents come from FileContents."""
    if len(blob) < 4:
        return []
    count = int.from_bytes(blob[0:4], "little")
    names: list[str] = []
    offset = 4
    for _ in range(max(count, 0)):
        if offset + FILEDESCRIPTORW_SIZE > len(blob):
            break
        raw = blob[offset + FD_NAME_OFFSET : offset + FD_NAME_OFFSET + MAX_PATH_WCHARS * 2]
        name = raw.decode("utf-16-le", errors="ignore").split("\0", 1)[0].strip()
        if name:
            names.append(name)
        offset += FILEDESCRIPTORW_SIZE
    return names


def parse_file_group_descriptor_a(blob: bytes) -> list[str]:
    if len(blob) < 4:
        return []
    count = int.from_bytes(blob[0:4], "little")
    names: list[str] = []
    offset = 4
    for _ in range(max(count, 0)):
        if offset + FILEDESCRIPTORA_SIZE > len(blob):
            break
        raw = blob[offset + FD_NAME_OFFSET : offset + FD_NAME_OFFSET + 260]
        name = raw.split(b"\0", 1)[0].decode("mbcs", errors="ignore").strip()
        if name:
            names.append(name)
        offset += FILEDESCRIPTORA_SIZE
    return names


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "drop", message)
    except Exception:
        return


def _live_com(punk: int) -> bool:
    """Real IUnknown*. Tests pass pdataobj=1; never `_vtable(1)`."""
    try:
        return int(punk) >= _MIN_LIVE_COM
    except (TypeError, ValueError):
        return False


def _fmt_hr(hr: int) -> str:
    return f"{int(hr) & 0xFFFFFFFF:#x}"


def _vtable(punk: int):
    if not _live_com(punk):
        raise ValueError("null COM pointer")
    lp_vtbl = cast(punk, POINTER(c_void_p)).contents
    if not lp_vtbl:
        raise ValueError("null vtable")
    return cast(lp_vtbl, POINTER(c_void_p))


def _addref(punk: int) -> int:
    if not _live_com(punk):
        return 0
    fn = WINFUNCTYPE(c_ulong, c_void_p)(_vtable(punk)[1])
    return int(fn(punk))


def _release(punk: int) -> int:
    if not _live_com(punk):
        return 0
    fn = WINFUNCTYPE(c_ulong, c_void_p)(_vtable(punk)[2])
    return int(fn(punk))


def _ensure_ole() -> bool:
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
    if not _ole_ready:
        _log(f"OleInitialize hr={hr:#x}", level="WARN")
    return _ole_ready


def _clipboard_format(name: str) -> int:
    windll.user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    windll.user32.RegisterClipboardFormatW.restype = wintypes.UINT
    return int(windll.user32.RegisterClipboardFormatW(name))


def _global_bytes(handle: int) -> bytes:
    if not handle:
        return b""
    try:
        kernel32 = windll.kernel32
        kernel32.GlobalSize.argtypes = [c_void_p]
        kernel32.GlobalSize.restype = c_ulonglong
        kernel32.GlobalLock.argtypes = [c_void_p]
        kernel32.GlobalLock.restype = c_void_p
        kernel32.GlobalUnlock.argtypes = [c_void_p]
        size = int(kernel32.GlobalSize(handle))
        if size <= 0:
            return b""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return b""
        try:
            return bytes(cast(locked, POINTER(c_byte * size)).contents)
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        return b""


def _release_medium(medium: STGMEDIUM) -> None:
    try:
        windll.ole32.ReleaseStgMedium.argtypes = [POINTER(STGMEDIUM)]
        windll.ole32.ReleaseStgMedium.restype = None
        windll.ole32.ReleaseStgMedium(byref(medium))
    except Exception:
        return


def _medium_bytes(medium: STGMEDIUM) -> bytes:
    """Read STGMEDIUM. tymed is a bitmask; Outlook may set ISTREAM|HGLOBAL."""
    try:
        tymed = int(medium.tymed)
        blob = b""
        if tymed & TYMED_HGLOBAL:
            blob = _global_bytes(medium.u.hGlobal or 0)
        if not blob and (tymed & TYMED_ISTREAM):
            blob = _read_istream(medium.u.pstm or 0)
        if not blob and (tymed & TYMED_ISTORAGE):
            blob = _read_istorage(medium.u.pstg or 0)
        if not blob and (tymed & TYMED_FILE) and medium.u.lpszFileName:
            path = wintypes.LPCWSTR(medium.u.lpszFileName).value
            if path:
                try:
                    blob = Path(path).read_bytes()
                except OSError:
                    blob = b""
        return blob
    except Exception:
        return b""


def _query_get_data(pdataobj: int, cf_format: int, *, lindex: int = -1, tymed: int = TYMED_HGLOBAL) -> bool:
    if not _live_com(pdataobj) or not cf_format:
        return False
    try:
        fmt = FORMATETC()
        fmt.cfFormat = cf_format
        fmt.ptd = None
        fmt.dwAspect = DVASPECT_CONTENT
        fmt.lindex = lindex
        fmt.tymed = tymed
        query = WINFUNCTYPE(c_int32, c_void_p, POINTER(FORMATETC))(_vtable(pdataobj)[5])
        return int(query(pdataobj, byref(fmt))) >= 0
    except Exception:
        return False


def _format_names(pdataobj: int) -> str:
    """QueryGetData only. Never probes FileContents (Outlook stream is once / can AV)."""
    if not pdataobj:
        return "none"
    found: list[str] = []
    probes = (
        (CF_HDROP, "CF_HDROP", TYMED_HGLOBAL, -1),
        (_clipboard_format("FileGroupDescriptorW"), "FileGroupDescriptorW", TYMED_HGLOBAL | TYMED_ISTREAM, -1),
        (_clipboard_format("FileGroupDescriptor"), "FileGroupDescriptor", TYMED_HGLOBAL | TYMED_ISTREAM, -1),
        (_clipboard_format("FileNameW"), "FileNameW", TYMED_HGLOBAL, -1),
        (_clipboard_format("FileName"), "FileName", TYMED_HGLOBAL, -1),
    )
    seen: set[str] = set()
    for cf_format, name, tymed, lindex in probes:
        if not cf_format or name in seen:
            continue
        if _query_get_data(pdataobj, cf_format, lindex=lindex, tymed=tymed):
            found.append(name)
            seen.add(name)
    return ",".join(found) or "none"


def _filecontents_lindex_candidates(index: int) -> list[int]:
    """FORMATETC.lindex for one FILEDESCRIPTOR.

    Shell and Outlook Copy are 0-based. Never fall back to lindex 0 for a later
    file — that duplicated the first PDF. The 1.61 1-based guess (index+1) was
    wrong and did not read file 2.
    """
    index = int(index)
    if index <= 0:
        return [0, -1]
    return [index]


def _try_get_data(
    pdataobj: int, cf_format: int, *, lindex: int = -1, tymed: int = TYMED_HGLOBAL
) -> tuple[int, STGMEDIUM | None]:
    """IDataObject::GetData. Never walks a fake test pointer."""
    global _last_get_hr
    _last_get_hr = 1
    if not _live_com(pdataobj) or not cf_format:
        return 1, None
    try:
        fmt = FORMATETC()
        fmt.cfFormat = cf_format
        fmt.ptd = None
        fmt.dwAspect = DVASPECT_CONTENT
        fmt.lindex = lindex
        fmt.tymed = tymed
        get_data = WINFUNCTYPE(c_int32, c_void_p, POINTER(FORMATETC), POINTER(STGMEDIUM))(
            _vtable(pdataobj)[3]
        )
        medium = STGMEDIUM()
        hr = int(get_data(pdataobj, byref(fmt), byref(medium)))
        _last_get_hr = hr
        if hr < 0:
            return hr, None
        return hr, medium
    except Exception:
        _last_get_hr = _hresult(E_UNEXPECTED)
        return _last_get_hr, None


def _get_data(pdataobj: int, cf_format: int, *, lindex: int = -1, tymed: int = TYMED_HGLOBAL) -> STGMEDIUM | None:
    _hr, medium = _try_get_data(pdataobj, cf_format, lindex=lindex, tymed=tymed)
    return medium


def _get_data_here(
    pdataobj: int,
    cf_format: int,
    *,
    lindex: int = -1,
    tymed: int = TYMED_ISTREAM,
) -> STGMEDIUM | None:
    """IDataObject::GetDataHere into a caller-owned IStream.

    Outlook's clipboard often returns an empty IStream from GetData for later
    FileContents indices; GetDataHere into a caller-owned stream is the fallback.
    Tests pass pdataobj=1 — never vtable that.
    """
    global _last_here_hr
    _last_here_hr = 1
    if not _live_com(pdataobj) or not cf_format or not ole_available():
        return None
    pstm = c_void_p()
    medium: STGMEDIUM | None = None
    try:
        ole32 = windll.ole32
        ole32.CreateStreamOnHGlobal.argtypes = [c_void_p, wintypes.BOOL, POINTER(c_void_p)]
        ole32.CreateStreamOnHGlobal.restype = c_int32
        hr = int(ole32.CreateStreamOnHGlobal(None, True, byref(pstm)))
        if hr < 0 or not pstm.value:
            _last_here_hr = hr if hr < 0 else 1
            return None
        fmt = FORMATETC()
        fmt.cfFormat = cf_format
        fmt.ptd = None
        fmt.dwAspect = DVASPECT_CONTENT
        fmt.lindex = lindex
        fmt.tymed = int(tymed) or TYMED_ISTREAM
        medium = STGMEDIUM()
        medium.tymed = TYMED_ISTREAM
        medium.u.pstm = pstm.value
        medium.pUnkForRelease = None
        get_here = WINFUNCTYPE(c_int32, c_void_p, POINTER(FORMATETC), POINTER(STGMEDIUM))(
            _vtable(pdataobj)[4]
        )
        hr = int(get_here(pdataobj, byref(fmt), byref(medium)))
        _last_here_hr = hr
        if hr < 0:
            _release_medium(medium)
            return None
        return medium
    except Exception:
        _last_here_hr = _hresult(E_UNEXPECTED)
        if medium is not None:
            with contextlib.suppress(Exception):
                _release_medium(medium)
        elif pstm.value:
            with contextlib.suppress(Exception):
                _release(int(pstm.value))
        return None


def _read_istream(pstm: int) -> bytes:
    if not pstm:
        return b""
    try:
        # Outlook's later FileContents streams are often already at EOF until Seek(0).
        with contextlib.suppress(Exception):
            seek_fn = WINFUNCTYPE(
                c_int32, c_void_p, c_int64, wintypes.DWORD, POINTER(c_ulonglong)
            )(_vtable(pstm)[5])
            seek_fn(pstm, 0, 0, None)
        read_fn = WINFUNCTYPE(c_int32, c_void_p, c_void_p, c_ulong, POINTER(c_ulong))(_vtable(pstm)[3])
        chunks: list[bytes] = []
        buf = (c_byte * 65536)()
        while True:
            got = c_ulong(0)
            hr = int(read_fn(pstm, buf, 65536, byref(got)))
            if hr < 0:
                break
            n = int(got.value)
            if n:
                chunks.append(bytes(buf[:n]))
            if n < 65536:
                break
            if len(chunks) > 512:
                break
        return b"".join(chunks)
    except Exception:
        return b""


def _read_istorage(pstg: int) -> bytes:
    if not pstg:
        return b""
    try:
        open_stream = WINFUNCTYPE(
            c_int32,
            c_void_p,
            wintypes.LPCWSTR,
            c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            POINTER(c_void_p),
        )(_vtable(pstg)[4])
        stgm_read = 0x00000000
        stgm_share_exclusive = 0x00000010
        for name in ("CONTENTS", "Package"):
            pstm = c_void_p()
            hr = int(open_stream(pstg, name, None, stgm_read | stgm_share_exclusive, 0, byref(pstm)))
            if hr < 0 or not pstm.value:
                continue
            try:
                blob = _read_istream(int(pstm.value))
            finally:
                _release(int(pstm.value))
            if blob:
                return blob
    except Exception:
        return b""
    return b""


def _hdrop_paths(hdrop: int) -> list[str]:
    if not hdrop:
        return []
    try:
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
    except Exception:
        return []


def _read_bytes(path: str) -> bytes | None:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return None
    return data


def extract_drop_sources(pdataobj: int) -> list[DropSource]:
    """Read HDROP paths and/or FileGroupDescriptorW + FileContents while IDataObject is live."""
    if not pdataobj:
        return []
    try:
        return _extract_drop_sources(pdataobj)
    except Exception as exc:
        _log(f"extract {exc}", level="WARN")
        return []


def _descriptor_names(pdataobj: int, cf_format: int, parse) -> list[str]:
    """GetData FILEGROUPDESCRIPTOR, parse names, ReleaseStgMedium immediately.

    1.62 held this medium across FileContents GetData. Live Outlook then returned
    empty IStreams for every index, including a single-file paste (names=1 ok=0).
    """
    if not cf_format:
        return []
    medium = _get_data(pdataobj, cf_format, tymed=TYMED_HGLOBAL | TYMED_ISTREAM)
    if medium is None:
        return []
    try:
        return parse(_medium_bytes(medium))
    finally:
        _release_medium(medium)


def _hdrop_source_paths(pdataobj: int) -> list[str]:
    medium = _get_data(pdataobj, CF_HDROP, tymed=TYMED_HGLOBAL)
    if medium is None:
        return []
    try:
        return _hdrop_paths(medium.u.hGlobal or 0)
    finally:
        _release_medium(medium)


def _extract_drop_sources(pdataobj: int) -> list[DropSource]:
    formats = _format_names(pdataobj)
    cf_desc_w = _clipboard_format("FileGroupDescriptorW")
    cf_desc_a = _clipboard_format("FileGroupDescriptor")
    cf_contents = _clipboard_format("FileContents")
    cf_filename_w = _clipboard_format("FileNameW")
    cf_filename_a = _clipboard_format("FileName")
    names = _descriptor_names(pdataobj, cf_desc_w, parse_file_group_descriptor_w)
    if not names:
        names = _descriptor_names(pdataobj, cf_desc_a, parse_file_group_descriptor_a)
    hdrop_paths = _hdrop_source_paths(pdataobj)
    sources: list[DropSource] = []
    by_name = {Path(path).name.casefold(): path for path in hdrop_paths}
    if names:
        blobs = _file_contents_batch(pdataobj, cf_contents, len(names))
        for index, name in enumerate(names):
            blob = blobs[index] if index < len(blobs) else None
            path = None
            if not blob:
                match = by_name.get(Path(name.replace("\\", "/")).name.casefold())
                if match:
                    path = Path(match)
                    blob = _read_bytes(match)
            sources.append(DropSource(name=name, path=path, data=blob))
            if not blob and path is None:
                _log(f"FileContents miss name={name[:80]} index={index}", level="WARN")
        ok = sum(1 for item in sources if item.data or item.path)
        _log(
            f"extract formats={formats} names={len(names)} hdrop={len(hdrop_paths)} ok={ok}",
            level="WARN" if ok == 0 else "INFO",
        )
        return sources

    if hdrop_paths:
        out: list[DropSource] = []
        for path in hdrop_paths:
            out.append(DropSource(name=Path(path).name, path=Path(path), data=_read_bytes(path)))
        _log(f"extract formats={formats} names=0 hdrop={len(hdrop_paths)} ok={len(out)}")
        return out

    for cf_name in (cf_filename_w, cf_filename_a):
        medium = _get_data(pdataobj, cf_name, tymed=TYMED_HGLOBAL)
        if medium is None:
            continue
        text = ""
        try:
            raw = _medium_bytes(medium)
            if cf_name == cf_filename_w:
                text = raw.decode("utf-16-le", errors="ignore").split("\0", 1)[0].strip()
            else:
                text = raw.split(b"\0", 1)[0].decode("mbcs", errors="ignore").strip()
        finally:
            _release_medium(medium)
        if text:
            source = [DropSource(name=Path(text).name, path=Path(text), data=_read_bytes(text))]
            _log(f"extract formats={formats} names=FileName hdrop=0 ok=1")
            return source

    blob = _file_contents_bytes(pdataobj, cf_contents, 0)
    if blob:
        source = [DropSource(name="attachment.pdf", path=None, data=blob)]
        _log(f"extract formats={formats} names=0 hdrop=0 ok=1 FileContents")
        return source
    _log(f"extract formats={formats} names={len(names)} hdrop={len(hdrop_paths)} ok=0", level="WARN")
    return sources


def _guid(data1: int, data2: int, data3: int, data4: bytes) -> GUID:
    return GUID(data1, data2, data3, (c_byte * 8)(*data4))


def _folder_pdf_state(folder: Path) -> dict[str, tuple[Path, int, int]]:
    found: dict[str, tuple[Path, int, int]] = {}
    try:
        for path in Path(folder).iterdir():
            if not path.is_file() or not is_pdf_filename(path.name):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            found[path.name.casefold()] = (path, int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        return {}
    return found


def _new_folder_pdfs(folder: Path, before: dict[str, tuple[Path, int, int]]) -> list[Path]:
    after = _folder_pdf_state(folder)
    out: list[Path] = []
    for key, (path, mtime, size) in after.items():
        prev = before.get(key)
        if prev is None or prev[1:] != (mtime, size):
            out.append(path)
    return out


def paste_dataobject_into_folder(pdataobj: int, folder: Path) -> list[Path]:
    """Paste an IDataObject into a directory the way Explorer pastes into a folder.

    Outlook Copy of attachments often advertises FileGroupDescriptorW names and
    then returns empty FileContents IStreams. Ctrl+V in Explorer still writes the
    files: IFileOperation::CopyItems, or the folder's IDropTarget. Same clipboard,
    that Shell path. Never call from gui.py.
    """
    dest = Path(folder)
    if not _live_com(pdataobj) or not ole_available() or not _ensure_ole():
        return []
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as vis:
        _log(f"folder paste mkdir {vis}", level="WARN")
        return []
    before = _folder_pdf_state(dest)
    copied = _file_operation_copy(pdataobj, dest) or _folder_drop_target_copy(pdataobj, dest)
    if not copied:
        _log("folder paste CopyItems and IDropTarget both missed", level="WARN")
        return []
    paths = _new_folder_pdfs(dest, before)
    names = ",".join(path.name[:80] for path in paths[:6]) or "none"
    _log(f"folder paste pdfs={len(paths)} names={names}")
    return paths


def _file_operation_copy(pdataobj: int, folder: Path) -> bool:
    """IFileOperation::CopyItems(IDataObject, dest folder)."""
    ole32 = windll.ole32
    shell32 = windll.shell32
    pfo = c_void_p()
    psi = c_void_p()
    try:
        ole32.CoCreateInstance.argtypes = [
            POINTER(GUID),
            c_void_p,
            wintypes.DWORD,
            POINTER(GUID),
            POINTER(c_void_p),
        ]
        ole32.CoCreateInstance.restype = c_int32
        clsid = _guid(0x3AD05575, 0x8857, 0x4850, b"\x92\x77\x11\xb8\x5b\xdb\x8e\x09")
        iid_fo = _guid(0x947AAB5F, 0x0A5C, 0x4C13, b"\xb4\xd6\x4b\xf7\x83\x6f\xc9\xf8")
        hr = int(ole32.CoCreateInstance(byref(clsid), None, CLSCTX_INPROC_SERVER, byref(iid_fo), byref(pfo)))
        if hr < 0 or not pfo.value:
            _log(f"folder paste CoCreateInstance hr={_fmt_hr(hr)}", level="WARN")
            return False
        shell32.SHCreateItemFromParsingName.argtypes = [
            wintypes.LPCWSTR,
            c_void_p,
            POINTER(GUID),
            POINTER(c_void_p),
        ]
        shell32.SHCreateItemFromParsingName.restype = c_int32
        iid_item = _guid(0x43826D1E, 0xE718, 0x42EE, b"\xbc\x55\xa1\xe2\x61\xc3\x7b\xfe")
        hr = int(
            shell32.SHCreateItemFromParsingName(str(folder), None, byref(iid_item), byref(psi))
        )
        if hr < 0 or not psi.value:
            _log(f"folder paste SHCreateItemFromParsingName hr={_fmt_hr(hr)}", level="WARN")
            return False
        set_flags = WINFUNCTYPE(c_int32, c_void_p, wintypes.DWORD)(_vtable(int(pfo.value))[5])
        copy_items = WINFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)(_vtable(int(pfo.value))[17])
        perform = WINFUNCTYPE(c_int32, c_void_p)(_vtable(int(pfo.value))[21])
        hr = int(set_flags(int(pfo.value), _FO_FLAGS))
        if hr < 0:
            _log(f"folder paste SetOperationFlags hr={_fmt_hr(hr)}", level="WARN")
            return False
        hr = int(copy_items(int(pfo.value), pdataobj, int(psi.value)))
        if hr < 0:
            _log(f"folder paste CopyItems hr={_fmt_hr(hr)}", level="WARN")
            return False
        hr = int(perform(int(pfo.value)))
        if hr < 0:
            _log(f"folder paste PerformOperations hr={_fmt_hr(hr)}", level="WARN")
            return False
        return True
    except Exception as vis:
        _log(f"folder paste IFileOperation {type(vis).__name__}: {vis}", level="WARN")
        return False
    finally:
        if psi.value:
            with contextlib.suppress(Exception):
                _release(int(psi.value))
        if pfo.value:
            with contextlib.suppress(Exception):
                _release(int(pfo.value))


def _folder_drop_target_copy(pdataobj: int, folder: Path) -> bool:
    """IDropTarget::Drop on the destination folder — Explorer's other paste path."""
    shell32 = windll.shell32
    ole32 = windll.ole32
    pidl = c_void_p()
    psf = c_void_p()
    pdt = c_void_p()
    last = c_void_p()
    try:
        shell32.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell32.ILCreateFromPathW.restype = c_void_p
        pidl.value = shell32.ILCreateFromPathW(str(folder))
        if not pidl.value:
            _log("folder paste ILCreateFromPathW empty", level="WARN")
            return False
        shell32.SHBindToParent.argtypes = [
            c_void_p,
            POINTER(GUID),
            POINTER(c_void_p),
            POINTER(c_void_p),
        ]
        shell32.SHBindToParent.restype = c_int32
        iid_folder = _guid(0x000214E6, 0x0000, 0x0000, IID_COM_DATA4)
        hr = int(shell32.SHBindToParent(pidl.value, byref(iid_folder), byref(psf), byref(last)))
        if hr < 0 or not psf.value or not last.value:
            _log(f"folder paste SHBindToParent hr={_fmt_hr(hr)}", level="WARN")
            return False
        get_ui = WINFUNCTYPE(
            c_int32,
            c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            POINTER(c_void_p),
            POINTER(GUID),
            POINTER(wintypes.UINT),
            POINTER(c_void_p),
        )(_vtable(int(psf.value))[10])
        iid_drop = _guid(IID_IDROPTARGET_DATA1, 0x0000, 0x0000, IID_COM_DATA4)
        child = c_void_p(last.value)
        hr = int(
            get_ui(int(psf.value), 0, 1, byref(child), byref(iid_drop), None, byref(pdt))
        )
        if hr < 0 or not pdt.value:
            _log(f"folder paste GetUIObjectOf IDropTarget hr={_fmt_hr(hr)}", level="WARN")
            return False
        enter = WINFUNCTYPE(
            c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)
        )(_vtable(int(pdt.value))[3])
        drop = WINFUNCTYPE(
            c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)
        )(_vtable(int(pdt.value))[6])
        leave = WINFUNCTYPE(c_int32, c_void_p)(_vtable(int(pdt.value))[5])
        effect = wintypes.DWORD(DROPEFFECT_COPY)
        pt = PointArg(0)
        hr = int(enter(int(pdt.value), pdataobj, MK_LBUTTON, pt, byref(effect)))
        if hr < 0 or int(effect.value) == DROPEFFECT_NONE:
            _log(f"folder paste DragEnter hr={_fmt_hr(hr)} effect={int(effect.value)}", level="WARN")
            with contextlib.suppress(Exception):
                leave(int(pdt.value))
            return False
        effect = wintypes.DWORD(DROPEFFECT_COPY)
        hr = int(drop(int(pdt.value), pdataobj, MK_LBUTTON, pt, byref(effect)))
        if hr < 0:
            _log(f"folder paste Drop hr={_fmt_hr(hr)}", level="WARN")
            return False
        return True
    except Exception as vis:
        _log(f"folder paste IDropTarget {type(vis).__name__}: {vis}", level="WARN")
        return False
    finally:
        if pdt.value:
            with contextlib.suppress(Exception):
                _release(int(pdt.value))
        if psf.value:
            with contextlib.suppress(Exception):
                _release(int(psf.value))
        if pidl.value:
            with contextlib.suppress(Exception):
                ole32.CoTaskMemFree.argtypes = [c_void_p]
                ole32.CoTaskMemFree.restype = None
                ole32.CoTaskMemFree(pidl.value)


_FILECONTENTS_TYMED = (
    TYMED_ISTREAM,
    TYMED_ISTREAM | TYMED_HGLOBAL | TYMED_FILE | TYMED_ISTORAGE,
    TYMED_HGLOBAL,
    TYMED_FILE,
    TYMED_ISTORAGE,
)


def _get_data_file_contents(pdataobj: int, cf_contents: int, index: int) -> tuple[STGMEDIUM | None, int, int]:
    """First successful GetData for this descriptor index. Does not read or release."""
    last_hr = 1
    last_tymed = 0
    for lindex in _filecontents_lindex_candidates(index):
        for mask in _FILECONTENTS_TYMED:
            medium = _get_data(pdataobj, cf_contents, lindex=lindex, tymed=mask)
            last_hr = _last_get_hr
            last_tymed = int(mask)
            if medium is not None:
                return medium, last_hr, last_tymed
    return None, last_hr, last_tymed


def _get_data_here_file_contents(pdataobj: int, cf_contents: int, index: int) -> tuple[STGMEDIUM | None, int, int]:
    """First successful GetDataHere for this descriptor index. Does not read or release."""
    last_hr = 1
    last_tymed = TYMED_ISTREAM
    for lindex in _filecontents_lindex_candidates(index):
        medium = _get_data_here(pdataobj, cf_contents, lindex=lindex, tymed=TYMED_ISTREAM)
        last_hr = _last_here_hr
        if medium is not None:
            return medium, last_hr, TYMED_ISTREAM
    return None, last_hr, last_tymed


def _read_and_release_medium(medium: STGMEDIUM | None) -> bytes | None:
    if medium is None:
        return None
    try:
        return _medium_bytes(medium) or None
    finally:
        _release_medium(medium)


def _log_file_contents(index: int, get_hr: int, tymed: int, n: int, here_hr: int | None) -> None:
    """Log every FileContents hop. 1.62 hid index 0, which hid the single-file miss."""
    line = f"FileContents index={index} GetData hr={_fmt_hr(get_hr)} tymed={tymed} bytes={n}"
    if here_hr is not None:
        line = (
            f"FileContents index={index} GetData hr={_fmt_hr(get_hr)} "
            f"GetDataHere hr={_fmt_hr(here_hr)} tymed={tymed} bytes={n}"
        )
    _log(line, level="WARN" if n == 0 else "INFO")
    if n == 0:
        _log(
            f"FileContents miss index={int(index)} tried={_filecontents_lindex_candidates(index)}",
            level="WARN",
        )


def _file_contents_batch(pdataobj: int, cf_contents: int, count: int) -> list[bytes | None]:
    """GetData + read + release each FileContents index; GetDataHere if that was empty.

    1.62 held every FileContents STGMEDIUM (and the FILEGROUPDESCRIPTOR) until
    after all GetData calls, then read. Live Outlook then returned names=2 ok=0
    and even names=1 ok=0: GetData index 1 was hr=0 tymed=ISTREAM bytes=0 so
    GetDataHere never ran, and file 0 was empty too. 1.61 sequential get-then-read
    staged file 0. Empty GetData must still try GetDataHere. Never falls back to
    lindex 0 for a later file.
    """
    if count <= 0:
        return []
    if not pdataobj or not cf_contents:
        return [None] * count
    return [_file_contents_bytes(pdataobj, cf_contents, index) for index in range(count)]


def _file_contents_bytes(pdataobj: int, cf_contents: int, index: int) -> bytes | None:
    """Read one FileContents index. Empty or invalid IDataObject returns None — never raises.

    Try every tymed (empty ISTREAM is not success — 1.63 stopped at the first
    medium). Then GetDataHere. Never falls back to lindex 0 for index>0.
    """
    if not pdataobj or not cf_contents:
        return None
    try:
        last_get_hr = 1
        last_tymed = 0
        for lindex in _filecontents_lindex_candidates(int(index)):
            for mask in _FILECONTENTS_TYMED:
                medium = _get_data(pdataobj, cf_contents, lindex=lindex, tymed=mask)
                last_get_hr = _last_get_hr
                if medium is None:
                    last_tymed = int(mask)
                    continue
                last_tymed = int(getattr(medium, "tymed", mask) or mask)
                blob = _read_and_release_medium(medium)
                if blob:
                    _log_file_contents(int(index), last_get_hr, last_tymed, len(blob), None)
                    return blob
        here_hr: int | None = None
        medium, here_hr, here_tymed = _get_data_here_file_contents(
            pdataobj, cf_contents, int(index)
        )
        blob = _read_and_release_medium(medium)
        n = len(blob) if blob else 0
        _log_file_contents(int(index), last_get_hr, int(here_tymed or last_tymed), n, here_hr)
        return blob
    except Exception as vis:
        _log(f"FileContents {vis}", level="WARN")
        return None


def _iid_match(riid: GUID, data1: int) -> bool:
    return (
        int(riid.Data1) == data1
        and int(riid.Data2) == 0
        and int(riid.Data3) == 0
        and bytes(riid.Data4) == IID_COM_DATA4
    )


def _set_copy_effect(pdw_effect) -> None:
    """Always advertise COPY. FileGroupDescriptorW / FileContents / HDROP need a copy cursor."""
    if not pdw_effect:
        return
    try:
        pdw_effect[0] = DROPEFFECT_COPY
    except (TypeError, ValueError, IndexError):
        return


def _set_none_effect(pdw_effect) -> None:
    if not pdw_effect:
        return
    try:
        pdw_effect[0] = DROPEFFECT_NONE
    except (TypeError, ValueError, IndexError):
        return


_TARGETS: dict[int, _ComDropTarget] = {}


class _ComDropTarget:
    def __init__(
        self,
        callback: DropCallback,
        hover: HoverCallback | None = None,
        leave: LeaveCallback | None = None,
        schedule: ScheduleCallback | None = None,
        drop_gate: DropGate | None = None,
    ) -> None:
        self.callback = callback
        self.hover = hover
        self.leave = leave
        self.schedule = schedule
        self.drop_gate = drop_gate
        self.ref = 1
        self._dataobj = 0
        self._hover_xy: tuple[int, int] | None = None
        self._hover_scheduled = False
        self._qi = WINFUNCTYPE(c_int32, c_void_p, POINTER(GUID), POINTER(c_void_p))(self._query_interface)
        self._add = WINFUNCTYPE(c_ulong, c_void_p)(self._add_ref)
        self._rel = WINFUNCTYPE(c_ulong, c_void_p)(self._release)
        self._enter = WINFUNCTYPE(
            c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)
        )(self._drag_enter)
        self._over = WINFUNCTYPE(c_int32, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD))(
            self._drag_over
        )
        self._leave = WINFUNCTYPE(c_int32, c_void_p)(self._drag_leave)
        self._drop = WINFUNCTYPE(
            c_int32, c_void_p, c_void_p, wintypes.DWORD, PointArg, POINTER(wintypes.DWORD)
        )(self._drop_method)
        self._vtbl = IDropTargetVtbl(
            QueryInterface=self._qi,
            AddRef=self._add,
            Release=self._rel,
            DragEnter=self._enter,
            DragOver=self._over,
            DragLeave=self._leave,
            Drop=self._drop,
        )
        self._obj = DropTargetObj(lpVtbl=pointer(self._vtbl))
        _TARGETS[addressof(self._obj)] = self

    def as_punk(self) -> int:
        return addressof(self._obj)

    def _schedule(self, fn: Callable[[], None]) -> None:
        if self.schedule is None:
            _log("schedule skipped: no Tk marshal", level="WARN")
            return
        try:
            self.schedule(fn)
        except Exception as exc:
            _log(f"schedule {exc}", level="WARN")

    def _query_interface(self, this, riid, ppv) -> int:
        try:
            if not ppv:
                return _hresult(E_NOINTERFACE)
            guid = riid.contents
            if _iid_match(guid, IID_IUNKNOWN_DATA1) or _iid_match(guid, IID_IDROPTARGET_DATA1):
                ppv[0] = this
                self._add_ref(this)
                return S_OK
            ppv[0] = None
            return _hresult(E_NOINTERFACE)
        except Exception as exc:
            _log(f"QueryInterface {exc}", level="WARN")
            return _hresult(E_NOINTERFACE)

    def _add_ref(self, _this) -> int:
        self.ref += 1
        return self.ref

    def _release(self, _this) -> int:
        if self.ref > 1:
            self.ref -= 1
        return self.ref

    def _clear_dataobj(self) -> None:
        if self._dataobj:
            with contextlib.suppress(Exception):
                _release(self._dataobj)
            self._dataobj = 0

    def _drag_enter(self, _this, pdataobj, _keys, pt, pdw_effect) -> int:
        try:
            _set_copy_effect(pdw_effect)
            self._clear_dataobj()
            if pdataobj:
                self._dataobj = pdataobj
                with contextlib.suppress(Exception):
                    _addref(pdataobj)
            _set_copy_effect(pdw_effect)
            with contextlib.suppress(Exception):
                self._notify_hover(pt)
            return S_OK
        except Exception as exc:
            _log(f"DragEnter {exc}", level="WARN")
            _set_copy_effect(pdw_effect)
            return S_OK

    def _drag_over(self, _this, _keys, pt, pdw_effect) -> int:
        try:
            _set_copy_effect(pdw_effect)
            with contextlib.suppress(Exception):
                self._notify_hover(pt)
            return S_OK
        except Exception as exc:
            _log(f"DragOver {exc}", level="WARN")
            _set_none_effect(pdw_effect)
            return S_OK

    def _drag_leave(self, _this) -> int:
        try:
            self._clear_dataobj()
            if self.leave is not None:
                self._schedule(self.leave)
            return S_OK
        except Exception as exc:
            _log(f"DragLeave {exc}", level="WARN")
            return S_OK

    def _notify_hover(self, pt) -> None:
        if self.hover is None:
            return
        x, y = unpack_pointl(pt)
        self._hover_xy = (x, y)
        if self._hover_scheduled:
            return
        self._hover_scheduled = True

        def run() -> None:
            self._hover_scheduled = False
            xy = self._hover_xy
            if self.hover is None or xy is None:
                return
            self.hover(xy[0], xy[1])

        self._schedule(run)

    def _drop_method(self, _this, pdataobj, _keys, pt, pdw_effect) -> int:
        if self.drop_gate is not None:
            with contextlib.suppress(Exception):
                self.drop_gate(True)
        try:
            try:
                self._hover_xy = None
                self._hover_scheduled = False
                _set_copy_effect(pdw_effect)
                obj = pdataobj or self._dataobj
                x, y = unpack_pointl(pt)
                sources = extract_drop_sources(obj) if obj else []
                self._clear_dataobj()
                captured = list(sources)
                ok = sum(1 for item in captured if item.data or item.path)
                names = ",".join((item.name or "?")[:80] for item in captured[:6]) or "none"
                _log(f"Drop pt={x},{y} sources={len(captured)} ok={ok} names={names}")

                def deliver(items=captured, px=x, py=y) -> None:
                    if self.leave is not None:
                        self.leave()
                    self.callback(items, px, py)

                self._schedule(deliver)
                return S_OK
            except Exception as exc:
                _log(f"Drop {exc}", level="WARN")
                with contextlib.suppress(Exception):
                    self._clear_dataobj()
                _set_none_effect(pdw_effect)
                return S_OK
        finally:
            if self.drop_gate is not None:
                with contextlib.suppress(Exception):
                    self.drop_gate(False)


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


def drop_target_hwnds(widget, extras=None) -> list[int]:
    """Toplevel client + wm_frame + optional board canvas. Never EnumChildWindows of rows."""
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
    for extra in extras or ():
        with contextlib.suppress(Exception):
            add(int(extra.winfo_id()))
    return hwnds


def collect_tk_hwnds(widget) -> list[int]:
    """Back-compat alias. Never walks the child HWND tree."""
    return drop_target_hwnds(widget)


class DropHost:
    """Register IDropTarget once on the toplevel (not every drawing-row HWND)."""

    def __init__(
        self,
        callback: DropCallback,
        hover: HoverCallback | None = None,
        leave: LeaveCallback | None = None,
    ) -> None:
        self._callback = callback
        self._hover = hover
        self._leave = leave
        self._target: _ComDropTarget | None = None
        self._hwnds: list[int] = []
        self._wanted: list[int] = []
        self._widget = None
        self._in_drop = 0
        self._detach_pending = False

    def _schedule(self, fn: Callable[[], None]) -> None:
        widget = self._widget
        if widget is None:
            _log("drop schedule skipped: no widget", level="WARN")
            return

        def run(job=fn) -> None:
            try:
                job()
            except Exception as exc:
                _log(f"scheduled {exc}", level="WARN")

        try:
            widget.after(0, run)
        except Exception as exc:
            _log(f"after(0) {exc}", level="WARN")

    def _drop_gate(self, entering: bool) -> None:
        if entering:
            self._in_drop += 1
            return

        def finish() -> None:
            self._in_drop = max(0, self._in_drop - 1)
            if self._in_drop == 0 and self._detach_pending:
                self._detach_pending = False
                self.detach()

        widget = self._widget
        if widget is not None:
            try:
                widget.after(0, finish)
                return
            except Exception:
                pass
        finish()

    def attach(self, widget, extras=None) -> None:
        self._widget = widget
        if not ole_available() or not _ensure_ole():
            return
        hwnds = drop_target_hwnds(widget, extras=extras)
        if self._target is not None and self._wanted == hwnds:
            return
        if self._in_drop:
            _log("RegisterDragDrop skipped during Drop")
            return
        self.detach()
        self._widget = widget
        self._wanted = list(hwnds)
        self._target = _ComDropTarget(
            self._callback,
            hover=self._hover,
            leave=self._leave,
            schedule=self._schedule,
            drop_gate=self._drop_gate,
        )
        punk = self._target.as_punk()
        ole32 = windll.ole32
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            ole32.RegisterDragDrop.argtypes = [wintypes.HWND, c_void_p]
            ole32.RegisterDragDrop.restype = c_int32
        for hwnd in hwnds:
            hr = int(ole32.RegisterDragDrop(hwnd, punk))
            if hr == S_OK:
                self._hwnds.append(hwnd)
                _log(f"RegisterDragDrop hwnd={hwnd:#x} hr=0")
            elif hr == _hresult(DRAGDROP_E_ALREADYREGISTERED):
                _log(f"RegisterDragDrop hwnd={hwnd:#x} already")
            else:
                _log(f"RegisterDragDrop hwnd={hwnd:#x} hr={hr:#x}", level="WARN")
        if not self._hwnds:
            _log("RegisterDragDrop attached 0 windows", level="WARN")
        if self not in _hosts:
            _hosts.append(self)

    def detach(self) -> None:
        if self._in_drop:
            self._detach_pending = True
            _log("RevokeDragDrop deferred until Drop returns")
            return
        self._detach_pending = False
        self._widget = None
        if not ole_available():
            self._hwnds = []
            self._wanted = []
            self._target = None
            return
        ole32 = getattr(windll, "ole32", None)
        if ole32 is None:
            self._hwnds = []
            self._wanted = []
            self._target = None
            return
        with contextlib.suppress(AttributeError, TypeError, ValueError):
            ole32.RevokeDragDrop.argtypes = [wintypes.HWND]
            ole32.RevokeDragDrop.restype = c_int32
        for hwnd in self._hwnds:
            try:
                ole32.RevokeDragDrop(hwnd)
            except Exception:
                continue
        self._hwnds = []
        self._wanted = []
        if self._target is not None:
            _TARGETS.pop(self._target.as_punk(), None)
        self._target = None
        if self in _hosts:
            _hosts.remove(self)


def register_hwnd(
    hwnd: int,
    callback: DropCallback,
    hover: HoverCallback | None = None,
    leave: LeaveCallback | None = None,
    schedule: ScheduleCallback | None = None,
    drop_gate: DropGate | None = None,
):
    """Register IDropTarget on one HWND. Child process only. Parent must not call this."""
    return register_hwnds(
        [hwnd],
        callback,
        hover=hover,
        leave=leave,
        schedule=schedule,
        drop_gate=drop_gate,
    )


def register_hwnds(
    hwnds: list[int],
    callback: DropCallback,
    hover: HoverCallback | None = None,
    leave: LeaveCallback | None = None,
    schedule: ScheduleCallback | None = None,
    drop_gate: DropGate | None = None,
):
    """Register the same IDropTarget on several HWNDs. Child process only."""
    wanted = [int(hwnd) for hwnd in hwnds if hwnd]
    if not wanted or not ole_available() or not _ensure_ole():
        _log("register_hwnd skipped", level="WARN")
        return None
    target = _ComDropTarget(
        callback,
        hover=hover,
        leave=leave,
        schedule=schedule or (lambda fn: fn()),
        drop_gate=drop_gate,
    )
    ole32 = windll.ole32
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        ole32.RegisterDragDrop.argtypes = [wintypes.HWND, c_void_p]
        ole32.RegisterDragDrop.restype = c_int32
    ok = False
    punk = target.as_punk()
    for hwnd in wanted:
        hr = int(ole32.RegisterDragDrop(hwnd, punk))
        if hr == S_OK:
            _log(f"RegisterDragDrop hwnd={hwnd:#x} hr=0 (child)")
            ok = True
        elif hr == _hresult(DRAGDROP_E_ALREADYREGISTERED):
            _log(f"RegisterDragDrop hwnd={hwnd:#x} already (child)")
            ok = True
        else:
            _log(f"RegisterDragDrop hwnd={hwnd:#x} hr={hr:#x}", level="WARN")
    if not ok:
        _TARGETS.pop(punk, None)
        return None
    return target
