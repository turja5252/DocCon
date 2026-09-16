# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""JSONL messages between the DocCon GUI process and drop_host. No COM."""
from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = 1
OP_READY = "ready"
OP_DROP = "drop"
OP_HOVER = "hover"
OP_LEAVE = "leave"
OP_LOG = "log"
OP_HELLO = "hello"
OP_GEOM = "geom"
OP_QUIT = "quit"
OP_BYE = "bye"

DROP_HOST_DIED = "drop_host died"
DROP_HELPER_DOWN = "drop helper not running"


def encode_msg(op: str, **fields: Any) -> bytes:
    payload: dict[str, Any] = {"v": PROTOCOL_VERSION, "op": str(op), **fields}
    return (json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def decode_line(line: str | bytes) -> dict[str, Any] | None:
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("v") or 0) != PROTOCOL_VERSION:
        return None
    op = str(data.get("op") or "").strip()
    if not op:
        return None
    return data


def parse_frames(buffer: bytes) -> tuple[list[dict[str, Any]], bytes]:
    """Split a TCP buffer into JSONL messages. Remainder stays in the buffer."""
    messages: list[dict[str, Any]] = []
    while b"\n" in buffer:
        raw, buffer = buffer.split(b"\n", 1)
        msg = decode_line(raw)
        if msg is not None:
            messages.append(msg)
    return messages, buffer


def drop_paths(msg: dict[str, Any]) -> list[str]:
    raw = msg.get("paths")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def drop_point(msg: dict[str, Any]) -> tuple[int, int]:
    try:
        x = int(msg.get("x") or 0)
    except (TypeError, ValueError):
        x = 0
    try:
        y = int(msg.get("y") or 0)
    except (TypeError, ValueError):
        y = 0
    return x, y
