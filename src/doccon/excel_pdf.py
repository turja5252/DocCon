# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Print one Excel sheet to PDF through Office, same idea as Databook import."""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path

from doccon.client_log import LogError
from doccon.kinds import CLIENT
from doccon.log_layout import layout_for

_EXPORT_TIMEOUT_S = 90


def export_sheet_pdf(
    workbook: Path,
    sheet_name: str,
    dest_pdf: Path,
    *,
    fit_pages_tall: int = 1,
) -> Path:
    if os.name != "nt":
        raise LogError("Client transmittal PDF needs Excel on Windows.")
    source = Path(workbook).resolve()
    dest = Path(dest_pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-ct-pdf-"))
    tmp_pdf = tmp_dir / (dest.stem + ".pdf")
    local_book = tmp_dir / source.name
    script_path = tmp_dir / "export.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    try:
        shutil.copy2(source, local_book)
        _unblock_file(local_book)
        _write_excel_script(
            script_path,
            local_book,
            sheet_name,
            tmp_pdf,
            pid_path,
            fail_path,
            fit_pages_tall=fit_pages_tall,
        )
        completed = _run_office_script(script_path, pid_path, timeout_s=_EXPORT_TIMEOUT_S)
        if completed.returncode != 0 or not tmp_pdf.is_file() or tmp_pdf.stat().st_size <= 0:
            detail = _office_error_text(
                completed, fail_path, fallback="Excel PDF export failed"
            )
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


def fill_eddi_form_and_export_pdf(workbook: Path, dest_pdf: Path, payload: dict) -> Path:
    """Fill the EDDI Project sheet through Excel (keeps VBA), save, print PDF.

    ``workbook`` must already be a local copy. Excel must not open a Dropbox path.
    """
    if os.name != "nt":
        raise LogError("EDDI snapshot needs Excel on Windows.")
    source = Path(workbook).resolve()
    dest = Path(dest_pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-eddi-"))
    tmp_pdf = tmp_dir / (dest.stem + ".pdf")
    script_path = tmp_dir / "eddi.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    payload_path = tmp_dir / "payload.json"
    body = {
        "path": str(source),
        "sheet": str(payload.get("sheet") or "Project"),
        "lock": _TEMPLATE_LOCK,
        "pdf": str(tmp_pdf),
        "stamp": str(payload.get("stamp") or ""),
        "inserts": list(payload.get("inserts") or []),
        "clear_rows": [int(row) for row in (payload.get("clear_rows") or [])],
        "fills": list(payload.get("fills") or []),
        "hide": [int(row) for row in (payload.get("hide") or [])],
        "unhide": [int(row) for row in (payload.get("unhide") or [])],
        "print_last": int(payload.get("print_last") or 1),
        "tables": list(payload.get("tables") or []),
        "merge_headers": [int(row) for row in (payload.get("merge_headers") or [])],
        "merge_ranges": [str(ref) for ref in (payload.get("merge_ranges") or [])],
        "drop_breaks": [int(row) for row in (payload.get("drop_breaks") or [])],
    }
    try:
        _unblock_file(source)
        payload_path.write_text(json.dumps(body), encoding="utf-8")
        _write_eddi_script(script_path, payload_path, pid_path, fail_path)
        completed = _run_office_script(script_path, pid_path, timeout_s=_FILE_TIMEOUT_S)
        if completed.returncode != 0:
            detail = _office_error_text(
                completed, fail_path, fallback="Excel EDDI update failed"
            )
            hint = ""
            if _looks_like_workbook_lock(detail):
                hint = " Close the EDDI if it is open, then try again."
            raise LogError(f"Could not update the EDDI snapshot in Excel.{hint}\n{detail}")
        if not tmp_pdf.is_file() or tmp_pdf.stat().st_size <= 0:
            raise LogError(
                "Updated the EDDI snapshot, but could not print Project to PDF. "
                "Close Excel if it is stuck, then Print that tab yourself."
            )
        if dest.exists():
            dest.unlink()
        shutil.move(str(tmp_pdf), str(dest))
        return dest
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_eddi_script(
    script_path: Path,
    payload_path: Path,
    pid_path: Path,
    fail_path: Path | None = None,
) -> None:
    fail = Path(fail_path) if fail_path else Path(str(pid_path) + ".err")
    script_path.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            f"$payloadPath = {_ps_lit(str(payload_path))}\n"
            f"$pidPath = {_ps_lit(str(pid_path))}\n"
            f"$failPath = {_ps_lit(str(fail))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_FAIL
            + "function Unlock-Book($book, $lock) {\n"
            "  if (-not $book.ProtectStructure -and -not $book.ProtectWindows) { return }\n"
            "  if ($lock) { try { $book.Unprotect($lock) } catch {} }\n"
            "  if ($book.ProtectStructure -or $book.ProtectWindows) {\n"
            "    try { $book.Unprotect([string]::Empty) } catch {}\n"
            "  }\n"
            "}\n"
            "function Unlock-Sheet($sheet, $lock) {\n"
            "  if (-not $sheet.ProtectContents) { return }\n"
            "  if ($lock) { try { $sheet.Unprotect($lock) } catch {} }\n"
            "  if ($sheet.ProtectContents) { try { $sheet.Unprotect([string]::Empty) } catch {} }\n"
            "}\n"
            "function Set-DocConCell($sheet, $row, $col, $raw) {\n"
            "  $text = [string]$raw\n"
            "  if (-not $text) { return }\n"
            "  if ($text -match '^\\d{4}-\\d{2}-\\d{2}$') {\n"
            "    $sheet.Cells.Item([int]$row, [int]$col).Value = [datetime]$text\n"
            "  } else {\n"
            "    $sheet.Cells.Item([int]$row, [int]$col).Value = $text\n"
            "  }\n"
            "}\n"
            "function Ensure-DocConMerge($sheet, $addr) {\n"
            "  $rng = $sheet.Range([string]$addr)\n"
            "  try { $rng.UnMerge() } catch {}\n"
            "  try { $rng.Merge() | Out-Null } catch {}\n"
            "  $rng.HorizontalAlignment = -4108\n"
            "  $rng.VerticalAlignment = -4108\n"
            "}\n"
            "try {\n"
            + _PS_START_EXCEL
            + "  try { Unblock-File -LiteralPath ([string]$p.path) } catch {}\n"
            "  $wb = $excel.Workbooks.Open([string]$p.path, 0, $false)\n"
            "  Unlock-Book $wb $p.lock\n"
            "  $ws = $wb.Worksheets.Item([string]$p.sheet)\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  if ($p.stamp) { $ws.Range('A2').Value = [string]$p.stamp }\n"
            "  foreach ($ins in @($p.inserts | Where-Object { $_ })) {\n"
            "    $count = [int]$ins.count\n"
            "    $at = [int]$ins.at\n"
            "    if ($count -le 0 -or $at -le 0) { continue }\n"
            "    $end = $at + $count - 1\n"
            "    $ws.Rows(\"${at}:${end}\").Insert(-4121, 0) | Out-Null\n"
            "  }\n"
            "  foreach ($tbl in @($p.tables | Where-Object { $_ })) {\n"
            "    try {\n"
            "      $lo = $ws.ListObjects.Item([string]$tbl.name)\n"
            "      $lo.Resize($ws.Range([string]$tbl.ref)) | Out-Null\n"
            "    } catch {}\n"
            "  }\n"
            "  foreach ($row in @($p.clear_rows | Where-Object { $_ })) {\n"
            "    $ws.Range(('A{0}:M{0}' -f [int]$row)).ClearContents() | Out-Null\n"
            "  }\n"
            "  foreach ($fill in @($p.fills | Where-Object { $_ })) {\n"
            "    $vals = @($fill.values)\n"
            "    for ($c = 1; $c -le 13; $c++) {\n"
            "      $raw = if ($c -le $vals.Count) { $vals[$c - 1] } else { '' }\n"
            "      Set-DocConCell $ws ([int]$fill.row) $c $raw\n"
            "    }\n"
            "  }\n"
            "  $shown = @{}\n"
            "  foreach ($row in @($p.unhide | Where-Object { $_ })) { $shown[[int]$row] = $true }\n"
            "  foreach ($row in @($p.hide | Where-Object { $_ })) {\n"
            "    $r = [int]$row\n"
            "    if (-not $shown.ContainsKey($r)) { $ws.Rows($r).Hidden = $true }\n"
            "  }\n"
            "  foreach ($row in @($p.unhide | Where-Object { $_ })) {\n"
            "    $ws.Rows([int]$row).Hidden = $false\n"
            "  }\n"
            "  foreach ($row in @($p.merge_headers | Where-Object { $_ })) {\n"
            "    $r = [int]$row\n"
            "    if ($r -le 0) { continue }\n"
            "    $addr = ('A{0}:M{0}' -f $r)\n"
            "    $color = $null\n"
            "    try { $color = $ws.Range(('A{0}' -f $r)).Interior.Color } catch {}\n"
            "    Ensure-DocConMerge $ws $addr\n"
            "    if ($null -ne $color) { try { $ws.Range($addr).Interior.Color = $color } catch {} }\n"
            "  }\n"
            "  foreach ($addr in @($p.merge_ranges | Where-Object { $_ })) {\n"
            "    Ensure-DocConMerge $ws ([string]$addr)\n"
            "  }\n"
            "  foreach ($row in @($p.drop_breaks | Where-Object { $_ })) {\n"
            "    $after = [int]$row\n"
            "    try { $ws.Rows($after).PageBreak = -4142 } catch {}\n"
            "    try { $ws.Rows(($after + 1)).PageBreak = -4142 } catch {}\n"
            "  }\n"
            "  try { $ws.PageSetup.Zoom = $false } catch {}\n"
            "  try { $ws.PageSetup.FitToPagesWide = 1 } catch {}\n"
            "  try { $ws.PageSetup.FitToPagesTall = 0 } catch {}\n"
            "  try { $ws.PageSetup.Orientation = 2 } catch {}\n"
            "  try { $ws.PageSetup.PaperSize = 1 } catch {}\n"
            "  $last = [int]$p.print_last\n"
            "  if ($last -lt 1) { $last = 1 }\n"
            "  try { $ws.PageSetup.PrintArea = ('A1:M{0}' -f $last) } catch {}\n"
            "  $wb.Save()\n"
            "  $saved = $true\n"
            "  if ($p.pdf) {\n"
            "    $ws.Select()\n"
            "    $ws.ExportAsFixedFormat(0, [string]$p.pdf)\n"
            "  }\n"
            + _ps_catch("Could not update the EDDI snapshot in Excel.")
            + "} finally {\n"
            "  if ($wb -ne $null) { try { $wb.Close($saved) } catch {} }\n"
            "  if ($ownedPid -gt 0 -and $excel -ne $null) { $excel.Quit() }\n"
            "  [GC]::Collect()\n"
            "  [GC]::WaitForPendingFinalizers()\n"
            "}\n"
        ),
        encoding="utf-8",
    )


