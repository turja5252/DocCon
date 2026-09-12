# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import base64
import json
import re
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from doccon.register import (
    APPROVAL_FIELD,
    CLIENT_DOC_FIELD,
    DUE_DATE_FIELD,
    EDDI_FIELD,
    FIELD_IFC_DATE_FIELD,
    FIELD_IFC_FIELD,
    INCOMING_REV_FIELD,
    JOB_NUMBER_FIELD,
    OUTGOING_REV_FIELD,
    PURPOSE_FIELD,
    RETURN_DATE_FIELD,
    RETURN_REQUEST_DATE_FIELD,
    SHOP_IFC_DATE_FIELD,
    SHOP_IFC_FIELD,
    SUBMISSION_DATE_FIELD,
    DrawingRow,
    JobProject,
    children_of_jql,
    drawing_fields_payload,
    drawing_from_issue,
    drawings_jql,
    eddi_field,
    iso_date,
    job_project_from_issues,
    job_project_jql,
    option_value,
    sort_pack_rows,
    summary_from_parts,
    visible_pack_rows,
)

JOB_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

DRAWING_FIELDS = [
    "summary",
    "status",
    "issuetype",
    "parent",
    "labels",
    JOB_NUMBER_FIELD,
    OUTGOING_REV_FIELD,
    PURPOSE_FIELD,
    APPROVAL_FIELD,
    INCOMING_REV_FIELD,
    SHOP_IFC_FIELD,
    FIELD_IFC_FIELD,
    CLIENT_DOC_FIELD,
    DUE_DATE_FIELD,
    EDDI_FIELD,
    SUBMISSION_DATE_FIELD,
    RETURN_REQUEST_DATE_FIELD,
    RETURN_DATE_FIELD,
    SHOP_IFC_DATE_FIELD,
    FIELD_IFC_DATE_FIELD,
]

# Now values are read on Load from the issue. These IDs are only for editmeta allowedValues.
REV_OPTION_FIELDS = {
    "outgoing_rev": OUTGOING_REV_FIELD,
    "incoming_rev": INCOMING_REV_FIELD,
    "shop_ifc_rev": SHOP_IFC_FIELD,
    "field_ifc_rev": FIELD_IFC_FIELD,
}


class JiraError(RuntimeError):
    pass


def parse_allowed_values(field_meta: object) -> tuple[str, ...]:
    """Labels from Jira editmeta / createmeta ``allowedValues``. Empty if Jira sent none."""
    if not isinstance(field_meta, dict):
        return ()
    allowed = field_meta.get("allowedValues")
    if not isinstance(allowed, list):
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for item in allowed:
        label = option_value(item)
        key = label.casefold()
        if label and key not in seen:
            seen.add(key)
            values.append(label)
    return tuple(values)


def _schema_type(field_meta: object) -> str:
    if not isinstance(field_meta, dict):
        return ""
    schema = field_meta.get("schema")
    if not isinstance(schema, dict):
        return ""
    return str(schema.get("type") or "").strip().casefold()


def _schema_custom(field_meta: object) -> str:
    if not isinstance(field_meta, dict):
        return ""
    schema = field_meta.get("schema")
    if not isinstance(schema, dict):
        return ""
    return str(schema.get("custom") or "").strip().casefold()


def field_meta_is_option(field_meta: object) -> bool:
    """True when Jira defines this as a select/option (allowedValues or select schema)."""
    if parse_allowed_values(field_meta):
        return True
    typ = _schema_type(field_meta)
    custom = _schema_custom(field_meta)
    if typ == "option":
        return True
    return "select" in custom or "radiobuttons" in custom


def parse_rev_option_lists(editmeta: object) -> dict[str, tuple[str, ...]]:
    """Rev Combobox lists from Jira editmeta. Omit a field when Jira did not send a list.

    Now values are not fetched here — Load already read them from the issue.
    Text-schema rev fields are omitted so the board keeps the editable convenience list.
    """
    if not isinstance(editmeta, dict):
        return {}
    fields = editmeta.get("fields")
    if not isinstance(fields, dict):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for attr, field_id in REV_OPTION_FIELDS.items():
        meta = fields.get(field_id)
        if not field_meta_is_option(meta):
            continue
        values = parse_allowed_values(meta)
        if not values:
            continue
        if "" not in values:
            values = ("",) + values
        out[attr] = values
    return out


