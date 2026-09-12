# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from doccon.jobs import local_team_dropbox_member_roots, team_dropbox_member_root
from doccon.register import DrawingRow

REV_IN_NAME = re.compile(r"^(.*?)\s+REV\s+(.+)$", re.IGNORECASE)
REV_IN_PARENS = re.compile(r"^(.*?)\s*\(\s*Rev\.?\s*([^)]+?)\s*\)\s*$", re.IGNORECASE)
EIS_TOKEN = re.compile(r"\beis-\d+(?:-[a-z0-9]+|[a-z]+)?\b", re.IGNORECASE)
SKIP_DIR_NAMES = frozenset({"old procedures", "original wps"})


@dataclass(frozen=True)
class PdfHit:
    path: Path
    drawing_id: str
    rev: str
    library: bool = False


@dataclass(frozen=True)
class MatchedRow:
    drawing: DrawingRow
    pdf: PdfHit | None
    confidence: str  # High | Missing


def parse_pdf_stem(stem: str) -> tuple[str, str]:
    text = (stem or "").strip()
    match = REV_IN_NAME.match(text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    match = REV_IN_PARENS.match(text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, ""


def compact_drawing_id(drawing_id: str, job_number: str) -> str:
    """2026-075-1-STWD + job 2026-075 -> 2026-075-STWD (PDF naming)."""
    drawing = (drawing_id or "").strip()
    job = (job_number or "").strip()
    if not drawing or not job:
        return drawing
    prefix = job + "-"
    if not drawing.upper().startswith(prefix.upper()):
        return drawing
    rest = drawing[len(prefix) :]
    unit, sep, sheet = rest.partition("-")
    if sep and unit.isdigit() and sheet and not sheet[:1].isdigit():
        return f"{job}-{sheet}"
    return drawing


DOC_TYPE_HINTS = (
    ("mr", ("mr", "material requisition", "material request")),
    ("itp", ("itp",)),
    ("wo", ("wo", "work order")),
    ("ws", ("ws", "weld summary", "welding summary")),
    ("wps", ("wps", "weld procedure", "welding procedure")),
    ("pqr", ("pqr",)),
)


def match_keys(drawing_id: str, job_number: str, *, title: str = "", summary: str = "") -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        key = (token or "").strip().casefold()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)

    add(drawing_id)
    compact_source = (drawing_id or "").replace(" ", "-")
    add(compact_source)
    compact = compact_drawing_id(compact_source, job_number)
    add(compact)
    blob = f"{drawing_id} {title} {summary}".casefold()
    for prefix, hints in DOC_TYPE_HINTS:
        token = (drawing_id or "").strip().casefold()
        if token.startswith(prefix + "-"):
            add(token[len(prefix) + 1 :])
            continue
        if any(re.search(rf"(^|[^a-z0-9]){re.escape(hint)}([^a-z0-9]|$)", blob) for hint in hints):
            add(f"{prefix}-{token}")
            if compact:
                add(f"{prefix}-{compact.casefold()}")
    for found in EIS_TOKEN.finditer(blob):
        add(found.group(0))
    return keys


def _is_current_pdf_dir(path: Path) -> bool:
    return "current pdf" in path.name.casefold()


def _name_starts(name: str, prefix: str) -> bool:
    token = (name or "").strip()
    return token == prefix or token.startswith(prefix + " ")


def _iter_dirs(folder: Path) -> list[Path]:
    try:
        return [child for child in folder.iterdir() if child.is_dir()]
    except OSError:
        return []


def extra_document_roots(job_folder: Path) -> list[Path]:
    """MR in 1.0 Engineering; ITP/WO in 4.3; weld summary in 4.7; job-local 4.4.1 if it exists."""
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path).casefold()
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    job = Path(job_folder)
    for child in _iter_dirs(job):
        if _name_starts(child.name, "1.0"):
            add(child)
        if not _name_starts(child.name, "4.0"):
            continue
        for sub in _iter_dirs(child):
            if _name_starts(sub.name, "4.3") or _name_starts(sub.name, "4.7") or _name_starts(sub.name, "4.4.1"):
                add(sub)
            if _name_starts(sub.name, "4.4"):
                for nested in _iter_dirs(sub):
                    if _name_starts(nested.name, "4.4.1"):
                        add(nested)
    return roots


def wps_library_roots(*, hint: Path | None = None) -> list[Path]:
    """Shared `4.4 QC / 4.4.1 WPS&PQR` on each Dropbox person folder — not inside the job."""
    if hint is None:
        return []
    job = Path(hint)
    if team_dropbox_member_root(job) is None:
        return []
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        if not path.is_dir():
            return
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path).casefold()
        if key in seen:
            return
        seen.add(key)
        roots.append(path)

    owner = team_dropbox_member_root(job)
    members: list[Path] = []
    if owner is not None:
        members.append(owner)
    for member in local_team_dropbox_member_roots(hint=job):
        if owner is not None:
            try:
                if member.resolve() == owner.resolve():
                    continue
            except OSError:
                if member == owner:
                    continue
        members.append(member)
    for member in members:
        before = len(roots)
        for child in _iter_dirs(member):
            if not _name_starts(child.name, "4.4"):
                continue
            for sub in _iter_dirs(child):
                if _name_starts(sub.name, "4.4.1"):
                    add(sub)
        if len(roots) > before:
            break
    return roots


