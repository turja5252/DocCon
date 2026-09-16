# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.drop_protocol import (
    OP_DROP,
    decode_line,
    drop_paths,
    drop_point,
    encode_msg,
    parse_frames,
)


def test_protocol_drop_roundtrip() -> None:
    raw = encode_msg(
        OP_DROP,
        paths=[r"C:\Users\TanzimNasir\AppData\Local\EliteIntegrity\DocCon\inbox\2026-Tanzim-1-1.pdf"],
        x=16,
        y=42,
        kind="outlook",
    )
    messages, rest = parse_frames(raw)
    assert rest == b""
    assert len(messages) == 1
    msg = messages[0]
    assert msg["op"] == OP_DROP
    assert msg["kind"] == "outlook"
    paths = drop_paths(msg)
    assert paths[0].endswith("2026-Tanzim-1-1.pdf")
    assert "2026-075" not in paths[0]
    assert drop_point(msg) == (16, 42)


def test_protocol_ignores_bad_frames() -> None:
    blob = b"not-json\n" + encode_msg("ready", pid=9) + b'{"v":2,"op":"drop"}\n'
    messages, _rest = parse_frames(blob)
    assert [m["op"] for m in messages] == ["ready"]
    assert decode_line("   ") is None
    assert decode_line(b'{"v":1}') is None


def test_parent_pair_modules_do_not_import_istream() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "doccon"
    gui = (root / "gui.py").read_text(encoding="utf-8")
    bridge = (root / "drop_bridge.py").read_text(encoding="utf-8")
    shell = (root / "shell_drop.py").read_text(encoding="utf-8")
    forbidden = (
        "IDropTarget",
        "RegisterDragDrop",
        "extract_drop_sources",
        "_read_istream",
        "FileContents",
        "QueryGetData",
        "from doccon.win_drop",
        "import doccon.win_drop",
    )
    for token in forbidden:
        assert token not in gui, token
        assert token not in bridge, token
    for token in ("IDropTarget", "RegisterDragDrop", "FileContents", "_read_istream", "QueryGetData"):
        assert token not in shell, token
    assert "WM_DROPFILES" in shell
    assert "DragAcceptFiles" in shell
    assert "doccon.drop_host" in bridge
    assert "_drop_dock" not in gui
    assert "DropBridge" not in gui
    assert "HdropOleHost" not in gui
    assert "IStream" not in gui
    assert "from doccon.win_drop" not in gui
    assert "_paint_queue or self.board._paint_after" not in gui
    host = (root / "drop_host.py").read_text(encoding="utf-8")
    assert "--paste" in (root / "clip_paste.py").read_text(encoding="utf-8")
    assert "overlay_ex_style" in host
    assert "IDropTarget" in host or "RegisterDragDrop" in host
    assert "WS_EX_TRANSPARENT" in host
    assert "& ~WS_EX_TRANSPARENT" in host
    ole = (root / "hdrop_ole.py").read_text(encoding="utf-8")
    assert "from doccon.hdrop_ole import HdropOleHost" not in gui
    assert "from doccon.win_drop" not in ole
    assert "_read_istream" not in ole
    assert "CF_HDROP" in ole
    assert "RegisterDragDrop" in ole
