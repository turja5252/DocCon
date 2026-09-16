# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from ctypes import pointer, wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest

from doccon import win_drop
from doccon.drop_pdfs import DropSource
from doccon.win_drop import DropHost, drop_target_hwnds, unpack_pointl


def test_unpack_pointl_packed_int64() -> None:
    x, y = unpack_pointl(0x0000002A00000010)
    assert x == 16
    assert y == 42
    x, y = unpack_pointl(-1)
    assert x == -1
    assert y == -1


def test_drop_target_hwnds_skip_child_windows() -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        children = [tk.Label(root, text=f"row-{index}") for index in range(40)]
        for label in children:
            label.pack()
        canvas = tk.Canvas(root, width=80, height=40)
        canvas.pack()
        root.update_idletasks()
        hwnds = drop_target_hwnds(root)
        assert 1 <= len(hwnds) <= 3
        child_ids = {int(label.winfo_id()) for label in children}
        assert child_ids.isdisjoint(set(hwnds))
        assert win_drop.collect_tk_hwnds(root) == hwnds
        with_canvas = drop_target_hwnds(root, extras=[canvas])
        assert int(canvas.winfo_id()) in with_canvas
        assert child_ids.isdisjoint(set(with_canvas))
        assert len(with_canvas) <= 4
    finally:
        root.destroy()


def test_drop_host_registers_toplevel_once(monkeypatch) -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    registered: list[int] = []

    class _Fn:
        def __init__(self, impl) -> None:
            self._impl = impl
            self.argtypes = None
            self.restype = None

        def __call__(self, *args, **kwargs):
            return self._impl(*args, **kwargs)

    class Ole32:
        def __init__(self) -> None:
            self.RegisterDragDrop = _Fn(lambda hwnd, _punk: registered.append(int(hwnd)) or 0)
            self.RevokeDragDrop = _Fn(lambda _hwnd: 0)
            self.OleInitialize = _Fn(lambda _arg: 0)

    ole32 = Ole32()
    monkeypatch.setattr(win_drop, "ole_available", lambda: True)
    monkeypatch.setattr(win_drop, "_ensure_ole", lambda: True)
    monkeypatch.setattr(win_drop, "windll", SimpleNamespace(ole32=ole32))
    try:
        for _index in range(24):
            tk.Frame(root).pack()
        root.update_idletasks()
        host = DropHost(lambda *_a: None)
        host.attach(root)
        first = list(registered)
        assert 1 <= len(first) <= 3
        host.attach(root)
        assert registered == first
        canvas = tk.Canvas(root, width=40, height=20)
        canvas.pack()
        root.update_idletasks()
        host.attach(root, extras=[canvas])
        assert int(canvas.winfo_id()) in registered
        assert len(registered) <= 8
        host.attach(root, extras=[canvas])
        assert registered.count(int(canvas.winfo_id())) == 1
        host.detach()
    finally:
        root.destroy()


def test_file_contents_empty_does_not_raise(monkeypatch) -> None:
    assert win_drop._file_contents_bytes(0, 0, 0) is None
    assert win_drop._file_contents_bytes(0, 15, 0) is None
    assert win_drop._file_contents_bytes(0, 15, -1) is None
    assert win_drop.extract_drop_sources(0) == []

    def boom(*_a, **_k):
        raise OSError("empty FileContents")

    monkeypatch.setattr(win_drop, "_get_data", boom)
    assert win_drop._file_contents_bytes(1, 1, 0) is None


def test_file_contents_later_index_does_not_fall_back_to_zero(monkeypatch) -> None:
    seen: list[int] = []

    def fake_get(_obj, _cf, lindex=0, tymed=0):
        seen.append(int(lindex))
        return None

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", lambda *_a, **_k: None)
    assert win_drop._file_contents_bytes(1, 15, 1) is None
    assert seen
    assert 0 not in seen
    assert 1 in seen
    assert 2 not in seen


