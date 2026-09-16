# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Copy dropped PDFs into the job DocCon folder, then pair. Does not rewrite Jira.

Staging copies under DocCon/dropped are deleted when a real job PDF replaces them
or when Confirm succeeds for packed email-dropped rows. Explorer originals stay.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from doccon.match import (
    MatchedRow,
    coerce_located_pdfs,
    is_dropped_pdf_path,
    match_pdf_hits,
    pair_pdf,
    pdf_hit_for_path,
)
from doccon.pack_state import PACK_DIR

DROPPED_NAME = "dropped"
INVALID_FILENAME = '<>:"/\\|?*'
LOAD_FIRST = "Load a job first."
NEED_FOLDER = "Locate the job folder first so DocCon can copy the PDF."
NOT_PDF = "That is not a PDF."
MSG_SKIP = "That is an email, not a drawing PDF."
UNREADABLE = "Could not read that attachment."


@dataclass(frozen=True)
class DropSource:
    """One dropped item. Outlook FileContents fills `data`; Explorer fills `path`."""

    name: str
    path: Path | None = None
    data: bytes | None = None


def sources_from_paths(paths: list[Path | str] | tuple[Path | str, ...]) -> list[DropSource]:
    """Parent pair path: filesystem paths only. No IDataObject / IStream."""
    out: list[DropSource] = []
    for raw in paths:
        path = Path(raw)
        name = path.name or "attachment.pdf"
        out.append(DropSource(name=name, path=path, data=None))
    return out


def dropped_dir(job_folder: Path) -> Path:
    """`{job}/3.0 Doc Con/DocCon/dropped` — same DocCon folder as client-pack.json."""
    return Path(job_folder) / PACK_DIR / DROPPED_NAME


def is_msg_filename(name: str) -> bool:
    return Path(name or "").suffix.casefold() == ".msg"


def is_pdf_filename(name: str) -> bool:
    return Path(name or "").suffix.casefold() == ".pdf"


def is_pdf_source(name: str, data: bytes | None = None) -> bool:
    if is_msg_filename(name):
        return False
    if is_pdf_filename(name):
        return True
    return bool(data) and data.lstrip().startswith(b"%PDF")


def safe_filename(name: str) -> str:
    raw = (name or "").replace("\\", "/").strip()
    base = Path(raw).name or "attachment.pdf"
    cleaned = "".join("_" if (ch in INVALID_FILENAME or ord(ch) < 32) else ch for ch in base).strip(" .")
    return (cleaned or "attachment.pdf")[:180]


def unique_dest(folder: Path, name: str, *, used: set[str] | None = None) -> Path:
    """Path for a staged PDF. Re-paste of the same original name overwrites.

    Numbered copies (`scan0042-2.pdf`) only when two files in this batch share a
    name (`used` tracks names already taken in this paste). Leftover copies in
    inbox / DocCon/dropped are overwritten, not cloned.
    """
    dest = folder / safe_filename(name)
    key = dest.name.casefold()
    if used is None:
        return dest
    if key not in used:
        used.add(key)
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = folder / f"{stem}-{n}{suffix}"
        ckey = candidate.name.casefold()
        if ckey not in used:
            used.add(ckey)
            return candidate
        n += 1


def _path_key(path: Path) -> str:
    try:
        return str(Path(path).resolve()).casefold()
    except OSError:
        return str(path).casefold()


def _already_in_dropped(source: Path, folder: Path) -> bool:
    try:
        return Path(source).resolve().parent == Path(folder).resolve()
    except OSError:
        return False


