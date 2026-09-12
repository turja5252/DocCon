# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

JOB_NUMBER_FIELD = "customfield_10300"
OUTGOING_REV_FIELD = "customfield_10280"
PURPOSE_FIELD = "customfield_10281"
INCOMING_REV_FIELD = "customfield_10283"
APPROVAL_FIELD = "customfield_10284"
SHOP_IFC_FIELD = "customfield_10285"
SHOP_IFC_DATE_FIELD = "customfield_10286"
FIELD_IFC_FIELD = "customfield_10287"
FIELD_IFC_DATE_FIELD = "customfield_10288"
CLIENT_DOC_FIELD = "customfield_10279"
EDDI_FIELD = "customfield_10289"
SUBMISSION_DATE_FIELD = "customfield_10301"
RETURN_REQUEST_DATE_FIELD = "customfield_10046"
RETURN_DATE_FIELD = "customfield_10066"
DUE_DATE_FIELD = "duedate"

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

EDDI_VALUES = (
    "",
    "0 - Generic Task",
    "1 - Fabrication Drawings - EDDI",
    "2 - Construction /  Installation Drawings - EDDI",
    "3 - Supplier Drawings - EDDI",
    "4 - Engineering - EDDI",
    "5 - QC - WO, ITP, NDE Records, Procedures - EDDI",
    "6 - QC - Welding - EDDI",
    "7 - QC -  Supplier - EDDI",
    "8 - Document Control - EDDI",
    "9 - Project Management - EDDI",
)

APPROVAL_VALUES = (
    "",
    "Approved",
    "Approved with Comments",
    "Revise & Resubmit",
    "Rejected",
    "Info",
    "Void",
)


MISSING_JIRA_PROJECT = "No Jira Project for this Job Number"


@dataclass(frozen=True)
class JobProject:
    key: str
    summary: str


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
    due_date: str = ""
    submission_date: str = ""
    return_request_date: str = ""
    return_date: str = ""
    shop_ifc_date: str = ""
    field_ifc_date: str = ""
    eddi_status: str = ""


# EDDI group 6 — QC Welding. Jira summary is the code, then this wording.
WELD_PROCEDURE_DESCRIPTION = "Welding Procedure Specification"
WELD_SUMMARY_DESCRIPTION = "Elite Weld Procedure Summary"
CWB_CERTIFICATE_ID = "CWB Certificate"
CWB_CERTIFICATE_DESCRIPTION = "CWB Certification"
WELD_MULTIWORD_IDS = (CWB_CERTIFICATE_ID,)
WELD_PROCEDURE_ID_PREFIXES = ("EIS-", "FM-WPS-", "SM-WPS-")


def _looks_like_language(token: str) -> bool:
    """True when this token starts description text, not another ID fragment."""
    piece = token.strip(".,;:()[]")
    if not piece or piece in {"-", "–", "—", "/", "&"}:
        return False
    letters = "".join(ch for ch in piece if ch.isalpha())
    if len(letters) >= 4 and any(ch.islower() for ch in piece):
        return True
    return len(letters) >= 5 and not any(ch.isdigit() for ch in piece)


def weld_package_description(drawing_id: str) -> str:
    """Set wording for a welding-package document number. Empty if it is not one."""
    token = (drawing_id or "").strip()
    if not token:
        return ""
    if token.casefold() == CWB_CERTIFICATE_ID.casefold():
        return CWB_CERTIFICATE_DESCRIPTION
    head = token.casefold()
    if head.startswith("ws-"):
        return WELD_SUMMARY_DESCRIPTION
    if any(head.startswith(prefix.casefold()) for prefix in WELD_PROCEDURE_ID_PREFIXES):
        return WELD_PROCEDURE_DESCRIPTION
    return ""


def _multiword_weld_id(text: str) -> tuple[str, str] | None:
    folded = text.casefold()
    for ident in WELD_MULTIWORD_IDS:
        if folded == ident.casefold():
            return ident, ""
        prefix = ident + " "
        if folded.startswith(prefix.casefold()):
            return ident, text[len(ident) :].strip(" -–—")
    return None


