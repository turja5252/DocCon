# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from doccon.client_log import LogError
from doccon.diag import log_path
from doccon.excel_pdf import (
    EXCEL_NOT_INSTALLED,
    EXCEL_OPEN_FAILED,
    EXCEL_PRINT_FAILED,
    EXCEL_TIMEOUT,
    _office_error_text,
    _popen_office,
    _transmittal_excel_error,
    _write_eddi_script,
    _write_excel_script,
    _write_file_script,
    export_sheet_pdf,
    file_client_with_excel,
    operator_excel_message,
    retry_excel_open,
)
from doccon.winproc import CREATE_NO_WINDOW, SW_HIDE


@pytest.fixture(autouse=True)
def _isolate_localapp(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))


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
    assert "Open-DocConBook" in text
    assert "Write-DocConFail $stage" in text
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
    assert "function Write-DocConFail" in text
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
    assert "Open-DocConBook" in text
    assert "[Activator]::CreateInstance($type)" in text
    assert "GetActiveObject" not in text
    assert "DispatchEx" not in text
    assert "foreach ($attempt in 1..3)" in text
    assert "$excel.EnableEvents = $false" in text
    assert "$p.cells" not in text
    assert "function Write-DocConFail" in text
    assert "$excel.Interactive = $false" not in text
    assert "Read-Host" not in text
    assert "cmd /k" not in text.casefold()
    assert "Write-DocConHop" in text
    assert "Workbooks.Open attempt" in text
    assert "$excel.Quit()" in text


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
    assert "Open-DocConBook" in text
    assert "[Activator]::CreateInstance($type)" in text
    assert "GetActiveObject" not in text
    assert "DispatchEx" not in text


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
    assert "could not open the workbook" in locked.casefold()
    assert "Close that file if it is open" in locked


def test_retry_excel_open_succeeds_on_second_try() -> None:
    calls: list[int] = []

    def opener(attempt: int) -> str:
        calls.append(attempt)
        if attempt == 0:
            raise OSError("Excel cannot access the file")
        return "wb"

    slept: list[float] = []
    assert retry_excel_open(opener, sleep=slept.append) == "wb"
    assert calls == [0, 1]
    assert slept


def test_retry_excel_open_maps_operator_message() -> None:
    from doccon.client_log import LogError

    def opener(_attempt: int) -> str:
        raise OSError("Excel cannot access 'book.xlsx'. The file is in use.")

    with pytest.raises(LogError, match="could not open the workbook") as caught:
        retry_excel_open(opener, attempts=1, sleep=lambda _s: None)
    assert EXCEL_OPEN_FAILED in str(caught.value)
    assert "doccon.log" in str(caught.value)
    assert "Traceback" not in str(caught.value)


def test_operator_excel_message_hides_traceback() -> None:
    raw = (
        "start\n"
        "Retrieving the COM class factory for component with CLSID "
        "{00024500-0000-0000-C000-000000000046} failed due to the following error: "
        "80080005 Server execution failed.\n"
        "ScriptStackTrace\n"
        "at System.Management.Automation.ExceptionHandlingOps.CheckActionPreference\n"
        "Traceback (most recent call last):\n"
        '  File "C:\\Python\\lib\\site-packages\\win32com\\client.py", line 1, in Open\n'
    )
    msg = operator_excel_message(raw, stage="start")
    assert EXCEL_NOT_INSTALLED in msg
    assert "doccon.log" in msg
    assert "Install or repair desktop Excel" in msg
    assert "Microsoft 365 in a browser" in msg
    assert "ScriptStackTrace" not in msg
    assert "Traceback" not in msg
    assert "site-packages" not in msg
    print_msg = operator_excel_message("print\nExportAsFixedFormat failed", stage="print")
    assert EXCEL_PRINT_FAILED in print_msg
    assert "doccon.log" in print_msg


