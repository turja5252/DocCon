# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Hidden Windows process helpers. Never CREATE_NEW_CONSOLE; never a visible cmd."""
from __future__ import annotations

import contextlib
import csv
import io
import os
import subprocess
from collections.abc import Callable

# Windows CREATE_NO_WINDOW. Not CREATE_NEW_CONSOLE (0x00000010).
CREATE_NO_WINDOW = 0x08000000
SW_HIDE = 0


def hidden_popen_kwargs() -> dict[str, object]:
    """Flags so powershell.exe / taskkill do not flash a console."""
    if os.name != "nt":
        return {}
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", CREATE_NO_WINDOW))
    kwargs: dict[str, object] = {"creationflags": flags}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= int(getattr(subprocess, "STARTF_USESHOWWINDOW", 1))
    startup.wShowWindow = int(getattr(subprocess, "SW_HIDE", SW_HIDE))
    kwargs["startupinfo"] = startup
    return kwargs


def drop_host_popen_kwargs() -> dict[str, object]:
    """No console flash, but do not SW_HIDE the helper's first HWND (that overlay is the OLE target)."""
    if os.name != "nt":
        return {}
    flags = int(getattr(subprocess, "CREATE_NO_WINDOW", CREATE_NO_WINDOW))
    return {"creationflags": flags}


def powershell_hidden_argv(host: str, *parts: str) -> list[str]:
    """powershell.exe with -WindowStyle Hidden before -File / -Command."""
    rest = [part for part in parts if part != "-NoProfile"]
    return [host, "-NoProfile", "-WindowStyle", "Hidden", *rest]


def hidden_run(argv: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    merged = dict(hidden_popen_kwargs())
    merged.update(kwargs)
    return subprocess.run(argv, **merged)


def hidden_run_tracked(
    argv: list[str],
    *,
    timeout: float,
    on_pid: Callable[[int], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Hidden spawn whose PID is reported, and whose whole tree dies on timeout.

    `subprocess.run(timeout=…)` only kills the process it started. A PowerShell
    blocked inside an Outlook COM call can leave children behind, so the timeout
    path goes through `kill_pid_tree` (taskkill /F /T) instead.
    """
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **hidden_popen_kwargs(),
    )
    if on_pid is not None:
        with contextlib.suppress(Exception):
            on_pid(int(proc.pid))
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_pid_tree(int(proc.pid))
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.communicate(timeout=5)
        raise
    return subprocess.CompletedProcess(argv, int(proc.returncode or 0), out or "", err or "")


def excel_pids() -> set[int]:
    """PIDs of EXCEL.EXE on this PC. Empty when tasklist is unavailable."""
    if os.name != "nt":
        return set()
    try:
        completed = hidden_run(
            ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    text = completed.stdout or ""
    if "no tasks" in text.casefold():
        return set()
    found: set[int] = set()
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 2:
            continue
        if "excel" not in row[0].casefold():
            continue
        try:
            found.add(int(row[1].strip()))
        except ValueError:
            continue
    return found


def kill_pid_tree(pid: int) -> None:
    """taskkill /F /T, hidden. No-op for pid <= 0."""
    if pid <= 0 or os.name != "nt":
        return
    try:
        hidden_run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def path_looks_32bit_powershell(host: str) -> bool:
    return "syswow64" in str(host).replace("/", "\\").casefold()
