# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Project Execution Plan in 7.0 Sales — cover TO/CC and project line."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook

from doccon.jobs import find_job_folder

SALES_DIR = Path("7.0 Sales")
PEP_SHEET = "C-109.5"
DOC_CONTROL_FROM = "doc.control@eliteintegrityservices.com"
_EMPTY_NAMES = {"", "tbd", "n/a", "na", "nil", "none", "xxx"}
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_REV_RE = re.compile(r"(?:rev|r)\s*(\d+)", re.I)
_EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
_PEP_SUFFIXES = _EXCEL_SUFFIXES | {".pdf"}


class PepError(ValueError):
    """Raised when the PEP cannot be found or read."""


@dataclass(frozen=True)
class PepCover:
    path: Path
    from_address: str
    to_line: str
    cc_line: str
    project_description: str
    client: str
    site: str
    tank_tag: str
    po: str
    wo: str

    @property
    def filled(self) -> bool:
        return bool(self.to_line or _usable(self.client))


def find_pep(
    job_folder: Path,
    job_number: str,
    *,
    leftover_names: set[str] | None = None,
) -> Path | None:
    """Highest-Rev PEP for this job in 7.0 Sales, or a filled sandbox copy.

    Skips blank C-109.5 and leftover files that still have the jobs-template name.
    Returns None when the operator should locate a file.
    """
    sales = Path(job_folder) / SALES_DIR
    if not sales.is_dir():
        return None
    leftovers = leftover_names if leftover_names is not None else template_pep_filenames()
    job = job_number.strip()
    ranked: list[tuple[int, int, int, Path]] = []
    try:
        children = list(sales.iterdir())
    except OSError:
        return None
    for child in children:
        if not _looks_like_pep_file(child):
            continue
        if child.name in leftovers and child.suffix.casefold() == ".pdf":
            continue
        try:
            cover = load_pep(child)
        except PepError:
            continue
        if not cover.filled:
            continue
        ranked.append(
            (
                _score_pep(child, job, cover),
                _rev_from_name(child.name),
                int(child.suffix.casefold() in _EXCEL_SUFFIXES),
                child,
            )
        )
    if not ranked:
        return None
    job_ranked = [item for item in ranked if _job_in_filename(item[3].name, job)]
    pool = job_ranked or ranked
    pool.sort(key=lambda item: (item[0], item[1], item[2], item[3].name.casefold()), reverse=True)
    return pool[0][3]


def load_pep(path: Path) -> PepCover:
    file_path = Path(path)
    if not file_path.is_file():
        raise PepError(f"PEP not found: {file_path}")
    excel = _excel_for(file_path)
    if excel is not None:
        return _load_excel(excel)
    if file_path.suffix.casefold() == ".pdf":
        return _load_pdf(file_path)
    raise PepError(f"{file_path.name} is not a PEP Excel or PDF.")


_LEFTOVER_PEP_NAMES: set[str] | None = None


def template_pep_filenames() -> set[str]:
    """Names of template PEP files. Cached so Load does not walk every job folder again."""
    global _LEFTOVER_PEP_NAMES
    if _LEFTOVER_PEP_NAMES is not None:
        return set(_LEFTOVER_PEP_NAMES)
    names: set[str] = set()
    for token in ("202X-0XX", "202X-XXX"):
        folder = find_job_folder(token)
        if folder is None:
            continue
        sales = folder / SALES_DIR
        if not sales.is_dir():
            continue
        try:
            for child in sales.iterdir():
                if _looks_like_pep_file(child):
                    names.add(child.name)
        except OSError:
            continue
    _LEFTOVER_PEP_NAMES = set(names)
    return set(names)


def empty_pep_workbook() -> Workbook:
    """C-109.5 layout for tests (not the Elite branded form)."""
    wb = Workbook()
    ws = wb.active
    ws.title = PEP_SHEET
    ws["A1"] = "202X-XXX"
    ws["A11"] = "Client:"
    ws["A13"] = "Purchase Order No.:"
    ws["A14"] = "Work Order No. / MOC No.:"
    ws["A15"] = "Tank Reference No.:"
    ws["A19"] = "Site Location (LSD):"
    ws["A35"] = "Elite Project Manager:"
    ws["G35"] = "Elite Project Engineer:"
    ws["A50"] = "Transmittal Recipients:"
    ws["C50"] = "Main:"
    ws["C51"] = "CC's:"
    return wb


def _excel_for(path: Path) -> Path | None:
    if path.suffix.casefold() in _EXCEL_SUFFIXES:
        return path
    if path.suffix.casefold() != ".pdf":
        return None
    for suffix in (".xlsx", ".xlsm"):
        sibling = path.with_suffix(suffix)
        if sibling.is_file():
            return sibling
    return None


