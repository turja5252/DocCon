# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import ctypes.wintypes as wintypes
from pathlib import Path

from doccon.drop_host import (
    DOCK_HEIGHT,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST,
    WS_EX_TRANSPARENT,
    geom_is_usable,
    overlay_accepts_ole_input,
    overlay_ex_style,
    parse_geom_arg,
    split_overlay_geom,
)


def test_overlay_ex_style_is_not_transparent_to_input() -> None:
    layered = overlay_ex_style(layered=True)
    dock = overlay_ex_style(layered=False)
    assert layered & WS_EX_TRANSPARENT == 0
    assert dock & WS_EX_TRANSPARENT == 0
    assert overlay_accepts_ole_input(layered)
    assert overlay_accepts_ole_input(dock)
    assert layered & WS_EX_LAYERED
    assert dock & WS_EX_LAYERED == 0
    for style in (layered, dock):
        assert style & WS_EX_TOOLWINDOW
        assert style & WS_EX_NOACTIVATE
        assert style & WS_EX_TOPMOST
    blocked = layered | WS_EX_TRANSPARENT
    assert not overlay_accepts_ole_input(blocked)
    assert overlay_ex_style(layered=True) & WS_EX_TRANSPARENT == 0


def test_dock_is_the_ole_drop_hwnd() -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(encoding="utf-8")
    assert "register_hwnds(" in text
    assert "[dock_hwnd]" in text
    assert "[dock_hwnd, board_hwnd]" not in text
    assert "WS_POPUP | WS_VISIBLE" in text
    assert "IDropTarget HWND" in text or "IDropTarget=1" in text


def test_overlay_source_never_ors_transparent() -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(encoding="utf-8")
    assert "overlay_ex_style(" in text
    assert "WS_EX_TRANSPARENT" in text
    assert "CreateWindowExW" in text
    assert "& ~WS_EX_TRANSPARENT" in text
    assert "ex_style | WS_EX_TRANSPARENT" not in text
    assert "WS_EX_TRANSPARENT |" not in text


def test_wndclass_uses_only_real_wintypes_names() -> None:
    """1.50-1.52 died before CreateWindowEx: ctypes.wintypes has no HCURSOR."""
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(
        encoding="utf-8"
    )
    used = set()
    for token in text.split("wintypes.")[1:]:
        name = ""
        for char in token:
            if char.isalnum() or char == "_":
                name += char
            else:
                break
        if name:
            used.add(name)
    assert used, "expected drop_host to reference ctypes.wintypes"
    missing = sorted(name for name in used if not hasattr(wintypes, name))
    assert missing == [], f"drop_host references non-existent ctypes.wintypes names: {missing}"


def test_dock_creation_and_registration_are_logged() -> None:
    """The no-entry cursor was invisible because nothing logged the HWND or the HRESULT."""
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(
        encoding="utf-8"
    )
    assert "dock created hwnd=" in text
    assert "topmost=" in text
    assert "RegisterDragDrop hwnd={dock_hwnd:#x} S_OK" in text
    assert "FAILED (no S_OK)" in text


def test_parent_alive_permission_denied_is_not_gone(monkeypatch) -> None:
    """os.kill raising OSError used to kill the helper 0.3 s after spawn."""
    from doccon.drop_host import parent_alive

    monkeypatch.setattr(
        "doccon.drop_host.os.kill",
        lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("OpenProcess")),
    )
    assert parent_alive(34916) is True


def test_parent_alive_missing_process_is_gone(monkeypatch) -> None:
    from doccon.drop_host import parent_alive

    monkeypatch.setattr(
        "doccon.drop_host.os.kill",
        lambda *_a, **_k: (_ for _ in ()).throw(ProcessLookupError("no such process")),
    )
    assert parent_alive(34916) is False


def test_defwindowproc_argtypes_are_declared() -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(
        encoding="utf-8"
    )
    assert "DefWindowProcW.argtypes" in text
    assert "DefWindowProcW.restype = LRESULT" in text


def test_paste_mode_needs_no_port() -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "drop_host.py").read_text(
        encoding="utf-8"
    )
    assert '"--paste"' in text
    assert "def run_paste(" in text


def test_split_overlay_geom_dock_then_board() -> None:
    dock, board = split_overlay_geom(10, 20, 400, 200, dock_h=DOCK_HEIGHT)
    assert dock == (10, 20, 400, DOCK_HEIGHT)
    assert board == (10, 20 + DOCK_HEIGHT, 400, 200 - DOCK_HEIGHT)
    only_dock, none = split_overlay_geom(0, 0, 120, DOCK_HEIGHT)
    assert only_dock[3] == DOCK_HEIGHT
    assert none is None
    assert geom_is_usable(80, 48)
    assert not geom_is_usable(40, 40)
    assert parse_geom_arg("8,16,640,400") == (8, 16, 640, 400)
    assert parse_geom_arg("bad") is None