def test_file_contents_lindex_is_zero_based() -> None:
    assert win_drop._filecontents_lindex_candidates(0) == [0, -1]
    assert win_drop._filecontents_lindex_candidates(1) == [1]
    assert win_drop._filecontents_lindex_candidates(2) == [2]


def test_get_data_here_skips_fake_pointer(monkeypatch) -> None:
    def boom(punk):
        raise AssertionError(f"vtable {punk}")

    monkeypatch.setattr(win_drop, "_vtable", boom)
    assert win_drop._get_data_here(1, 15, lindex=1) is None
    assert win_drop._get_data(1, 15, lindex=1) is None
    assert win_drop._file_contents_batch(1, 15, 2) == [None, None]


def test_file_contents_batch_reads_and_releases_each_index_before_the_next(monkeypatch) -> None:
    live: set[int] = set()
    order: list[str] = []

    class Medium:
        def __init__(self, idx: int) -> None:
            self.idx = idx

    def fake_get(_obj, _cf, lindex=0, tymed=0):
        idx = int(lindex)
        if idx < 0:
            return None
        if live:
            order.append(f"get{idx}-while-held={sorted(live)}")
            return None
        medium = Medium(idx)
        live.add(idx)
        order.append(f"get{idx}")
        return medium

    def fake_release(medium) -> None:
        live.discard(medium.idx)
        order.append(f"rel{medium.idx}")

    def fake_bytes(medium) -> bytes:
        order.append(f"read{medium.idx}")
        return {0: b"%PDF-a", 1: b"%PDF-b"}[medium.idx]

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", lambda *_a, **_k: None)
    monkeypatch.setattr(win_drop, "_release_medium", fake_release)
    monkeypatch.setattr(win_drop, "_medium_bytes", fake_bytes)
    blobs = win_drop._file_contents_batch(1, 15, 2)
    assert blobs == [b"%PDF-a", b"%PDF-b"]
    assert all("while-held" not in op for op in order)
    assert order[:6] == ["get0", "read0", "rel0", "get1", "read1", "rel1"]


def test_file_contents_later_index_uses_getdatahere(monkeypatch) -> None:
    class Medium:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    def fake_get(_obj, _cf, lindex=0, tymed=0):
        if int(lindex) == 0:
            return Medium("get0")
        return None

    def fake_here(_obj, _cf, lindex=0, tymed=0):
        if int(lindex) == 1:
            return Medium("here1")
        return None

    def fake_bytes(medium) -> bytes:
        return {"get0": b"%PDF-a", "here1": b"%PDF-here"}[medium.tag]

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", fake_here)
    monkeypatch.setattr(win_drop, "_medium_bytes", fake_bytes)
    monkeypatch.setattr(win_drop, "_release_medium", lambda _m: None)
    blobs = win_drop._file_contents_batch(1, 15, 2)
    assert blobs == [b"%PDF-a", b"%PDF-here"]


def test_file_contents_empty_getdata_still_tries_getdatahere(monkeypatch) -> None:
    """Live 1.62: GetData index=1 hr=0 tymed=ISTREAM bytes=0 skipped GetDataHere."""

    class Medium:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    def fake_get(_obj, _cf, lindex=0, tymed=0):
        if int(lindex) < 0:
            return None
        return Medium(f"get{int(lindex)}")

    def fake_here(_obj, _cf, lindex=0, tymed=0):
        if int(lindex) == 1:
            return Medium("here1")
        return None

    def fake_bytes(medium) -> bytes:
        return {"get0": b"%PDF-a", "get1": b"", "here1": b"%PDF-here"}[medium.tag]

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", fake_here)
    monkeypatch.setattr(win_drop, "_medium_bytes", fake_bytes)
    monkeypatch.setattr(win_drop, "_release_medium", lambda _m: None)
    blobs = win_drop._file_contents_batch(1, 15, 2)
    assert blobs == [b"%PDF-a", b"%PDF-here"]