def _load_excel(path: Path) -> PepCover:
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:
        raise PepError(f"Could not open PEP {path.name}.") from exc
    try:
        ws = wb[PEP_SHEET] if PEP_SHEET in wb.sheetnames else wb.worksheets[0]
        client = _cell_text(ws["C11"].value)
        site = _collapse(_cell_text(ws["C19"].value))
        tank = _cell_text(ws["C15"].value)
        po = _cell_text(ws["C13"].value)
        wo = _cell_text(ws["C14"].value)
        to_line = _format_emails(_cell_text(ws["D50"].value))
        cc_emails = _format_emails(_cell_text(ws["D51"].value))
        pm = _cell_text(ws["C35"].value)
        pe = _cell_text(ws["I35"].value)
        cc_line = _cc_line(cc_emails, pm, pe)
        job_cell = _cell_text(ws["A1"].value)
        if job_cell.lower().startswith("insert elite job number") and not client and not to_line:
            raise PepError(f"{path.name} is a blank PEP template.")
        return PepCover(
            path=path,
            from_address=DOC_CONTROL_FROM,
            to_line=to_line,
            cc_line=cc_line,
            project_description=_project_line(client, site, tank, po, wo),
            client=client,
            site=site,
            tank_tag=tank,
            po=po,
            wo=wo,
        )
    finally:
        wb.close()


def _load_pdf(path: Path) -> PepCover:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PepError(f"{path.name} is a PDF. Locate the PEP Excel (C-109.5) instead.") from exc
    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise PepError(f"Could not read PEP PDF {path.name}.") from exc
    folded = text.casefold()
    if "project execution" not in folded and "transmittal recipients" not in folded and "c-109.5" not in folded:
        raise PepError(f"{path.name} does not look like a Project Execution Plan.")
    to_line = ""
    match = re.search(r"Transmittal Recipients:\s*(.+)", text, re.I)
    if match:
        to_line = _format_emails(match.group(1))
    if not to_line:
        to_line = _format_emails(text)
    client_match = re.search(r"PROJECT SUMMARY DETAILS\s*([A-Za-z][A-Za-z0-9 .&'/-]*)", text, re.I)
    client = _collapse(client_match.group(1) if client_match else "")
    client = _collapse(client.split("Quote")[0] if client else "")
    site = _pdf_after(text, "Site Location (LSD):")
    if not site:
        lsd = re.search(r"([A-Za-z][A-Za-z .]+,\s*\d{2}-\d{2}-\d{3}-\d{2}-W\d)", text)
        site = _collapse(lsd.group(1) if lsd else "")
    tank = _pdf_after(text, "Tank Reference No.:")
    po = _pdf_after(text, "Purchase Order No.:")
    if not po:
        po_match = re.search(r"\b(\d{7,})\b", text)
        po = po_match.group(1) if po_match else ""
    wo = _pdf_after(text, "Work Order No. / MOC No.:")
    pm = _pdf_after(text, "Elite Project Manager:")
    pe = _pdf_after(text, "Elite Project Engineer:")
    if not _usable(client) and not to_line:
        raise PepError(f"Could not read Transmittal Recipients from {path.name}.")
    return PepCover(
        path=path,
        from_address=DOC_CONTROL_FROM,
        to_line=to_line,
        cc_line=_cc_line("", pm, pe),
        project_description=_project_line(client, site, tank, po, wo),
        client=client,
        site=site,
        tank_tag=tank,
        po=po,
        wo=wo,
    )


def _pdf_after(text: str, label: str) -> str:
    match = re.search(re.escape(label) + r"\s*([^\n]*)", text, re.I)
    if not match:
        return ""
    token = _collapse(match.group(1))
    if token.casefold() in _EMPTY_NAMES:
        return ""
    return token


def _looks_like_pep_file(path: Path) -> bool:
    if not path.is_file() or path.name.startswith("~$"):
        return False
    if path.suffix.casefold() not in _PEP_SUFFIXES:
        return False
    name = path.name.casefold()
    return (
        "project execution plan" in name
        or "c-109.5" in name
        or re.search(r"\bpep\b", name) is not None
        or name.endswith(" pep.pdf")
        or " pep." in name
    )


def _job_in_filename(name: str, job: str) -> bool:
    token = job.strip()
    if not token:
        return False
    return token.casefold() in name.casefold()


def _rev_from_name(name: str) -> int:
    match = _REV_RE.search(name)
    if match:
        return int(match.group(1))
    return 0


def _score_pep(path: Path, job: str, cover: PepCover) -> int:
    score = 0
    if _job_in_filename(path.name, job):
        score += 100
    if path.suffix.casefold() in _EXCEL_SUFFIXES:
        score += 20
    if cover.to_line:
        score += 10
    if _usable(cover.client):
        score += 5
    return score


def _project_line(client: str, site: str, tank: str, po: str, wo: str) -> str:
    return (
        f"{_na(client)} | Loc: {_na(site)} | Ref. Tag: {_na(tank)} | "
        f"PO#: {_na(po)} | WO#/MOC#: {_na(wo)}"
    )


def _cc_line(cc_emails: str, pm: str, pe: str) -> str:
    return _format_emails("; ".join(part for part in (cc_emails, pm, pe) if part))


def email_line(text: str) -> str:
    """TO/CC as unique email addresses, semicolon separated."""
    return _format_emails(text)


def _format_emails(text: str) -> str:
    seen: list[str] = []
    found: set[str] = set()
    for match in _EMAIL_RE.findall(text or ""):
        addr = match.strip().rstrip(">").strip()
        key = addr.casefold()
        if key in found:
            continue
        found.add(key)
        seen.append(addr)
    return "; ".join(seen)


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.casefold() in _EMPTY_NAMES:
        return ""
    return _collapse(text)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def _usable(text: str) -> bool:
    token = (text or "").strip()
    if not token:
        return False
    return token.casefold() not in _EMPTY_NAMES


def _na(text: str) -> str:
    return text.strip() if _usable(text) else "N/A"