def _prune_walk_dir(name: str, *, current_pdf_only: bool) -> bool:
    folded = (name or "").casefold()
    if folded in SKIP_DIR_NAMES or "void" in folded:
        return True
    return bool(current_pdf_only and "old pdf" in folded)


def _is_procedure_id(drawing_id: str) -> bool:
    token = (drawing_id or "").casefold()
    return token.startswith(("eis-", "wps-", "pqr-"))


def _pdf_hits_under(root: Path, *, current_pdf_only: bool, library: bool = False) -> list[PdfHit]:
    hits: list[PdfHit] = []
    if not root.is_dir():
        return hits
    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dirnames[:] = [name for name in dirnames if not _prune_walk_dir(name, current_pdf_only=current_pdf_only)]
            folder = Path(dirpath)
            if current_pdf_only and not _is_current_pdf_dir(folder):
                continue
            for name in filenames:
                if not name.casefold().endswith(".pdf"):
                    continue
                pdf = folder / name
                drawing_id, rev = parse_pdf_stem(pdf.stem)
                if library and not _is_procedure_id(drawing_id):
                    continue
                if drawing_id:
                    hits.append(PdfHit(path=pdf, drawing_id=drawing_id, rev=rev, library=library))
    except OSError:
        return hits
    return hits


def _is_drafting_hit(hit: PdfHit) -> bool:
    return any(part.casefold() == "2.0 drafting" for part in hit.path.parts)


def _hit_kind(hit: PdfHit) -> int:
    if _is_drafting_hit(hit):
        return 0
    if hit.library:
        return 2
    return 1


def _prefer_hit(previous: PdfHit | None, hit: PdfHit) -> PdfHit:
    if previous is None:
        return hit
    prev_kind = _hit_kind(previous)
    new_kind = _hit_kind(hit)
    if new_kind != prev_kind:
        return hit if new_kind < prev_kind else previous
    if new_kind == 2:
        prev_depth = len(previous.path.parts)
        new_depth = len(hit.path.parts)
        if new_depth != prev_depth:
            return hit if new_depth < prev_depth else previous
    try:
        if hit.path.stat().st_mtime >= previous.path.stat().st_mtime:
            return hit
    except OSError:
        return hit
    return previous


def scan_current_pdfs(job_folder: Path) -> list[PdfHit]:
    hits: list[PdfHit] = []
    drafting = job_folder / "2.0 Drafting"
    if drafting.is_dir():
        hits.extend(_pdf_hits_under(drafting, current_pdf_only=True))
    for root in extra_document_roots(job_folder):
        hits.extend(_pdf_hits_under(root, current_pdf_only=False))
    for root in wps_library_roots(hint=job_folder):
        hits.extend(_pdf_hits_under(root, current_pdf_only=False, library=True))
    return hits


def match_pdf_hits(
    rows: list[DrawingRow], hits: list[PdfHit], job_number: str
) -> tuple[list[MatchedRow], int]:
    by_key: dict[str, PdfHit] = {}
    for hit in hits:
        key = hit.drawing_id.casefold()
        by_key[key] = _prefer_hit(by_key.get(key), hit)
    used: set[str] = set()
    matched: list[MatchedRow] = []
    for row in rows:
        hit = None
        job = job_number or row.job_number
        for key in match_keys(row.drawing_id, job, title=row.title, summary=row.summary):
            candidate = by_key.get(key)
            if candidate is not None:
                hit = candidate
                used.add(key)
                break
        matched.append(
            MatchedRow(
                drawing=row,
                pdf=hit,
                confidence="High" if hit else "Missing",
            )
        )
    orphans = sum(1 for key, hit in by_key.items() if key not in used and not hit.library)
    return matched, orphans


def attach_pdfs(rows: list[DrawingRow], job_folder: Path | None, job_number: str) -> tuple[list[MatchedRow], int]:
    if job_folder is None:
        return [MatchedRow(drawing=row, pdf=None, confidence="Missing") for row in rows], 0
    return match_pdf_hits(rows, scan_current_pdfs(job_folder), job_number)


def pair_pdf(row: MatchedRow, path: Path) -> MatchedRow:
    pdf_path = Path(path)
    drawing_id, rev = parse_pdf_stem(pdf_path.stem)
    hit = PdfHit(
        path=pdf_path,
        drawing_id=drawing_id or row.drawing.drawing_id,
        rev=rev,
    )
    return replace(row, pdf=hit, confidence="High")


def apply_located_pdfs(rows: list[MatchedRow], located: dict[str, str]) -> list[MatchedRow]:
    out: list[MatchedRow] = []
    for row in rows:
        path = (located or {}).get(row.drawing.key)
        if row.pdf is None and path:
            pdf_path = Path(path)
            if pdf_path.is_file():
                row = pair_pdf(row, pdf_path)
        out.append(row)
    return out
