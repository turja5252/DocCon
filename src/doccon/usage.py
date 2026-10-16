# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""How many letters, Jira updates, and EDDI sheets DocCon has finished.

One file per PC, next to Elite DocCon, so Dropbox can add them up.
A line is written only after the work succeeds. Tanzim Nasir is left out of the total.
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


EVENT_TRANSMITTAL = "transmittal"
EVENT_JIRA = "jira"
EVENT_EDDI = "eddi"
_EVENTS = frozenset({EVENT_TRANSMITTAL, EVENT_JIRA, EVENT_EDDI})


def _operator() -> str:
    return (os.environ.get("USERNAME") or "").strip()


def _folded(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _excluded_person(name: str) -> bool:
    """Tanzim Nasir's Windows account stays out of the Ctrl+Shift+L total."""
    token = _folded(name)
    return token == "tanzimnasir" or token.startswith("tanzimnasir")


def _excluded_log(path: Path) -> bool:
    name = path.name.casefold()
    if "conflicted" in name:
        return True
    return "tanzim" in _folded(path.stem)


def record_event(*, event: str, cover: str = "", job: str = "", kind: str = "") -> None:
    """Append one finished action. A blank letter is ignored. Disk errors stay quiet."""
    token = (event or "").strip().casefold()
    cover_id = (cover or "").strip()
    if token not in _EVENTS:
        return
    if token == EVENT_TRANSMITTAL and not cover_id:
        return
    try:
        folder = usage_dir()
        folder.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "event": token,
                "cover": cover_id,
                "job": (job or "").strip(),
                "kind": (kind or "").strip(),
                "operator": _operator(),
            },
            ensure_ascii=False,
        )
        with usage_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        log("WARN", "usage", f"could not record {token}: {exc}")


def record_transmittal(*, cover: str, job: str = "", kind: str = "") -> None:
    """Append one filed transmittal. A blank cover is ignored. Disk errors stay quiet."""
    record_event(event=EVENT_TRANSMITTAL, cover=cover, job=job, kind=kind)


def record_jira_update(*, job: str = "") -> None:
    """Append one successful Update Jira. Create transmittal is not this count."""
    record_event(event=EVENT_JIRA, job=job)


def record_eddi(*, job: str = "") -> None:
    """Append one successful Create EDDI. The sheet inside a letter is not this count."""
    record_event(event=EVENT_EDDI, job=job)


def usage_counts() -> dict[str, int]:
    """CT, ST, FT, Update Jira, and Create EDDI. Tanzim Nasir is omitted."""
    counts = {"ct": 0, "st": 0, "ft": 0, "jira": 0, "eddi": 0}
    folder = usage_dir()
    if not folder.is_dir():
        return counts
    for path in sorted(folder.glob("usage-*.jsonl")):
        if _excluded_log(path):
            continue
        for row in _rows(path):
            if _excluded_person(str(row.get("operator") or "")):
                continue
            bucket = _bucket(row)
            if bucket:
                counts[bucket] += 1
    return counts


def usage_summary() -> str:
    counts = usage_counts()
    return "\n".join(
        (
            f"CT {counts['ct']}",
            f"ST {counts['st']}",
            f"FT {counts['ft']}",
            f"Jira updates {counts['jira']}",
            f"EDDI creations {counts['eddi']}",
        )
    )


def transmittal_count() -> int:
    """Filed CT, ST, and FT letters. Tanzim Nasir is omitted."""
    counts = usage_counts()
    return counts["ct"] + counts["st"] + counts["ft"]


def _bucket(row: dict) -> str:
    event = str(row.get("event") or "").strip().casefold()
    cover = str(row.get("cover") or "").strip()
    if not event and cover:
        event = EVENT_TRANSMITTAL
    if event == EVENT_JIRA:
        return "jira"
    if event == EVENT_EDDI:
        return "eddi"
    if event != EVENT_TRANSMITTAL or not cover:
        return ""
    kind = str(row.get("kind") or "").strip().casefold()
    head = cover.casefold()
    if kind in {"client", "ct"} or head.startswith("ct-"):
        return "ct"
    if kind in {"shop", "st"} or head.startswith("st-"):
        return "st"
    if kind in {"field", "ft"} or head.startswith("ft-"):
        return "ft"
    return ""


def _rows(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    found: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            found.append(row)
    return found