def _ps_lit(value: str) -> str:
    return json.dumps(str(value))


_PS_WRITE_FAIL = (
    "function Write-DocConFail($step, $err) {\n"
    "  $lines = New-Object System.Collections.Generic.List[string]\n"
    "  if ($step) { $lines.Add([string]$step) }\n"
    "  if ($err -ne $null) {\n"
    "    try { if ($err.Exception.Message) { $lines.Add([string]$err.Exception.Message) } } catch {}\n"
    "    try {\n"
    "      $inner = $err.Exception.InnerException\n"
    "      if ($inner -and $inner.Message) { $lines.Add([string]$inner.Message) }\n"
    "    } catch {}\n"
    "    try { $lines.Add('HRESULT ' + ('{0:X8}' -f ($err.Exception.HResult))) } catch {}\n"
    "    try { if ($err.FullyQualifiedErrorId) { $lines.Add([string]$err.FullyQualifiedErrorId) } } catch {}\n"
    "    try { if ($err.ScriptStackTrace) { $lines.Add([string]$err.ScriptStackTrace) } } catch {}\n"
    "    try {\n"
    "      $dump = [string]$err.Exception\n"
    "      if ($dump -and $dump -ne [string]$err.Exception.Message) { $lines.Add($dump) }\n"
    "    } catch {}\n"
    "  }\n"
    "  $msg = [string]::Join([Environment]::NewLine, $lines)\n"
    "  if (-not $msg) { $msg = 'Excel failed.' }\n"
    "  try { [Console]::Error.WriteLine($msg) } catch {}\n"
    "  try { Set-Content -LiteralPath $failPath -Value $msg -Encoding UTF8 } catch {}\n"
    "}\n"
)

