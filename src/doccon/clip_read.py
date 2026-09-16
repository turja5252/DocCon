# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Child-only clipboard read: OleGetClipboard -> IDataObject -> PDF sources.

Never import this module from gui.py. It pulls in win_drop, whose FileContents /
IStream reads can AV on an Outlook attachment. That fault must land in the helper
process, not the console. The parent side lives in `clip_paste`.
"""
from __future__ import annotations

import contextlib
from pathlib import Path

from doccon.drop_pdfs import DropSource, is_pdf_filename


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "paste", message)
    except Exception:
        return


def needs_folder_paste(sources: list[DropSource]) -> bool:
    """True when Outlook named files but FileContents gave no bytes/path."""
    if not sources:
        return False
    return any(not item.data and item.path is None for item in sources)


def merge_folder_paths(sources: list[DropSource], paths: list[Path]) -> list[DropSource]:
    """Fill nameless FileContents misses from an Explorer-style folder paste."""
    by_name = {
        path.name.casefold(): path
        for path in paths
        if path.is_file() and is_pdf_filename(path.name)
    }
    used: set[str] = set()
    out: list[DropSource] = []
    for src in sources:
        key = Path((src.name or "").replace("\\", "/")).name.casefold()
        if src.data or src.path is not None:
            out.append(src)
            if key:
                used.add(key)
            continue
        match = by_name.get(key) if key else None
        if match is not None:
            out.append(DropSource(name=src.name or match.name, path=match, data=None))
            used.add(key)
        else:
            out.append(src)
    for key, path in by_name.items():
        if key not in used:
            out.append(DropSource(name=path.name, path=path, data=None))
    return out


def paste_clipboard_into_folder(folder: Path) -> list[Path]:
    """OleGetClipboard, then the same paste Explorer uses on a directory."""
    from ctypes import POINTER, byref, c_int32, c_void_p

    from doccon.win_drop import (
        _ensure_ole,
        _release,
        ole_available,
        paste_dataobject_into_folder,
        windll,
    )

    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    if not ole_available() or not _ensure_ole():
        _log("folder paste OLE unavailable", level="WARN")
        return []
    ole32 = windll.ole32
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        ole32.OleGetClipboard.argtypes = [POINTER(c_void_p)]
        ole32.OleGetClipboard.restype = c_int32
    pdataobj = c_void_p()
    hr = int(ole32.OleGetClipboard(byref(pdataobj)))
    if hr < 0 or not pdataobj.value:
        _log(f"folder paste OleGetClipboard hr={hr:#x}", level="WARN")
        return []
    punk = int(pdataobj.value)
    try:
        paths = paste_dataobject_into_folder(punk, dest)
    finally:
        with contextlib.suppress(Exception):
            _release(punk)
    names = ",".join(path.name[:80] for path in paths[:6]) or "none"
    _log(f"folder paste into inbox pdfs={len(paths)} names={names}")
    return paths


def read_clipboard_sources(dest: Path | None = None) -> list[DropSource]:
    """PDFs sitting on the Windows clipboard. Empty list when there are none.

    `dest` is the inbox. When FileContents is empty but Outlook named files,
    paste that IDataObject into `dest` the way Explorer pastes into a folder —
    before releasing the clipboard object.
    """
    from ctypes import POINTER, byref, c_int32, c_void_p

    from doccon.win_drop import (
        _ensure_ole,
        _release,
        extract_drop_sources,
        ole_available,
        paste_dataobject_into_folder,
        windll,
    )

    if not ole_available() or not _ensure_ole():
        _log("OLE unavailable", level="WARN")
        return []
    ole32 = windll.ole32
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        ole32.OleGetClipboard.argtypes = [POINTER(c_void_p)]
        ole32.OleGetClipboard.restype = c_int32
    pdataobj = c_void_p()
    hr = int(ole32.OleGetClipboard(byref(pdataobj)))
    if hr < 0 or not pdataobj.value:
        _log(f"OleGetClipboard hr={hr:#x} empty=1", level="WARN")
        return []
    punk = int(pdataobj.value)
    try:
        sources = extract_drop_sources(punk)
        if dest is not None and needs_folder_paste(sources):
            _log("FileContents empty; Explorer-folder paste into inbox")
            sources = merge_folder_paths(
                sources, paste_dataobject_into_folder(punk, Path(dest))
            )
    finally:
        with contextlib.suppress(Exception):
            _release(punk)
    names = ",".join((item.name or "?")[:80] for item in sources[:6]) or "none"
    _log(f"clipboard sources={len(sources)} names={names}")
    return sources
