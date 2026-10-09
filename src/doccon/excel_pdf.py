# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Print one Excel sheet to PDF through Office, same idea as Databook import."""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar

from doccon.client_log import LogError
from doccon.diag import describe_path, ingest_hop_file, log, log_runtime, redact, with_log_details
from doccon.kinds import CLIENT
from doccon.log_layout import layout_for
from doccon.winproc import (
    excel_pids,
    hidden_popen_kwargs,
    hidden_run,
    kill_pid_tree,
    path_looks_32bit_powershell,
    powershell_hidden_argv,
)

_EXPORT_TIMEOUT_S = 90
_FILE_TIMEOUT_S = 120
_OPEN_ATTEMPTS = 3
_OPEN_BACKOFF_S = (0.4, 1.0, 2.0)
# Same Protect password the CT VBA uses in Unprotect. Not an API token.
_TEMPLATE_LOCK = "redshirt"

EXCEL_NOT_INSTALLED = (
    "DocCon could not start desktop Excel on this PC. "
    "Install or repair desktop Excel (not Microsoft 365 in a browser), then try again."
)
EXCEL_OPEN_FAILED = (
    "DocCon could not open the workbook in Excel. "
    "Close that file if it is open, wait for Dropbox to finish syncing, then try again."
)
EXCEL_PRINT_FAILED = (
    "Wrote the workbook, but could not print the PDF. "
    "Close that PDF if it is open in a reader, then try again."
)
EXCEL_TIMEOUT = (
    "Excel took too long. Close Excel if it is stuck, finish any Excel sign-in or repair dialog, then try again."
)
EXCEL_PDF_LOCKED = (
    "Wrote the workbook, but the PDF is open in another program. Close that PDF, then try again."
)

T = TypeVar("T")


class ExcelPrintError(LogError):
    """Workbook was saved; PDF export or copy failed."""


def doccon_temp_dir(prefix: str = "run-") -> Path:
    """A this-PC folder under %TEMP%\\DocCon. Excel must not open a Dropbox path."""
    root = Path(os.environ.get("TEMP") or tempfile.gettempdir()) / "DocCon"
    root.mkdir(parents=True, exist_ok=True)
    token = prefix if prefix.endswith("-") else f"{prefix}-"
    return Path(tempfile.mkdtemp(prefix=token, dir=str(root)))


def copy_workbook_local(source: Path, dest_dir: Path | None = None) -> Path:
    """Copy a Dropbox workbook to %TEMP%\\DocCon and clear the download mark."""
    src = Path(source)
    folder = dest_dir if dest_dir is not None else doccon_temp_dir("book-")
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name
    log("INFO", "copy", f"Copied {describe_path(src)} -> {describe_path(dest)}")
    shutil.copy2(src, dest)
    _unblock_file(dest)
    return dest


def is_retryable_excel_open(exc: object) -> bool:
    text = _exception_text(exc).casefold()
    return any(
        token in text
        for token in (
            "cannot access",
            "in use",
            "being used by another",
            "locked for editing",
            "rpc",
            "remote procedure",
            "rejected by callee",
            "800706ba",
            "800706be",
            "80010105",
            "80010108",
            "80010001",
            "8001010a",
            "sharing violation",
            "winerror 32",
            "error 32",
        )
    )


def retry_excel_open(
    opener: Callable[[int], T],
    *,
    attempts: int = _OPEN_ATTEMPTS,
    sleep: Callable[[float], None] | None = None,
) -> T:
    """Call opener(attempt_index). Retry 2–3 times on cannot-access / RPC / file in use."""
    pause = sleep if sleep is not None else time.sleep
    last: BaseException | None = None
    total = max(1, int(attempts))
    for attempt in range(total):
        log("INFO", "open", f"Workbooks.Open attempt {attempt + 1} of {total}")
        try:
            return opener(attempt)
        except Exception as exc:
            last = exc
            log("ERROR", "open", f"Workbooks.Open attempt {attempt + 1} failed {redact(_exception_text(exc))}")
            if attempt >= total - 1 or not is_retryable_excel_open(exc):
                break
            pause(_OPEN_BACKOFF_S[min(attempt, len(_OPEN_BACKOFF_S) - 1)])
    assert last is not None
    if isinstance(last, LogError):
        raise last
    raise LogError(operator_excel_message(_exception_text(last), stage="open")) from None


def operator_excel_message(detail: str, *, stage: str = "") -> str:
    """Sarah-facing Excel text. No Python traceback, no PowerShell stack."""
    text = _sanitize_office_text(detail)
    mapped = (stage or _fail_stage(text)).casefold()
    if mapped == "start" or _looks_like_com_start_failure(text):
        body = EXCEL_NOT_INSTALLED
    elif mapped == "print" or _looks_like_print_failure(text):
        body = EXCEL_PDF_LOCKED if _is_sharing_text(text) else EXCEL_PRINT_FAILED
    elif mapped == "open" or _looks_like_open_failure(text):
        body = EXCEL_OPEN_FAILED
    elif mapped == "file":
        body = str(_transmittal_excel_error(text))
    elif mapped == "fill":
        hint = ""
        if _looks_like_workbook_lock(text):
            hint = " Close the EDDI if it is open, then try again."
        extra = _operator_extra_line(text)
        body = f"Could not update the EDDI snapshot in Excel.{hint}"
        if extra:
            body = f"{body}\n{extra}"
    else:
        extra = _operator_extra_line(text)
        body = extra if extra else "Excel failed."
    return with_log_details(body)