def fetch_rev_option_lists(site: str, email: str, token: str, issue_key: str) -> dict[str, tuple[str, ...]]:
    """GET editmeta for one issue. Does not replace the Load fetch of Now values."""
    key = (issue_key or "").strip()
    if not key or "/" in key:
        return {}
    payload = _request(site, email, token, "GET", f"/rest/api/3/issue/{key}/editmeta")
    return parse_rev_option_lists(payload)


def normalize_site(site: str) -> str:
    text = (site or "").strip().rstrip("/")
    if not text:
        raise JiraError("Jira site is empty.")
    if not text.startswith("http://") and not text.startswith("https://"):
        text = "https://" + text
    return text


def _basic_auth(email: str, token: str) -> str:
    raw = f"{email.strip()}:{token.strip()}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _request(site: str, email: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = normalize_site(site) + path
    data = None
    headers = {
        "Authorization": _basic_auth(email, token),
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        if exc.code == 401:
            raise JiraError("Jira login failed (401). Check email and API token in Settings.") from exc
        raise JiraError(f"Jira HTTP {exc.code}: {detail[:400]}") from exc
    except URLError as exc:
        raise JiraError(f"Could not reach Jira: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JiraError("Jira returned a non-JSON response.") from exc
    if not isinstance(parsed, dict):
        raise JiraError("Jira returned unexpected JSON.")
    return parsed


def ping(site: str, email: str, token: str) -> str:
    payload = _request(site, email, token, "GET", "/rest/api/3/myself")
    name = str(payload.get("displayName") or payload.get("emailAddress") or "").strip()
    if not name:
        raise JiraError("Jira responded but did not return a user.")
    return name


def _search_issues(site: str, email: str, token: str, jql: str) -> list[dict]:
    issues: list[dict] = []
    next_page: str | None = None
    while True:
        body: dict = {
            "jql": jql,
            "maxResults": 100,
            "fields": DRAWING_FIELDS,
        }
        if next_page:
            body["nextPageToken"] = next_page
        payload = _request(site, email, token, "POST", "/rest/api/3/search/jql", body)
        page = payload.get("issues") or []
        if not isinstance(page, list):
            raise JiraError("Jira search did not return issues.")
        for issue in page:
            if isinstance(issue, dict):
                issues.append(issue)
        token_page = payload.get("nextPageToken")
        is_last = payload.get("isLast", True)
        if is_last or not token_page:
            break
        next_page = str(token_page)
    return issues


def _search_many(site: str, email: str, token: str, jqls: list[str]) -> list[list[dict]]:
    results: list[list[dict] | None] = [None] * len(jqls)
    errors: list[BaseException] = []

    def run(index: int, jql: str) -> None:
        try:
            results[index] = _search_issues(site, email, token, jql)
        except Exception as exc:
            errors.append(exc)

    if len(jqls) == 1:
        return [_search_issues(site, email, token, jqls[0])]
    threads = [threading.Thread(target=run, args=(index, jql), daemon=True) for index, jql in enumerate(jqls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors:
        raise errors[0]
    return [page or [] for page in results]


def _row_from_issue(issue: dict) -> DrawingRow | None:
    fields = issue.get("fields") or {}
    if option_value(fields.get("issuetype")).casefold() == "project":
        return None
    row = drawing_from_issue(issue)
    return row if row.key else None


def fetch_job_pack(
    site: str, email: str, token: str, job_number: str, project_key: str
) -> tuple[list[DrawingRow], JobProject | None]:
    job = (job_number or "").strip()
    if not JOB_PATTERN.fullmatch(job):
        raise JiraError("Job Number can only contain letters, numbers, dot, underscore, and hyphen.")
    key = project_key.strip() or "P2024"
    seen: dict[str, DrawingRow] = {}

    def add_issues(issues: list[dict]) -> list[str]:
        keys: list[str] = []
        for issue in issues:
            row = _row_from_issue(issue)
            if row is None:
                continue
            if row.key not in seen:
                seen[row.key] = row
            keys.append(row.key)
        return keys

    pack_issues, project_issues = _search_many(
        site,
        email,
        token,
        [drawings_jql(job, key), job_project_jql(job, key)],
    )
    add_issues(pack_issues)
    job_project = job_project_from_issues(project_issues)
    job_keys = [
        str(issue.get("key") or "").strip()
        for issue in project_issues
        if str(issue.get("key") or "").strip()
    ]
    if job_keys:
        child_keys = add_issues(_search_issues(site, email, token, children_of_jql(job_keys, key)))
        if child_keys:
            add_issues(_search_issues(site, email, token, children_of_jql(child_keys, key)))
    return sort_pack_rows(visible_pack_rows(list(seen.values()))), job_project


def fetch_drawings(site: str, email: str, token: str, job_number: str, project_key: str) -> list[DrawingRow]:
    rows, _project = fetch_job_pack(site, email, token, job_number, project_key)
    return rows


def update_summary(site: str, email: str, token: str, issue_key: str, summary: str) -> None:
    key = (issue_key or "").strip()
    text = (summary or "").strip()
    if not key or not text:
        raise JiraError("Issue key and summary are required.")
    _request(
        site,
        email,
        token,
        "PUT",
        f"/rest/api/3/issue/{key}",
        {"fields": {"summary": text}},
    )


def parse_transitions(payload: dict) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    items = payload.get("transitions") or []
    if not isinstance(items, list):
        return rows
    for item in items:
        if not isinstance(item, dict):
            continue
        dest = item.get("to") if isinstance(item.get("to"), dict) else {}
        available = item.get("isAvailable", True)
        if available is False:
            continue
        transition_id = str(item.get("id") or "").strip()
        to_status = str(dest.get("name") or "").strip()
        if not transition_id or not to_status:
            continue
        rows.append(
            {
                "id": transition_id,
                "name": str(item.get("name") or "").strip(),
                "to": to_status,
            }
        )
    return rows


def transition_id_for_status(transitions: list[dict[str, str]], target: str) -> str:
    want = (target or "").strip().casefold()
    if not want:
        return ""
    for item in transitions:
        if item.get("to", "").strip().casefold() == want:
            return item.get("id") or ""
    return ""


def allowed_status_names(transitions: list[dict[str, str]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in transitions:
        name = (item.get("to") or "").strip()
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def list_transitions(site: str, email: str, token: str, issue_key: str) -> list[dict[str, str]]:
    key = (issue_key or "").strip()
    if not key or "/" in key:
        raise JiraError("Issue key is required.")
    payload = _request(site, email, token, "GET", f"/rest/api/3/issue/{key}/transitions")
    return parse_transitions(payload)


def transition_drawing(site: str, email: str, token: str, issue_key: str, current_status: str, next_status: str) -> None:
    key = (issue_key or "").strip()
    current = (current_status or "").strip()
    target = (next_status or "").strip()
    if not key:
        raise JiraError("Issue key is required.")
    if not target or target.casefold() == current.casefold():
        return
    transitions = list_transitions(site, email, token, key)
    transition_id = transition_id_for_status(transitions, target)
    if not transition_id:
        allowed = ", ".join(allowed_status_names(transitions)) or "(none)"
        raise JiraError(
            f"Cannot move {key} from {current or '(none)'} to {target}. From here Jira allows: {allowed}."
        )
    _request(
        site,
        email,
        token,
        "POST",
        f"/rest/api/3/issue/{key}/transitions",
        {"transition": {"id": transition_id}},
    )


def update_eddi_status(site: str, email: str, token: str, issue_key: str, status: str) -> None:
    """Write one EDDI Status option. Does not file a transmittal or send mail."""
    key = (issue_key or "").strip()
    chosen = (status or "").strip()
    if not key:
        raise JiraError("Issue key is required.")
    payload = eddi_field(chosen)
    if not payload or len(payload) != 1:
        raise JiraError(f"{key}: pick one EDDI Status.")
    _request(
        site,
        email,
        token,
        "PUT",
        f"/rest/api/3/issue/{key}",
        {"fields": {EDDI_FIELD: payload}},
    )


def update_drawing_fields(site: str, email: str, token: str, drawing: DrawingRow) -> None:
    key = (drawing.key or "").strip()
    fields = drawing_fields_payload(drawing)
    if not key:
        raise JiraError("Issue key is required.")
    if not fields:
        raise JiraError("No Jira fields to write.")
    _request(
        site,
        email,
        token,
        "PUT",
        f"/rest/api/3/issue/{key}",
        {"fields": fields},
    )


DATE_ATTRS = (
    ("due_date", "Due Date (Jira)"),
    ("submission_date", "Submission Date"),
    ("return_request_date", "Return Request Date"),
    ("return_date", "Return Date"),
    ("shop_ifc_date", "Shop IFC Date"),
    ("field_ifc_date", "Field IFC Date"),
)


def preflight_drawing_update(site: str, email: str, token: str, current: DrawingRow, nxt: DrawingRow) -> None:
    """Raise if this update cannot be applied. Does not write Jira."""
    key = (nxt.key or current.key or "").strip()
    if not key:
        raise JiraError("Issue key is required.")
    for attr, label in DATE_ATTRS:
        raw = str(getattr(nxt, attr, "") or "").strip()
        if not raw or raw.casefold() in {"n/a", "na"}:
            continue
        if iso_date(raw) is None:
            raise JiraError(f"{key}: {label} must be YYYY-MM-DD (got {raw}).")
    current_status = (current.status or "").strip()
    next_status = (nxt.status or "").strip()
    if next_status and next_status.casefold() != current_status.casefold():
        transitions = list_transitions(site, email, token, key)
        if not transition_id_for_status(transitions, next_status):
            allowed = ", ".join(allowed_status_names(transitions)) or "(none)"
            raise JiraError(
                f"Cannot move {key} from {current_status or '(none)'} to {next_status}. "
                f"From here Jira allows: {allowed}."
            )


def preflight_jira_updates(
    site: str, email: str, token: str, pairs: list[tuple[DrawingRow, DrawingRow]]
) -> None:
    for current, nxt in pairs:
        preflight_drawing_update(site, email, token, current, nxt)


def revert_drawing_update(site: str, email: str, token: str, current: DrawingRow, nxt: DrawingRow) -> None:
    """Best-effort undo of apply_drawing_update (original values)."""
    key = (nxt.key or current.key or "").strip()
    if not key:
        return
    was_summary = (current.summary or "").strip()
    if was_summary and was_summary != (nxt.summary or "").strip():
        update_summary(site, email, token, key, was_summary)
    fields = drawing_fields_payload(current)
    if fields:
        update_drawing_fields(site, email, token, current)
    was_status = (current.status or "").strip()
    now_status = (nxt.status or "").strip()
    if was_status and now_status and was_status.casefold() != now_status.casefold():
        transition_drawing(site, email, token, key, now_status, was_status)


def apply_jira_updates(
    site: str, email: str, token: str, pairs: list[tuple[DrawingRow, DrawingRow]]
) -> None:
    """Write every drawing. If one fails, roll back those already written."""
    done: list[tuple[DrawingRow, DrawingRow]] = []
    try:
        for current, nxt in pairs:
            apply_drawing_update(site, email, token, current, nxt)
            done.append((current, nxt))
    except Exception:
        revert_errors: list[str] = []
        for current, nxt in reversed(done):
            try:
                revert_drawing_update(site, email, token, current, nxt)
            except JiraError as exc:
                revert_errors.append(f"{nxt.key or current.key}: {exc}")
        if revert_errors:
            raise JiraError(
                "Jira write aborted. Rollback failed, so some issues may still be changed: "
                + "; ".join(revert_errors)
            ) from None
        raise


def run_jira_register_update(
    site: str, email: str, token: str, pairs: list[tuple[DrawingRow, DrawingRow]]
) -> int:
    """Preflight, then write Next values. No Excel, no Outlook. Abort writes nothing."""
    if not pairs:
        raise JiraError("No Next changes to write.")
    preflight_jira_updates(site, email, token, pairs)
    apply_jira_updates(site, email, token, pairs)
    return len(pairs)


def apply_drawing_update(site: str, email: str, token: str, current: DrawingRow, nxt: DrawingRow) -> None:
    key = (nxt.key or current.key or "").strip()
    if not key:
        raise JiraError("Issue key is required.")
    wrote = False
    next_summary = summary_from_parts(nxt.drawing_id or current.drawing_id, nxt.title)
    if next_summary and next_summary != (current.summary or "").strip():
        update_summary(site, email, token, key, next_summary)
        wrote = True
    fields = drawing_fields_payload(nxt)
    if fields:
        update_drawing_fields(site, email, token, nxt)
        wrote = True
    current_status = (current.status or "").strip()
    next_status = (nxt.status or "").strip()
    if next_status and next_status.casefold() != current_status.casefold():
        transition_drawing(site, email, token, key, current_status, next_status)
        wrote = True
    if not wrote:
        raise JiraError("No Jira fields to write.")
