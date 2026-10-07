# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Open an Outlook draft: transmittal PDF plus a zip of the drawing PDFs."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from doccon.client_log import LogError
from doccon.excel_pdf import _ps_lit
from doccon.kinds import CLIENT, PREFIX
from doccon.match import MatchedRow
from doccon.pep import DOC_CONTROL_FROM, email_line
from doccon.winproc import hidden_run, powershell_hidden_argv


def normalize_recipients(text: str) -> str:
    return email_line(text)


def drawing_pdfs(rows: list[MatchedRow]) -> list[Path]:
    return attach_pdfs(rows, ())


def attach_pdfs(rows: list[MatchedRow], extra_paths: list[Path] | tuple[Path, ...]) -> list[Path]:
    """Packed drawing PDFs, then PDFs that have no Jira issue. The transmittal form is not included."""
    files: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        resolved = path.resolve()
        key = str(resolved).casefold()
        if key in seen:
            return
        seen.add(key)
        files.append(resolved)

    for row in rows:
        if row.pdf is not None:
            add(row.pdf.path)
    for path in extra_paths:
        add(Path(path))
    return files


def write_drawings_zip(dest: Path, pdfs: list[Path], *, exclude: Path | None = None) -> Path:
    """Zip drawing PDFs. Never include the transmittal form PDF."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    skip: set[str] = set()
    if exclude is not None and Path(exclude).is_file():
        skip.add(str(Path(exclude).resolve()).casefold())
    cover_beside = dest.with_suffix(".pdf")
    if cover_beside.is_file():
        skip.add(str(cover_beside.resolve()).casefold())
    written = 0
    used_names: set[str] = set()
    with ZipFile(dest, "w", compression=ZIP_DEFLATED) as zipped:
        for pdf in pdfs:
            resolved = Path(pdf).resolve()
            if not resolved.is_file():
                continue
            if str(resolved).casefold() in skip:
                continue
            arc = _unique_arcname(resolved.name, used_names)
            zipped.write(resolved, arcname=arc)
            written += 1
    if written <= 0:
        dest.unlink(missing_ok=True)
        raise LogError("No drawing PDFs to zip.")
    return dest.resolve()


def _unique_arcname(name: str, used: set[str]) -> str:
    key = name.casefold()
    if key not in used:
        used.add(key)
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while True:
        candidate = f"{stem}_{n}{suffix}"
        token = candidate.casefold()
        if token not in used:
            used.add(token)
            return candidate
        n += 1


def mail_attachments(cover_pdf: Path | None, pack_zip: Path | None) -> list[Path]:
    files: list[Path] = []
    if cover_pdf is not None and Path(cover_pdf).is_file():
        files.append(Path(cover_pdf).resolve())
    if pack_zip is not None and Path(pack_zip).is_file():
        files.append(Path(pack_zip).resolve())
    return files


def cover_pdf_for_book(book: Path, job: str, next_number: int, kind: str = CLIENT) -> tuple[str, Path | None]:
    folder = Path(book).parent
    next_id = f"{PREFIX[kind]}-{job}-{next_number}"
    next_pdf = folder / f"{next_id}.pdf"
    if next_pdf.is_file():
        return next_id, next_pdf
    if next_number > 1:
        prev_id = f"{PREFIX[kind]}-{job}-{next_number - 1}"
        prev_pdf = folder / f"{prev_id}.pdf"
        if prev_pdf.is_file():
            return prev_id, prev_pdf
    return next_id, None


def attachment_note(files: list[Path]) -> str:
    names = [path.name for path in files]
    if not names:
        return "No PDFs attached."
    return "Attached: " + "; ".join(names)


@dataclass(frozen=True)
class MailFacts:
    """Values the email wording can insert. Blank tokens are left out."""

    urgent: str = ""
    issued_for: str = ""
    client: str = ""
    location: str = ""
    tag: str = ""
    po: str = ""
    wo: str = ""
    moc: str = ""
    itp_note: str = ""


def split_wo_moc(text: str) -> tuple[str, str]:
    """The PEP stores Work Order and MOC in one cell. A slash splits them."""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    parts = [part.strip() for part in re.split(r"\s*/\s*", raw, maxsplit=1)]
    parts = [part for part in parts if part]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return raw, ""


def issued_for_text(rows: list[MatchedRow], kind: str) -> str:
    """Issued For on this pack: the letter's purpose list, once per distinct value."""
    if kind == "shop":
        field = "shop_purpose"
    elif kind == "field":
        field = "field_purpose"
    else:
        field = "purpose"
    seen: list[str] = []
    folded: set[str] = set()
    for row in rows:
        value = str(getattr(row.drawing, field, "") or "").strip()
        key = value.casefold()
        if not value or key in folded:
            continue
        folded.add(key)
        seen.append(value)
    return ", ".join(seen)


