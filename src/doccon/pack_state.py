# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Draft cover for this client pack — job folder JSON, not Jira."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PACK_DIR = Path("3.0 Doc Con") / "DocCon"
PACK_NAME = "client-pack.json"


@dataclass(frozen=True)
class ClientPack:
    job_number: str
    pep_path: str = ""
    issued: str = ""
    expected: str = ""
    to_line: str = ""
    cc_line: str = ""
    project_description: str = ""
    selected_keys: tuple[str, ...] = ()


def pack_path(job_folder: Path) -> Path:
    return Path(job_folder) / PACK_DIR / PACK_NAME


def load_client_pack(job_folder: Path | None, job_number: str) -> ClientPack | None:
    if job_folder is None:
        return None
    path = pack_path(job_folder)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    keys = raw.get("selected_keys") or []
    if not isinstance(keys, list):
        keys = []
    return ClientPack(
        job_number=str(raw.get("job_number") or job_number).strip() or job_number,
        pep_path=str(raw.get("pep_path") or "").strip(),
        issued=str(raw.get("issued") or "").strip(),
        expected=str(raw.get("expected") or "").strip(),
        to_line=str(raw.get("to_line") or "").strip(),
        cc_line=str(raw.get("cc_line") or "").strip(),
        project_description=str(raw.get("project_description") or "").strip(),
        selected_keys=tuple(str(item) for item in keys if str(item).strip()),
    )


def save_client_pack(job_folder: Path, pack: ClientPack) -> Path:
    dest = pack_path(job_folder)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "job_number": pack.job_number,
        "pep_path": pack.pep_path,
        "issued": pack.issued,
        "expected": pack.expected,
        "to_line": pack.to_line,
        "cc_line": pack.cc_line,
        "project_description": pack.project_description,
        "selected_keys": list(pack.selected_keys),
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest
