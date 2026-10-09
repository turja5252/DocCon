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


BLANK_EXTRA_NAME = "New document"


def suggest_extra_identity(path: Path) -> tuple[str, str]:
    """Document number and rev from a PDF name. Description stays blank for the operator."""
    document_no, rev = parse_pdf_stem(Path(path).stem)
    return (document_no or Path(path).stem), rev


def document_no_for_file(current: str, path: Path) -> str:
    """Use the PDF name while the row is still the blank New document line."""
    suggested, _rev = suggest_extra_identity(path)
    kept = (current or "").strip()
    if not kept or kept.casefold() == BLANK_EXTRA_NAME.casefold():
        return suggested
    return kept


def blank_extra(*, kind: str) -> PackExtra:
    """A Non Jira row with no file yet. Locate or Assign adds the PDF later."""
    return PackExtra(
        path="",
        document_no=BLANK_EXTRA_NAME,
        rev="",
        description="",
        status=letter_status(kind, ""),
        email_dropped=False,
        id=f"x:{uuid.uuid4().hex[:12]}",
        packed=True,
    )


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
    cc_engineer: str = ""
    cc_pm: str = ""
    cc_pep: str = ""
    cc_additional: str = ""
    cc_parts_saved: bool = False
    cc_permanent: str = ""
    cc_permanent_saved: bool = False
    permanent_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    kind_cc_additional: dict[str, str] = field(default_factory=dict)
    mail_overrides: dict[str, tuple[str, str]] = field(default_factory=dict)
    project_description: str = ""
    client: str = ""
    location: str = ""
    tag: str = ""
    po: str = ""
    wo: str = ""
    moc: str = ""
    pep_fields_saved: bool = False
    cover_captured: bool = False
    cover_initialized: bool = False
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


def _kind_cc_additional(raw: object) -> dict[str, str]:
    """Shop or Field additional CC, only when this job saved a difference."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("shop", "field"):
        if key in raw:
            out[key] = str(raw.get(key) or "").strip()
    return out


def _permanent_overrides(raw: object) -> dict[str, dict[str, str]]:
    """Job copies of permanent TO / CC, only for a side the operator changed."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for key, item in raw.items():
        name = str(key or "").strip().casefold()
        if name not in {"client", "shop", "field"} or not isinstance(item, dict):
            continue
        slot: dict[str, str] = {}
        for side in ("to", "cc"):
            if side in item:
                slot[side] = str(item.get(side) or "").strip()
        if slot:
            out[name] = slot
    return out


def _mail_overrides(raw: object) -> dict[str, tuple[str, str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for key, item in raw.items():
        name = str(key or "").strip()
        if not name or not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").replace("\r\n", "\n")
        body = str(item.get("body") or "").replace("\r\n", "\n")
        if subject.strip() or body.strip():
            out[name] = (subject, body)
    return out


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
        cc_engineer=str(raw.get("cc_engineer") or "").strip(),
        cc_pm=str(raw.get("cc_pm") or "").strip(),
        cc_pep=str(raw.get("cc_pep") or "").strip(),
        cc_additional=str(raw.get("cc_additional") or "").strip(),
        cc_parts_saved=bool(raw.get("cc_parts_saved")),
        cc_permanent=str(raw.get("cc_permanent") or "").strip(),
        cc_permanent_saved=bool(raw.get("cc_permanent_saved")),
        permanent_overrides=_permanent_overrides(raw.get("permanent_overrides")),
        kind_cc_additional=_kind_cc_additional(raw.get("kind_cc_additional")),
        mail_overrides=_mail_overrides(raw.get("mail_overrides")),
        project_description=str(raw.get("project_description") or "").strip(),
        client=str(raw.get("client") or "").strip(),
        location=str(raw.get("location") or "").strip(),
        tag=str(raw.get("tag") or "").strip(),
        po=str(raw.get("po") or "").strip(),
        wo=str(raw.get("wo") or "").strip(),
        moc=str(raw.get("moc") or "").strip(),
        pep_fields_saved=any(name in raw for name in ("client", "location", "tag", "po", "wo", "moc")),
        cover_captured=bool(raw.get("cover_captured")),
        cover_initialized=bool(raw.get("cover_initialized")),
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
        "cc_engineer": pack.cc_engineer,
        "cc_pm": pack.cc_pm,
        "cc_pep": pack.cc_pep,
        "cc_additional": pack.cc_additional,
        "cc_parts_saved": bool(pack.cc_parts_saved),
        "cc_permanent": pack.cc_permanent,
        "cc_permanent_saved": bool(pack.cc_permanent_saved),
        "permanent_overrides": {
            key: dict(slot) for key, slot in pack.permanent_overrides.items()
        },
        "kind_cc_additional": dict(pack.kind_cc_additional),
        "mail_overrides": {
            key: {"subject": subject, "body": body} for key, (subject, body) in pack.mail_overrides.items()
        },
        "project_description": pack.project_description,
        "client": pack.client,
        "location": pack.location,
        "tag": pack.tag,
        "po": pack.po,
        "wo": pack.wo,
        "moc": pack.moc,
        "cover_captured": bool(pack.cover_captured),
        "cover_initialized": bool(pack.cover_initialized),
        "selected_keys": list(pack.selected_keys),
        "located_pdfs": _dump_located_pdfs(pack.located_pdfs),
        "next_edits": {key: dict(fields) for key, fields in pack.next_edits.items()},
        "pack_extras": _dump_pack_extras(pack.pack_extras),
        "shop_folders": dict(_shop_folders(pack.shop_folders)),
        "job_folder": pack.job_folder,
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def pack_cover_initialized(pack: ClientPack | None) -> bool:
    """The operator located a PEP or saved the cover. Load does not open a PEP."""
    if pack is None:
        return False
    if pack.cover_initialized or pack.cover_captured:
        return True
    return any(
        (
            (pack.to_line or "").strip(),
            (pack.cc_line or "").strip(),
            (pack.project_description or "").strip(),
            (pack.pep_path or "").strip(),
        )
    )


def pack_recipients_saved(pack: ClientPack | None) -> bool:
    """True when this pack already has a TO or CC to show on the cover."""
    if pack is None:
        return False
    return bool(pack.cc_parts_saved or (pack.to_line or "").strip() or (pack.cc_line or "").strip())


def pack_cover_is_saved(pack: ClientPack | None) -> bool:
    """Load can fill the cover from the pack and skip the letter and the PEP."""
    if pack is None:
        return False
    if pack.cover_captured:
        return True
    return any(
        (
            pack.to_line,
            pack.cc_line,
            pack.project_description,
            pack.shop_to,
            pack.shop_cc,
            pack.field_to,
            pack.field_cc,
            pack.client,
            pack.location,
            pack.tag,
            pack.po,
            pack.wo,
            pack.moc,
        )
    )


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
