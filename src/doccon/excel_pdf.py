# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Print one Excel sheet to PDF through Office, same idea as Databook import."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path

from doccon.client_log import LogError

_EXPORT_TIMEOUT_S = 90


def export_sheet_pdf(workbook: Path, sheet_name: str, dest_pdf: Path) -> Path:
    if os.name != "nt":
        raise LogError("Client transmittal PDF needs Excel on Windows.")
    source = Path(workbook).resolve()
    dest = Path(dest_pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-ct-pdf-"))
    tmp_pdf = tmp_dir / (dest.stem + ".pdf")
    script_path = tmp_dir / "export.ps1"
    pid_path = tmp_dir / "office.pid"
    try:
        _write_excel_script(script_path, source, sheet_name, tmp_pdf, pid_path)
        completed = _run_office_script(script_path, pid_path, timeout_s=_EXPORT_TIMEOUT_S)
        if completed.returncode != 0 or not tmp_pdf.is_file() or tmp_pdf.stat().st_size <= 0:
            detail = (completed.stderr or completed.stdout or "Excel PDF export failed").strip()
            raise LogError(
                f"Filed the Excel tab, but could not print {sheet_name} to PDF. "
                f"Close Excel if it is stuck, then Print that tab yourself.\n{detail}"
            )
        if dest.exists():
            dest.unlink()
        shutil.move(str(tmp_pdf), str(dest))
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return dest.resolve()


def _ps_lit(value: str) -> str:
    return json.dumps(str(value))


def _write_excel_script(
    script_path: Path,
    source: Path,
    sheet_name: str,
    pdf_path: Path,
    pid_path: Path,
) -> None:
    script_path.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            f"$sourcePath = {_ps_lit(str(source.resolve()))}\n"
            f"$sheetName = {_ps_lit(sheet_name)}\n"
            f"$pdfPath = {_ps_lit(str(pdf_path))}\n"
            f"$pidPath = {_ps_lit(str(pid_path))}\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$ownedPid = 0\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            "try {\n"
            "  $excel = New-Object -ComObject Excel.Application\n"
            "  Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object {\n"
            "    if (-not $before.ContainsKey($_.Id)) { $ownedPid = $_.Id }\n"
            "  }\n"
            "  if ($ownedPid -gt 0) { Set-Content -Path $pidPath -Value $ownedPid }\n"
            "  $excel.Visible = $false\n"
            "  $excel.DisplayAlerts = $false\n"
            "  $excel.Interactive = $false\n"
            "  $excel.ScreenUpdating = $false\n"
            "  $wb = $excel.Workbooks.Open($sourcePath, 0, $true)\n"
            "  $ws = $wb.Worksheets.Item($sheetName)\n"
            "  $ws.Select()\n"
            "  try { $ws.PageSetup.Zoom = $false } catch {}\n"
            "  try { $ws.PageSetup.FitToPagesWide = 1 } catch {}\n"
            "  $ws.ExportAsFixedFormat(0, $pdfPath)\n"
            "} finally {\n"
            "  if ($wb -ne $null) { $wb.Close($false) }\n"
            "  if ($ownedPid -gt 0 -and $excel -ne $null) { $excel.Quit() }\n"
            "  [GC]::Collect()\n"
            "  [GC]::WaitForPendingFinalizers()\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def _read_pid_file(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(text) if text else 0
    except (OSError, ValueError):
        return 0


def _kill_process_tree(pid: int) -> None:
    if pid <= 0 or os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
        check=False,
    )


def _run_office_script(script_path: Path, pid_path: Path, *, timeout_s: int) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-STA",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc.pid)
        _kill_process_tree(_read_pid_file(pid_path))
        try:
            proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise LogError("Excel took too long. Close Excel if it is stuck.") from None
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


_FILE_TIMEOUT_S = 120
# Same Protect password the CT VBA uses in Unprotect. Not an API token.
_TEMPLATE_LOCK = "redshirt"


def file_client_with_excel(
    path: Path,
    *,
    job: str,
    number: int,
    pages: int,
    lines: list,
    issued,
    expected_return,
    cover,
    template: Path | None,
    archive: bool = True,
) -> None:
    """Copy TRANSMITTAL with Excel so the logo and macro buttons stay intact."""
    if os.name != "nt":
        raise LogError("Client transmittal File on .xlsm needs Excel on Windows.")
    source = Path(path).resolve()
    expected = expected_return
    expected_is_date = False
    if expected is None or expected == "":
        expected_text = "N/A"
    elif isinstance(expected, datetime):
        expected_text = expected.date().isoformat()
        expected_is_date = True
    elif isinstance(expected, date):
        expected_text = expected.isoformat()
        expected_is_date = True
    else:
        expected_text = str(expected)
    payload = {
        "path": str(source),
        "template": str(Path(template).resolve()) if template and Path(template).is_file() else "",
        "lock": _TEMPLATE_LOCK,
        "job": job,
        "number": int(number),
        "pages": int(pages),
        "from": getattr(cover, "from_address", None) or "doc.control@eliteintegrityservices.com",
        "to": getattr(cover, "to_line", None) or "",
        "cc": getattr(cover, "cc_line", None) or "",
        "project": getattr(cover, "project_description", None) or "",
        "issued": issued.isoformat() if hasattr(issued, "isoformat") else str(issued),
        "expected": expected_text,
        "expected_is_date": expected_is_date,
        "archive": bool(archive),
        "lines": [
            {
                "document_no": line.document_no,
                "rev": line.rev,
                "description": line.description,
                "status": line.status,
                "notes": line.notes or "",
            }
            for line in lines
        ],
    }
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-ct-file-"))
    script_path = tmp_dir / "file.ps1"
    pid_path = tmp_dir / "office.pid"
    payload_path = tmp_dir / "payload.json"
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        _write_file_script(script_path, payload_path, pid_path)
        completed = _run_office_script(script_path, pid_path, timeout_s=_FILE_TIMEOUT_S)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Excel File Transmittal failed").strip()
            raise LogError(
                "Could not write the client transmittal in Excel. "
                "Close the CT workbook if it is open, then try again.\n"
                f"{detail}"
            )
    except LogError:
        raise
    except Exception as exc:
        raise LogError(f"Could not write the client transmittal in Excel.\n{exc}") from exc
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_file_script(script_path: Path, payload_path: Path, pid_path: Path) -> None:
    script_path.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            f"$payloadPath = {_ps_lit(str(payload_path))}\n"
            f"$pidPath = {_ps_lit(str(pid_path))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$tpl = $null\n"
            "$ownedPid = 0\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            "function Unlock-Book($book, $lock) {\n"
            "  if (-not $book.ProtectStructure -and -not $book.ProtectWindows) { return }\n"
            "  if ($lock) { try { $book.Unprotect($lock) } catch {} }\n"
            "  if ($book.ProtectStructure -or $book.ProtectWindows) { try { $book.Unprotect([string]::Empty) } catch {} }\n"
            "}\n"
            "function Unlock-Sheet($sheet, $lock) {\n"
            "  if (-not $sheet.ProtectContents) { return }\n"
            "  if ($lock) { try { $sheet.Unprotect($lock) } catch {} }\n"
            "  if ($sheet.ProtectContents) { try { $sheet.Unprotect([string]::Empty) } catch {} }\n"
            "}\n"
            "function Copy-Shape($srcShape, $dstSheet) {\n"
            "  $top = $srcShape.Top; $left = $srcShape.Left; $width = $srcShape.Width; $height = $srcShape.Height\n"
            "  $srcShape.Copy() | Out-Null\n"
            "  $dstSheet.Activate()\n"
            "  $dstSheet.Paste()\n"
            "  $new = $dstSheet.Shapes.Item($dstSheet.Shapes.Count)\n"
            "  $new.Top = $top; $new.Left = $left; $new.Width = $width; $new.Height = $height\n"
            "}\n"
            "function Get-Action($sh) {\n"
            "  try { return [string]$sh.OnAction } catch { return '' }\n"
            "}\n"
            "function Restore-Art($srcWs, $dstWs, $buttons) {\n"
            "  $hasPic = $false\n"
            "  $hasBtn = $false\n"
            "  foreach ($sh in @($dstWs.Shapes)) {\n"
            "    try { if ($sh.Type -eq 13) { $hasPic = $true } } catch {}\n"
            "    $act = Get-Action $sh\n"
            "    if ($act -match 'INSERT_PG' -or $act -match 'counter') { $hasBtn = $true }\n"
            "  }\n"
            "  foreach ($sh in @($srcWs.Shapes)) {\n"
            "    $act = Get-Action $sh\n"
            "    $isBtn = ($act -match 'INSERT_PG' -or $act -match 'counter')\n"
            "    $isPic = $false\n"
            "    try { if ($sh.Type -eq 13) { $isPic = $true } } catch {}\n"
            "    if ($isPic -and -not $hasPic) { Copy-Shape $sh $dstWs; $hasPic = $true; continue }\n"
            "    if ($buttons -and $isBtn -and -not $hasBtn) { Copy-Shape $sh $dstWs }\n"
            "  }\n"
            "}\n"
            "try {\n"
            "  $excel = New-Object -ComObject Excel.Application\n"
            "  Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object {\n"
            "    if (-not $before.ContainsKey($_.Id)) { $ownedPid = $_.Id }\n"
            "  }\n"
            "  if ($ownedPid -gt 0) { Set-Content -Path $pidPath -Value $ownedPid }\n"
            "  $excel.Visible = $false\n"
            "  $excel.DisplayAlerts = $false\n"
            "  $excel.Interactive = $false\n"
            "  $excel.ScreenUpdating = $false\n"
            "  $excel.AskToUpdateLinks = $false\n"
            "  $wb = $excel.Workbooks.Open($p.path, 0, $false)\n"
            "  $protectBook = [bool]$wb.ProtectStructure\n"
            "  Unlock-Book $wb $p.lock\n"
            "  $ws = $wb.Worksheets.Item('TRANSMITTAL')\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  if ($p.template) {\n"
            "    $tpl = $excel.Workbooks.Open($p.template, 0, $true)\n"
            "    $src = $tpl.Worksheets.Item('TRANSMITTAL')\n"
            "    Unlock-Sheet $src $p.lock\n"
            "    Restore-Art $src $ws $true\n"
            "    foreach ($sheet in @($wb.Worksheets)) {\n"
            "      if ($sheet.Name -match '^\\d+$') {\n"
            "        Unlock-Sheet $sheet $p.lock\n"
            "        Restore-Art $src $sheet $false\n"
            "      }\n"
            "    }\n"
            "    $tpl.Close($false)\n"
            "    $tpl = $null\n"
            "  }\n"
            "  $ws.Range('A2').Value = [int]$p.number\n"
            "  $ws.Range('A3').Value = [int]$p.pages\n"
            "  $ws.Range('A12').Value = [string]$p.job\n"
            "  $ws.Range('C4').Value = [string]$p.from\n"
            "  if ($p.to) { $ws.Range('C6').Value = [string]$p.to }\n"
            "  if ($p.cc) { $ws.Range('C8').Value = [string]$p.cc }\n"
            "  if ($p.project) { $ws.Range('A10').Value = [string]$p.project }\n"
            "  $ws.Range('C12').Value = [datetime]$p.issued\n"
            "  if ($p.expected_is_date) { $ws.Range('D12').Value = [datetime]$p.expected }\n"
            "  else { $ws.Range('D12').Value = [string]$p.expected }\n"
            "  $ws.Range('A15:E94').ClearContents()\n"
            "  $row = 15\n"
            "  foreach ($line in @($p.lines)) {\n"
            "    $ws.Cells.Item($row, 1).Value = [string]$line.document_no\n"
            "    $ws.Cells.Item($row, 2).Value = [string]$line.rev\n"
            "    $ws.Cells.Item($row, 3).Value = [string]$line.description\n"
            "    $ws.Cells.Item($row, 4).Value = [string]$line.status\n"
            "    if ($line.notes) { $ws.Cells.Item($row, 5).Value = [string]$line.notes }\n"
            "    $row++\n"
            "  }\n"
            "  $ws.Rows('33:62').EntireRow.Hidden = ([int]$p.pages -lt 2)\n"
            "  $ws.Rows('63:94').EntireRow.Hidden = ([int]$p.pages -lt 3)\n"
            "  if ($p.archive) {\n"
            "    $ws.Copy([Type]::Missing, $wb.Worksheets.Item(1))\n"
            "    $copy = $excel.ActiveSheet\n"
            "    $copy.Name = [string]$p.number\n"
            "    foreach ($sh in @($copy.Shapes)) {\n"
            "      $act = Get-Action $sh\n"
            "      if ($act -match 'INSERT_PG' -or $act -match '(?i)counter') { $sh.Delete() }\n"
            "    }\n"
            "    try { $copy.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "    $ws.Activate()\n"
            "    $ws.Range('C12').ClearContents()\n"
            "    $ws.Range('D12').ClearContents()\n"
            "    $ws.Range('E12').ClearContents()\n"
            "    $ws.Range('A15:E94').ClearContents()\n"
            "    $ws.Range('A96:E96').ClearContents()\n"
            "    $ws.Rows('33:94').EntireRow.Hidden = $true\n"
            "    $ws.Range('A2').Value = ([int]$p.number + 1)\n"
            "    $ws.Range('A3').Value = 1\n"
            "  }\n"
            "  try { $ws.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "  foreach ($sheet in @($wb.Worksheets)) {\n"
            "    if ($sheet.Name -match '^\\d+$') {\n"
            "      try { $sheet.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "    }\n"
            "  }\n"
            "  if ($protectBook) { try { $wb.Protect($p.lock, $true, $false) } catch {} }\n"
            "  $wb.Save()\n"
            "} finally {\n"
            "  if ($tpl -ne $null) { try { $tpl.Close($false) } catch {} }\n"
            "  if ($wb -ne $null) { try { $wb.Close($true) } catch {} }\n"
            "  if ($ownedPid -gt 0 -and $excel -ne $null) { $excel.Quit() }\n"
            "  [GC]::Collect()\n"
            "  [GC]::WaitForPendingFinalizers()\n"
            "}\n"
        ),
        encoding="utf-8",
    )