def test_file_contents_empty_istream_still_tries_hglobal(monkeypatch) -> None:
    class Medium:
        def __init__(self, tag: str) -> None:
            self.tag = tag
            self.tymed = 4 if tag == "stream" else 1

    def fake_get(_obj, _cf, lindex=0, tymed=0):
        if int(lindex) != 0:
            return None
        if int(tymed) == win_drop.TYMED_ISTREAM:
            return Medium("stream")
        if int(tymed) == win_drop.TYMED_HGLOBAL:
            return Medium("hglobal")
        return None

    def fake_bytes(medium) -> bytes:
        return b"" if medium.tag == "stream" else b"%PDF-hglobal"

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", lambda *_a, **_k: None)
    monkeypatch.setattr(win_drop, "_medium_bytes", fake_bytes)
    monkeypatch.setattr(win_drop, "_release_medium", lambda _m: None)
    assert win_drop._file_contents_bytes(1, 15, 0) == b"%PDF-hglobal"


def test_paste_dataobject_into_folder_skips_fake_pointer(tmp_path: Path) -> None:
    assert win_drop.paste_dataobject_into_folder(0, tmp_path) == []
    assert win_drop.paste_dataobject_into_folder(1, tmp_path) == []


def test_new_folder_pdfs_sees_written_files(tmp_path: Path) -> None:
    before = win_drop._folder_pdf_state(tmp_path)
    written = tmp_path / "scan0042.pdf"
    written.write_bytes(b"%PDF-new")
    assert win_drop._new_folder_pdfs(tmp_path, before) == [written]


def test_parse_file_group_descriptor_w_two_names() -> None:
    def pack_name(name: str) -> bytes:
        blob = bytearray(win_drop.FILEDESCRIPTORW_SIZE)
        encoded = name.encode("utf-16-le") + b"\0\0"
        blob[win_drop.FD_NAME_OFFSET : win_drop.FD_NAME_OFFSET + len(encoded)] = encoded
        return bytes(blob)

    blob = (2).to_bytes(4, "little") + pack_name("scan0042.pdf") + pack_name("scan0043.pdf")
    assert win_drop.parse_file_group_descriptor_w(blob) == ["scan0042.pdf", "scan0043.pdf"]


def test_extract_two_named_contents_keeps_distinct_bytes(monkeypatch) -> None:
    blobs = {0: b"%PDF-a", 1: b"%PDF-b"}
    names = {"FileGroupDescriptorW": 1, "FileGroupDescriptor": 2, "FileContents": 3, "FileNameW": 4, "FileName": 5}
    monkeypatch.setattr(win_drop, "_format_names", lambda _o: ["FileGroupDescriptorW", "FileContents"])
    monkeypatch.setattr(win_drop, "_clipboard_format", lambda name: names[name])
    monkeypatch.setattr(win_drop, "parse_file_group_descriptor_w", lambda _b: ["one.pdf", "two.pdf"])
    monkeypatch.setattr(
        win_drop, "_file_contents_batch", lambda _o, _cf, count: [blobs[index] for index in range(count)]
    )
    monkeypatch.setattr(win_drop, "_medium_bytes", lambda _m: b"unused")
    monkeypatch.setattr(win_drop, "_release_medium", lambda _m: None)

    def fake_get(pdataobj, cf, lindex=0, tymed=0):
        if cf == 1:
            return object()
        return None

    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    sources = win_drop.extract_drop_sources(1)
    assert [item.name for item in sources] == ["one.pdf", "two.pdf"]
    assert [item.data for item in sources] == [b"%PDF-a", b"%PDF-b"]