def place_file(source: Path, dest: Path, *, unique_if_locked: bool = False) -> Path:
    """Move or copy onto dest. If locked and unique_if_locked, use dest-2, dest-3, …"""
    src = Path(source)
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if target.exists():
            target.unlink()
        try:
            shutil.move(str(src), str(target))
        except OSError:
            shutil.copy2(src, target)
            with contextlib.suppress(OSError):
                src.unlink()
        return target.resolve()
    except OSError as exc:
        if _is_sharing_violation(exc):
            log("ERROR", "place_file", f"WinError 32 {describe_path(target)}")
        if not _is_sharing_violation(exc):
            raise
        if not unique_if_locked:
            raise
        alt = _unique_sibling(target)
        shutil.copy2(src, alt)
        with contextlib.suppress(OSError):
            src.unlink()
        return alt.resolve()


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
    tmp_dir = doccon_temp_dir("ct-pdf-")
    tmp_pdf = tmp_dir / (dest.stem + ".pdf")
    script_path = tmp_dir / "export.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    log_runtime()
    log("INFO", "export_pdf", f"begin sheet={sheet_name} {describe_path(source)}")
    try:
        local_book = copy_workbook_local(source, tmp_dir)
        log("INFO", "open", f"Workbooks.Open attempt file={describe_path(local_book)}")
        _write_excel_script(
            script_path,
            local_book,
            sheet_name,
            tmp_pdf,
            pid_path,
            fail_path,
            fit_pages_tall=fit_pages_tall,
        )
        completed = _run_office_script(
            script_path, pid_path, timeout_s=_EXPORT_TIMEOUT_S, fail_path=fail_path
        )
        if completed.returncode != 0 or not tmp_pdf.is_file() or tmp_pdf.stat().st_size <= 0:
            detail = _office_error_text(
                completed, fail_path, fallback="Excel PDF export failed"
            )
            log("ERROR", _fail_stage(detail) or "print", redact(detail))
            raise LogError(
                operator_excel_message(detail, stage=_fail_stage(detail) or "print")
            )
        try:
            return place_file(tmp_pdf, dest, unique_if_locked=False)
        except OSError as exc:
            if _is_sharing_violation(exc):
                raise LogError(with_log_details(EXCEL_PDF_LOCKED)) from None
            raise
    except LogError:
        raise
    except Exception as exc:
        raise LogError(operator_excel_message(_exception_text(exc), stage="print")) from None
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)


