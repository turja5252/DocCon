# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from doccon.register import DrawingRow

REV_IN_NAME = re.compile(r"^(.*?)\s+REV\s+(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class PdfHit:
    path: Path
    drawing_id: str
    rev: str


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


def match_keys(drawing_id: str, job_number: str) -> set[str]:
    keys = {drawing_id.strip().casefold()}
    compact = compact_drawing_id(drawing_id, job_number)
    if compact:
        keys.add(compact.casefold())
    return {key for key in keys if key}


def _in_void(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "void" in path.as_posix().casefold()
    return any("void" in part.casefold() for part in relative.parts)


def _is_current_pdf_dir(path: Path) -> bool:
    return "current pdf" in path.name.casefold()


def scan_current_pdfs(job_folder: Path) -> list[PdfHit]:
    drafting = job_folder / "2.0 Drafting"
    if not drafting.is_dir():
        return []
    hits: list[PdfHit] = []
    for pdf in drafting.rglob("*.pdf"):
        if not pdf.is_file():
            continue
        if _in_void(pdf, drafting):
            continue
        if not any(_is_current_pdf_dir(parent) for parent in pdf.parents if parent != drafting):
            continue
        drawing_id, rev = parse_pdf_stem(pdf.stem)
        if drawing_id:
            hits.append(PdfHit(path=pdf, drawing_id=drawing_id, rev=rev))
    return hits


def attach_pdfs(rows: list[DrawingRow], job_folder: Path | None, job_number: str) -> tuple[list[MatchedRow], int]:
    if job_folder is None:
        return [MatchedRow(drawing=row, pdf=None, confidence="Missing") for row in rows], 0
    hits = scan_current_pdfs(job_folder)
    by_key: dict[str, PdfHit] = {}
    for hit in hits:
        key = hit.drawing_id.casefold()
        previous = by_key.get(key)
        if previous is None or hit.path.stat().st_mtime >= previous.path.stat().st_mtime:
            by_key[key] = hit
    used: set[str] = set()
    matched: list[MatchedRow] = []
    for row in rows:
        hit = None
        for key in match_keys(row.drawing_id, job_number or row.job_number):
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
    orphans = sum(1 for key in by_key if key not in used)
    return matched, orphans
