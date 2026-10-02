# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Open an Outlook draft: transmittal PDF plus a zip of the drawing PDFs."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
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


def draft_subject(cover_id: str, job: str, *, template: str = "") -> str:
    text = apply_mail_template(
        template,
        fallback=default_mail_subject(),
        cover=cover_id,
        job=job,
        project="",
        documents="",
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
MAIL_MARKERS = "{cover}    {job}    {project}    {documents}"
MAIL_KIND_LABELS = (("client", "Client"), ("shop", "Shop"), ("field", "Field"))


def load_mail_formats() -> dict[str, tuple[str, str]]:
    """Subject and body overrides shared on Dropbox. Missing file means today's wording."""
    from doccon.paths import mail_formats_path

    path = mail_formats_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
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
    from doccon.paths import mail_formats_path

    payload: dict[str, dict[str, str]] = {}
    for key in MAIL_KINDS:
        subject, body = formats.get(key, ("", ""))
        subject = str(subject or "").replace("\r\n", "\n")
        body = str(body or "").replace("\r\n", "\n")
        if subject.strip() == default_mail_subject().strip():
            subject = ""
        if body.strip() == default_mail_body(key).strip():
            body = ""
        if subject.strip() or body.strip():
            payload[key] = {"subject": subject, "body": body}
    path = mail_formats_path()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


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


def default_mail_subject() -> str:
    return "{cover}  {job}"


def default_mail_body(kind: str) -> str:
    key = mail_kind_key(kind)
    label = {"shop": "shop transmittal", "field": "field transmittal"}.get(key, "client transmittal")
    closing = (
        "The transmittal form is attached."
        if key == "shop"
        else "The transmittal PDF is attached. Drawing PDFs are in the zip (not the transmittal form)."
    )
    return (
        f"Please find {label} {{cover}}.\n"
        "\n"
        "{project}\n"
        "\n"
        "Documents:\n"
        "{documents}\n"
        "\n"
        f"{closing}\n"
    )


def apply_mail_template(
    template: str,
    *,
    fallback: str,
    cover: str,
    job: str,
    project: str,
    documents: str,
) -> str:
    text = template if (template or "").strip() else fallback
    if not (project or "").strip():
        text = "\n".join(line for line in text.splitlines() if line.strip() != "{project}")
    return (
        text.replace("{cover}", cover or "")
        .replace("{job}", job or "")
        .replace("{project}", project or "")
        .replace("{documents}", documents or "")
    )


def draft_body(
    *,
    cover_id: str,
    project: str,
    rows: list[MatchedRow],
    job: str = "",
    template: str = "",
) -> str:
    kind = mail_kind_key(cover_id)
    return apply_mail_template(
        template,
        fallback=default_mail_body(kind),
        cover=cover_id,
        job=job,
        project=project,
        documents=documents_text(rows),
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