def fill_eddi_form_and_export_pdf(workbook: Path, dest_pdf: Path, payload: dict) -> Path:
    """Fill the EDDI Project sheet through Excel (keeps VBA), save, print PDF.

    ``workbook`` must already be a local copy. Excel must not open a Dropbox path.
    """
    if os.name != "nt":
        raise LogError("EDDI snapshot needs Excel on Windows.")
    source = Path(workbook).resolve()
    dest = Path(dest_pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = doccon_temp_dir("eddi-")
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
        "column_inserts": [int(col) for col in (payload.get("column_inserts") or [])],
        "header_cells": list(payload.get("header_cells") or []),
        "item_cols": int(payload.get("item_cols") or 15),
        "group_last_rows": [int(row) for row in (payload.get("group_last_rows") or [])],
        "shop_validation": str(payload.get("shop_validation") or ""),
        "field_validation": str(payload.get("field_validation") or ""),
        "shop_list": str(payload.get("shop_list") or "IFC,IFI,IFU,Purchasing Only"),
        "field_list": str(payload.get("field_list") or "IFC,IFI"),
        "shop_purpose_col": int(payload.get("shop_purpose_col") or 11),
        "field_purpose_col": int(payload.get("field_purpose_col") or 14),
    }
    log_runtime()
    log("INFO", "eddi", f"begin sheet={body['sheet']} {describe_path(source)}")
    try:
        _unblock_file(source)
        payload_path.write_text(json.dumps(body), encoding="utf-8")
        log("INFO", "open", f"Workbooks.Open attempt file={describe_path(source)}")
        _write_eddi_script(script_path, payload_path, pid_path, fail_path)
        completed = _run_office_script(
            script_path, pid_path, timeout_s=_FILE_TIMEOUT_S, fail_path=fail_path
        )
        if completed.returncode != 0:
            detail = _office_error_text(
                completed, fail_path, fallback="Excel EDDI update failed"
            )
            log("ERROR", _fail_stage(detail) or "fill", redact(detail))
            stage = _fail_stage(detail)
            if completed.returncode == 2 or stage == "print":
                raise ExcelPrintError(operator_excel_message(detail, stage="print"))
            raise LogError(operator_excel_message(detail, stage=stage or "fill"))
        if not tmp_pdf.is_file() or tmp_pdf.stat().st_size <= 0:
            raise ExcelPrintError(with_log_details(EXCEL_PRINT_FAILED))
        try:
            return place_file(tmp_pdf, dest, unique_if_locked=True)
        except OSError as exc:
            if _is_sharing_violation(exc):
                raise ExcelPrintError(with_log_details(EXCEL_PDF_LOCKED)) from None
            raise
    except (LogError, ExcelPrintError):
        raise
    except Exception as exc:
        raise LogError(operator_excel_message(_exception_text(exc), stage="fill")) from None
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
            f"$diagPath = {_ps_lit(str(fail.with_suffix('.hops')))}\n"
            f"$stepPath = {_ps_lit(str(fail.with_suffix('.step')))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$stage = 'start'\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_HOP
            + _PS_WRITE_FAIL
            + _PS_OPEN_BOOK
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
            + "  $stage = 'open'\n"
            "  Write-DocConHop 'INFO' 'unblock' 'Unblock-File'\n"
            "  try { Unblock-File -LiteralPath ([string]$p.path) } catch {\n"
            "    Write-DocConHop 'WARN' 'unblock' ([string]$_.Exception.Message)\n"
            "  }\n"
            "  $wb = Open-DocConBook $excel ([string]$p.path) $false\n"
            "  $stage = 'fill'\n"
            "  Unlock-Book $wb $p.lock\n"
            "  Write-DocConHop 'INFO' 'sheet' ('sheet=' + [string]$p.sheet)\n"
            "  $ws = $wb.Worksheets.Item([string]$p.sheet)\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  if ($p.stamp) { $ws.Range('A2').Value = [string]$p.stamp }\n"
            "  $lastCol = [int]$p.item_cols\n"
            "  if ($lastCol -lt 1) { $lastCol = 15 }\n"
            "  $endCol = [string]([char](64 + $lastCol))\n"
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
            "    $ws.Range(('A{0}:{1}{0}' -f [int]$row, $endCol)).ClearContents() | Out-Null\n"
            "  }\n"
            "  foreach ($fill in @($p.fills | Where-Object { $_ })) {\n"
            "    $vals = @($fill.values)\n"
            "    for ($c = 1; $c -le $lastCol; $c++) {\n"
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
            "  foreach ($fill in @($p.fills | Where-Object { $_ })) {\n"
            "    $vals = @($fill.values)\n"
            "    $shopCol = [int]$p.shop_purpose_col\n"
            "    $fieldCol = [int]$p.field_purpose_col\n"
            "    $shopText = if ($shopCol -gt 0 -and $vals.Count -ge $shopCol) { [string]$vals[$shopCol - 1] } else { '' }\n"
            "    $fieldText = if ($fieldCol -gt 0 -and $vals.Count -ge $fieldCol) { [string]$vals[$fieldCol - 1] } else { '' }\n"
            "    if ($shopText.Length -le 12 -and $fieldText.Length -le 12) { continue }\n"
            "    $r = [int]$fill.row\n"
            "    if ($shopCol -gt 0) { $ws.Cells.Item($r, $shopCol).WrapText = $true }\n"
            "    if ($fieldCol -gt 0) { $ws.Cells.Item($r, $fieldCol).WrapText = $true }\n"
            "    if ($ws.Rows.Item($r).RowHeight -lt 30) { $ws.Rows.Item($r).RowHeight = 30 }\n"
            "  }\n"
            "  foreach ($row in @($p.group_last_rows | Where-Object { $_ })) {\n"
            "    $r = [int]$row\n"
            "    for ($c = 1; $c -le $lastCol; $c++) {\n"
            "      $edge = $ws.Cells.Item($r, $c).Borders.Item(9)\n"
            "      $edge.LineStyle = 1\n"
            "      $edge.Weight = 2\n"
            "    }\n"
            "  }\n"
            "  function Add-DocConList($sheet, $sqref, $formula) {\n"
            "    $addr = ([string]$sqref).Trim()\n"
            "    if (-not $addr -or -not $formula) { return }\n"
            "    $addr = $addr -replace '\\s+', ','\n"
            "    $rng = $sheet.Range($addr)\n"
            "    try { $rng.Validation.Delete() } catch {}\n"
            "    $rng.Validation.Add(3, 1, 1, [string]$formula) | Out-Null\n"
            "  }\n"
            "  Add-DocConList $ws ([string]$p.shop_validation) ([string]$p.shop_list)\n"
            "  Add-DocConList $ws ([string]$p.field_validation) ([string]$p.field_list)\n"
            "  foreach ($row in @($p.merge_headers | Where-Object { $_ })) {\n"
            "    $r = [int]$row\n"
            "    if ($r -le 0) { continue }\n"
            "    $addr = ('A{0}:{1}{0}' -f $r, $endCol)\n"
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
            "  try { $ws.PageSetup.PrintArea = ('A1:{0}{1}' -f $endCol, $last) } catch {}\n"
            "  Write-DocConHop 'INFO' 'save' 'Workbook.Save'\n"
            "  $wb.Save()\n"
            "  $saved = $true\n"
            "  Write-DocConHop 'INFO' 'save' 'Workbook.Save ok'\n"
            "  if ($p.pdf) {\n"
            "    $stage = 'print'\n"
            "    try {\n"
            "      $ws.Select()\n"
            "      Write-DocConHop 'INFO' 'print' 'ExportAsFixedFormat'\n"
            "      $ws.ExportAsFixedFormat(0, [string]$p.pdf)\n"
            "      Write-DocConHop 'INFO' 'print' 'ExportAsFixedFormat ok'\n"
            "    } catch {\n"
            "      Write-DocConFail 'print' $_\n"
            "      exit 2\n"
            "    }\n"
            "  }\n"
            + _ps_catch_stage()
            + "} finally {\n"
            + _PS_QUIT_EXCEL
            + "}\n"
        ),
        encoding="utf-8",
    )


