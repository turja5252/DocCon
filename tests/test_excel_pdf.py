# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import subprocess
from pathlib import Path

from doccon.excel_pdf import (
    _office_error_text,
    _transmittal_excel_error,
    _write_eddi_script,
    _write_excel_script,
    _write_file_script,
)


def test_file_script_clears_merged_date_cells(tmp_path: Path) -> None:
    script = tmp_path / "file.ps1"
    _write_file_script(script, tmp_path / "payload.json", tmp_path / "office.pid")
    text = script.read_text(encoding="utf-8")
    assert "function Clear-Addr" in text
    assert "MergeArea.ClearContents" in text
    assert "foreach ($addr in @($p.reset_cells))" in text
    assert "$ws.Range('A96:E96').ClearContents()" not in text


def test_file_script_records_excel_errors_and_skips_template(tmp_path: Path) -> None:
    script = tmp_path / "file.ps1"
    _write_file_script(script, tmp_path / "payload.json", tmp_path / "office.pid")
    text = script.read_text(encoding="utf-8")
    assert "function Write-DocConFail" in text
    assert "Could not file the transmittal workbook." in text
    assert "$excel.Interactive = $false" not in text
    assert "if ($ownedPid -gt 0)" in text
    assert "Restore-Art $src $ws $true" in text
    restore_at = text.index("Restore-Art $src $ws $true")
    assert "try {" in text[:restore_at]
    assert "} catch {" in text[restore_at:]


def test_eddi_script_saves_then_prints(tmp_path: Path) -> None:
    script = tmp_path / "eddi.ps1"
    _write_eddi_script(script, tmp_path / "payload.json", tmp_path / "office.pid")
    text = script.read_text(encoding="utf-8")
    assert "$wb.Save()" in text
    assert "ExportAsFixedFormat" in text
    assert "ClearContents" in text
    assert ".Insert(" in text
    assert "Hidden" in text
    assert "FitToPagesTall = 0" in text
    assert "FitToPagesWide = 1" in text
    assert "PaperSize = 1" in text
    assert "Ensure-DocConMerge" in text
    assert "HorizontalAlignment = -4108" in text
    assert "VerticalAlignment = -4108" in text
    assert "merge_headers" in text
    assert "PageBreak = -4142" in text
    assert "Unblock-File" in text
    assert "Workbooks.Open([string]$p.path, 0, $false)" in text
    assert "$p.cells" not in text
    assert "function Write-DocConFail" in text
    assert "$excel.Interactive = $false" not in text


def test_excel_print_script_unblocks_and_allows_multi_page(tmp_path: Path) -> None:
    script = tmp_path / "export.ps1"
    _write_excel_script(
        script,
        tmp_path / "book.xlsx",
        "EDDI",
        tmp_path / "out.pdf",
        tmp_path / "office.pid",
        fit_pages_tall=0,
    )
    text = script.read_text(encoding="utf-8")
    assert "Unblock-File" in text
    assert "FitToPagesTall = 0" in text
    assert "ExportAsFixedFormat" in text


def test_office_error_prefers_fail_file(tmp_path: Path) -> None:
    fail = tmp_path / "office.err"
    fail.write_text("Open failed\nHRESULT 800A03EC", encoding="utf-8")
    completed = subprocess.CompletedProcess(["powershell"], 1, "", "")
    detail = _office_error_text(completed, fail, fallback="Excel File Transmittal failed.")
    assert "Open failed" in detail
    assert "800A03EC" in detail


def test_transmittal_error_only_hints_close_when_locked() -> None:
    generic = str(_transmittal_excel_error("HRESULT 800A03EC"))
    assert "Could not write the transmittal in Excel." in generic
    assert "Close that workbook" not in generic
    locked = str(_transmittal_excel_error("The file is already open"))
    assert "Close that workbook" in locked