def value_or_na(saved: str, detected: str = "") -> str:
    """A typed value stays. N/A means not found yet, so a real detected value can replace it."""
    typed = (saved or "").strip()
    found = (detected or "").strip()
    if typed and typed.casefold() != "n/a":
        return typed
    if found and found.casefold() != "n/a":
        return found
    return "N/A"


def mail_facts(
    *,
    urgent: str = "",
    issued_for: str = "",
    client: str = "",
    location: str = "",
    tag: str = "",
    po: str = "",
    wo_moc: str = "",
) -> MailFacts:
    wo, moc = split_wo_moc(wo_moc)
    flag = "URGENT" if (urgent or "").strip().casefold() in {"same", "plus1", "urgent"} else ""
    return MailFacts(
        urgent=flag,
        issued_for=value_or_na(issued_for),
        client=value_or_na(client),
        location=value_or_na(location),
        tag=value_or_na(tag),
        po=value_or_na(po),
        wo=value_or_na(wo),
        moc=value_or_na(moc),
    )


def draft_subject(
    cover_id: str,
    job: str,
    *,
    template: str = "",
    facts: "MailFacts | None" = None,
) -> str:
    text = apply_mail_template(
        template,
        fallback=default_mail_subject(cover_id),
        cover=cover_id,
        job=job,
        project="",
        documents="",
        facts=facts,
    )
    return text.strip()


def documents_text(rows: list[MatchedRow]) -> str:
    lines: list[str] = []
    for row in rows:
        drawing = row.drawing
        rev = (row.pdf.rev if row.pdf else "") or drawing.outgoing_rev or "—"
        title = (drawing.title or "").strip()
        line = f"  {drawing.drawing_id or drawing.key}  Rev {rev}"
        if title:
            line = f"{line}  {title}"
        lines.append(line)
    return "\n".join(lines)


MAIL_KINDS = ("client", "shop", "field")
MAIL_MARKERS = (
    "{urgent}  {transmittal}  {cover}  {job}  {issued_for}  {project}  {documents}  {itp_note}\n"
    "{client}  {location}  {tag}  {po}  {wo}  {moc}"
)
MAIL_KIND_LABELS = (("client", "Client"), ("shop", "Shop"), ("field", "Field"))


def _mail_file() -> tuple[Path, dict]:
    from doccon.paths import mail_formats_path

    path = mail_formats_path()
    if not path.is_file():
        return path, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return path, {}
    return path, raw if isinstance(raw, dict) else {}