def _ps_lit(value: str) -> str:
    return json.dumps(str(value))


_PS_WRITE_HOP = (
    "function Write-DocConHop($level, $step, $msg) {\n"
    "  if ($step) {\n"
    "    try { Set-Content -LiteralPath $stepPath -Value ([string]$step) -Encoding UTF8 } catch {}\n"
    "  }\n"
    "  if (-not $diagPath) { return }\n"
    "  $line = ([string]$level) + '|' + ([string]$step) + '|' + ([string]$msg)\n"
    "  try { Add-Content -LiteralPath $diagPath -Value $line -Encoding UTF8 } catch {}\n"
    "}\n"
)

_PS_WRITE_FAIL = (
    "function Write-DocConFail($step, $err) {\n"
    "  $lines = New-Object System.Collections.Generic.List[string]\n"
    "  if ($step) { $lines.Add([string]$step) }\n"
    "  if ($err -ne $null) {\n"
    "    try {\n"
    "      if ($err.Exception -and $err.Exception.Message) {\n"
    "        $lines.Add([string]$err.Exception.Message)\n"
    "      } elseif ($err.ToString) { $lines.Add([string]$err) }\n"
    "    } catch { try { $lines.Add([string]$err) } catch {} }\n"
    "    try {\n"
    "      $inner = $err.Exception.InnerException\n"
    "      if ($inner -and $inner.Message) { $lines.Add([string]$inner.Message) }\n"
    "    } catch {}\n"
    "    try { $lines.Add('HRESULT ' + ('{0:X8}' -f ($err.Exception.HResult))) } catch {}\n"
    "  }\n"
    "  $msg = [string]::Join([Environment]::NewLine, $lines)\n"
    "  if (-not $msg) { $msg = 'Excel failed.' }\n"
    "  try { Write-DocConHop 'ERROR' $step $msg } catch {}\n"
    "  try { [Console]::Error.WriteLine($msg) } catch {}\n"
    "  try { Set-Content -LiteralPath $failPath -Value $msg -Encoding UTF8 } catch {}\n"
    "}\n"
)

_PS_OPEN_BOOK = (
    "function Open-DocConBook($app, $path, $readOnly) {\n"
    "  $last = $null\n"
    "  foreach ($attempt in 1..3) {\n"
    "    if ($attempt -eq 3) {\n"
    "      try { $app.Visible = $true } catch {}\n"
    "      try { Write-DocConHop 'INFO' 'visible' 'Excel.Visible=True (open attempt 3)' } catch {}\n"
    "    }\n"
    "    try {\n"
    "      $vis = $false\n"
    "      try { $vis = [bool]$app.Visible } catch {}\n"
    "      Write-DocConHop 'INFO' 'open' ('Workbooks.Open attempt ' + [string]$attempt + ' visible=' + [string]$vis)\n"
    "      $missing = [Type]::Missing\n"
    "      $book = $app.Workbooks.Open("
    "[string]$path, 0, [bool]$readOnly, $missing, $missing, $missing, $true)\n"
    "      Write-DocConHop 'INFO' 'open' ('Workbooks.Open attempt ' + [string]$attempt + ' ok')\n"
    "      return $book\n"
    "    } catch {\n"
    "      $last = $_\n"
    "      $msg = [string]$_.Exception.Message\n"
    "      $hr = ''\n"
    "      try { $hr = '{0:X8}' -f $_.Exception.HResult } catch {}\n"
    "      Write-DocConHop 'ERROR' 'open' (\n"
    "        'Workbooks.Open attempt ' + [string]$attempt + ' failed HRESULT ' + $hr + ' ' + $msg)\n"
    "      $blob = ($msg + ' ' + $hr)\n"
    "      if ($attempt -ge 3) { throw }\n"
    "      if ($blob -notmatch 'cannot access|in use|being used|locked for editing|"
    "RPC|remote procedure|rejected by callee|800706BA|800706BE|80010105|"
    "80010108|80010001|8001010A') { throw }\n"
    "      Start-Sleep -Milliseconds (400 * $attempt * $attempt)\n"
    "    }\n"
    "  }\n"
    "  throw $last\n"
    "}\n"
)