def test_extract_releases_descriptor_before_file_contents(monkeypatch) -> None:
    released: list[str] = []
    contents_after_desc_released: list[int] = []

    class Medium:
        def __init__(self, kind: str) -> None:
            self.kind = kind

    names = {"FileGroupDescriptorW": 1, "FileGroupDescriptor": 2, "FileContents": 3, "FileNameW": 4, "FileName": 5}

    def fake_get(_obj, cf, lindex=0, tymed=0):
        if cf == 1:
            return Medium("desc")
        if cf == 3:
            assert "desc" in released
            contents_after_desc_released.append(int(lindex))
            return Medium(f"c{int(lindex)}")
        return None

    def fake_release(medium) -> None:
        released.append(medium.kind)

    def fake_bytes(medium) -> bytes:
        if medium.kind == "desc":
            return b"unused"
        return b"%PDF-" + medium.kind.encode()

    monkeypatch.setattr(win_drop, "_format_names", lambda _o: ["FileGroupDescriptorW", "FileContents"])
    monkeypatch.setattr(win_drop, "_clipboard_format", lambda name: names[name])
    monkeypatch.setattr(win_drop, "parse_file_group_descriptor_w", lambda _b: ["one.pdf", "two.pdf"])
    monkeypatch.setattr(win_drop, "_get_data", fake_get)
    monkeypatch.setattr(win_drop, "_get_data_here", lambda *_a, **_k: None)
    monkeypatch.setattr(win_drop, "_release_medium", fake_release)
    monkeypatch.setattr(win_drop, "_medium_bytes", fake_bytes)
    sources = win_drop.extract_drop_sources(1)
    assert [item.name for item in sources] == ["one.pdf", "two.pdf"]
    assert [item.data for item in sources] == [b"%PDF-c0", b"%PDF-c1"]
    assert 0 in contents_after_desc_released
    assert 1 in contents_after_desc_released
    assert released[0] == "desc"


def test_drop_schedules_after_not_sync_pair(monkeypatch) -> None:
    for source in (
        DropSource(name="explorer.pdf", data=b"%PDF-1.4"),
        DropSource(name="outlook.pdf", data=b"%PDF-email"),
    ):
        scheduled: list = []
        paired: list = []

        def pair(sources, x, y, bucket=paired) -> None:
            bucket.append((list(sources), x, y))

        monkeypatch.setattr(win_drop, "extract_drop_sources", lambda _obj, captured=source: [captured])
        target = win_drop._ComDropTarget(pair, schedule=scheduled.append)
        effect = wintypes.DWORD(win_drop.DROPEFFECT_COPY)
        hr = target._drop_method(0, 1, 0, 0x0000002A00000010, pointer(effect))
        assert hr == win_drop.S_OK
        assert int(effect.value) == win_drop.DROPEFFECT_COPY
        assert paired == []
        assert len(scheduled) == 1
        scheduled[0]()
        assert len(paired) == 1
        assert paired[0][0][0].name == source.name
        assert paired[0][0][0].data == source.data
        assert paired[0][1:] == (16, 42)
        assert "2026-075" not in source.name


def test_drop_error_returns_ok_none_effect(monkeypatch) -> None:
    scheduled: list = []
    paired: list = []

    def boom(_obj):
        raise RuntimeError("ole")

    monkeypatch.setattr(win_drop, "extract_drop_sources", boom)
    target = win_drop._ComDropTarget(lambda *args: paired.append(args), schedule=scheduled.append)
    effect = wintypes.DWORD(win_drop.DROPEFFECT_COPY)
    hr = target._drop_method(0, 1, 0, 0, pointer(effect))
    assert hr == win_drop.S_OK
    assert int(effect.value) == win_drop.DROPEFFECT_NONE
    assert scheduled == []
    assert paired == []


