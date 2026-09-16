# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from doccon import __version__
from doccon.diag import (
    LOG_DIR_ENV,
    MAX_LOG_BYTES,
    describe_path,
    ingest_hop_file,
    log,
    log_dir_override,
    log_path,
    log_runtime,
    operator_log_details,
    production_log_dir,
    real_log_dir,
    real_log_path,
    redact,
    store_python_cache_root,
    under_pytest,
    with_log_details,
)


def _as_real_run(monkeypatch) -> None:
    """Pretend this is Sarah's console, not pytest: no override, no redirect flag."""
    monkeypatch.delenv(LOG_DIR_ENV, raising=False)
    monkeypatch.setattr("doccon.diag.under_pytest", lambda: False)


def test_real_log_path_falls_back_to_the_documented_one(tmp_path, monkeypatch) -> None:
    """No Store-Python redirect: the real path is the documented path."""
    _as_real_run(monkeypatch)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr("doccon.diag.sys.executable", str(tmp_path / "python.exe"))
    assert store_python_cache_root() is None
    assert real_log_path() == log_path()
    assert real_log_dir() == log_path().parent


def test_store_python_redirect_is_followed_to_the_newer_log(tmp_path, monkeypatch) -> None:
    """Running from source under Store Python hid 1.44-1.52 from the operator."""
    _as_real_run(monkeypatch)
    local = tmp_path / "Local"
    documented = local / "EliteIntegrity" / "DocCon"
    documented.mkdir(parents=True)
    (documented / "doccon.log").write_text("old frozen-exe run\n", encoding="utf-8")

    cache = local / "Packages" / "PythonSoftwareFoundation.Python.3.13_abc" / "LocalCache" / "Local"
    redirected = cache / "EliteIntegrity" / "DocCon"
    redirected.mkdir(parents=True)
    log_file = redirected / "doccon.log"
    log_file.write_text("fresh source run\n", encoding="utf-8")
    import os

    os.utime(documented / "doccon.log", (1000, 1000))
    os.utime(log_file, (9000, 9000))

    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(
        "doccon.diag.sys.executable",
        r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe",
    )
    monkeypatch.setattr("doccon.diag.os.name", "nt")
    assert store_python_cache_root() == cache
    assert real_log_path() == log_file
    assert real_log_path() != log_path()


def test_logger_writes_temp_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    log("INFO", "session", "DocCon started token=SUPERSECRET")
    path = log_path()
    assert path.name == "doccon.log"
    assert path.parent.name == "DocCon"
    assert "Dropbox" not in path.parts
    text = path.read_text(encoding="utf-8")
    assert "session" in text
    assert "DocCon started" in text
    assert "SUPERSECRET" not in text
    assert "token=[redacted]" in text


def test_runtime_line_has_version_and_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setenv("USERNAME", "SarahChan")
    log_runtime()
    text = log_path().read_text(encoding="utf-8")
    assert f"version={__version__}" in text
    assert "user=SarahChan" in text
    assert "pid=" in text
    assert "source=" in text or "frozen exe=" in text


def test_session_start_flushes_before_ole(tmp_path, monkeypatch) -> None:
    from doccon.diag import log_session_start

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    log_session_start()
    text = log_path().read_text(encoding="utf-8")
    assert f"version={__version__}" in text
    assert "start pid=" in text
    assert "kind=source" in text or "kind=frozen" in text


