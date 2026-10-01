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
PROJECT_LEAD_FIELD = "customfield_10071"
SUBMISSION_DATE_FIELD = "customfield_10301"
RETURN_REQUEST_DATE_FIELD = "customfield_10046"
RETURN_DATE_FIELD = "customfield_10066"
DUE_DATE_FIELD = "duedate"

DEFAULT_SITE = "https://eliteintegrityservices.atlassian.net"
DEFAULT_PROJECT = "P2024"
SUBTASK_ISSUE_TYPE_ID = "10013"

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
class PackageTask:
    """A Task under the job Project — valid parent for a new Sub-task."""

    key: str
    summary: str


@dataclass(frozen=True)
class EpicCopy:
    """Job Number and Project Lead / Sponsor copied from the job Project (epic)."""

    key: str
    summary: str
    job_number: str
    lead_account_ids: tuple[str, ...] = ()


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
    issue_type: str = ""


DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def normalize_option_key(text: str) -> str:
    """Match option labels across case, dash character, and stray/doubled whitespace."""
    token = text or ""
    for dash in DASH_CHARS:
        token = token.replace(dash, "-")
    return " ".join(token.split()).casefold()


@dataclass(frozen=True)
class FieldOption:
    """One option from a single issue's own Jira field context.

    Multi-checkbox contexts are per project / issue type, so an option read from one
    issue is not valid on another. ``option_id`` is context-safe; write that when Jira
    sends it.
    """

    label: str
    option_id: str = ""


def resolve_field_option(label: str, options: tuple[FieldOption, ...]) -> FieldOption | None:
    """That issue's option for this label, or None when its context has no such option."""
    want = normalize_option_key(label)
    if not want:
        return None
    for option in options:
        if normalize_option_key(option.label) == want:
            return option
    return None


def option_payload(option: FieldOption) -> dict:
    return {"id": option.option_id} if option.option_id else {"value": option.label}


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


def drawing_id_error(issue_key: str, drawing_id: str) -> str:
    """Operator message for a rejected JIRA ID Next. Empty string when it is usable.

    Light on purpose: the ID is the single leading code of the summary, so blank
    leaves nothing to write and an inner space would silently push the rest into
    the description. Elite numbering itself is not enforced here.
    """
    token = (drawing_id or "").strip()
    who = (issue_key or "").strip() or "This issue"
    if not token:
        return f"{who}: JIRA ID cannot be blank. Type the leading code, or restore Now."
    if any(char.isspace() for char in token):
        return f"{who}: JIRA ID cannot contain a space (got {token}). Put wording in Description."
    return ""


def new_issue_id_error(drawing_id: str) -> str:
    """Rejected JIRA ID on create. Empty string when it is usable."""
    token = (drawing_id or "").strip()
    if not token:
        return "JIRA ID cannot be blank. Type the leading code."
    if any(char.isspace() for char in token):
        return f"JIRA ID cannot contain a space (got {token}). Put wording in Description."
    return ""


def people_account_ids(field: object) -> tuple[str, ...]:
    """Account ids from a Jira People field (single user or list)."""
    if field is None:
        return ()
    rows = field if isinstance(field, list) else [field]
    out: list[str] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        aid = str(item.get("accountId") or "").strip()
        if aid and aid not in seen:
            seen.add(aid)
            out.append(aid)
    return tuple(out)


def create_eddi_choices(options: tuple[FieldOption, ...]) -> tuple[FieldOption, ...]:
    """Sub-task create list: groups 1–9 only, option ids kept."""
    return tuple(option for option in options if option.label and 1 <= eddi_group_rank(option.label) <= 9)


def new_issue_preflight_error(
    *,
    drawing_id: str,
    parent_key: str,
    eddi_label: str,
    job_number: str,
    eddi_options: tuple[FieldOption, ...] = (),
) -> str:
    """Operator message when create cannot POST. Empty string when the payload is ready."""
    bad_id = new_issue_id_error(drawing_id)
    if bad_id:
        return bad_id
    if not (parent_key or "").strip():
        return "Pick a Parent Task."
    if not (job_number or "").strip():
        return "The Jira Project has no Job Number. Nothing was created."
    if not eddi_options:
        return "Jira sent no EDDI Status options for Sub-task."
    chosen = (eddi_label or "").strip()
    if not chosen:
        return "Pick an EDDI Status (groups 1–9)."
    if is_generic_eddi(chosen) or not (1 <= eddi_group_rank(chosen) <= 9):
        return "Pick an EDDI Status in groups 1–9. Generic is not listed."
    if resolve_field_option(chosen, eddi_options) is None:
        allowed = ", ".join(option.label for option in eddi_options) or "(none)"
        return f'EDDI Status "{chosen}" is not an option on Sub-task create. Jira allows: {allowed}.'
    return ""