def test_export_sheet_pdf_opens_local_temp_not_dropbox(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    monkeypatch.setattr("doccon.excel_pdf.os.name", "nt")
    src = tmp_path / "Dropbox" / "CT-2026-Tanzim.xlsm"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"book")
    dest = tmp_path / "Dropbox" / "CT-2026-Tanzim-1.pdf"
    seen: dict[str, Path | str] = {}

    def fake_run(script_path, pid_path, timeout_s=90, fail_path=None):
        tmp = Path(script_path).parent
        seen["tmp"] = tmp
        seen["script"] = script_path.read_text(encoding="utf-8")
        assert (tmp / src.name).is_file()
        (tmp / (dest.stem + ".pdf")).write_bytes(b"%PDF")
        return subprocess.CompletedProcess(["powershell"], 0, "", "")

    monkeypatch.setattr("doccon.excel_pdf._run_office_script", fake_run)
    monkeypatch.setattr("doccon.excel_pdf._unblock_file", lambda _p: None)
    out = export_sheet_pdf(src, "TRANSMITTAL", dest)
    assert out == dest.resolve()
    assert dest.is_file()
    tmp = Path(seen["tmp"])
    assert tmp.parent.name == "DocCon"
    assert "Dropbox" not in tmp.parts
    assert "Open-DocConBook" in str(seen["script"])
    assert str(src) not in str(seen["script"])


def test_file_client_opens_local_temp_not_dropbox(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    monkeypatch.setattr("doccon.excel_pdf.os.name", "nt")
    src = tmp_path / "Dropbox" / "CT-2026-Tanzim.xlsm"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"book")
    seen: dict[str, str] = {}

    def fake_run(script_path, pid_path, timeout_s=90, fail_path=None):
        payload = json.loads((Path(script_path).parent / "payload.json").read_text(encoding="utf-8"))
        seen["path"] = payload["path"]
        Path(payload["path"]).write_bytes(b"saved")
        return subprocess.CompletedProcess(["powershell"], 0, "", "")

    monkeypatch.setattr("doccon.excel_pdf._run_office_script", fake_run)
    monkeypatch.setattr("doccon.excel_pdf._unblock_file", lambda _p: None)
    cover = SimpleNamespace(
        from_address="",
        to_line="",
        cc_line="",
        project_description="",
        client="",
        site="",
    )
    file_client_with_excel(
        src,
        job="2026-Tanzim",
        number=1,
        pages=1,
        lines=[],
        issued=date(2026, 9, 15),
        expected_return="N/A",
        cover=cover,
        template=None,
        archive=True,
    )
    opened = Path(seen["path"])
    assert opened.parent.parent.name == "DocCon"
    assert "Dropbox" not in opened.parts
    assert src.read_bytes() == b"saved"


def test_office_scripts_have_no_pause_or_read_host(tmp_path: Path) -> None:
    eddi = tmp_path / "eddi.ps1"
    export = tmp_path / "export.ps1"
    filed = tmp_path / "file.ps1"
    _write_eddi_script(eddi, tmp_path / "payload.json", tmp_path / "office.pid")
    _write_excel_script(
        export,
        tmp_path / "book.xlsx",
        "TRANSMITTAL",
        tmp_path / "out.pdf",
        tmp_path / "office.pid",
    )
    _write_file_script(filed, tmp_path / "payload.json", tmp_path / "office.pid")
    for script in (eddi, export, filed):
        text = script.read_text(encoding="utf-8")
        low = text.casefold()
        assert "read-host" not in low
        assert "cmd /k" not in low
        assert "cmd.exe" not in low
        assert "create_new_console" not in low
        assert "$excel.Quit()" in text
        assert "Write-DocConHop" in text


