# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Watch Downloads / Desktop / the DocCon inbox for new PDFs.

Pure `os.scandir` and mtime on a Tk timer in the GUI process: no COM, no OLE, no
child process, so this route cannot fault the console. It is the always-works
fallback — drag an Outlook attachment to the Desktop and DocCon picks it up.

Dropbox is never scanned.
"""
from __future__ import annotations

import os
import time
from collections.abc import Iterable
from pathlib import Path

from doccon.drop_inbox import inbox_dir
from doccon.match import MatchedRow, match_pdf_hits, pdf_hit_for_path

# A file still being written should not be paired. Tests pass settle_s=0.0.
SETTLE_S = 1.0
MAX_NEW_PER_POLL = 12
MAX_ENTRIES_PER_DIR = 400
POLL_MS = 1500


def is_dropbox_path(path: Path | str) -> bool:
    return "dropbox" in str(path).replace("/", "\\").casefold()


def watched_dirs() -> list[Path]:
    """Downloads, Desktop, and the DocCon-owned inbox. Never a Dropbox folder."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [home / "Downloads", home / "Desktop", inbox_dir()]
    out: list[Path] = []
    seen: set[str] = set()
    for folder in candidates:
        if is_dropbox_path(folder):
            continue
        token = str(folder).casefold()
        if token in seen:
            continue
        seen.add(token)
        out.append(folder)
    return out


def _token(path: Path | str) -> str:
    return str(path).replace("/", "\\").casefold()


class InboxWatcher:
    """New `*.pdf` since session start. Cheap enough to run on a 1.5s Tk timer."""

    def __init__(
        self,
        folders: Iterable[Path] | None = None,
        *,
        started: float | None = None,
        settle_s: float = SETTLE_S,
        now=time.time,
    ) -> None:
        self._now = now
        self._settle = float(settle_s)
        self._started = float(started) if started is not None else float(now())
        self._seen: set[str] = set()
        self.set_folders(folders)

    def set_folders(self, folders: Iterable[Path] | None) -> None:
        raw = list(folders) if folders is not None else watched_dirs()
        self._folders = [Path(item) for item in raw if not is_dropbox_path(item)]

    @property
    def folders(self) -> list[Path]:
        return list(self._folders)

    def forget(self, path: Path | str) -> None:
        self._seen.discard(_token(path))

    def mark_seen(self, path: Path | str) -> None:
        self._seen.add(_token(path))

    def poll(self) -> list[Path]:
        """PDFs that appeared after session start and have finished being written."""
        found: list[Path] = []
        now = float(self._now())
        for folder in self._folders:
            if is_dropbox_path(folder):
                continue
            for path, mtime in self._scan(folder):
                token = _token(path)
                if token in self._seen:
                    continue
                if mtime < self._started:
                    # Pre-existing file: remember it so it never fires later.
                    self._seen.add(token)
                    continue
                if self._settle > 0 and (now - mtime) < self._settle:
                    continue
                self._seen.add(token)
                found.append(path)
                if len(found) >= MAX_NEW_PER_POLL:
                    return found
        return found

    def _scan(self, folder: Path) -> list[tuple[Path, float]]:
        out: list[tuple[Path, float]] = []
        try:
            with os.scandir(folder) as entries:
                for index, entry in enumerate(entries):
                    if index >= MAX_ENTRIES_PER_DIR:
                        break
                    if not entry.name.casefold().endswith(".pdf"):
                        continue
                    try:
                        if not entry.is_file():
                            continue
                        stat = entry.stat()
                    except OSError:
                        continue
                    if stat.st_size <= 0:
                        continue
                    out.append((Path(entry.path), float(stat.st_mtime)))
        except OSError:
            return out
        return out


def plan_watch_hits(
    rows: list[MatchedRow], paths: list[Path], job_number: str
) -> tuple[list[tuple[str, Path]], list[Path]]:
    """Same filename match as the folder hunt. Returns (row key, pdf) pairs and the rest."""
    if not rows or not paths:
        return [], list(paths)
    hits = [pdf_hit_for_path(path) for path in paths]
    matched, _orphans = match_pdf_hits([row.drawing for row in rows], hits, job_number)
    pairs: list[tuple[str, Path]] = []
    used: set[str] = set()
    for row, new in zip(rows, matched, strict=True):
        if new.pdf is None:
            continue
        pairs.append((row.drawing.key, new.pdf.path))
        used.add(_token(new.pdf.path))
    unmatched = [path for path in paths if _token(path) not in used]
    return pairs, unmatched