def _write_mail_file(path: Path, raw: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return path


def load_mail_formats() -> dict[str, tuple[str, str]]:
    """Subject and body overrides shared on Dropbox. Missing file means today's wording."""
    _path, raw = _mail_file()
    out: dict[str, tuple[str, str]] = {}
    for key in MAIL_KINDS:
        item = raw.get(key)
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").replace("\r\n", "\n")
        body = str(item.get("body") or "").replace("\r\n", "\n")
        if subject.strip() or body.strip():
            out[key] = (subject, body)
    return out


def save_mail_formats(formats: dict[str, tuple[str, str]]) -> Path:
    """Write the shared wording file next to the program. Does not touch this PC's settings."""
    path, raw = _mail_file()
    for key in MAIL_KINDS:
        subject, body = formats.get(key, ("", ""))
        subject = str(subject or "").replace("\r\n", "\n")
        body = str(body or "").replace("\r\n", "\n")
        if subject.strip() == default_mail_subject(key).strip():
            subject = ""
        if body.strip() == default_mail_body(key).strip():
            body = ""
        if subject.strip() or body.strip():
            raw[key] = {"subject": subject, "body": body}
        else:
            raw.pop(key, None)
    return _write_mail_file(path, raw)


def _address_tuple(text: str) -> tuple[str, ...]:
    from doccon.pep import email_line

    line = email_line(text)
    return tuple(part.strip() for part in line.split(";") if part.strip())


def _blank_permanent() -> dict[str, dict[str, tuple[str, ...]]]:
    return {kind: {"to": (), "cc": ()} for kind, _title in MAIL_KIND_LABELS}


def load_permanent() -> dict[str, dict[str, tuple[str, ...]]]:
    """Permanent TO and CC for Client, Shop, and Field. Shared file, not this PC."""
    from doccon.pep import email_line

    _path, raw = _mail_file()
    out = _blank_permanent()
    stored = raw.get("permanent")
    if isinstance(stored, dict):
        for kind in out:
            slot = stored.get(kind)
            if not isinstance(slot, dict):
                continue
            for side in ("to", "cc"):
                out[kind][side] = _address_tuple("; ".join(str(item) for item in slot.get(side) or []))
    if not out["client"]["cc"]:
        legacy_line = email_line("; ".join(str(item) for item in raw.get("cc_permanent") or []))
        if legacy_line:
            out["client"]["cc"] = _address_tuple(legacy_line)
        else:
            try:
                from doccon.settings import load_settings

                legacy = load_settings().cc_permanent
            except (OSError, TypeError, ValueError):
                legacy = ()
            if legacy and not isinstance(stored, dict) and not raw.get("cc_permanent"):
                out["client"]["cc"] = tuple(legacy)
                save_permanent({"client": {"to": "", "cc": "; ".join(legacy)}})
    return out


def permanent_line(kind: str, side: str) -> str:
    """One permanent list: kind is client, shop, or field; side is to or cc."""
    lists = load_permanent()
    key = mail_kind_key(kind)
    slot = lists.get(key) or {}
    which = "cc" if (side or "").strip().casefold() == "cc" else "to"
    return "; ".join(slot.get(which) or ())


def pick_address_lists(kind: str, side: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Permanent addresses for this box, then the shared address book, without duplicates."""
    standing = tuple(part.strip() for part in permanent_line(kind, side).split(";") if part.strip())
    seen = {part.casefold() for part in standing}
    saved: list[str] = []
    try:
        book = load_saved_addresses()
    except (OSError, TypeError, ValueError):
        book = ()
    for addr in book:
        key = addr.casefold()
        if not addr or key in seen:
            continue
        seen.add(key)
        saved.append(addr)
    return standing, tuple(saved)


def load_saved_addresses() -> tuple[str, ...]:
    """The shared TO/CC address book. A list already on this PC is copied in once."""
    from doccon.settings import normalize_saved_emails

    _path, raw = _mail_file()
    if "saved_addresses" in raw:
        return normalize_saved_emails(raw.get("saved_addresses"))
    try:
        from doccon.settings import load_settings

        legacy = load_settings().saved_emails
    except (OSError, TypeError, ValueError):
        legacy = ()
    if legacy:
        save_saved_addresses(legacy)
    return tuple(legacy)


def save_saved_addresses(values: object) -> Path:
    """Write the shared address book. Permanent lists and wording stay as they are."""
    from doccon.settings import normalize_saved_emails

    path, raw = _mail_file()
    raw["saved_addresses"] = list(normalize_saved_emails(values))
    return _write_mail_file(path, raw)


def save_permanent(values: dict[str, dict[str, str]]) -> Path:
    """Write permanent TO and CC for each transmittal into the shared wording file."""
    path, raw = _mail_file()
    stored: dict[str, dict[str, list[str]]] = {}
    for kind, _title in MAIL_KIND_LABELS:
        slot = values.get(kind) or {}
        stored[kind] = {
            "to": list(_address_tuple(str(slot.get("to") or ""))),
            "cc": list(_address_tuple(str(slot.get("cc") or ""))),
        }
    raw["permanent"] = stored
    raw["cc_permanent"] = list(stored["client"]["cc"])
    return _write_mail_file(path, raw)


def load_cc_permanent() -> tuple[str, ...]:
    """Permanent client CC. Shared file next to DocCon, not this PC's settings."""
    return load_permanent()["client"]["cc"]


def save_cc_permanent(text: str) -> Path:
    """Write the permanent client CC. Shop, Field, and the TO lists stay as they are."""
    current = {
        kind: {"to": "; ".join(slot["to"]), "cc": "; ".join(slot["cc"])}
        for kind, slot in load_permanent().items()
    }
    current["client"]["cc"] = text
    return save_permanent(current)


def mother_wording(kind: str) -> tuple[str, str]:
    """Settings wording for this transmittal. The program default is used when Settings has none."""
    stored = load_mail_formats().get(mail_kind_key(kind), ("", ""))
    subject = (stored[0] or "").strip() or default_mail_subject(kind)
    body = (stored[1] or "").strip() or default_mail_body(kind)
    return subject, body


def job_mail_override(kind: str, subject: str, body: str) -> tuple[str, str] | None:
    """A job copy only when the text differs from Settings. None means use Settings."""
    mother_subject, mother_body = mother_wording(kind)
    if subject.strip() == mother_subject and body.replace("\r\n", "\n").strip() == mother_body.strip():
        return None
    return subject.strip(), body.replace("\r\n", "\n")


def mail_kind_key(kind: str) -> str:
    token = (kind or "").strip().casefold()
    if token in {"shop", "st"} or token.startswith("st-"):
        return "shop"
    if token in {"field", "ft"} or token.startswith("ft-"):
        return "field"
    if token.startswith("st"):
        return "shop"
    if token.startswith("ft"):
        return "field"
    return "client"


def default_mail_subject(kind: str = "") -> str:
    if mail_kind_key(kind) == "client":
        return (
            "{urgent} Trans. # {transmittal} | ISSUED FOR {issued_for} | {client} | "
            "Loc: {location} | Ref. Tag: {tag} | PO#: {po} | WO#: {wo} | MOC#: {moc}"
        )
    return (
        "{urgent} Trans. # {transmittal} | {issued_for} | {client} | "
        "Loc: {location} | Ref. Tag: {tag}"
    )


ITP_SIGNOFF_NOTE = (
    "Rows 1.1, 1.2, 1.3, 1.4 under client column on ITP are to be signed off "
    "when approving/returning.  Thank you."
)


def pack_includes_itp(rows: list[MatchedRow]) -> bool:
    """True when a packed document number or title is an ITP."""
    for row in rows:
        drawing = row.drawing
        blob = f"{drawing.drawing_id} {drawing.title} {drawing.summary}"
        if re.search(r"(?<![A-Za-z])ITP(?![A-Za-z])", blob, re.IGNORECASE):
            return True
    return False


def default_mail_body(kind: str) -> str:
    key = mail_kind_key(kind)
    if key == "client":
        return (
            "Good Day,\n"
            "\n"
            "Please find transmittal and associated documents attached. "
            f"Please return all \"for approval\" documents to {DOC_CONTROL_FROM}.\n"
            "\n"
            "{itp_note}\n"
            "\n"
            "Kind Regards,\n"
        )
    if key == "shop":
        return (
            "Good Day,\n"
            "\n"
            "Please find transmittal attached and associated documents uploaded "
            "into 1.0 Current IFC Drawings folder.\n"
            "\n"
            "Kind Regards,\n"
        )
    return (
        "Good Day,\n"
        "\n"
        "Please find transmittal attached and associated documents in the job "
        "specific Field Construction folder.\n"
        "\n"
        "Kind Regards,\n"
    )


def apply_mail_template(
    template: str,
    *,
    fallback: str,
    cover: str,
    job: str,
    project: str,
    documents: str,
    facts: "MailFacts | None" = None,
) -> str:
    info = facts or MailFacts()
    mapping = {
        "cover": cover or "",
        "transmittal": cover or "",
        "job": job or "",
        "project": project or "",
        "documents": documents or "",
        "urgent": info.urgent,
        "issued_for": info.issued_for,
        "client": info.client,
        "location": info.location,
        "tag": info.tag,
        "po": info.po,
        "wo": info.wo,
        "moc": info.moc,
        "itp_note": info.itp_note,
    }
    text = template if (template or "").strip() else fallback
    kept: list[str] = []
    for line in text.splitlines():
        token = line.strip()
        marker = token[1:-1] if token.startswith("{") and token.endswith("}") and token.count("{") == 1 else ""
        if marker and marker not in mapping:
            marker = ""
        if marker and not mapping.get(marker, "").strip() and token == "{" + marker + "}":
            continue
        kept.append(line)
    text = "\n".join(kept)
    na_fields = {"issued_for", "client", "location", "tag", "po", "wo", "moc"}
    for key, value in mapping.items():
        shown = value_or_na(value) if key in na_fields else (value or "")
        text = text.replace("{" + key + "}", shown)
    cleaned: list[str] = []
    for line in text.splitlines():
        if line.startswith("  ") or line.startswith("\t"):
            cleaned.append(line.rstrip())
            continue
        cleaned.append(re.sub(r"[ \t]{2,}", " ", line).strip() if line.strip() else "")
    return "\n".join(cleaned)


def draft_body(
    *,
    cover_id: str,
    project: str,
    rows: list[MatchedRow],
    job: str = "",
    template: str = "",
    facts: "MailFacts | None" = None,
) -> str:
    kind = mail_kind_key(cover_id)
    note = ITP_SIGNOFF_NOTE if kind == "client" and pack_includes_itp(rows) else ""
    info = replace(facts or MailFacts(), itp_note=note)
    return apply_mail_template(
        template,
        fallback=default_mail_body(kind),
        cover=cover_id,
        job=job,
        project=project,
        documents=documents_text(rows),
        facts=info,
    ).rstrip() + "\n"


def pick_outlook_send_account(addresses: list[str], *, preferred: str = DOC_CONTROL_FROM) -> str:
    """Use doc.control when that Outlook account is on this PC; else the signed-in default."""
    want = (preferred or "").strip().casefold()
    if not want:
        return ""
    for addr in addresses:
        text = (addr or "").strip()
        if text.casefold() == want:
            return text
    return ""


def display_outlook_draft(
    *,
    to_line: str,
    cc_line: str,
    subject: str,
    body: str,
    attachments: list[Path],
    require_to: bool = True,
    send_account: str = DOC_CONTROL_FROM,
) -> None:
    if os.name != "nt":
        raise LogError("Outlook draft needs Windows Outlook.")
    to_line = normalize_recipients(to_line)
    if require_to and not to_line:
        raise LogError("TO is empty. Type recipients on the Cover pane.")
    payload = {
        "to": to_line,
        "cc": normalize_recipients(cc_line),
        "subject": subject,
        "body": body,
        "files": [str(Path(path).resolve()) for path in attachments],
        "send_account": (send_account or "").strip(),
    }
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-outlook-"))
    script_path = tmp_dir / "draft.ps1"
    payload_path = tmp_dir / "payload.json"
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        script_path.write_text(
            (
                "$ErrorActionPreference = 'Stop'\n"
                f"$payloadPath = {_ps_lit(str(payload_path))}\n"
                "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
                "$outlook = $null\n"
                "try {\n"
                "  $outlook = [Runtime.InteropServices.Marshal]::GetActiveObject('Outlook.Application')\n"
                "} catch {\n"
                "  $outlook = New-Object -ComObject Outlook.Application\n"
                "}\n"
                "$mail = $outlook.CreateItem(0)\n"
                "$preferred = [string]$p.send_account\n"
                "if ($preferred) {\n"
                "  $account = $null\n"
                "  foreach ($acc in @($outlook.Session.Accounts)) {\n"
                "    try { $smtp = [string]$acc.SmtpAddress } catch { $smtp = '' }\n"
                "    if ($smtp -and $smtp.ToLower() -eq $preferred.ToLower()) { $account = $acc; break }\n"
                "  }\n"
                "  if ($account -ne $null) { try { $mail.SendUsingAccount = $account } catch {} }\n"
                "}\n"
                "$mail.To = [string]$p.to\n"
                "if ($p.cc) { $mail.CC = [string]$p.cc }\n"
                "$mail.Subject = [string]$p.subject\n"
                "$mail.Body = [string]$p.body\n"
                "foreach ($file in @($p.files)) {\n"
                "  if (Test-Path -LiteralPath $file) { $mail.Attachments.Add($file) | Out-Null }\n"
                "}\n"
                "$mail.Display()\n"
            ),
            encoding="utf-8",
        )
        completed = hidden_run(
            powershell_hidden_argv(
                "powershell",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Outlook draft failed").strip()
            raise LogError(
                "Could not open an Outlook draft. Sign into Outlook on this PC, then try again.\n"
                f"{detail}"
            )
    except subprocess.TimeoutExpired as vis:
        raise LogError("Outlook took too long to open a draft. Is Outlook signed in?") from vis
    finally:
        try:
            for child in tmp_dir.glob("*"):
                child.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass
