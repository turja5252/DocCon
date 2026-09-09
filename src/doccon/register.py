# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

from dataclasses import dataclass

JOB_NUMBER_FIELD = "customfield_10300"
OUTGOING_REV_FIELD = "customfield_10280"
PURPOSE_FIELD = "customfield_10281"
INCOMING_REV_FIELD = "customfield_10283"
APPROVAL_FIELD = "customfield_10284"
SHOP_IFC_FIELD = "customfield_10285"
FIELD_IFC_FIELD = "customfield_10287"
CLIENT_DOC_FIELD = "customfield_10279"

DEFAULT_SITE = "https://eliteintegrityservices.atlassian.net"
DEFAULT_PROJECT = "P2024"

DRAWING_STATUSES = (
    "To Do",
    "In Progress",
    "OFA",
    "Awaiting Client Information",
    "Roadblock",
    "Back from Client",
    "IFI",
    "IFC",
    "Done",
)


@dataclass(frozen=True)
class DrawingRow:
    key: str
    summary: str
    drawing_id: str
    title: str
    status: str
    job_number: str
    outgoing_rev: str
    purpose: str
    parent_summary: str
    incoming_rev: str = ""
    approval: str = ""
    shop_ifc_rev: str = ""
    field_ifc_rev: str = ""
    client_document_number: str = ""


def parse_summary(summary: str) -> tuple[str, str]:
    text = (summary or "").strip()
    if not text:
        return "", ""
    token, _, rest = text.partition(" ")
    return token.strip(), rest.strip()


def adopted_summary(current_summary: str, pdf_drawing_id: str) -> str:
    drawing_id = (pdf_drawing_id or "").strip()
    if not drawing_id:
        return (current_summary or "").strip()
    _, title = parse_summary(current_summary)
    if title:
        return f"{drawing_id} {title}"
    return drawing_id


def option_value(field: object) -> str:
    if field is None:
        return ""
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, dict):
        value = field.get("value") or field.get("name") or ""
        return str(value).strip()
    return str(field).strip()


def drawing_from_issue(issue: dict) -> DrawingRow:
    fields = issue.get("fields") or {}
    summary = str(fields.get("summary") or "")
    drawing_id, title = parse_summary(summary)
    status = option_value(fields.get("status"))
    parent = fields.get("parent") or {}
    parent_fields = parent.get("fields") or {}
    return DrawingRow(
        key=str(issue.get("key") or ""),
        summary=summary,
        drawing_id=drawing_id,
        title=title,
        status=status,
        job_number=option_value(fields.get(JOB_NUMBER_FIELD)),
        outgoing_rev=option_value(fields.get(OUTGOING_REV_FIELD)),
        purpose=option_value(fields.get(PURPOSE_FIELD)),
        parent_summary=str(parent_fields.get("summary") or ""),
        incoming_rev=option_value(fields.get(INCOMING_REV_FIELD)),
        approval=option_value(fields.get(APPROVAL_FIELD)),
        shop_ifc_rev=option_value(fields.get(SHOP_IFC_FIELD)),
        field_ifc_rev=option_value(fields.get(FIELD_IFC_FIELD)),
        client_document_number=option_value(fields.get(CLIENT_DOC_FIELD)),
    )


def option_field(value: str) -> dict | None:
    token = (value or "").strip()
    return {"value": token} if token else None


def drawing_fields_payload(drawing: DrawingRow) -> dict:
    payload: dict = {}
    options = {
        OUTGOING_REV_FIELD: drawing.outgoing_rev,
        PURPOSE_FIELD: drawing.purpose,
        INCOMING_REV_FIELD: drawing.incoming_rev,
        APPROVAL_FIELD: drawing.approval,
        SHOP_IFC_FIELD: drawing.shop_ifc_rev,
        FIELD_IFC_FIELD: drawing.field_ifc_rev,
    }
    for key, value in options.items():
        item = option_field(value)
        if item is not None:
            payload[key] = item
    client_no = (drawing.client_document_number or "").strip()
    if client_no:
        payload[CLIENT_DOC_FIELD] = client_no
    return payload


def drawings_jql(job_number: str, project_key: str = DEFAULT_PROJECT) -> str:
    job = job_number.strip()
    return (
        f"project = {project_key} AND issuetype = Sub-task AND labels = Drafting "
        f'AND "Job Number" ~ "{job}" ORDER BY summary ASC'
    )