_PS_START_EXCEL = (
    "  Write-DocConHop 'INFO' 'com_create' 'method=Activator.CreateInstance'\n"
    "  $type = [Type]::GetTypeFromProgID('Excel.Application')\n"
    "  if ($null -eq $type) {\n"
    "    Write-DocConHop 'ERROR' 'com_create' 'Excel.Application is not registered.'\n"
    "    throw 'Excel.Application is not registered.'\n"
    "  }\n"
    "  $excel = $null\n"
    "  foreach ($boot in 1..3) {\n"
    "    try {\n"
    "      Write-DocConHop 'INFO' 'com_create' ('CreateInstance attempt ' + [string]$boot)\n"
    "      $excel = [Activator]::CreateInstance($type)\n"
    "      Write-DocConHop 'INFO' 'com_create' ('CreateInstance attempt ' + [string]$boot + ' ok')\n"
    "      break\n"
    "    } catch {\n"
    "      $hr = ''\n"
    "      try { $hr = '{0:X8}' -f $_.Exception.HResult } catch {}\n"
    "      Write-DocConHop 'ERROR' 'com_create' (\n"
    "        'CreateInstance attempt ' + [string]$boot + ' HRESULT ' + $hr + ' ' + [string]$_.Exception.Message)\n"
    "      if ($boot -ge 3) { throw }\n"
    "      Start-Sleep -Milliseconds (700 * $boot)\n"
    "    }\n"
    "  }\n"
    "  if ($excel -eq $null) { throw 'Excel.Application is not registered.' }\n"
    "  foreach ($wait in 1..8) {\n"
    "    Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object {\n"
    "      if (-not $before.ContainsKey($_.Id)) { $ownedPid = $_.Id }\n"
    "    }\n"
    "    if ($ownedPid -gt 0) { break }\n"
    "    Start-Sleep -Milliseconds 150\n"
    "  }\n"
    "  if ($ownedPid -gt 0) { Set-Content -Path $pidPath -Value $ownedPid }\n"
    "  $psBits = if ([Environment]::Is64BitProcess) { '64-bit' } else { '32-bit' }\n"
    "  Write-DocConHop 'INFO' 'bitness' ('PowerShell ' + $psBits + ' excel_pid=' + [string]$ownedPid)\n"
    "  if ($ownedPid -gt 0) {\n"
    "    try {\n"
    "      $epath = [string](Get-Process -Id $ownedPid -ErrorAction Stop).Path\n"
    "      $guess = '64-bit'\n"
    "      if ($epath -match '\\(x86\\)|SysWOW64') { $guess = '32-bit' }\n"
    "      Write-DocConHop 'INFO' 'excel_bitness' ('guess=' + $guess + ' path=' + $epath)\n"
    "    } catch {}\n"
    "  } else {\n"
    "    Write-DocConHop 'WARN' 'com_create' 'Excel pid not seen after CreateInstance'\n"
    "  }\n"
    "  $excel.DisplayAlerts = $false\n"
    "  try { $excel.EnableEvents = $false } catch {}\n"
    "  try { $excel.AskToUpdateLinks = $false } catch {}\n"
    "  if ($ownedPid -gt 0) {\n"
    "    try { $excel.AutomationSecurity = 3 } catch {}\n"
    "    try { $excel.IgnoreRemoteRequests = $true } catch {}\n"
    "    try { $excel.Visible = $false } catch {}\n"
    "    try { $excel.ScreenUpdating = $false } catch {}\n"
    "    Write-DocConHop 'INFO' 'visible' 'Excel.Visible=False'\n"
    "  }\n"
)

_PS_QUIT_EXCEL = (
    "  try { Write-DocConHop 'INFO' 'quit' ('finally Close/Quit saved=' + [string]$saved) } catch {}\n"
    "  if ($wb -ne $null) { try { $wb.Close($saved) } catch {} }\n"
    "  if ($excel -ne $null) {\n"
    "    try { $excel.Quit() } catch {}\n"
    "    try { Write-DocConHop 'INFO' 'quit' 'Excel.Quit' } catch {}\n"
    "  }\n"
    "  [GC]::Collect()\n"
    "  [GC]::WaitForPendingFinalizers()\n"
)


