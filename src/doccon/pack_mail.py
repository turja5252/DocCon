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


def draft_subject(cover_id: str, job: str) -> str:
    return f"{cover_id}  {job}"


def draft_body(*, cover_id: str, project: str, rows: list[MatchedRow]) -> str:
    token = (cover_id or "").split("-", 1)[0].upper()
    if token == "ST":
        label = "shop transmittal"
    elif token == "FT":
        label = "field transmittal"
    else:
        label = "client transmittal"
    lines = [
        f"Please find {label} {cover_id}.",
        "",
    ]
    if project:
        lines.extend([project, ""])
    lines.append("Documents:")
    for row in rows:
        drawing = row.drawing
        rev = (row.pdf.rev if row.pdf else "") or drawing.outgoing_rev or "—"
        title = (drawing.title or "").strip()
        line = f"  {drawing.drawing_id or drawing.key}  Rev {rev}"
        if title:
            line = f"{line}  {title}"
        lines.append(line)
    lines.extend(
        ["", "The transmittal PDF is attached. Drawing PDFs are in the zip (not the transmittal form).", ""]
    )
    return "\n".join(lines)


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
