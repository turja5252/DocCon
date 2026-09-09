# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Client transmittal log: fill TRANSMITTAL, File Transmittal, next CT number.

Does not run the Excel macros. Replays what File Transmittal already does:
copy the working sheet to a tab named with the current number, clear the list,
increment n. Shop and Field books are not written here.
"""
from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.worksheet.worksheet import Worksheet

from doccon.jobs import find_job_folder
from doccon.kinds import CLIENT, PREFIX
from doccon.match import MatchedRow
from doccon.pep import DOC_CONTROL_FROM, PepCover
from doccon.transmittal_books import adopt_transmittal_books

CLIENT_OUT = Path("3.0 Doc Con") / "3.1 Client Transmittals" / "3.1.1 Out"
WORKING_SHEET = "TRANSMITTAL"
TEMPLATE_BOOK_NAMES = ("CT-202X-XXX.xlsm", "CT-20XX-XXX.xlsm", "CT-202X-XXX.xlsx")
PLACEHOLDER_JOBS = {"", "202X-XXX", "20XX-XXX", "202X-0XX"}

DOC_START_ROW = 15
PAGE1_LAST_ROW = 32
PAGE2_LAST_ROW = 62
PAGE3_LAST_ROW = 94
MAX_LINES = PAGE3_LAST_ROW - DOC_START_ROW + 1  # 80

CLIENT_STATUSES = ("APPROVAL", "CONSTRUCTION", "INFORMATION", "REVIEW", "AS-BUILT")


class LogError(ValueError):
    """Raised when the client book cannot be filled or filed."""


@dataclass(frozen=True)
class LogLine:
    document_no: str
    rev: str
    description: str
    status: str
    notes: str = ""


@dataclass(frozen=True)
class ClientBook:
    path: Path
    job_number: str
    next_number: int
    filed_tabs: tuple[str, ...]

    @property
    def cover_id(self) -> str:
        return f"{PREFIX[CLIENT]}-{self.job_number}-{self.next_number}"


@dataclass(frozen=True)
class FileClientResult:
    book: Path
    cover_id: str
    sheet_name: str
    line_count: int
    pdf_path: Path | None


def client_status_from_jira(purpose: str) -> str:
    token = (purpose or "").strip().casefold().replace("_", " ")
    mapping = {
        "approval": "APPROVAL",
        "info": "INFORMATION",
        "information": "INFORMATION",
        "planned": "REVIEW",
        "na": "INFORMATION",
        "n/a": "INFORMATION",
        "construction": "CONSTRUCTION",
        "review": "REVIEW",
        "as-built": "AS-BUILT",
        "as built": "AS-BUILT",
    }
    return mapping.get(token, "APPROVAL")


def lines_from_rows(rows: list[MatchedRow]) -> list[LogLine]:
    lines: list[LogLine] = []
    for row in rows:
        drawing = row.drawing
        rev = ""
        if row.pdf and row.pdf.rev:
            rev = str(row.pdf.rev).strip()
        elif drawing.outgoing_rev:
            rev = str(drawing.outgoing_rev).strip()
        lines.append(
            LogLine(
                document_no=drawing.drawing_id or drawing.key,
                rev=rev,
                description=drawing.title or drawing.summary,
                status=client_status_from_jira(drawing.purpose),
            )
        )
    return lines


def pages_needed(line_count: int) -> int:
    if line_count <= 0:
        return 1
    if line_count <= (PAGE1_LAST_ROW - DOC_START_ROW + 1):
        return 1
    if line_count <= (PAGE2_LAST_ROW - DOC_START_ROW + 1):
        return 2
    if line_count <= MAX_LINES:
        return 3
    raise LogError(f"Client transmittal holds {MAX_LINES} documents (3 pages). This pack has {line_count}.")


def find_client_book(job_folder: Path, job_number: str) -> Path | None:
    out = Path(job_folder) / CLIENT_OUT
    if not out.is_dir():
        return None
    job = job_number.strip()
    exact = out / f"CT-{job}.xlsm"
    if exact.is_file():
        return exact
    for name in TEMPLATE_BOOK_NAMES:
        candidate = out / name
        if candidate.is_file():
            return candidate
    found: list[Path] = []
    try:
        children = list(out.iterdir())
    except OSError:
        return None
    for child in children:
        if child.name.startswith("~$"):
            continue
        if child.suffix.casefold() not in {".xlsm", ".xlsx"}:
            continue
        if child.name.casefold().startswith("ct-"):
            found.append(child)
    if len(found) == 1:
        return found[0]
    return None


def template_client_book() -> Path | None:
    """Blank CT book from the jobs template — logo and Add Page / File buttons."""
    for token in ("202X-0XX", "202X-XXX"):
        folder = find_job_folder(token)
        if folder is None:
            continue
        for name in TEMPLATE_BOOK_NAMES:
            candidate = folder / CLIENT_OUT / name
            if candidate.is_file():
                return candidate
    return None


def prepare_client_book(job_folder: Path, job_number: str) -> Path:
    """Point at CT-{job}.xlsm, renaming a template book when that name is free."""
    job = job_number.strip()
    if not job:
        raise LogError("Job Number is required.")
    adopt_transmittal_books(job_folder, job)
    dest = Path(job_folder) / CLIENT_OUT / f"CT-{job}.xlsm"
    if dest.is_file():
        return dest
    found = find_client_book(job_folder, job)
    if found is None:
        raise LogError(
            f"No client transmittal book in {CLIENT_OUT}. "
            f"Expected CT-{job}.xlsm (or the blank CT-202X-XXX.xlsm from the jobs template)."
        )
    return found


def inspect_client_book(path: Path, job_number: str) -> ClientBook:
    job = job_number.strip()
    wb = load_workbook(path, data_only=False, keep_vba=path.suffix.casefold() == ".xlsm")
    try:
        if WORKING_SHEET not in wb.sheetnames:
            raise LogError(f"{path.name} has no {WORKING_SHEET} tab.")
        ws = wb[WORKING_SHEET]
        stored_job = str(ws["A12"].value or "").strip()
        if stored_job and stored_job not in PLACEHOLDER_JOBS and stored_job.casefold() != job.casefold():
            raise LogError(f"{path.name} is for job {stored_job}, not {job}.")
        next_number = _as_int(ws["A2"].value, default=1)
        filed = tuple(name for name in wb.sheetnames if name != WORKING_SHEET and _is_filed_tab(name))
    finally:
        wb.close()
    return ClientBook(path=path, job_number=job, next_number=next_number, filed_tabs=filed)


def file_client_transmittal(
    path: Path,
    job_number: str,
    lines: list[LogLine],
    *,
    issued: date | None = None,
    expected_return: date | str | None = None,
    cover: PepCover | None = None,
) -> FileClientResult:
    return _commit_client_transmittal(
        path,
        job_number,
        lines,
        issued=issued,
        expected_return=expected_return,
        cover=cover,
        archive=True,
    )


def fill_client_transmittal(
    path: Path,
    job_number: str,
    lines: list[LogLine],
    *,
    issued: date | None = None,
    expected_return: date | str | None = None,
    cover: PepCover | None = None,
) -> FileClientResult:
    """Write TRANSMITTAL only. Leave Add Page / File Transmittal for Excel."""
    return _commit_client_transmittal(
        path,
        job_number,
        lines,
        issued=issued,
        expected_return=expected_return,
        cover=cover,
        archive=False,
    )


def _commit_client_transmittal(
    path: Path,
    job_number: str,
    lines: list[LogLine],
    *,
    issued: date | None = None,
    expected_return: date | str | None = None,
    cover: PepCover | None = None,
    archive: bool,
) -> FileClientResult:
    if not lines:
        raise LogError("Select at least one drawing for this client transmittal.")
    pages = pages_needed(len(lines))
    job = job_number.strip()
    keep_vba = path.suffix.casefold() == ".xlsm"
    wb = load_workbook(path, data_only=False, keep_vba=keep_vba)
    try:
        if WORKING_SHEET not in wb.sheetnames:
            raise LogError(f"{path.name} has no {WORKING_SHEET} tab.")
        ws = wb[WORKING_SHEET]
        stored_job = str(ws["A12"].value or "").strip()
        if stored_job and stored_job not in PLACEHOLDER_JOBS and stored_job.casefold() != job.casefold():
            raise LogError(f"{path.name} is for job {stored_job}, not {job}.")
        number = _as_int(ws["A2"].value, default=1)
        sheet_name = str(number)
        if archive and sheet_name in wb.sheetnames:
            raise LogError(f"{path.name} already has a tab named {sheet_name}.")
        if path.suffix.casefold() == ".xlsm" and os.name == "nt":
            wb.close()
            from doccon.excel_pdf import file_client_with_excel

            file_client_with_excel(
                path,
                job=job,
                number=number,
                pages=pages,
                lines=lines,
                issued=issued or date.today(),
                expected_return=expected_return,
                cover=cover,
                template=template_client_book(),
                archive=archive,
            )
            cover_id = f"{PREFIX[CLIENT]}-{job}-{number}"
            return FileClientResult(
                book=path,
                cover_id=cover_id,
                sheet_name=sheet_name if archive else WORKING_SHEET,
                line_count=len(lines),
                pdf_path=None,
            )
        _write_working_sheet(
            ws,
            job=job,
            number=number,
            pages=pages,
            lines=lines,
            issued=issued or date.today(),
            expected_return=expected_return,
            cover=cover,
        )
        if archive:
            archived = wb.copy_worksheet(ws)
            archived.title = sheet_name
            _strip_action_buttons(archived)
            current_index = wb.sheetnames.index(sheet_name)
            wb.move_sheet(archived, offset=1 - current_index)
            _reset_working_sheet(ws, next_number=number + 1)
        wb.save(path)
    finally:
        with contextlib.suppress(Exception):
            wb.close()
    cover_id = f"{PREFIX[CLIENT]}-{job}-{number}"
    return FileClientResult(
        book=path,
        cover_id=cover_id,
        sheet_name=sheet_name if archive else WORKING_SHEET,
        line_count=len(lines),
        pdf_path=None,
    )


def parse_issued_date(text: str, *, default: date | None = None) -> date:
    token = (text or "").strip()
    if not token:
        return default or date.today()
    parsed = _try_date(token)
    if parsed is None:
        raise LogError(f"Date issued must be a date (for example {(default or date.today()):%Y-%m-%d}).")
    return parsed


def parse_expected_return(text: str) -> date | str:
    token = (text or "").strip()
    if not token:
        return "N/A"
    parsed = _try_date(token)
    return parsed if parsed is not None else token


def _try_date(text: str) -> date | None:
    token = text.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%b-%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _date_cell(value: date) -> datetime:
    return datetime(value.year, value.month, value.day)


def _expected_cell(value: date | str | None) -> object:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, date) and not isinstance(value, datetime):
        return _date_cell(value)
    if isinstance(value, datetime):
        return value
    return str(value)


def _write_working_sheet(
    ws: Worksheet,
    *,
    job: str,
    number: int,
    pages: int,
    lines: list[LogLine],
    issued: date,
    expected_return: date | str | None = None,
    cover: PepCover | None = None,
) -> None:
    ws["A2"] = number
    ws["A3"] = pages
    ws["A12"] = job
    _set_value(ws, "C4", DOC_CONTROL_FROM)
    if cover is not None:
        _set_value(ws, "C6", cover.to_line or None)
        _set_value(ws, "C8", cover.cc_line or None)
        _set_value(ws, "A10", cover.project_description or None)
    _set_value(ws, "C12", _date_cell(issued))
    _set_value(ws, "D12", _expected_cell(expected_return))
    last_row = PAGE3_LAST_ROW if pages >= 3 else PAGE2_LAST_ROW if pages >= 2 else PAGE1_LAST_ROW
    for row in range(DOC_START_ROW, PAGE3_LAST_ROW + 1):
        hidden = row > last_row
        ws.row_dimensions[row].hidden = hidden
        for col in range(1, 6):
            _set_value(ws, ws.cell(row, col).coordinate, None)
    for index, line in enumerate(lines):
        row = DOC_START_ROW + index
        _set_value(ws, f"A{row}", line.document_no)
        _set_value(ws, f"B{row}", _rev_value(line.rev))
        _set_value(ws, f"C{row}", line.description)
        _set_value(ws, f"D{row}", line.status)
        _set_value(ws, f"E{row}", line.notes or None)


def _reset_working_sheet(ws: Worksheet, *, next_number: int) -> None:
    ws["A2"] = next_number
    ws["A3"] = 1
    _set_value(ws, "C12", None)
    _set_value(ws, "D12", None)
    _set_value(ws, "E12", None)
    for row in range(DOC_START_ROW, PAGE3_LAST_ROW + 1):
        ws.row_dimensions[row].hidden = row > PAGE1_LAST_ROW
        for col in range(1, 6):
            _set_value(ws, ws.cell(row, col).coordinate, None)
    for row in (95, 96):
        for col in range(1, 6):
            coord = ws.cell(row, col).coordinate
            cell = ws[coord]
            if isinstance(cell, MergedCell):
                continue
            if cell.value == "GENERAL NOTES/COMMENTS":
                continue
            if row == 95 and col == 1:
                continue
            _set_value(ws, coord, None)


def _set_value(ws: Worksheet, coord: str, value: object) -> None:
    cell = ws[coord]
    if isinstance(cell, MergedCell):
        return
    cell.value = value


def _strip_action_buttons(ws: Worksheet) -> None:
    try:
        drawing = getattr(ws, "_drawing", None)
        anchors = getattr(drawing, "twoCellAnchor", None) if drawing is not None else None
        if not anchors:
            return
        keep = []
        for anchor in list(anchors):
            sp = getattr(anchor, "sp", None)
            macro = str(getattr(sp, "macro", "") or "")
            if "INSERT_PG" in macro.upper() or "counter" in macro.casefold():
                continue
            keep.append(anchor)
        if len(keep) != len(anchors):
            anchors[:] = keep
    except (AttributeError, TypeError, ValueError):
        return


def _as_int(value: object, default: int) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+", text):
        return int(text)
    return default


def _rev_value(rev: str) -> str | int | None:
    token = (rev or "").strip()
    if not token:
        return None
    if re.fullmatch(r"\d+", token):
        return int(token)
    return token


def _is_filed_tab(name: str) -> bool:
    return bool(re.fullmatch(r"\d+", name.strip()))


def empty_client_workbook() -> Workbook:
    """Minimal TRANSMITTAL layout for tests (not the Elite branded book)."""
    wb = Workbook()
    ws = wb.active
    ws.title = WORKING_SHEET
    ws["E1"] = '="CT-"&A12&"-"&A2'
    ws["A2"] = 1
    ws["A3"] = 1
    ws["C3"] = "FROM:"
    ws["C4"] = DOC_CONTROL_FROM
    ws["C5"] = "TO:"
    ws["C7"] = "CC:"
    ws["A9"] = "PROJECT DESCRIPTON:"
    ws["A11"] = "ELITE JOB NUMBER:"
    ws["C11"] = "DATE ISSUED:"
    ws["D11"] = "EXPECTED DOCUMENT RETURNED DATE:"
    ws["A12"] = "202X-XXX"
    ws["A14"] = "DOCUMENT NO."
    ws["B14"] = "REV"
    ws["C14"] = "DESCRIPTION"
    ws["D14"] = "STATUS"
    ws["E14"] = "NOTES/COMMENTS"
    ws["A95"] = "GENERAL NOTES/COMMENTS"
    return wb
