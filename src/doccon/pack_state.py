# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Draft cover for this client pack — job folder JSON, not Jira."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

from doccon.kinds import FIELD, SHOP
from doccon.log_layout import layout_for
from doccon.match import LocatedPdf, coerce_located_pdfs, is_dropped_pdf_path, parse_pdf_stem

PACK_DIR = Path("3.0 Doc Con") / "DocCon"
PACK_NAME = "client-pack.json"
PACK_SCHEMA = 2


@dataclass(frozen=True)
class PackExtra:
    """A PDF on this transmittal with no Jira issue and no EDDI line."""

    path: str
    document_no: str
    rev: str = ""
    description: str = ""
    status: str = ""
    email_dropped: bool = False
    id: str = ""
    packed: bool = True

    def label(self) -> str:
        name = Path(self.path).name
        rev = f" REV {self.rev}" if (self.rev or "").strip() else ""
        return f"{self.document_no}{rev} — {name}"


def default_extra_status(kind: str) -> str:
    allowed = layout_for(kind).statuses
    if "INFORMATION" in allowed:
        return "INFORMATION"
    return allowed[0] if allowed else "INFORMATION"


def letter_status(kind: str, status: str) -> str:
    allowed = layout_for(kind).statuses
    token = (status or "").strip()
    for option in allowed:
        if option.casefold() == token.casefold():
            return option
    return default_extra_status(kind)


def suggest_extra_identity(path: Path) -> tuple[str, str]:
    """Document number and rev from a PDF name. Description stays blank for the operator."""
    document_no, rev = parse_pdf_stem(Path(path).stem)
    return (document_no or Path(path).stem), rev


def extra_from_path(path: Path, *, kind: str, description: str = "", status: str = "") -> PackExtra:
    document_no, rev = suggest_extra_identity(path)
    return PackExtra(
        path=str(path),
        document_no=document_no,
        rev=rev,
        description=(description or "").strip(),
        status=letter_status(kind, status or default_extra_status(kind)),
        email_dropped=is_dropped_pdf_path(path),
        id=f"x:{uuid.uuid4().hex[:12]}",
        packed=True,
    )


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
    located_pdfs: dict[str, LocatedPdf] = field(default_factory=dict)
    next_edits: dict[str, dict[str, str]] = field(default_factory=dict)
    pack_extras: tuple[PackExtra, ...] = ()
    shop_folders: dict[str, str] = field(default_factory=dict)
    job_folder: str = ""
    schema_version: int = PACK_SCHEMA


def pack_path(job_folder: Path) -> Path:
    return Path(job_folder) / PACK_DIR / PACK_NAME


def _located_pdfs(raw: object) -> dict[str, LocatedPdf]:
    if not isinstance(raw, dict):
        return {}
    return coerce_located_pdfs(raw)


def _dump_located_pdfs(located: dict[str, LocatedPdf]) -> dict[str, str | dict[str, object]]:
    """String path for Locate…; object with email_dropped for a drag-drop bypass."""
    payload: dict[str, str | dict[str, object]] = {}
    for key, rec in located.items():
        if rec.email_dropped:
            payload[key] = {"path": rec.path, "email_dropped": True}
        else:
            payload[key] = rec.path
    return payload


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


def _shop_folders(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    picks: dict[str, str] = {}
    for key, value in raw.items():
        item = str(key or "").strip()
        label = str(value or "").strip()
        if item and label and label.casefold() != "root":
            picks[item] = label
    return picks


def _pack_extras(raw: object) -> tuple[PackExtra, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[PackExtra] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "").strip()
        document_no = str(entry.get("document_no") or "").strip()
        if not path or not document_no:
            continue
        packed = entry.get("packed")
        items.append(
            PackExtra(
                path=path,
                document_no=document_no,
                rev=str(entry.get("rev") or "").strip(),
                description=str(entry.get("description") or "").strip(),
                status=str(entry.get("status") or "").strip(),
                email_dropped=bool(entry.get("email_dropped")),
                id=str(entry.get("id") or "").strip() or f"x:{uuid.uuid4().hex[:12]}",
                packed=True if packed is None else bool(packed),
            )
        )
    return tuple(items)


def _dump_pack_extras(items: tuple[PackExtra, ...]) -> list[dict[str, object]]:
    return [
        {
            "path": item.path,
            "document_no": item.document_no,
            "rev": item.rev,
            "description": item.description,
            "status": item.status,
            "email_dropped": bool(item.email_dropped),
            "id": item.id,
            "packed": bool(item.packed),
        }
        for item in items
    ]


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
        pack_extras=_pack_extras(raw.get("pack_extras")),
        shop_folders=_shop_folders(raw.get("shop_folders")),
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
        "located_pdfs": _dump_located_pdfs(pack.located_pdfs),
        "next_edits": {key: dict(fields) for key, fields in pack.next_edits.items()},
        "pack_extras": _dump_pack_extras(pack.pack_extras),
        "shop_folders": dict(_shop_folders(pack.shop_folders)),
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