_PS_START_EXCEL = (
    "  $excel = New-Object -ComObject Excel.Application\n"
    "  Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object {\n"
    "    if (-not $before.ContainsKey($_.Id)) { $ownedPid = $_.Id }\n"
    "  }\n"
    "  if ($ownedPid -gt 0) { Set-Content -Path $pidPath -Value $ownedPid }\n"
    "  $excel.DisplayAlerts = $false\n"
    "  try { $excel.AskToUpdateLinks = $false } catch {}\n"
    "  if ($ownedPid -gt 0) {\n"
    "    $excel.Visible = $false\n"
    "    $excel.ScreenUpdating = $false\n"
    "  }\n"
)


def _ps_catch(step: str) -> str:
    return (
        "} catch {\n"
        f"  Write-DocConFail {_ps_lit(step)} $_\n"
        "  exit 1\n"
    )


def _office_error_text(
    completed: subprocess.CompletedProcess[str] | None,
    fail_path: Path,
    *,
    fallback: str,
) -> str:
    parts: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = (raw or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        parts.append(text)

    with contextlib.suppress(OSError):
        add(fail_path.read_text(encoding="utf-8-sig", errors="replace"))
    if completed is not None:
        add(completed.stderr or "")
        add(completed.stdout or "")
    return "\n".join(parts) if parts else fallback


def _looks_like_workbook_lock(detail: str) -> bool:
    low = (detail or "").casefold()
    return any(
        token in low
        for token in (
            "already open",
            "in use",
            "being used by another",
            "locked for editing",
            "cannot access the file",
        )
    )


def _transmittal_excel_error(detail: str) -> LogError:
    text = (detail or "").strip() or "Excel File Transmittal failed."
    hint = ""
    if _looks_like_workbook_lock(text):
        hint = "\nClose that workbook in Excel if it is open, then try again."
    return LogError(f"Could not write the transmittal in Excel.\n{text}{hint}")


def _unblock_file(path: Path) -> None:
    with contextlib.suppress(OSError):
        os.remove(f"{path}:Zone.Identifier")


def _write_excel_script(
    script_path: Path,
    source: Path,
    sheet_name: str,
    pdf_path: Path,
    pid_path: Path,
    fail_path: Path | None = None,
    *,
    fit_pages_tall: int = 1,
) -> None:
    fail = Path(fail_path) if fail_path else Path(str(pid_path) + ".err")
    tall = int(fit_pages_tall)
    script_path.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            f"$sourcePath = {_ps_lit(str(source.resolve()))}\n"
            f"$sheetName = {_ps_lit(sheet_name)}\n"
            f"$pdfPath = {_ps_lit(str(pdf_path))}\n"
            f"$pidPath = {_ps_lit(str(pid_path))}\n"
            f"$failPath = {_ps_lit(str(fail))}\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$ownedPid = 0\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_FAIL
            + "try {\n"
            + _PS_START_EXCEL
            + "  try { Unblock-File -LiteralPath $sourcePath } catch {}\n"
            "  $wb = $excel.Workbooks.Open($sourcePath, 0, $true)\n"
            "  $ws = $wb.Worksheets.Item($sheetName)\n"
            "  $ws.Select()\n"
            "  try { $ws.PageSetup.Zoom = $false } catch {}\n"
            "  try { $ws.PageSetup.FitToPagesWide = 1 } catch {}\n"
            f"  try {{ $ws.PageSetup.FitToPagesTall = {tall} }} catch {{}}\n"
            "  $ws.ExportAsFixedFormat(0, $pdfPath)\n"
            + _ps_catch("Could not print the Excel sheet to PDF.")
            + "} finally {\n"
            "  if ($wb -ne $null) { try { $wb.Close($false) } catch {} }\n"
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
    kind: str = CLIENT,
) -> None:
    """Copy TRANSMITTAL with Excel so the logo and macro buttons stay intact."""
    if os.name != "nt":
        raise LogError("Transmittal PDF / File on .xlsm needs Excel on Windows.")
    source = Path(path).resolve()
    layout = layout_for(kind)
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
        "client": getattr(cover, "client", None) or "",
        "site": getattr(cover, "site", None) or "",
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
        **layout.payload(),
    }
    tmp_dir = Path(tempfile.mkdtemp(prefix="elite-doccon-ct-file-"))
    script_path = tmp_dir / "file.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    payload_path = tmp_dir / "payload.json"
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        _write_file_script(script_path, payload_path, pid_path, fail_path)
        completed = _run_office_script(script_path, pid_path, timeout_s=_FILE_TIMEOUT_S)
        if completed.returncode != 0:
            raise _transmittal_excel_error(
                _office_error_text(
                    completed, fail_path, fallback="Excel File Transmittal failed."
                )
            )
    except LogError:
        raise
    except Exception as exc:
        raise LogError(f"Could not write the transmittal in Excel.\n{exc}") from exc
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_file_script(
    script_path: Path,
    payload_path: Path,
    pid_path: Path,
    fail_path: Path | None = None,
) -> None:
    fail = Path(fail_path) if fail_path else Path(str(pid_path) + ".err")
    script_path.write_text(
        (
            "$ErrorActionPreference = 'Stop'\n"
            f"$payloadPath = {_ps_lit(str(payload_path))}\n"
            f"$pidPath = {_ps_lit(str(pid_path))}\n"
            f"$failPath = {_ps_lit(str(fail))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$tpl = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_FAIL
            + "function Unlock-Book($book, $lock) {\n"
            "  if (-not $book.ProtectStructure -and -not $book.ProtectWindows) { return }\n"
            "  if ($lock) { try { $book.Unprotect($lock) } catch {} }\n"
            "  if ($book.ProtectStructure -or $book.ProtectWindows) {\n"
            "    try { $book.Unprotect([string]::Empty) } catch {}\n"
            "  }\n"
            "}\n"
            "function Unlock-Sheet($sheet, $lock) {\n"
            "  if (-not $sheet.ProtectContents) { return }\n"
            "  if ($lock) { try { $sheet.Unprotect($lock) } catch {} }\n"
            "  if ($sheet.ProtectContents) { try { $sheet.Unprotect([string]::Empty) } catch {} }\n"
            "}\n"
            "function Clear-Addr($sheet, $addr) {\n"
            "  $sheet.Range($addr).MergeArea.ClearContents()\n"
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
            + _PS_START_EXCEL
            + "  $wb = $excel.Workbooks.Open($p.path, 0, $false)\n"
            "  $protectBook = [bool]$wb.ProtectStructure\n"
            "  Unlock-Book $wb $p.lock\n"
            "  $ws = $wb.Worksheets.Item('TRANSMITTAL')\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  if ($p.template) {\n"
            "    try {\n"
            "      $tpl = $excel.Workbooks.Open($p.template, 0, $true)\n"
            "      $src = $tpl.Worksheets.Item('TRANSMITTAL')\n"
            "      Unlock-Sheet $src $p.lock\n"
            "      Restore-Art $src $ws $true\n"
            "      foreach ($sheet in @($wb.Worksheets)) {\n"
            "        if ($sheet.Name -match '^\\d+$') {\n"
            "          Unlock-Sheet $sheet $p.lock\n"
            "          Restore-Art $src $sheet $false\n"
            "        }\n"
            "      }\n"
            "      $tpl.Close($false)\n"
            "      $tpl = $null\n"
            "    } catch {\n"
            "      if ($tpl -ne $null) { try { $tpl.Close($false) } catch {} }\n"
            "      $tpl = $null\n"
            "    }\n"
            "  }\n"
            "  $ws.Range([string]$p.number_cell).Value = [int]$p.number\n"
            "  $ws.Range([string]$p.pages_cell).Value = [int]$p.pages\n"
            "  $ws.Range([string]$p.job_cell).Value = [string]$p.job\n"
            "  if ($p.from_cell) { $ws.Range([string]$p.from_cell).Value = [string]$p.from }\n"
            "  if ($p.to_cell -and $p.to) { $ws.Range([string]$p.to_cell).Value = [string]$p.to }\n"
            "  if ($p.cc_cell -and $p.cc) { $ws.Range([string]$p.cc_cell).Value = [string]$p.cc }\n"
            "  if ($p.project_cell -and $p.project) { $ws.Range([string]$p.project_cell).Value = [string]$p.project }\n"
            "  if ($p.customer_cell -and $p.client) { $ws.Range([string]$p.customer_cell).Value = [string]$p.client }\n"
            "  if ($p.site_cell -and $p.site) { $ws.Range([string]$p.site_cell).Value = [string]$p.site }\n"
            "  if ($p.issued_cell) { $ws.Range([string]$p.issued_cell).Value = [datetime]$p.issued }\n"
            "  if ($p.expected_cell) {\n"
            "    if ($p.expected_is_date) { $ws.Range([string]$p.expected_cell).Value = [datetime]$p.expected }\n"
            "    else { $ws.Range([string]$p.expected_cell).Value = [string]$p.expected }\n"
            "  }\n"
            "  $start = [int]$p.doc_start_row\n"
            "  $end = [int]$p.page3_last_row\n"
            "  $last = [int]$p.page1_last_row\n"
            "  if ([int]$p.pages -ge 2) { $last = [int]$p.page2_last_row }\n"
            "  if ([int]$p.pages -ge 3) { $last = [int]$p.page3_last_row }\n"
            "  $cols = @([int]$p.doc_no_col, [int]$p.rev_col, "
            "[int]$p.desc_col, [int]$p.status_col, [int]$p.notes_col)\n"
            "  for ($r = $start; $r -le $end; $r++) {\n"
            "    $ws.Rows($r).Hidden = ($r -gt $last)\n"
            "    foreach ($col in $cols) {\n"
            "      $ws.Cells.Item($r, $col).MergeArea.ClearContents()\n"
            "    }\n"
            "  }\n"
            "  $row = $start\n"
            "  foreach ($line in @($p.lines)) {\n"
            "    $ws.Cells.Item($row, [int]$p.doc_no_col).Value = [string]$line.document_no\n"
            "    $ws.Cells.Item($row, [int]$p.rev_col).Value = [string]$line.rev\n"
            "    $ws.Cells.Item($row, [int]$p.desc_col).Value = [string]$line.description\n"
            "    $ws.Cells.Item($row, [int]$p.status_col).Value = [string]$line.status\n"
            "    if ($line.notes) { $ws.Cells.Item($row, [int]$p.notes_col).Value = [string]$line.notes }\n"
            "    $row++\n"
            "  }\n"
            "  if ($p.hide_page2) { $ws.Rows([string]$p.hide_page2).EntireRow.Hidden = ([int]$p.pages -lt 2) }\n"
            "  if ($p.hide_page3) { $ws.Rows([string]$p.hide_page3).EntireRow.Hidden = ([int]$p.pages -lt 3) }\n"
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
            "    foreach ($addr in @($p.reset_cells)) { if ($addr) { Clear-Addr $ws $addr } }\n"
            "    for ($r = $start; $r -le $end; $r++) {\n"
            "      foreach ($col in $cols) {\n"
            "        $ws.Cells.Item($r, $col).MergeArea.ClearContents()\n"
            "      }\n"
            "    }\n"
            "    if ($p.reset_hide) { $ws.Rows([string]$p.reset_hide).EntireRow.Hidden = $true }\n"
            "    $ws.Range([string]$p.number_cell).Value = ([int]$p.number + 1)\n"
            "    $ws.Range([string]$p.pages_cell).Value = 1\n"
            "  }\n"
            "  try { $ws.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "  foreach ($sheet in @($wb.Worksheets)) {\n"
            "    if ($sheet.Name -match '^\\d+$') {\n"
            "      try { $sheet.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "    }\n"
            "  }\n"
            "  if ($protectBook) { try { $wb.Protect($p.lock, $true, $false) } catch {} }\n"
            "  $wb.Save()\n"
            "  $saved = $true\n"
            + _ps_catch("Could not file the transmittal workbook.")
            + "} finally {\n"
            "  if ($tpl -ne $null) { try { $tpl.Close($false) } catch {} }\n"
            "  if ($wb -ne $null) { try { $wb.Close($saved) } catch {} }\n"
            "  if ($ownedPid -gt 0 -and $excel -ne $null) { $excel.Quit() }\n"
            "  [GC]::Collect()\n"
            "  [GC]::WaitForPendingFinalizers()\n"
            "}\n"
        ),
        encoding="utf-8",
    )