def test_pytest_never_writes_the_operator_log(tmp_path, monkeypatch) -> None:
    """Test lines in doccon.log buried the operator's real session. Never again."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    production = production_log_dir() / "doccon.log"
    assert under_pytest() is True
    assert log_dir_override() is not None
    log("INFO", "session", "gui init pid=8304 before drop install")
    written = log_path()
    assert written != production
    assert production_log_dir() not in written.parents
    assert not production.exists()
    assert "gui init pid=8304" in written.read_text(encoding="utf-8")
    assert "Dropbox" not in written.parts


def test_log_dir_env_redirects_children_of_a_test(tmp_path, monkeypatch) -> None:
    """The paste / drop_host children inherit the env var, so they land in tmp too."""
    folder = tmp_path / "child-log"
    monkeypatch.setenv(LOG_DIR_ENV, str(folder))
    assert log_dir_override() == folder
    assert log_path() == folder / "doccon.log"
    log("INFO", "drop_host", "paste staged pdfs=1")
    assert (folder / "doccon.log").is_file()


def test_without_the_env_var_pytest_still_lands_in_tmp(monkeypatch) -> None:
    """Belt and braces: a test that forgets the fixture is still not production."""
    monkeypatch.delenv(LOG_DIR_ENV, raising=False)
    assert under_pytest() is True
    folder = log_dir_override()
    assert folder is not None
    assert folder != production_log_dir()
    assert folder.name == "DocCon"


def test_a_real_run_resolves_the_redirected_production_log(tmp_path, monkeypatch) -> None:
    """1.53 Store-Python behaviour is intact: Open log folder still finds the real file."""
    local = tmp_path / "Local"
    documented = local / "EliteIntegrity" / "DocCon"
    documented.mkdir(parents=True)
    (documented / "doccon.log").write_text("old\n", encoding="utf-8")
    cache = local / "Packages" / "PythonSoftwareFoundation.Python.3.13_qbz" / "LocalCache" / "Local"
    redirected = cache / "EliteIntegrity" / "DocCon"
    redirected.mkdir(parents=True)
    (redirected / "doccon.log").write_text("live source run\n", encoding="utf-8")
    import os

    os.utime(documented / "doccon.log", (1000, 1000))
    os.utime(redirected / "doccon.log", (9000, 9000))

    _as_real_run(monkeypatch)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(
        "doccon.diag.sys.executable",
        r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe",
    )
    monkeypatch.setattr("doccon.diag.os.name", "nt")
    assert log_dir_override() is None
    assert production_log_dir() == documented
    assert log_path() == documented / "doccon.log"
    assert real_log_dir() == redirected
    assert real_log_path() == redirected / "doccon.log"


def test_redact_strips_emails_and_passwords() -> None:
    blob = "to=sarah@elite.com password=hunter2 api_token=ABC123"
    cleaned = redact(blob)
    assert "sarah@elite.com" not in cleaned
    assert "hunter2" not in cleaned
    assert "ABC123" not in cleaned
    assert "[email]" in cleaned


def test_describe_path_marks_dropbox_vs_temp(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TEMP", str(tmp_path / "Temp"))
    drop = tmp_path / "Dropbox" / "EDDI-2026-Tanzim.xlsm"
    temp = tmp_path / "Temp" / "DocCon" / "EDDI-2026-Tanzim.xlsm"
    drop.parent.mkdir(parents=True)
    temp.parent.mkdir(parents=True)
    drop.write_bytes(b"x")
    temp.write_bytes(b"x")
    assert "Dropbox" in describe_path(drop)
    assert "TEMP" in describe_path(temp)
    assert drop.name in describe_path(drop)


def test_with_log_details_points_at_doccon_log() -> None:
    text = with_log_details("Excel failed.")
    assert "Excel failed." in text
    assert "doccon.log" in text
    assert r"%LOCALAPPDATA%\EliteIntegrity\DocCon\doccon.log" in text
    assert operator_log_details() in text


def test_ingest_hops_and_rotate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    hops = tmp_path / "office.hops"
    hops.write_text("INFO|open|Workbooks.Open attempt 1 visible=False\n", encoding="utf-8")
    ingest_hop_file(hops)
    text = log_path().read_text(encoding="utf-8")
    assert "Workbooks.Open attempt 1" in text
    fat = log_path()
    fat.write_bytes(b"x" * (MAX_LOG_BYTES + 10))
    log("INFO", "rotate", "after cap")
    old = fat.with_name("doccon.log.old")
    assert old.is_file()
    assert "after cap" in fat.read_text(encoding="utf-8")
