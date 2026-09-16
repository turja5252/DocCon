# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from types import SimpleNamespace

from doccon.shell_drop import drop_hwnds, make_dropfiles_blob, parse_dropfiles_blob


def test_parse_dropfiles_blob_wide_paths() -> None:
    path = r"C:\Temp\DocCon\2026-Tanzim-1-1 REV 0.pdf"
    blob = make_dropfiles_blob([path], x=16, y=42)
    names, x, y = parse_dropfiles_blob(blob)
    assert names == [path]
    assert x == 16
    assert y == 42
    assert "2026-075" not in path
    assert names[0].endswith(".pdf")


def test_parse_dropfiles_blob_empty() -> None:
    assert parse_dropfiles_blob(b"") == ([], 0, 0)
    assert parse_dropfiles_blob(b"\x00" * 8) == ([], 0, 0)


def test_drop_hwnds_includes_board_and_dock_extras() -> None:
    dock = SimpleNamespace(winfo_id=lambda: 0x21)
    canvas = SimpleNamespace(winfo_id=lambda: 0x22)
    inner = SimpleNamespace(winfo_id=lambda: 0x23)
    root = SimpleNamespace(
        winfo_id=lambda: 0x11,
        winfo_toplevel=lambda: SimpleNamespace(winfo_id=lambda: 0x11, wm_frame=lambda: "0x10"),
    )
    hwnds = drop_hwnds(root, extras=[dock, canvas, inner], children=False)
    assert 0x11 in hwnds
    assert 0x10 in hwnds
    assert 0x21 in hwnds
    assert 0x22 in hwnds
    assert 0x23 in hwnds
    assert "2026-075" not in str(hwnds)