def parse_summary(summary: str) -> tuple[str, str]:
    """Split a Jira summary into drawing ID and optional description.

    The ID is the leading code (``2026-075-ITP-1-1``, ``2026-075-1-STWD``). It may
    be the whole summary. Description is any wording after that code. Empty is
    fine — there is no required title format. Welding-package ``CWB Certificate``
    is a two-word ID.
    """
    tokens = [part for part in re.split(r"\s+", (summary or "").strip()) if part]
    if not tokens:
        return "", ""
    text = " ".join(tokens)
    weld_id = _multiword_weld_id(text)
    if weld_id is not None:
        return weld_id
    end = 1
    while end < len(tokens) and not _looks_like_language(tokens[end]):
        end += 1
    drawing_id = " ".join(tokens[:end]).strip(" \t-–—:")
    title = " ".join(tokens[end:]).strip(" -–—")
    return drawing_id, title


def adopted_summary(current_summary: str, pdf_drawing_id: str) -> str:
    drawing_id = (pdf_drawing_id or "").strip()
    if not drawing_id:
        return (current_summary or "").strip()
    _, title = parse_summary(current_summary)
    if title:
        return f"{drawing_id} {title}"
    return drawing_id


def summary_from_parts(drawing_id: str, description: str) -> str:
    drawing = (drawing_id or "").strip()
    desc = (description or "").strip()
    if drawing and desc:
        return f"{drawing} {desc}"
    return drawing or desc


def option_value(field: object) -> str:
    if field is None:
        return ""
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, dict):
        value = field.get("value") or field.get("name") or ""
        return str(value).strip()
    return str(field).strip()


def date_value(field: object) -> str:
    token = option_value(field)
    if not token:
        return ""
    return token[:10]


def eddi_status_choices(status: str) -> tuple[str, ...]:
    """Split a stored EDDI Status (joined or single) into option labels."""
    token = (status or "").strip()
    if not token:
        return ()
    if "; " in token:
        return tuple(part.strip() for part in token.split("; ") if part.strip())
    if ";" in token:
        return tuple(part.strip() for part in token.split(";") if part.strip())
    return (token,)


def eddi_options(field: object) -> tuple[str, ...]:
    """Parse Jira EDDI Status as a list of options (multi-checkbox)."""
    if field is None:
        return ()
    if isinstance(field, list):
        parts = [option_value(item) for item in field]
        return tuple(part for part in parts if part)
    return eddi_status_choices(option_value(field))


def eddi_value(field: object) -> str:
    return "; ".join(eddi_options(field))


def has_multiple_eddi(status: str) -> bool:
    return len(eddi_status_choices(status)) > 1


def eddi_fix_options() -> tuple[str, ...]:
    """Console groups 1–9. Generic (0) is not offered on the Load fixer."""
    return tuple(name for name in EDDI_VALUES if name and 1 <= eddi_group_rank(name) <= 9)


def iso_date(value: str) -> str | None:
    token = (value or "").strip()
    if not token or token.casefold() in {"n/a", "na"}:
        return None
    try:
        return date.fromisoformat(token[:10]).isoformat()
    except ValueError:
        return None


def due_date_from_return_request(current_due: str, current_return: str, next_return: str) -> str:
    """Jira due date follows a newly entered return request date. Controllers do not edit due date."""
    nxt = iso_date(next_return)
    if nxt and nxt != iso_date(current_return):
        return nxt
    return (current_due or "").strip()


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
        due_date=date_value(fields.get(DUE_DATE_FIELD)),
        submission_date=date_value(fields.get(SUBMISSION_DATE_FIELD)),
        return_request_date=date_value(fields.get(RETURN_REQUEST_DATE_FIELD)),
        return_date=date_value(fields.get(RETURN_DATE_FIELD)),
        shop_ifc_date=date_value(fields.get(SHOP_IFC_DATE_FIELD)),
        field_ifc_date=date_value(fields.get(FIELD_IFC_DATE_FIELD)),
        eddi_status=eddi_value(fields.get(EDDI_FIELD)),
    )


def option_field(value: str) -> dict | None:
    token = (value or "").strip()
    return {"value": token} if token else None


