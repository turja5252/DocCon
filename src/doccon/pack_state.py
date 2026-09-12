# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Draft cover for this client pack — job folder JSON, not Jira."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from doccon.kinds import FIELD, SHOP

PACK_DIR = Path("3.0 Doc Con") / "DocCon"
PACK_NAME = "client-pack.json"
PACK_SCHEMA = 2


@dataclass(frozen=True)
class ClientPack:
    job_number: str
    pep_path: str = ""
    issued: str = ""
    expected: str = ""
    to_line: str = ""
    cc_line: str = ""
    shop_to: str = ""
    shop_cc: str = ""
    field_to: str = ""
    field_cc: str = ""
    project_description: str = ""
    selected_keys: tuple[str, ...] = ()
    located_pdfs: dict[str, str] = field(default_factory=dict)
    next_edits: dict[str, dict[str, str]] = field(default_factory=dict)
    job_folder: str = ""
    schema_version: int = PACK_SCHEMA


def pack_path(job_folder: Path) -> Path:
    return Path(job_folder) / PACK_DIR / PACK_NAME


def _located_pdfs(raw: object) -> dict[str, str]:
    located: dict[str, str] = {}
    if not isinstance(raw, dict):
        return located
    for item_key, item_path in raw.items():
        key = str(item_key).strip()
        path = str(item_path).strip()
        if key and path:
            located[key] = path
    return located


def _next_edits(raw: object) -> dict[str, dict[str, str]]:
    """Dirty Next fields keyed by Jira issue key (or drawing id). Skip junk."""
    edits: dict[str, dict[str, str]] = {}
    if not isinstance(raw, dict):
        return edits
    for item_key, fields in raw.items():
        key = str(item_key).strip()
        if not key or not isinstance(fields, dict):
            continue
        row: dict[str, str] = {}
        for name, value in fields.items():
            field = str(name).strip()
            if field:
                row[field] = "" if value is None else str(value)
        if row:
            edits[key] = row
    return edits


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
    schema = raw.get("schema_version")
    try:
        schema_version = int(schema) if schema is not None else PACK_SCHEMA
    except (TypeError, ValueError):
        schema_version = PACK_SCHEMA
    return ClientPack(
        job_number=str(raw.get("job_number") or job_number).strip() or job_number,
        pep_path=str(raw.get("pep_path") or "").strip(),
        issued=str(raw.get("issued") or "").strip(),
        expected=str(raw.get("expected") or "").strip(),
        to_line=str(raw.get("to_line") or "").strip(),
        cc_line=str(raw.get("cc_line") or "").strip(),
        shop_to=str(raw.get("shop_to") or "").strip(),
        shop_cc=str(raw.get("shop_cc") or "").strip(),
        field_to=str(raw.get("field_to") or "").strip(),
        field_cc=str(raw.get("field_cc") or "").strip(),
        project_description=str(raw.get("project_description") or "").strip(),
        selected_keys=tuple(str(item) for item in keys if str(item).strip()),
        located_pdfs=_located_pdfs(raw.get("located_pdfs")),
        next_edits=_next_edits(raw.get("next_edits")),
        job_folder=str(raw.get("job_folder") or "").strip(),
        schema_version=schema_version,
    )


def save_client_pack(job_folder: Path, pack: ClientPack) -> Path:
    dest = pack_path(job_folder)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": pack.schema_version or PACK_SCHEMA,
        "job_number": pack.job_number,
        "pep_path": pack.pep_path,
        "issued": pack.issued,
        "expected": pack.expected,
        "to_line": pack.to_line,
        "cc_line": pack.cc_line,
        "shop_to": pack.shop_to,
        "shop_cc": pack.shop_cc,
        "field_to": pack.field_to,
        "field_cc": pack.field_cc,
        "project_description": pack.project_description,
        "selected_keys": list(pack.selected_keys),
        "located_pdfs": dict(pack.located_pdfs),
        "next_edits": {key: dict(fields) for key, fields in pack.next_edits.items()},
        "job_folder": pack.job_folder,
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def cover_recipients(pack: ClientPack | None, kind: str) -> tuple[str, str]:
    if pack is None:
        return "", ""
    if kind == SHOP:
        return pack.shop_to, pack.shop_cc
    if kind == FIELD:
        return pack.field_to, pack.field_cc
    return pack.to_line, pack.cc_line


def with_cover_recipients(pack: ClientPack, kind: str, to_line: str, cc_line: str) -> ClientPack:
    if kind == SHOP:
        return replace(pack, shop_to=to_line, shop_cc=cc_line)
    if kind == FIELD:
        return replace(pack, field_to=to_line, field_cc=cc_line)
    return replace(pack, to_line=to_line, cc_line=cc_line)
