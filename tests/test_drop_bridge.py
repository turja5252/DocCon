# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path
from types import SimpleNamespace

from doccon.drop_bridge import (
    DropBridge,
    drop_host_argv,
    drop_host_cwd,
    drop_host_env,
    format_geom_arg,
    union_screen_rect,
)
from doccon.drop_protocol import DROP_HELPER_DOWN, DROP_HOST_DIED, OP_DROP, OP_READY, encode_msg, parse_frames
from doccon.winproc import drop_host_popen_kwargs


def test_drop_host_died_is_logged(monkeypatch) -> None:
    lines: list[str] = []

    def capture(level: str, step: str, message: str = "") -> None:
        lines.append(f"{level} {step} {message}")

    monkeypatch.setattr("doccon.drop_bridge._log", lambda message, level="INFO": capture(level, "drop", message))
    bridge = DropBridge(lambda *_a: None)
    bridge.note_child_exit(1, pid=4242)
    assert any(DROP_HOST_DIED in line for line in lines)
    assert any("pid=4242" in line for line in lines)


def test_spawn_failure_logs_and_status_drop_helper_not_running(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    statuses: list[str] = []
    scheduled: list = []

    def boom(*_a, **_k):
        raise OSError("python -m doccon.drop_host failed from cwd")

    monkeypatch.setattr("doccon.drop_bridge.subprocess.Popen", boom)
    bridge = DropBridge(lambda *_a: None, schedule=scheduled.append, on_status=statuses.append)
    bridge._inbox = tmp_path / "inbox"
    bridge._inbox.mkdir()
    bridge._spawn()
    assert bridge._proc is None
    assert scheduled
    scheduled[0]()
    assert statuses == [DROP_HELPER_DOWN]


def test_drop_host_argv_uses_module_and_src_on_pythonpath() -> None:
    argv = drop_host_argv(9, Path("inbox"), 1, 0, "1,2,80,52")
    assert "-m" in argv
    assert "doccon.drop_host" in argv
    assert "--geom" in argv
    env = drop_host_env()
    assert "src" in (env.get("PYTHONPATH") or "").replace("\\", "/")
    assert drop_host_cwd()


def test_bridge_dispatches_drop_on_tk_thread() -> None:
    paired: list[tuple[list[str], int, int]] = []
    scheduled: list = []
    bridge = DropBridge(lambda paths, x, y: paired.append((paths, x, y)), schedule=scheduled.append)
    raw = encode_msg(OP_DROP, paths=[r"C:\inbox\2026-Tanzim-1-1.pdf"], x=8, y=9, kind="outlook")
    messages, _rest = parse_frames(raw)
    bridge._dispatch(messages[0])
    assert paired == []
    assert scheduled
    scheduled[0]()
    assert paired[0][0][0].endswith("2026-Tanzim-1-1.pdf")
    assert "2026-075" not in paired[0][0][0]
    assert paired[0][1:] == (8, 9)


def test_union_screen_rect_covers_dock_and_board() -> None:
    dock = SimpleNamespace(
        winfo_rootx=lambda: 10,
        winfo_rooty=lambda: 20,
        winfo_width=lambda: 400,
        winfo_height=lambda: 36,
        winfo_viewable=lambda: True,
    )
    board = SimpleNamespace(
        winfo_rootx=lambda: 10,
        winfo_rooty=lambda: 56,
        winfo_width=lambda: 400,
        winfo_height=lambda: 300,
        winfo_viewable=lambda: True,
    )
    x, y, w, h, visible = union_screen_rect([dock, board])
    assert (x, y, w, h, visible) == (10, 20, 400, 336, True)
    assert format_geom_arg((10, 20, 400, 336, True)) == "10,20,400,336"


def test_drop_host_popen_does_not_hide_overlay_hwnd() -> None:
    kwargs = drop_host_popen_kwargs()
    assert "startupinfo" not in kwargs


def test_ready_logs_overlay_hwnd(monkeypatch) -> None:
    lines: list[str] = []
    monkeypatch.setattr("doccon.drop_bridge._log", lambda message, level="INFO": lines.append(message))
    bridge = DropBridge(lambda *_a: None)
    bridge._port = 54321
    raw = encode_msg(OP_READY, pid=99, hwnd=0x11, dock_hwnd=0x22)
    messages, _rest = parse_frames(raw)
    bridge._dispatch(messages[0])
    text = " ".join(lines)
    assert "drop_host started" in text
    assert "bind port=54321" in text
    assert "overlay hwnd=" in text
    assert "dock hwnd=" in text
