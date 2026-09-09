# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from doccon.register import (
    APPROVAL_FIELD,
    CLIENT_DOC_FIELD,
    FIELD_IFC_FIELD,
    INCOMING_REV_FIELD,
    JOB_NUMBER_FIELD,
    OUTGOING_REV_FIELD,
    PURPOSE_FIELD,
    SHOP_IFC_FIELD,
    DrawingRow,
    drawing_fields_payload,
    drawing_from_issue,
    drawings_jql,
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
]


class JiraError(RuntimeError):
    pass


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


def fetch_drawings(site: str, email: str, token: str, job_number: str, project_key: str) -> list[DrawingRow]:
    job = (job_number or "").strip()
    if not JOB_PATTERN.fullmatch(job):
        raise JiraError("Job Number can only contain letters, numbers, dot, underscore, and hyphen.")
    rows: list[DrawingRow] = []
    next_page: str | None = None
    jql = drawings_jql(job, project_key.strip() or "P2024")
    while True:
        body: dict = {
            "jql": jql,
            "maxResults": 50,
            "fields": DRAWING_FIELDS,
        }
        if next_page:
            body["nextPageToken"] = next_page
        payload = _request(site, email, token, "POST", "/rest/api/3/search/jql", body)
        issues = payload.get("issues") or []
        if not isinstance(issues, list):
            raise JiraError("Jira search did not return issues.")
        for issue in issues:
            if isinstance(issue, dict):
                rows.append(drawing_from_issue(issue))
        token_page = payload.get("nextPageToken")
        is_last = payload.get("isLast", True)
        if is_last or not token_page:
            break
        next_page = str(token_page)
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
        f"/rest/api/3/issue/{key}?notifyUsers=false",
        {"fields": fields},
    )


def apply_drawing_update(site: str, email: str, token: str, current: DrawingRow, nxt: DrawingRow) -> None:
    key = (nxt.key or current.key or "").strip()
    if not key:
        raise JiraError("Issue key is required.")
    fields = drawing_fields_payload(nxt)
    if fields:
        update_drawing_fields(site, email, token, nxt)
    current_status = (current.status or "").strip()
    next_status = (nxt.status or "").strip()
    if next_status and next_status.casefold() != current_status.casefold():
        transition_drawing(site, email, token, key, current_status, next_status)
    elif not fields:
        raise JiraError("No Jira fields to write.")
