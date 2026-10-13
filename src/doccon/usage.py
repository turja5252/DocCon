# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""How many transmittals DocCon has filed.

One file per PC, next to Elite DocCon, so Dropbox can add them up.
A line is written only after the letter is filed.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from doccon.diag import log
from doccon.paths import install_dir


def usage_dir() -> Path:
    return install_dir() / "usage"


def _pc_name() -> str:
    raw = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "pc"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")
    return (safe or "pc")[:40]


def usage_path() -> Path:
    return usage_dir() / f"usage-{_pc_name()}.jsonl"


def record_transmittal(*, cover: str, job: str = "", kind: str = "") -> None:
    """Append one filed transmittal. A blank cover is ignored. Disk errors stay quiet."""
    token = (cover or "").strip()
    if not token:
        return
    try:
        folder = usage_dir()
        folder.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "cover": token,
                "job": (job or "").strip(),
                "kind": (kind or "").strip(),
            },
            ensure_ascii=False,
        )
        with usage_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        log("WARN", "usage", f"could not record {token}: {exc}")


def transmittal_count() -> int:
    """Filed transmittals on every PC whose log is in this DocCon folder."""
    folder = usage_dir()
    if not folder.is_dir():
        return 0
    total = 0
    for path in sorted(folder.glob("usage-*.jsonl")):
        if "conflicted" in path.name.casefold():
            continue
        total += _count_file(path)
    return total


def _count_file(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("cover") or "").strip():
            count += 1
    return count