def test_drag_enter_sets_copy_even_if_source_effect_is_none(monkeypatch) -> None:
    queried: list[int] = []

    def boom(_obj):
        queried.append(1)
        raise RuntimeError("do not QueryGetData FileContents on DragEnter")

    monkeypatch.setattr(win_drop, "_format_names", boom)
    target = win_drop._ComDropTarget(lambda *_a: None, schedule=lambda _fn: None)
    effect = wintypes.DWORD(0)
    hr = target._drag_enter(0, 0, 0, 0x0000002A00000010, pointer(effect))
    assert hr == win_drop.S_OK
    assert int(effect.value) == win_drop.DROPEFFECT_COPY
    assert queried == []


def test_drag_enter_and_over_schedule_hover_not_sync() -> None:
    hovers: list[tuple[int, int]] = []
    scheduled: list = []
    target = win_drop._ComDropTarget(
        lambda *_a: None,
        hover=lambda x, y: hovers.append((x, y)),
        schedule=scheduled.append,
    )
    effect = wintypes.DWORD(win_drop.DROPEFFECT_COPY)
    hr = target._drag_enter(0, 0, 0, 0x0000002A00000010, pointer(effect))
    assert hr == win_drop.S_OK
    assert hovers == []
    assert scheduled
    scheduled.pop(0)()
    assert hovers == [(16, 42)]
    hovers.clear()
    hr = target._drag_over(0, 0, 0x0000002A00000010, pointer(effect))
    assert hr == win_drop.S_OK
    assert hovers == []
    scheduled[-1]()
    assert hovers == [(16, 42)]


def test_drop_host_after_does_not_pair_until_tk() -> None:
    class FakeTk:
        def __init__(self) -> None:
            self.queued: list[tuple[int, object]] = []

        def after(self, ms, fn):
            self.queued.append((int(ms), fn))
            return "after0"

    paired: list = []
    host = DropHost(lambda sources, x, y: paired.append((sources, x, y)))
    fake = FakeTk()
    host._widget = fake
    src = [DropSource(name="board.pdf", data=b"%PDF")]
    host._schedule(lambda: host._callback(src, 8, 9))
    assert paired == []
    assert fake.queued
    assert fake.queued[0][0] == 0
    fake.queued[0][1]()
    assert paired[0][0][0].name == "board.pdf"
    assert paired[0][1:] == (8, 9)


def test_detach_during_drop_does_not_revoke(monkeypatch) -> None:
    revoked: list[int] = []

    class _Fn:
        def __init__(self, impl) -> None:
            self._impl = impl
            self.argtypes = None
            self.restype = None

        def __call__(self, *args, **kwargs):
            return self._impl(*args, **kwargs)

    ole32 = SimpleNamespace(
        RevokeDragDrop=_Fn(lambda hwnd: revoked.append(int(hwnd)) or 0),
        RegisterDragDrop=_Fn(lambda _hwnd, _punk: 0),
        OleInitialize=_Fn(lambda _arg: 0),
    )
    monkeypatch.setattr(win_drop, "ole_available", lambda: True)
    monkeypatch.setattr(win_drop, "windll", SimpleNamespace(ole32=ole32))
    host = DropHost(lambda *_a: None)
    host._hwnds = [0x11]
    host._drop_gate(True)
    host.detach()
    assert revoked == []
    assert host._detach_pending is True
    assert host._hwnds == [0x11]


def test_drop_host_after_does_not_pair_until_idle(monkeypatch) -> None:
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    paired: list = []
    host = DropHost(lambda sources, x, y: paired.append((sources, x, y)))
    host._widget = root
    source = DropSource(name="board.pdf", data=b"%PDF")
    monkeypatch.setattr(win_drop, "extract_drop_sources", lambda _obj: [source])
    target = win_drop._ComDropTarget(host._callback, schedule=host._schedule)
    effect = wintypes.DWORD(win_drop.DROPEFFECT_COPY)
    try:
        hr = target._drop_method(0, 1, 0, 0x0000002A00000010, pointer(effect))
        assert hr == win_drop.S_OK
        assert paired == []
        root.update()
        assert len(paired) == 1
        assert paired[0][0][0].name == "board.pdf"
    finally:
        root.destroy()