def write_pdf_bytes_into_dropped(
    job_folder: Path, filename: str, data: bytes, *, used: set[str] | None = None
) -> Path:
    """Outlook FileContents path: write attachment bytes into DocCon/dropped and return that file.

    No live Outlook. Tests pass fake bytes. Same original name overwrites a leftover copy.
    """
    folder = dropped_dir(job_folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = safe_filename(filename)
    if not is_pdf_filename(name):
        name = f"{Path(name).stem or 'attachment'}.pdf"
    dest = unique_dest(folder, name, used=used)
    dest.write_bytes(data)
    return dest


def copy_into_dropped(job_folder: Path, source: Path, *, used: set[str] | None = None) -> Path:
    src = Path(source)
    folder = dropped_dir(job_folder)
    folder.mkdir(parents=True, exist_ok=True)
    if _already_in_dropped(src, folder):
        if used is not None:
            used.add(src.name.casefold())
        return src
    dest = unique_dest(folder, src.name, used=used)
    try:
        shutil.copy2(src, dest)
    except OSError:
        dest.write_bytes(src.read_bytes())
    return dest


def _unique_notes(notes: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        if note and note not in seen:
            seen.add(note)
            out.append(note)
    return out


def ingest_sources(job_folder: Path, sources: list[DropSource]) -> tuple[list[Path], list[str]]:
    """Copy PDFs into dropped/. Skip .msg and non-PDF. Returns stable paths and skip notes."""
    pdfs: list[Path] = []
    skipped: list[str] = []
    used: set[str] = set()
    for src in sources:
        name = (src.name or "").strip() or (src.path.name if src.path is not None else "attachment")
        data = src.data
        if data is None and src.path is not None:
            try:
                data = src.path.read_bytes()
            except OSError:
                data = None
        if is_msg_filename(name) or (src.path is not None and is_msg_filename(src.path.name)):
            skipped.append(MSG_SKIP)
            continue
        if not is_pdf_source(name, data):
            skipped.append(NOT_PDF)
            continue
        if src.path is not None:
            try:
                pdfs.append(copy_into_dropped(job_folder, src.path, used=used))
            except OSError:
                skipped.append(UNREADABLE)
            continue
        if data:
            write_name = name if is_pdf_filename(name) else f"{Path(name).stem or 'attachment'}.pdf"
            pdfs.append(write_pdf_bytes_into_dropped(job_folder, write_name, data, used=used))
            continue
        skipped.append(UNREADABLE)
    return pdfs, _unique_notes(skipped)


def row_matches_pdf(row: MatchedRow, path: Path, job_number: str) -> bool:
    job = job_number or row.drawing.job_number
    matched, _orphans = match_pdf_hits([row.drawing], [pdf_hit_for_path(path)], job)
    return matched[0].pdf is not None


def pick_pdf_for_row(row: MatchedRow, pdfs: list[Path], job_number: str) -> Path:
    """One file: that PDF. Several: the one that clearly matches this JIRA ID, else the first."""
    if len(pdfs) == 1:
        return pdfs[0]
    hits = [path for path in pdfs if row_matches_pdf(row, path, job_number)]
    if len(hits) == 1:
        return hits[0]
    return pdfs[0]


def _norm_path(path: Path | str) -> str:
    """Compare paths without Path.resolve() (Dropbox resolve can hang the UI thread)."""
    return str(path).replace("/", "\\").strip().rstrip("\\").casefold()


def _same_file(left: Path | str, right: Path | str) -> bool:
    return _norm_path(left) == _norm_path(right)


def delete_dropped_copy(path: Path | str | None) -> bool:
    """Unlink our staging file under DocCon/dropped. Never Downloads / Current PDF."""
    if path is None or str(path).strip() == "":
        return False
    target = Path(path)
    if not is_dropped_pdf_path(target):
        return False
    try:
        if not target.is_file():
            return False
        target.unlink()
        return True
    except OSError:
        return False


def delete_replaced_dropped_copy(
    previous: Path | str | None, replacement: Path | str | None
) -> bool:
    """Delete the old dropped/ staging file when the row pairs a different PDF."""
    if previous is None or str(previous).strip() == "":
        return False
    if not is_dropped_pdf_path(previous):
        return False
    if replacement is not None and str(replacement).strip() and _same_file(previous, replacement):
        return False
    return delete_dropped_copy(previous)


def replace_paired_pdf(
    row: MatchedRow, path: Path, *, email_dropped: bool | None = None
) -> MatchedRow:
    """Pair `path` and delete the previous DocCon/dropped copy if this row is leaving it."""
    previous = row.pdf.path if row.pdf is not None else None
    updated = pair_pdf(row, path, email_dropped=email_dropped)
    new_path = updated.pdf.path if updated.pdf is not None else None
    delete_replaced_dropped_copy(previous, new_path)
    return updated


def sweep_replaced_dropped_copies(
    rows: list[MatchedRow], located: dict[str, object] | None
) -> None:
    """Hunt/Load: if a real job PDF replaced an email-drop, delete our dropped/ copy."""
    live = {row.drawing.key: row for row in rows}
    for key, rec in coerce_located_pdfs(located).items():
        row = live.get(key)
        if row is None:
            continue
        new_path = None if row.pdf is None else row.pdf.path
        delete_replaced_dropped_copy(rec.path, new_path)


def delete_pack_dropped_copies(rows: list[MatchedRow]) -> list[Path]:
    """Confirm success: delete email-dropped staging copies used by these packed rows."""
    deleted: list[Path] = []
    seen: set[str] = set()
    for row in rows:
        if row.pdf is None or not row.pdf.email_dropped:
            continue
        path = row.pdf.path
        token = _norm_path(path)
        if token in seen:
            continue
        seen.add(token)
        if delete_dropped_copy(path):
            deleted.append(path)
    return deleted


def resolve_drop_row_key(*keys: str | None) -> str | None:
    """First non-empty Jira issue key: drop hit, last cursor, then selected row."""
    for key in keys:
        text = str(key or "").strip()
        if text:
            return text
    return None


def apply_row_drop(row: MatchedRow, pdfs: list[Path], job_number: str) -> tuple[MatchedRow, list[Path]]:
    chosen = pick_pdf_for_row(row, pdfs, job_number)
    leftover = [path for path in pdfs if _path_key(path) != _path_key(chosen)]
    return replace_paired_pdf(row, chosen), leftover


def apply_board_drop(
    rows: list[MatchedRow], pdfs: list[Path], job_number: str
) -> tuple[list[MatchedRow], list[Path]]:
    """Same filename match as the folder hunt. High → pair. Leftovers unmatched."""
    hits = [pdf_hit_for_path(path) for path in pdfs]
    matched, _orphans = match_pdf_hits([row.drawing for row in rows], hits, job_number)
    used: set[str] = set()
    out: list[MatchedRow] = []
    for old, new in zip(rows, matched, strict=True):
        if new.pdf is not None:
            out.append(replace_paired_pdf(old, new.pdf.path))
            used.add(_path_key(new.pdf.path))
        else:
            out.append(old)
    leftover = [path for path in pdfs if _path_key(path) not in used]
    return out, leftover