def _ps_catch_stage() -> str:
    return (
        "} catch {\n"
        "  Write-DocConFail $stage $_\n"
        "  if ($saved) { exit 2 } else { exit 1 }\n"
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
    text = _sanitize_office_text(detail) or "Excel File Transmittal failed."
    if _looks_like_com_start_failure(text):
        return LogError(with_log_details(EXCEL_NOT_INSTALLED))
    if _looks_like_open_failure(text):
        return LogError(with_log_details(EXCEL_OPEN_FAILED))
    hint = ""
    if _looks_like_workbook_lock(text):
        hint = "\nClose that workbook in Excel if it is open, then try again."
    extra = _operator_extra_line(text)
    head = "Could not write the transmittal in Excel."
    if extra and extra not in {head, "file"}:
        return LogError(with_log_details(f"{head}\n{extra}{hint}"))
    return LogError(with_log_details(f"{head}{hint}"))


def _unblock_file(path: Path) -> None:
    log("INFO", "unblock", f"Unblock-File {describe_path(path)}")
    with contextlib.suppress(OSError):
        os.remove(f"{path}:Zone.Identifier")
    if os.name != "nt":
        return
    with contextlib.suppress(Exception):
        hidden_run(
            powershell_hidden_argv(
                "powershell",
                "-NonInteractive",
                "-Command",
                f"Unblock-File -LiteralPath {_ps_lit(str(path))}",
            ),
            capture_output=True,
            check=False,
            timeout=20,
        )


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
            f"$diagPath = {_ps_lit(str(fail.with_suffix('.hops')))}\n"
            f"$stepPath = {_ps_lit(str(fail.with_suffix('.step')))}\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$stage = 'start'\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_HOP
            + _PS_WRITE_FAIL
            + _PS_OPEN_BOOK
            + "try {\n"
            + _PS_START_EXCEL
            + "  $stage = 'open'\n"
            "  Write-DocConHop 'INFO' 'unblock' 'Unblock-File'\n"
            "  try { Unblock-File -LiteralPath $sourcePath } catch {\n"
            "    Write-DocConHop 'WARN' 'unblock' ([string]$_.Exception.Message)\n"
            "  }\n"
            "  $wb = Open-DocConBook $excel $sourcePath $true\n"
            "  $stage = 'print'\n"
            "  Write-DocConHop 'INFO' 'sheet' ('sheet=' + [string]$sheetName)\n"
            "  $ws = $wb.Worksheets.Item($sheetName)\n"
            "  $ws.Select()\n"
            "  try { $ws.PageSetup.Zoom = $false } catch {}\n"
            "  try { $ws.PageSetup.FitToPagesWide = 1 } catch {}\n"
            f"  try {{ $ws.PageSetup.FitToPagesTall = {tall} }} catch {{}}\n"
            "  Write-DocConHop 'INFO' 'print' 'ExportAsFixedFormat'\n"
            "  $ws.ExportAsFixedFormat(0, $pdfPath)\n"
            "  Write-DocConHop 'INFO' 'print' 'ExportAsFixedFormat ok'\n"
            + _ps_catch_stage()
            + "} finally {\n"
            + _PS_QUIT_EXCEL
            + "}\n"
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
    if pid <= 0:
        return
    log("INFO", "kill", f"taskkill pid={pid} hidden=yes")
    kill_pid_tree(pid)


def _powershell_hosts() -> list[str]:
    hosts: list[str] = ["powershell"]
    windir = Path(os.environ.get("WINDIR") or r"C:\Windows")
    wow64 = windir / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    sys32 = windir / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    for candidate in (wow64, sys32):
        if candidate.is_file():
            text = str(candidate)
            if text not in hosts:
                hosts.append(text)
    return hosts


def _run_office_script(
    script_path: Path,
    pid_path: Path,
    *,
    timeout_s: int,
    fail_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    fail = fail_path if fail_path is not None else Path(str(pid_path) + ".err")
    hops = fail.with_suffix(".hops")
    last: subprocess.CompletedProcess[str] | None = None
    hosts = _powershell_hosts()
    for index, host in enumerate(hosts):
        with contextlib.suppress(OSError):
            if pid_path.is_file():
                pid_path.unlink()
        if index > 0 and path_looks_32bit_powershell(host):
            log(
                "INFO",
                "powershell",
                f"32-bit powershell fallback hidden=yes attempt={index + 1} exe={host}",
            )
        completed = _popen_office(
            host, script_path, pid_path, timeout_s, hops_path=hops, attempt=index + 1
        )
        last = completed
        ingest_hop_file(hops)
        if completed.returncode == 0:
            log("INFO", "powershell", f"ok hidden=yes attempt={index + 1} exe={host}")
            return completed
        detail = _office_error_text(completed, fail, fallback="")
        log("ERROR", _fail_stage(detail) or "powershell", redact(detail or "office script failed"))
        _kill_process_tree(_read_pid_file(pid_path))
        if index + 1 < len(hosts) and _looks_like_com_start_failure(detail):
            continue
        return completed
    assert last is not None
    return last


def _popen_office(
    host: str,
    script_path: Path,
    pid_path: Path,
    timeout_s: int,
    *,
    hops_path: Path | None = None,
    attempt: int = 1,
) -> subprocess.CompletedProcess[str]:
    argv = powershell_hidden_argv(
        host,
        "-STA",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
    )
    hidden = hidden_popen_kwargs()
    before = excel_pids()
    log(
        "INFO",
        "spawn",
        f"attempt={attempt} hidden=yes exe={host} window=CREATE_NO_WINDOW,SW_HIDE "
        f"timeout_s={timeout_s}",
    )
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **hidden,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        ingest_hop_file(hops_path)
        last_step = _read_last_step(Path(hops_path).with_suffix(".step") if hops_path else None)
        owned = _read_pid_file(pid_path)
        log(
            "ERROR",
            "timeout",
            f"Excel timeout after {timeout_s}s last_step={last_step or 'unknown'} "
            f"powershell_pid={proc.pid} excel_pid={owned}",
        )
        _kill_process_tree(proc.pid)
        _kill_process_tree(owned)
        for pid in excel_pids() - before:
            _kill_process_tree(pid)
        try:
            proc.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise LogError(with_log_details(EXCEL_TIMEOUT)) from None
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def _read_last_step(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        return ""


def delete_transmittal_tab_with_excel(
    path: Path,
    *,
    tab: str,
    number_cell: str,
    next_number: int,
) -> None:
    """Remove one numbered tab and write the next number. The PDF and zip are left alone."""
    if os.name != "nt":
        raise LogError("Deleting a transmittal tab in an .xlsm needs Excel on Windows.")
    source = Path(path).resolve()
    tmp_dir = doccon_temp_dir("ct-delete-")
    log("INFO", "file", f"delete tab {tab} {describe_path(source)}")
    try:
        local_book = copy_workbook_local(source, tmp_dir)
    except OSError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise LogError(operator_excel_message(_exception_text(exc), stage="open")) from None
    payload = {
        "path": str(local_book),
        "lock": _TEMPLATE_LOCK,
        "tab": str(tab),
        "number_cell": number_cell,
        "next_number": int(next_number),
    }
    script_path = tmp_dir / "delete.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    payload_path = tmp_dir / "payload.json"
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        _write_delete_tab_script(script_path, payload_path, pid_path, fail_path)
        completed = _run_office_script(
            script_path, pid_path, timeout_s=_FILE_TIMEOUT_S, fail_path=fail_path
        )
        if completed.returncode != 0:
            raise _transmittal_excel_error(
                _office_error_text(completed, fail_path, fallback="Excel could not delete that transmittal tab.")
            )
        try:
            place_file(local_book, source, unique_if_locked=False)
        except OSError as exc:
            if _is_sharing_violation(exc):
                raise LogError(
                    with_log_details(
                        "Could not write the transmittal book.\n"
                        "Close that workbook in Excel if it is open, then try again."
                    )
                ) from None
            raise
    except LogError:
        raise
    except Exception as exc:
        raise LogError(operator_excel_message(_exception_text(exc), stage="file")) from None
    finally:
        _kill_process_tree(_read_pid_file(pid_path))
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_delete_tab_script(
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
            f"$diagPath = {_ps_lit(str(fail.with_suffix('.hops')))}\n"
            f"$stepPath = {_ps_lit(str(fail.with_suffix('.step')))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$stage = 'start'\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_HOP
            + _PS_WRITE_FAIL
            + _PS_OPEN_BOOK
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
            "try {\n"
            + _PS_START_EXCEL
            + "  $excel.DisplayAlerts = $false\n"
            "  $stage = 'open'\n"
            "  try { Unblock-File -LiteralPath ([string]$p.path) } catch {}\n"
            "  $wb = Open-DocConBook $excel ([string]$p.path) $false\n"
            "  $stage = 'delete'\n"
            "  $protectBook = [bool]$wb.ProtectStructure\n"
            "  Unlock-Book $wb $p.lock\n"
            "  $ws = $wb.Worksheets.Item('TRANSMITTAL')\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  $tab = $wb.Worksheets.Item([string]$p.tab)\n"
            "  Unlock-Sheet $tab $p.lock\n"
            "  $ws.Activate()\n"
            "  $tab.Delete()\n"
            "  $ws.Range([string]$p.number_cell).Value = [int]$p.next_number\n"
            "  try { $ws.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "  foreach ($sheet in @($wb.Worksheets)) {\n"
            "    if ($sheet.Name -match '^\\d+$') {\n"
            "      try { $sheet.Protect($p.lock, $true, $true, $true, $false, $true) } catch {}\n"
            "    }\n"
            "  }\n"
            "  if ($protectBook) { try { $wb.Protect($p.lock, $true, $false) } catch {} }\n"
            "  $wb.Save()\n"
            "  $saved = $true\n"
            + _ps_catch_stage()
            + "} finally {\n"
            + _PS_QUIT_EXCEL
            + "}\n"
        ),
        encoding="utf-8",
    )


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
    tmp_dir = doccon_temp_dir("ct-file-")
    template_local = ""
    log_runtime()
    log("INFO", "file", f"begin {describe_path(source)}")
    try:
        local_book = copy_workbook_local(source, tmp_dir)
        if template and Path(template).is_file():
            tpl_src = Path(template).resolve()
            tpl_dest = tmp_dir / f"template-{tpl_src.name}"
            shutil.copy2(tpl_src, tpl_dest)
            _unblock_file(tpl_dest)
            template_local = str(tpl_dest)
    except OSError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise LogError(operator_excel_message(_exception_text(exc), stage="open")) from None
    payload = {
        "path": str(local_book),
        "template": template_local,
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
    script_path = tmp_dir / "file.ps1"
    pid_path = tmp_dir / "office.pid"
    fail_path = tmp_dir / "office.err"
    payload_path = tmp_dir / "payload.json"
    try:
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        log("INFO", "open", f"Workbooks.Open attempt file={describe_path(local_book)}")
        _write_file_script(script_path, payload_path, pid_path, fail_path)
        completed = _run_office_script(
            script_path, pid_path, timeout_s=_FILE_TIMEOUT_S, fail_path=fail_path
        )
        if completed.returncode != 0:
            raise _transmittal_excel_error(
                _office_error_text(
                    completed, fail_path, fallback="Excel File Transmittal failed."
                )
            )
        try:
            place_file(local_book, source, unique_if_locked=False)
        except OSError as exc:
            if _is_sharing_violation(exc):
                raise LogError(
                    with_log_details(
                        "Could not write the transmittal in Excel.\n"
                        "Close that workbook in Excel if it is open, then try again."
                    )
                ) from None
            raise
    except LogError:
        raise
    except Exception as exc:
        raise LogError(operator_excel_message(_exception_text(exc), stage="file")) from None
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
            f"$diagPath = {_ps_lit(str(fail.with_suffix('.hops')))}\n"
            f"$stepPath = {_ps_lit(str(fail.with_suffix('.step')))}\n"
            "$p = Get-Content -Raw -Encoding UTF8 $payloadPath | ConvertFrom-Json\n"
            "$excel = $null\n"
            "$wb = $null\n"
            "$tpl = $null\n"
            "$saved = $false\n"
            "$ownedPid = 0\n"
            "$stage = 'start'\n"
            "$before = @{}\n"
            "Get-Process excel -ErrorAction SilentlyContinue | ForEach-Object { $before[$_.Id] = $true }\n"
            + _PS_WRITE_HOP
            + _PS_WRITE_FAIL
            + _PS_OPEN_BOOK
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
            + "  $stage = 'open'\n"
            "  Write-DocConHop 'INFO' 'unblock' 'Unblock-File'\n"
            "  try { Unblock-File -LiteralPath ([string]$p.path) } catch {\n"
            "    Write-DocConHop 'WARN' 'unblock' ([string]$_.Exception.Message)\n"
            "  }\n"
            "  if ($p.template) { try { Unblock-File -LiteralPath ([string]$p.template) } catch {} }\n"
            "  $wb = Open-DocConBook $excel ([string]$p.path) $false\n"
            "  $stage = 'file'\n"
            "  Write-DocConHop 'INFO' 'sheet' 'sheet=TRANSMITTAL'\n"
            "  $protectBook = [bool]$wb.ProtectStructure\n"
            "  Unlock-Book $wb $p.lock\n"
            "  $ws = $wb.Worksheets.Item('TRANSMITTAL')\n"
            "  Unlock-Sheet $ws $p.lock\n"
            "  if ($p.template) {\n"
            "    try {\n"
            "      $tpl = Open-DocConBook $excel ([string]$p.template) $true\n"
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
            "  Write-DocConHop 'INFO' 'save' 'Workbook.Save'\n"
            "  $wb.Save()\n"
            "  $saved = $true\n"
            "  Write-DocConHop 'INFO' 'save' 'Workbook.Save ok'\n"
            + _ps_catch_stage()
            + "} finally {\n"
            "  if ($tpl -ne $null) { try { $tpl.Close($false) } catch {} }\n"
            + _PS_QUIT_EXCEL
            + "}\n"
        ),
        encoding="utf-8",
    )


def _fail_stage(detail: str) -> str:
    first = (detail or "").splitlines()[0].strip().casefold() if detail else ""
    for name in ("start", "open", "fill", "print", "file"):
        if first == name:
            return name
    return ""


def _looks_like_com_start_failure(detail: str) -> bool:
    low = (detail or "").casefold()
    return any(
        token in low
        for token in (
            "80080005",
            "80040154",
            "800401f3",
            "server execution failed",
            "class not registered",
            "not registered",
            "retrieving the com class factory",
            "cannot create activex",
            "invalid class string",
            "excel.application is not registered",
            "operation unavailable",
        )
    )


def _looks_like_open_failure(detail: str) -> bool:
    low = (detail or "").casefold()
    if _looks_like_print_failure(low):
        return False
    return any(
        token in low
        for token in (
            "workbooks.open",
            "could not open",
            "cannot access",
            "cannot open",
            "can't open",
            "could not open the workbook",
            "protected view",
        )
    ) or _looks_like_workbook_lock(low)


def _looks_like_print_failure(detail: str) -> bool:
    low = (detail or "").casefold()
    return any(
        token in low
        for token in (
            "exportasfixedformat",
            "could not print",
            "print the pdf",
            "print project to pdf",
            "pdf export",
        )
    )


def _sanitize_office_text(detail: str) -> str:
    lines: list[str] = []
    for raw in (detail or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.casefold()
        if any(
            marker in low
            for marker in (
                "scriptstacktrace",
                "at system.",
                "at microsoft.",
                "traceback (most recent",
                'file "',
                "site-packages",
                "fullyqualifiederrorid",
            )
        ):
            continue
        if re.match(r"at .+\.ps1:\d+", low):
            continue
        lines.append(line)
    return "\n".join(lines)


def _operator_extra_line(detail: str) -> str:
    text = _sanitize_office_text(detail)
    for line in text.splitlines():
        token = line.strip()
        if not token:
            continue
        if token.casefold() in {"start", "open", "fill", "print", "file", "excel failed."}:
            continue
        if token.casefold().startswith("hresult "):
            continue
        if len(token) > 220:
            token = token[:217] + "..."
        return token
    return ""


def _exception_text(exc: object) -> str:
    if isinstance(exc, BaseException):
        parts = [str(exc).strip()]
        winerror = getattr(exc, "winerror", None)
        if winerror is not None:
            parts.append(f"WinError {winerror}")
        return "\n".join(part for part in parts if part)
    return str(exc or "").strip()


def _is_sharing_violation(exc: BaseException) -> bool:
    if getattr(exc, "winerror", None) == 32:
        return True
    return _is_sharing_text(_exception_text(exc))


def _is_sharing_text(detail: str) -> bool:
    low = (detail or "").casefold()
    return any(
        token in low
        for token in (
            "winerror 32",
            "error 32",
            "sharing violation",
            "being used by another process",
            "the process cannot access",
        )
    )


def _unique_sibling(path: Path) -> Path:
    stem, suffix, parent = path.stem, path.suffix, path.parent
    for number in range(2, 80):
        candidate = parent / f"{stem}-{number}{suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}-{os.getpid()}{suffix}"