def create_subtask_payload(
    *,
    jira_project: str,
    parent_key: str,
    summary: str,
    job_number: str,
    eddi: FieldOption,
    lead_account_ids: tuple[str, ...] = (),
) -> dict:
    """POST /rest/api/3/issue body. Reporter stays Jira’s default."""
    fields: dict = {
        "project": {"key": (jira_project or "").strip() or DEFAULT_PROJECT},
        "issuetype": {"id": SUBTASK_ISSUE_TYPE_ID},
        "parent": {"key": (parent_key or "").strip()},
        "summary": (summary or "").strip(),
        JOB_NUMBER_FIELD: (job_number or "").strip(),
        EDDI_FIELD: [option_payload(eddi)],
    }
    leads = [aid for aid in lead_account_ids if (aid or "").strip()]
    if leads:
        fields[PROJECT_LEAD_FIELD] = [{"accountId": aid} for aid in leads]
    return {"fields": fields}


def package_tasks_from_issues(issues: list[dict]) -> list[PackageTask]:
    """Tasks only. Generic EDDI stays — those package Tasks are valid parents."""
    out: list[PackageTask] = []
    seen: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        fields = issue.get("fields") or {}
        if option_value(fields.get("issuetype")).casefold() != "task":
            continue
        key = str(issue.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        summary = str(fields.get("summary") or "").strip()
        out.append(PackageTask(key=key, summary=summary or key))
    return out


def epic_copy_from_issue(issue: dict) -> EpicCopy:
    fields = issue.get("fields") or {}
    return EpicCopy(
        key=str(issue.get("key") or "").strip(),
        summary=str(fields.get("summary") or "").strip(),
        job_number=option_value(fields.get(JOB_NUMBER_FIELD)),
        lead_account_ids=people_account_ids(fields.get(PROJECT_LEAD_FIELD)),
    )


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


def eddi_fix_options(options: tuple[FieldOption, ...] = ()) -> tuple[str, ...]:
    """Groups 1–9 for the Load fixer. Generic (0) is not offered.

    That issue's own Jira labels when its field context is known; otherwise the Elite list.
    """
    names = [option.label for option in options] if options else [name for name in EDDI_VALUES if name]
    return tuple(name for name in names if name and 1 <= eddi_group_rank(name) <= 9)


def eddi_option_labels(options: tuple[FieldOption, ...]) -> tuple[str, ...]:
    """Board ▼ list for one row: blank, then only that issue's own options."""
    labels = tuple(option.label for option in options if option.label)
    if not labels:
        return ()
    return ("",) + labels


def unknown_eddi_options(status: str, options: tuple[FieldOption, ...]) -> tuple[str, ...]:
    """Chosen labels that this issue's own EDDI context does not have. Empty when unknown."""
    if not options:
        return ()
    return tuple(
        part for part in eddi_status_choices(status) if resolve_field_option(part, options) is None
    )


def iso_date(value: str) -> str | None:
    token = (value or "").strip()
    if not token or token.casefold() in {"n/a", "na"}:
        return None
    try:
        return date.fromisoformat(token[:10]).isoformat()
    except ValueError:
        return None


def due_date_from_return_request(current_due: str, current_return: str, next_return: str) -> str:
    """Jira due date follows a newly entered return request date. Controllers do not edit due date.

    An explicit N/A (no return date) clears the due date that was following the return request.
    """
    token = (next_return or "").strip()
    if token.casefold() in {"n/a", "na"}:
        return "N/A"
    nxt = iso_date(token)
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
        issue_type=option_value(fields.get("issuetype")),
    )


def option_field(value: str) -> dict | None:
    token = (value or "").strip()
    return {"value": token} if token else None


def eddi_field(value: str, options: tuple[FieldOption, ...] = ()) -> list[dict] | None:
    """EDDI Status payload. Option ids when this issue's own context is known.

    Options are separated by ``;`` only — a comma is part of an option name
    (``5 - QC - WO, ITP, NDE Records, Procedures - EDDI``), never a separator.
    """
    parts = eddi_status_choices(value)
    if not parts:
        return None
    payload: list[dict] = []
    for part in parts:
        option = resolve_field_option(part, options)
        payload.append(option_payload(option) if option is not None else {"value": part})
    return payload


def drawing_fields_payload(drawing: DrawingRow, eddi_options: tuple[FieldOption, ...] = ()) -> dict:
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
        token = (value or "").strip()
        if token.casefold() in {"n/a", "na"}:
            payload[key] = None
            continue
        iso = iso_date(token)
        if iso:
            payload[key] = iso
    eddi = eddi_field(drawing.eddi_status, eddi_options)
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


def parent_tasks_of_jql(epic_key: str, project_key: str = DEFAULT_PROJECT) -> str:
    key = epic_key.strip()
    return f"project = {project_key} AND issuetype = Task AND parent = {key} ORDER BY summary ASC"


def parent_tasks_by_job_jql(job_number: str, project_key: str = DEFAULT_PROJECT) -> str:
    job = job_number.strip()
    return (
        f"project = {project_key} AND issuetype = Task AND {job_number_clause(job)} ORDER BY summary ASC"
    )


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
    allowed: tuple[str, ...] = ()


def eddi_conflicts(
    rows: list[DrawingRow], contexts: dict[str, tuple[FieldOption, ...]] | None = None
) -> list[EddiConflict]:
    """Issues whose EDDI Status has more than one option. Generic-only is not a conflict.

    ``allowed`` is what the fixer may offer for that issue: its own Jira options
    (groups 1–9), or the Elite list when Jira did not send a context.
    """
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
                    allowed=eddi_fix_options((contexts or {}).get(row.key, ())),
                )
            )
    return found
