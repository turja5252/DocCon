# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""This-PC diagnostic log for Excel COM hops. Never Dropbox, never tokens."""
from __future__ import annotations

import contextlib
import getpass
import os
import re
import struct
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from doccon.paths import user_data_dir

LOG_NAME = "doccon.log"
MAX_LOG_BYTES = 2 * 1024 * 1024
OPERATOR_LOG_ENV = r"%LOCALAPPDATA%\EliteIntegrity\DocCon\doccon.log"
LOG_DIR_ENV = "DOCCON_LOG_DIR"

_LOCK = threading.Lock()
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(api[_-]?token|api[_-]?key|access[_-]?token|token|password|passwd|secret|authorization|"
    r"credential|bearer)\b\s*[:=]\s*\S+"
)
_BASIC_AUTH = re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/=]{12,}")
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")


def production_log_dir() -> Path:
    """The documented %LOCALAPPDATA% folder. Never a tmp path, never Dropbox."""
    return user_data_dir()


def under_pytest() -> bool:
    """True inside a pytest run, and inside any child process it spawned.

    `PYTEST_CURRENT_TEST` is inherited through the environment, so the paste /
    drop_host children of a test are caught too.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return "pytest" in sys.modules


def log_dir_override() -> Path | None:
    """Where the log must go instead of production. Set by the test suite.

    A pytest run that appends to the operator's `doccon.log` buries the session
    he is asking about, so tests are redirected even without the fixture.
    """
    raw = (os.environ.get(LOG_DIR_ENV) or "").strip()
    if raw:
        return Path(raw)
    if under_pytest():
        return Path(tempfile.gettempdir()) / "doccon-pytest" / "EliteIntegrity" / "DocCon"
    return None


def log_path() -> Path:
    return log_dir() / LOG_NAME


def log_dir() -> Path:
    override = log_dir_override()
    return override if override is not None else production_log_dir()


def store_python_cache_root() -> Path | None:
    """Microsoft-Store Python redirects %LOCALAPPDATA% writes into its own package cache.

    Running from source under that interpreter means doccon.log is NOT at the
    documented path, which is why 1.44-1.52 looked silent to the operator.
    """
    if os.name != "nt":
        return None
    exe = str(sys.executable or "").replace("/", "\\").casefold()
    if "\\windowsapps\\" not in exe:
        return None
    local = os.environ.get("LOCALAPPDATA") or ""
    if not local:
        return None
    packages = Path(local) / "Packages"
    try:
        entries = sorted(packages.glob("PythonSoftwareFoundation.Python.*"))
    except OSError:
        return None
    for entry in entries:
        cache = entry / "LocalCache" / "Local"
        if cache.is_dir():
            return cache
    return None


def real_log_dir() -> Path:
    """Folder the log actually lands in on this PC. Newest doccon.log wins the redirect."""
    override = log_dir_override()
    if override is not None:
        return override
    wanted = production_log_dir()
    cache = store_python_cache_root()
    if cache is None:
        return wanted
    local = os.environ.get("LOCALAPPDATA") or ""
    if not local:
        return wanted
    try:
        redirected = cache / wanted.relative_to(Path(local))
    except ValueError:
        return wanted
    best = wanted
    newest = -1.0
    for folder in (wanted, redirected):
        try:
            stamp = (folder / LOG_NAME).stat().st_mtime
        except OSError:
            continue
        if stamp > newest:
            newest, best = stamp, folder
    return best


def real_log_path() -> Path:
    return real_log_dir() / LOG_NAME


def operator_log_details() -> str:
    """Sarah-facing pointer. No stack, no HRESULT dump."""
    return f"Details: {OPERATOR_LOG_ENV}"


def with_log_details(message: str) -> str:
    hint = operator_log_details()
    text = (message or "").rstrip()
    if not text:
        return hint
    if hint in text or "doccon.log" in text.casefold():
        return text
    return f"{text}\n{hint}"


def describe_path(path: Path | str | None) -> str:
    """File name plus Dropbox vs TEMP vs this-PC settings. Full path is extra."""
    if path is None or str(path).strip() == "":
        return "(none)"
    raw = Path(path)
    kind = path_kind(raw)
    return f"{raw.name} ({kind}) path={raw}"


def path_kind(path: Path | str | None) -> str:
    if path is None or str(path).strip() == "":
        return "other"
    raw = Path(path)
    text = str(raw).replace("/", "\\").casefold()
    if "dropbox" in text:
        return "Dropbox"
    temp_root = Path(os.environ.get("TEMP") or tempfile.gettempdir())
    if _is_relative_to(raw, temp_root) or "\\temp\\" in f"\\{text}\\" or "\\tmp\\" in f"\\{text}\\":
        return "TEMP"
    if _is_relative_to(raw, user_data_dir()):
        return "LOCALAPPDATA"
    return "other"


def redact(text: str) -> str:
    """Strip tokens, passwords, and email addresses. Keep HRESULT and file names."""
    out = _SECRET_ASSIGN.sub(lambda m: f"{m.group(1)}=[redacted]", text or "")
    out = _BASIC_AUTH.sub("Basic [redacted]", out)
    out = _BEARER.sub("Bearer [redacted]", out)
    out = _EMAIL.sub("[email]", out)
    return out


def runtime_summary() -> str:
    bits = struct.calcsize("P") * 8
    frozen = bool(getattr(sys, "frozen", False))
    kind = "frozen exe" if frozen else "source"
    user = _windows_user()
    exe = sys.executable or ""
    return (
        f"version={_app_version()} user={user} {kind}={bits}-bit "
        f"pid={os.getpid()} exe={exe} excel_bitness=unknown"
    )


def log(level: str, step: str, message: str = "") -> None:
    """Append one line and flush to disk. A native AV must not hide that we started."""
    line = _format_line(level, step, message)
    with _LOCK:
        try:
            path = log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _rotate_unlocked(path)
            with path.open("a", encoding="utf-8", buffering=1) as handle:
                handle.write(line + "\n")
                handle.flush()
                with contextlib.suppress(OSError):
                    os.fsync(handle.fileno())
        except OSError:
            return


def log_runtime(*, step: str = "session") -> None:
    log("INFO", step, runtime_summary())


def log_session_start(*, step: str = "session") -> None:
    """First line of a process. Call before OLE, Tk drop, or drop_host spawn."""
    log_runtime(step=step)
    frozen = bool(getattr(sys, "frozen", False))
    kind = "frozen" if frozen else "source"
    log("INFO", step, f"start pid={os.getpid()} kind={kind} python={sys.executable or ''}")
    actual = real_log_path()
    note = f"log file={actual}"
    if actual != log_path():
        note += f" (Store Python redirected away from {log_path()})"
    log("INFO", step, note)


def ingest_hop_file(path: Path | str | None) -> None:
    """Copy PowerShell hop lines (LEVEL|step|message) into the this-PC log."""
    if path is None:
        return
    hops = Path(path)
    try:
        if not hops.is_file():
            return
        raw = hops.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return
    for line in raw.splitlines():
        token = line.strip()
        if not token:
            continue
        parts = token.split("|", 2)
        if len(parts) == 3:
            log(parts[0] or "INFO", parts[1] or "excel", parts[2])
        else:
            log("INFO", "excel", token)


def open_log_folder() -> Path:
    """Open the folder the log really lands in, not the documented one."""
    folder = real_log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(folder)  # type: ignore[attr-defined]
    return folder


def _app_version() -> str:
    try:
        from doccon import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _windows_user() -> str:
    for key in ("USERNAME", "USER"):
        token = (os.environ.get(key) or "").strip()
        if token:
            return token
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _format_line(level: str, step: str, message: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lvl = (level or "INFO").strip().upper() or "INFO"
    name = (step or "excel").strip() or "excel"
    body = redact((message or "").replace("\r", " ").replace("\n", " | ").strip())
    if body:
        return f"{stamp} {lvl} {name} {body}"
    return f"{stamp} {lvl} {name}"


def _rotate_unlocked(path: Path) -> None:
    try:
        if not path.is_file() or path.stat().st_size < MAX_LOG_BYTES:
            return
        old = path.with_name(path.name + ".old")
        if old.exists():
            old.unlink()
        path.replace(old)
    except OSError:
        return


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False