def eddi_field(value: str) -> list[dict] | None:
    parts = [part.strip() for part in (value or "").replace(",", ";").split(";") if part.strip()]
    if not parts:
        return None
    return [{"value": part} for part in parts]


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
    dates = {
        DUE_DATE_FIELD: drawing.due_date,
        SUBMISSION_DATE_FIELD: drawing.submission_date,
        RETURN_REQUEST_DATE_FIELD: drawing.return_request_date,
        RETURN_DATE_FIELD: drawing.return_date,
        SHOP_IFC_DATE_FIELD: drawing.shop_ifc_date,
        FIELD_IFC_DATE_FIELD: drawing.field_ifc_date,
    }
    for key, value in dates.items():
        token = iso_date(value)
        if token:
            payload[key] = token
    eddi = eddi_field(drawing.eddi_status)
    if eddi:
        payload[EDDI_FIELD] = eddi
    return payload


def job_number_clause(job_number: str) -> str:
    job = job_number.strip()
    return f'"Job Number" ~ "{job}"'


def drawings_jql(job_number: str, project_key: str = DEFAULT_PROJECT) -> str:
    job = job_number.strip()
    return (
        f"project = {project_key} AND issuetype != Project "
        f"AND {job_number_clause(job)} ORDER BY summary ASC"
    )


def job_project_jql(job_number: str, project_key: str = DEFAULT_PROJECT) -> str:
    job = job_number.strip()
    return f"project = {project_key} AND issuetype = Project AND {job_number_clause(job)}"


def job_project_from_issue(issue: dict) -> JobProject | None:
    fields = issue.get("fields") or {}
    if option_value(fields.get("issuetype")).casefold() != "project":
        return None
    key = str(issue.get("key") or "").strip()
    summary = str(fields.get("summary") or "").strip()
    if not key and not summary:
        return None
    return JobProject(key=key, summary=summary)


def job_project_from_issues(issues: list[dict]) -> JobProject | None:
    for issue in issues:
        if isinstance(issue, dict):
            found = job_project_from_issue(issue)
            if found is not None:
                return found
    return None


def jira_project_label(project: JobProject | None) -> str:
    if project is None or (not project.key and not project.summary):
        return MISSING_JIRA_PROJECT
    if project.key and project.summary:
        return f"{project.key}  {project.summary}"
    return project.key or project.summary


def children_of_jql(keys: list[str], project_key: str = DEFAULT_PROJECT) -> str:
    joined = ", ".join(key.strip() for key in keys if key.strip())
    return f"project = {project_key} AND issuetype != Project AND parent in ({joined})"


def eddi_group_rank(status: str) -> int:
    token = (status or "").strip()
    if not token:
        return 99
    head = token.split(" ", 1)[0]
    if head.isdigit():
        return int(head)
    return 50


def eddi_group_title(status: str) -> str:
    token = (status or "").strip()
    if not token:
        return "Ungrouped"
    title = token
    for name in EDDI_VALUES:
        if name and token.casefold() == name.casefold():
            title = name
            break
    if title.casefold().endswith(" - eddi"):
        title = title[: -len(" - EDDI")].rstrip()
    return title


def pack_sort_key(drawing: DrawingRow) -> tuple:
    return (
        eddi_group_rank(drawing.eddi_status),
        (drawing.drawing_id or drawing.summary or "").casefold(),
        drawing.key,
    )


def sort_pack_rows(rows: list[DrawingRow]) -> list[DrawingRow]:
    return sorted(rows, key=pack_sort_key)


def is_generic_eddi(status: str) -> bool:
    return eddi_group_rank(status) == 0


def visible_pack_rows(rows: list[DrawingRow]) -> list[DrawingRow]:
    return [row for row in rows if not is_generic_eddi(row.eddi_status)]


@dataclass(frozen=True)
class EddiConflict:
    key: str
    drawing_id: str
    summary: str
    options: tuple[str, ...]


def eddi_conflicts(rows: list[DrawingRow]) -> list[EddiConflict]:
    """Issues whose EDDI Status has more than one option. Generic-only is not a conflict."""
    found: list[EddiConflict] = []
    for row in rows:
        options = eddi_status_choices(row.eddi_status)
        if len(options) > 1:
            found.append(
                EddiConflict(
                    key=row.key,
                    drawing_id=row.drawing_id,
                    summary=row.summary,
                    options=options,
                )
            )
    return found
