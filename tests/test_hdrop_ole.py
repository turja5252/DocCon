# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Explorer CF_HDROP OLE in the GUI process. Never FileContents / IStream."""
from __future__ import annotations

from ctypes import pointer, wintypes
from pathlib import Path

from doccon import hdrop_ole


def test_unpack_pointl_screen_xy() -> None:
    packed = 0x0000002A00000010
    assert hdrop_ole.unpack_pointl(packed) == (16, 42)
    pt = hdrop_ole.POINTL(8, 9)
    assert hdrop_ole.unpack_pointl(pt) == (8, 9)


def test_drag_enter_copy_for_hdrop_none_without(monkeypatch) -> None:
    scheduled: list = []
    hovers: list[tuple[int, int]] = []
    target = hdrop_ole._HdropDropTarget(
        lambda *_a: None,
        hover=lambda x, y: hovers.append((x, y)),
        leave=None,
        schedule=scheduled.append,
    )
    monkeypatch.setattr(hdrop_ole, "data_object_has_hdrop", lambda _obj: True)
    effect = wintypes.DWORD(0)
    packed = 0x0000002A00000010
    hr = target._drag_enter(None, 1, 0, packed, pointer(effect))
    assert hr == hdrop_ole.S_OK
    assert int(effect.value) == hdrop_ole.DROPEFFECT_COPY
    assert hovers == []
    assert scheduled
    scheduled[0]()
    assert hovers == [(16, 42)]

    monkeypatch.setattr(hdrop_ole, "data_object_has_hdrop", lambda _obj: False)
    effect = wintypes.DWORD(hdrop_ole.DROPEFFECT_COPY)
    hr = target._drag_enter(None, 1, 0, packed, pointer(effect))
    assert hr == hdrop_ole.S_OK
    assert int(effect.value) == hdrop_ole.DROPEFFECT_NONE


def test_drop_is_scheduled_not_sync(monkeypatch) -> None:
    paired: list = []
    scheduled: list = []
    target = hdrop_ole._HdropDropTarget(
        lambda paths, x, y: paired.append((list(paths), x, y)),
        hover=None,
        leave=None,
        schedule=scheduled.append,
    )
    monkeypatch.setattr(
        hdrop_ole,
        "hdrop_paths_from_data_object",
        lambda _obj: [r"C:\Temp\scan0042.pdf"],
    )
    effect = wintypes.DWORD(0)
    packed = 0x0000002A00000010
    hr = target._drop(None, 1, 0, packed, pointer(effect))
    assert hr == hdrop_ole.S_OK
    assert int(effect.value) == hdrop_ole.DROPEFFECT_COPY
    assert paired == []
    scheduled[-1]()
    assert paired[0][0] == [r"C:\Temp\scan0042.pdf"]
    assert paired[0][1:] == (16, 42)
    assert "2026-075" not in paired[0][0][0]


def test_hdrop_ole_never_extracts_outlook_streams() -> None:
    text = Path(hdrop_ole.__file__).read_text(encoding="utf-8")
    assert "CF_HDROP" in text
    assert "RegisterDragDrop" in text
    assert "from doccon.win_drop" not in text
    assert "import doccon.win_drop" not in text
    assert "_read_istream" not in text
    assert "TYMED_ISTREAM" not in text
    assert "never asks for FileGroupDescriptorW" in text
    assert "FileContents" in text
    assert "never touches an IStream" in text


def test_hdrop_ole_wintypes_names_exist() -> None:
    import ctypes.wintypes as wintypes_mod

    text = Path(hdrop_ole.__file__).read_text(encoding="utf-8")
    used: set[str] = set()
    for token in text.split("wintypes.")[1:]:
        name = ""
        for char in token:
            if char.isalnum() or char == "_":
                name += char
            else:
                break
        if name:
            used.add(name)
    missing = sorted(name for name in used if not hasattr(wintypes_mod, name))
    assert missing == [], f"hdrop_ole references missing ctypes.wintypes names: {missing}"
