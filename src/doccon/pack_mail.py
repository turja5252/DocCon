# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Zip the client pack and open an Outlook draft from the signed-in account."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

from doccon.client_log import LogError
from doccon.excel_pdf import _ps_lit
from doccon.kinds import PREFIX, CLIENT
from doccon.match import MatchedRow
from doccon.pep import email_line


def normalize_recipients(text: str) -> str:
    return email_line(text)


def pack_files(rows: list[MatchedRow], cover_pdf: Path | None) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    if cover_pdf is not None and cover_pdf.is_file():
        files.append(cover_pdf.resolve())
        seen.add(str(cover_pdf.resolve()).casefold())
    for row in rows:
        if row.pdf is None or not row.pdf.path.is_file():
            continue
        resolved = row.pdf.path.resolve()
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        files.append(resolved)
    return files


def cover_pdf_for_book(book: Path, job: str, next_number: int) -> tuple[str, Path | None]:
    folder = Path(book).parent
    next_id = f"{PREFIX[CLIENT]}-{job}-{next_number}"
    next_pdf = folder / f"{next_id}.pdf"
    if next_pdf.is_file():
        return next_id, next_pdf
    if next_number > 1:
        prev_id = f"{PREFIX[CLIENT]}-{job}-{next_number - 1}"
        prev_pdf = folder / f"{prev_id}.pdf"
        if prev_pdf.is_file():
            return prev_id, prev_pdf
    return next_id, None


def write_pack_zip(dest: Path, files: list[Path]) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in files:
            zipped.write(path, arcname=path.name)
    return dest.resolve()


def draft_subject(cover_id: str, job: str) -> str:
    return f"{cover_id}  {job}"


def draft_body(*, cover_id: str, project: str, rows: list[MatchedRow], zip_name: str) -> str:
    lines = [
        f"Please find client transmittal {cover_id}.",
        "",
    ]
    if project:
        lines.extend([project, ""])
    lines.append("Documents:")
    for row in rows:
        drawing = row.drawing
        rev = (row.pdf.rev if row.pdf else "") or drawing.outgoing_rev or "—"
        title = drawing.title or drawing.summary
        lines.append(f"  {drawing.drawing_id or drawing.key}  Rev {rev}  {title}")
    lines.extend(["", f"Pack saved as {zip_name}.", ""])
    return "\n".join(lines)


def display_outlook_draft(
    *,
    to_line: str,
    cc_line: str,
    subject: str,
    body: str,
    attachments: list[Path],
) -> None:
    if os.name != "nt":
        raise LogError("Outlook draft needs Windows Outlook.")
    to_line = normalize_recipients(to_line)
    if not to_line:
        raise LogError("TO is empty. Type recipients on the Cover pane.")
    payload = {
        "to": to_line,
        "cc": normalize_recipients(cc_line),
        "subject": subject,
        "body": body,
        "files": [str(Path(path).resolve()) for path in attachments],
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
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
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