def test_popen_office_hides_console(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeProc:
        pid = 11
        returncode = 0
        args: object = None

        def communicate(self, timeout=None):
            return "", ""

    def fake_popen(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        proc = FakeProc()
        proc.args = args
        return proc

    monkeypatch.setattr("doccon.excel_pdf.subprocess.Popen", fake_popen)
    monkeypatch.setattr("doccon.excel_pdf.excel_pids", lambda: set())
    script = tmp_path / "export.ps1"
    script.write_text("# nop\n", encoding="utf-8")
    _popen_office("powershell", script, tmp_path / "office.pid", 5, attempt=1)
    args = list(seen["args"])  # type: ignore[arg-type]
    assert "-WindowStyle" in args
    assert "Hidden" in args
    kwargs = seen["kwargs"]
    assert kwargs.get("creationflags") == CREATE_NO_WINDOW
    assert "CREATE_NEW_CONSOLE" not in kwargs
    startup = kwargs.get("startupinfo")
    assert startup is not None
    assert int(getattr(startup, "wShowWindow", 1)) == SW_HIDE


def test_timeout_kills_powershell_and_tracked_excel(tmp_path: Path, monkeypatch) -> None:
    killed: list[int] = []
    pid_path = tmp_path / "office.pid"
    pid_path.write_text("777\n", encoding="utf-8")
    hops = tmp_path / "office.hops"
    hops.write_text("INFO|open|Workbooks.Open attempt 1 visible=False\n", encoding="utf-8")
    (tmp_path / "office.step").write_text("open", encoding="utf-8")
    calls = {"n": 0}

    def fake_excel_pids() -> set[int]:
        calls["n"] += 1
        return {100} if calls["n"] == 1 else {100, 777}

    class FakeProc:
        pid = 4242
        args = ["powershell"]

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="powershell", timeout=timeout)

        def kill(self) -> None:
            killed.append(-1)

    monkeypatch.setattr("doccon.excel_pdf.subprocess.Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr("doccon.excel_pdf.excel_pids", fake_excel_pids)
    monkeypatch.setattr("doccon.excel_pdf._kill_process_tree", lambda pid: killed.append(pid))
    with pytest.raises(LogError, match="too long") as caught:
        _popen_office(
            "powershell",
            tmp_path / "export.ps1",
            pid_path,
            1,
            hops_path=hops,
            attempt=1,
        )
    assert EXCEL_TIMEOUT in str(caught.value)
    assert "doccon.log" in str(caught.value)
    assert 4242 in killed
    assert 777 in killed
    text = log_path().read_text(encoding="utf-8")
    assert "timeout" in text.casefold()
    assert "Workbooks.Open attempt" in text
    assert "SUPERSECRET" not in text


def test_excel_helper_logs_open_attempt_without_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    monkeypatch.setattr("doccon.excel_pdf.os.name", "nt")
    src = tmp_path / "Dropbox" / "CT-2026-Tanzim.xlsm"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"book")
    dest = tmp_path / "Dropbox" / "CT-2026-Tanzim-1.pdf"

    def fake_popen(args, **kwargs):
        script = Path(args[-1])
        hops = script.parent / "office.hops"
        hops.write_text(
            "INFO|open|Workbooks.Open attempt 1 visible=False\n"
            "ERROR|open|Workbooks.Open attempt 1 failed HRESULT 800A03EC cannot access\n",
            encoding="utf-8",
        )
        (script.parent / "office.err").write_text(
            "open\nCannot access workbook\nHRESULT 800A03EC\napi_token=SUPERSECRET\n",
            encoding="utf-8",
        )

        class FakeProc:
            pid = 9
            args = args
            returncode = 1

            def communicate(self, timeout=None):
                return "", "api_token=SUPERSECRET"

        return FakeProc()

    monkeypatch.setattr("doccon.excel_pdf.subprocess.Popen", fake_popen)
    monkeypatch.setattr("doccon.excel_pdf.excel_pids", lambda: set())
    monkeypatch.setattr("doccon.excel_pdf._unblock_file", lambda _p: None)
    monkeypatch.setattr("doccon.excel_pdf._kill_process_tree", lambda _p: None)
    monkeypatch.setattr("doccon.excel_pdf._powershell_hosts", lambda: ["powershell"])
    with pytest.raises(LogError):
        export_sheet_pdf(src, "TRANSMITTAL", dest)
    text = log_path().read_text(encoding="utf-8")
    assert "open attempt" in text.casefold()
    assert "SUPERSECRET" not in text
    assert "Dropbox" not in log_path().parts
    assert src.parent not in log_path().parents

