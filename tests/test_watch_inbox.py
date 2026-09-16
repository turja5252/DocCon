# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Watched inbox: new PDFs on Downloads / Desktop pair themselves. No COM, no Dropbox."""
from __future__ import annotations

import os
from pathlib import Path

from doccon.match import MatchedRow
from doccon.register import DrawingRow
from doccon.watch_inbox import (
    InboxWatcher,
    is_dropbox_path,
    plan_watch_hits,
    watched_dirs,
)

JOB = "2026-Tanzim"


def _row(*, key: str, drawing_id: str, title: str = "") -> MatchedRow:
    return MatchedRow(
        drawing=DrawingRow(
            key=key,
            summary=f"{drawing_id} {title}".strip(),
            drawing_id=drawing_id,
            title=title,
            status="To Do",
            job_number=JOB,
            outgoing_rev="",
            purpose="",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )


def _write(folder: Path, name: str, *, mtime: float) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"%PDF-1.4\nstub\n")
    os.utime(path, (mtime, mtime))
    return path


def test_new_pdf_is_seen_and_matched_to_a_stub_row(tmp_path: Path) -> None:
    watched = tmp_path / "Downloads"
    watched.mkdir()
    watcher = InboxWatcher([watched], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    assert watcher.poll() == []

    fresh = _write(watched, "2026-Tanzim-1-1 REV A.pdf", mtime=1500.0)
    found = watcher.poll()
    assert found == [fresh]

    rows = [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1")]
    pairs, unmatched = plan_watch_hits(rows, found, JOB)
    assert pairs == [("P2024-1", fresh)]
    assert unmatched == []


def test_pre_existing_and_old_files_are_ignored(tmp_path: Path) -> None:
    watched = tmp_path / "Desktop"
    _write(watched, "yesterday.pdf", mtime=10.0)
    _write(watched, "this-morning.pdf", mtime=999.0)
    watcher = InboxWatcher([watched], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    assert watcher.poll() == []

    fresh = _write(watched, "just-arrived.pdf", mtime=1200.0)
    assert watcher.poll() == [fresh]


def test_each_new_pdf_fires_once(tmp_path: Path) -> None:
    watched = tmp_path / "Downloads"
    watcher = InboxWatcher([watched], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    fresh = _write(watched, "2026-Tanzim-1-2 REV 0.pdf", mtime=1500.0)
    assert watcher.poll() == [fresh]
    assert watcher.poll() == []


def test_non_pdf_and_empty_files_are_skipped(tmp_path: Path) -> None:
    watched = tmp_path / "Downloads"
    watched.mkdir()
    _write(watched, "note.txt", mtime=1500.0)
    (watched / "empty.pdf").write_bytes(b"")
    os.utime(watched / "empty.pdf", (1500.0, 1500.0))
    watcher = InboxWatcher([watched], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    assert watcher.poll() == []


def test_a_file_still_being_written_waits_for_settle(tmp_path: Path) -> None:
    watched = tmp_path / "Downloads"
    partial = _write(watched, "half-written.pdf", mtime=1999.5)
    watcher = InboxWatcher([watched], started=1000.0, settle_s=1.0, now=lambda: 2000.0)
    assert watcher.poll() == []

    settled = InboxWatcher([watched], started=1000.0, settle_s=1.0, now=lambda: 2010.0)
    assert settled.poll() == [partial]


def test_unmatched_pdf_goes_to_the_new_pdfs_list(tmp_path: Path) -> None:
    watched = tmp_path / "Downloads"
    stray = _write(watched, "some-invoice.pdf", mtime=1500.0)
    watcher = InboxWatcher([watched], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    found = watcher.poll()
    assert found == [stray]

    rows = [_row(key="P2024-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1")]
    pairs, unmatched = plan_watch_hits(rows, found, JOB)
    assert pairs == []
    assert unmatched == [stray]


def test_dropbox_folders_are_never_watched(tmp_path: Path) -> None:
    dropbox = tmp_path / "Elite Integrity Serv Dropbox" / "3.0 Doc Con"
    _write(dropbox, "2026-Tanzim-1-1 REV A.pdf", mtime=1500.0)
    assert is_dropbox_path(dropbox)

    watcher = InboxWatcher([dropbox], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    assert watcher.folders == []
    assert watcher.poll() == []

    for folder in watched_dirs():
        assert not is_dropbox_path(folder)


def test_watcher_survives_a_missing_folder(tmp_path: Path) -> None:
    watcher = InboxWatcher([tmp_path / "gone"], started=1000.0, settle_s=0.0, now=lambda: 2000.0)
    assert watcher.poll() == []


def test_watch_route_uses_no_com(tmp_path: Path) -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "doccon" / "watch_inbox.py").read_text(
        encoding="utf-8"
    )
    assert "ctypes" not in text
    assert "win_drop" not in text
    assert "subprocess" not in text
    assert "os.scandir" in text
