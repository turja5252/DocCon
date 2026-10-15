# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Print an Excel or Word file to a temporary PDF so Preview can read it.

The source file is opened read-only and is not saved. The PDF stays in
LOCALAPPDATA. The ID and description boxes then work on that PDF.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import subprocess
from pathlib import Path

from doccon.winproc import hidden_popen_kwargs, kill_pid_tree, powershell_hidden_argv

EXCEL_SUFFIXES = frozenset({".xlsx", ".xlsm", ".xls", ".xlsb"})
WORD_SUFFIXES = frozenset({".docx", ".doc", ".docm"})
PREVIEW_TIMEOUT = 120

_SCRIPT = r"""
param(
  [Parameter(Mandatory = $true)][string]$Kind,
  [Parameter(Mandatory = $true)][string]$Source,
  [Parameter(Mandatory = $true)][string]$Dest
)
$ErrorActionPreference = 'Stop'
$app = $null
$item = $null
try {
  if ($Kind -eq 'excel') {
    $app = New-Object -ComObject Excel.Application
    $app.Visible = $false
    $app.DisplayAlerts = $false
    $app.AskToUpdateLinks = $false
    $app.AutomationSecurity = 3
    $item = $app.Workbooks.Open($Source, 0, $true)
    $item.ExportAsFixedFormat(0, $Dest)
  } else {
    $app = New-Object -ComObject Word.Application
    $app.Visible = $false
    $app.DisplayAlerts = 0
    $app.AutomationSecurity = 3
    $item = $app.Documents.Open($Source, $false, $true, $false)
    $item.ExportAsFixedFormat($Dest, 17)
  }
} finally {
  if ($item -ne $null) {
    try { $item.Close(0) } catch {}
  }
  if ($app -ne $null) {
    try { $app.Quit() } catch {}
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
"""


class OfficePreviewError(Exception):
    """Excel or Word could not print a preview PDF."""


def can_preview(path: Path | None) -> bool:
    """PDFs open directly. Excel and Word are printed to a preview PDF first."""
    if path is None:
        return False
    suffix = Path(path).suffix.casefold()
    return suffix == ".pdf" or suffix in EXCEL_SUFFIXES or suffix in WORD_SUFFIXES


def preview_cache_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
    folder = Path(root) / "EliteIntegrity" / "DocCon" / "preview"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def office_to_preview_pdf(path: Path) -> Path:
    """Return a PDF of this spreadsheet or document. A PDF path is returned as-is."""
    source = Path(path)
    if source.suffix.casefold() == ".pdf":
        return source
    if not source.is_file():
        raise OfficePreviewError(f"That file is not on disk: {source.name}")
    kind = _kind(source)
    if not kind:
        raise OfficePreviewError(f"Preview is for PDF, Excel, and Word. {source.name} is not one of those.")
    cached = _cached_pdf(source)
    if _is_pdf(cached):
        return cached
    cached.unlink(missing_ok=True)
    script = preview_cache_dir() / "_preview.ps1"
    script.write_text(_SCRIPT, encoding="utf-8")
    argv = powershell_hidden_argv(
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Kind",
        kind,
        "-Source",
        str(source.resolve()),
        "-Dest",
        str(cached),
    )
    try:
        completed = _run(argv, PREVIEW_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        cached.unlink(missing_ok=True)
        raise OfficePreviewError(
            f"Preview of {source.name} took too long. Close it in {_app_name(kind)} and try again."
        ) from exc
    except OSError as exc:
        raise OfficePreviewError(f"Could not preview {source.name}.") from exc
    if completed.returncode != 0 or not _is_pdf(cached):
        cached.unlink(missing_ok=True)
        raise OfficePreviewError(_failure_message(kind, source.name, completed.stderr or completed.stdout or ""))
    return cached


def _kind(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in EXCEL_SUFFIXES:
        return "excel"
    if suffix in WORD_SUFFIXES:
        return "word"
    return ""


def _app_name(kind: str) -> str:
    return "Excel" if kind == "excel" else "Word"


def _cached_pdf(source: Path) -> Path:
    stat = source.stat()
    digest = hashlib.sha1(str(source.resolve()).casefold().encode("utf-8")).hexdigest()[:16]
    return preview_cache_dir() / f"{digest}-{stat.st_mtime_ns}-{stat.st_size}.pdf"


def _is_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 5:
        return False
    with path.open("rb") as handle:
        return handle.read(5) == b"%PDF-"


def _run(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **hidden_popen_kwargs(),
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_pid_tree(int(proc.pid))
        with contextlib.suppress(Exception):
            proc.kill()
        raise
    return subprocess.CompletedProcess(argv, int(proc.returncode or 0), out or "", err or "")


def _failure_message(kind: str, name: str, detail: str) -> str:
    text = (detail or "").casefold()
    app = _app_name(kind)
    if any(token in text for token in ("80040154", "not registered", "invalid class", "800401f3")):
        return f"{app} needs to be installed to preview {name}."
    return f"Could not preview {name}."
