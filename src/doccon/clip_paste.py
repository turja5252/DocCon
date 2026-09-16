# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Parent side of Paste PDF. Runs the clipboard read in a short-lived child.

This module is stdlib only: subprocess plus JSON. The GUI never touches the
clipboard COM surface, so a native fault in `clip_read` cannot kill the console.
The child stages PDFs into the this-PC inbox and prints their paths.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

from doccon.drop_bridge import drop_host_cwd, drop_host_env
from doccon.drop_inbox import inbox_dir
from doccon.winproc import hidden_popen_kwargs

PASTE_TIMEOUT_S = 20
RESULT_PREFIX = "DOCCON_PASTE "
NO_PDF_ON_CLIPBOARD = (
    "No PDF on the clipboard. In Outlook, select one or more PDF attachments, "
    "right-click and choose Copy, then click Paste PDF again."
)
PASTE_FAILED = "Could not read the clipboard."


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def paste_result_path(inbox: Path, token: str = "") -> Path:
    """Sidecar JSON the noconsole exe can write; stdout is empty when console=False."""
    suffix = (token or str(os.getpid())).strip() or "0"
    return Path(inbox) / f".doccon-paste-{suffix}.json"


def paste_argv(inbox: Path | None = None, result: Path | None = None) -> list[str]:
    """One-shot helper. Frozen exe: same process image with --paste (never `-m`, never a second GUI)."""
    folder = Path(inbox) if inbox is not None else inbox_dir()
    if _frozen():
        argv = [sys.executable, "--paste", "--inbox", str(folder)]
    else:
        argv = [sys.executable, "-m", "doccon.drop_host", "--paste", "--inbox", str(folder)]
    if result is not None:
        argv.extend(["--result", str(result)])
    return argv


def parse_paste_output(text: str) -> list[Path]:
    """Pull the JSON result line out of the child's stdout. Junk lines are ignored."""
    for line in reversed(str(text or "").splitlines()):
        token = line.strip()
        if not token.startswith(RESULT_PREFIX):
            continue
        try:
            data = json.loads(token[len(RESULT_PREFIX) :])
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        raw = data.get("paths")
        if not isinstance(raw, list):
            return []
        return [Path(str(item)) for item in raw if str(item or "").strip()]
    return []


def format_paste_result(paths: list[Path] | list[str]) -> str:
    payload = json.dumps({"paths": [str(item) for item in paths]}, separators=(",", ":"))
    return RESULT_PREFIX + payload


def _log(message: str, *, level: str = "INFO") -> None:
    try:
        from doccon.diag import log

        log(level, "paste", message)
    except Exception:
        return


def _read_result_file(path: Path) -> list[Path]:
    if not path.is_file():
        return []
    try:
        return parse_paste_output(path.read_text(encoding="utf-8"))
    except OSError:
        return []


def clipboard_pdfs(inbox: Path | None = None, *, timeout: float = PASTE_TIMEOUT_S) -> list[Path]:
    """Run the helper and return staged PDF paths. Never raises for a bad clipboard."""
    if os.name != "nt":
        return []
    folder = Path(inbox) if inbox is not None else inbox_dir()
    folder.mkdir(parents=True, exist_ok=True)
    result = paste_result_path(folder)
    with contextlib.suppress(OSError):
        result.unlink()
    argv = paste_argv(folder, result=result)
    _log(f"paste helper start inbox={folder} frozen={_frozen()}")
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=drop_host_cwd(),
            env=drop_host_env(),
            check=False,
            **hidden_popen_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired) as vis:
        _log(f"paste helper failed {vis}", level="WARN")
        with contextlib.suppress(OSError):
            result.unlink()
        return []
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip()[-300:]
        _log(f"paste helper code={completed.returncode} err={tail}", level="WARN")
    paths = parse_paste_output(completed.stdout or "")
    if not paths:
        paths = _read_result_file(result)
    with contextlib.suppress(OSError):
        result.unlink()
    live = [path for path in paths if path.is_file()]
    _log(f"paste helper pdfs={len(live)}")
    return live
