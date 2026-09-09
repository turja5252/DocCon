# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from doccon.client_log import (
    CLIENT_OUT,
    LogError,
    LogLine,
    client_status_from_jira,
    empty_client_workbook,
    file_client_transmittal,
    fill_client_transmittal,
    find_client_book,
    inspect_client_book,
    lines_from_rows,
    pages_needed,
    parse_expected_return,
    parse_issued_date,
    prepare_client_book,
)
from doccon.match import MatchedRow, PdfHit
from doccon.pep import DOC_CONTROL_FROM, PepCover
from doccon.register import DrawingRow


def _drawing(**kwargs) -> DrawingRow:
    values = {
        "key": "P2024-1",
        "summary": "2026-Tanzim-1-1 Drawing-1",
        "drawing_id": "2026-Tanzim-1-1",
        "title": "Drawing-1",
        "status": "To Do",
        "job_number": "2026-Tanzim",
        "outgoing_rev": "A",
        "purpose": "Approval",
        "parent_summary": "Drawing Package",
    }
    values.update(kwargs)
    return DrawingRow(**values)


def test_status_maps_jira_purpose() -> None:
    assert client_status_from_jira("Approval") == "APPROVAL"
    assert client_status_from_jira("Info") == "INFORMATION"
    assert client_status_from_jira("") == "APPROVAL"


def test_pages_needed() -> None:
    assert pages_needed(1) == 1
    assert pages_needed(18) == 1
    assert pages_needed(19) == 2
    assert pages_needed(80) == 3


def test_lines_prefer_pdf_rev() -> None:
    drawing = _drawing(outgoing_rev="A")
    hit = PdfHit(path=Path("2026-Tanzim-1-1 REV 0.pdf"), drawing_id="2026-Tanzim-1-1", rev="0")
    lines = lines_from_rows([MatchedRow(drawing=drawing, pdf=hit, confidence="High")])
    assert lines[0].rev == "0"
    assert lines[0].status == "APPROVAL"


def test_find_prefers_named_book(tmp_path: Path) -> None:
    out = tmp_path / CLIENT_OUT
    out.mkdir(parents=True)
    (out / "CT-202X-XXX.xlsm").write_bytes(b"old")
    wanted = out / "CT-2026-Tanzim.xlsm"
    wanted.write_bytes(b"new")
    assert find_client_book(tmp_path, "2026-Tanzim") == wanted


def test_prepare_renames_template_book(tmp_path: Path) -> None:
    out = tmp_path / CLIENT_OUT
    out.mkdir(parents=True)
    template = out / "CT-202X-XXX.xlsm"
    template.write_bytes(b"book")
    dest = prepare_client_book(tmp_path, "2026-Tanzim")
    assert dest.name == "CT-2026-Tanzim.xlsm"
    assert dest.is_file()
    assert not template.exists()


def test_file_client_copies_tab_and_bumps_number(tmp_path: Path) -> None:
    path = tmp_path / "CT-2026-Tanzim.xlsx"
    empty_client_workbook().save(path)
    lines = [
        LogLine("2026-Tanzim-1-1", "A", "Drawing-1", "APPROVAL"),
        LogLine("2026-Tanzim-1-2", "A", "Drawing-2", "APPROVAL"),
    ]
    result = file_client_transmittal(path, "2026-Tanzim", lines, issued=date(2026, 9, 1))
    assert result.cover_id == "CT-2026-Tanzim-1"
    assert result.sheet_name == "1"
    wb = load_workbook(path)
    assert wb.sheetnames[0] == "TRANSMITTAL"
    assert "1" in wb.sheetnames
    filed = wb["1"]
    assert filed["A12"].value == "2026-Tanzim"
    assert filed["A15"].value == "2026-Tanzim-1-1"
    assert filed["C15"].value == "Drawing-1"
    assert filed["D15"].value == "APPROVAL"
    working = wb["TRANSMITTAL"]
    assert working["A2"].value == 2
    assert working["A15"].value is None
    wb.close()
    inspect = inspect_client_book(path, "2026-Tanzim")
    assert inspect.next_number == 2
    assert inspect.filed_tabs == ("1",)
    second = file_client_transmittal(
        path,
        "2026-Tanzim",
        [LogLine("2026-Tanzim-1-2", "0", "Drawing-2", "CONSTRUCTION")],
        issued=date(2026, 9, 2),
    )
    assert second.cover_id == "CT-2026-Tanzim-2"
    wb = load_workbook(path)
    assert wb.sheetnames[:3] == ["TRANSMITTAL", "2", "1"]
    wb.close()


def test_fill_writes_working_sheet_without_archive(tmp_path: Path) -> None:
    path = tmp_path / "CT-2026-Tanzim.xlsx"
    empty_client_workbook().save(path)
    pep = tmp_path / "pep.xlsx"
    cover = PepCover(
        path=pep,
        from_address=DOC_CONTROL_FROM,
        to_line="client@example.com",
        cc_line="pm@eliteintegrityservices.com",
        project_description="Client | Loc: Site | Ref. Tag: TK1 | PO#: 1 | WO#/MOC#: N/A",
        client="Client",
        site="Site",
        tank_tag="TK1",
        po="1",
        wo="",
    )
    result = fill_client_transmittal(
        path,
        "2026-Tanzim",
        [LogLine("2026-Tanzim-1-1", "A", "Drawing-1", "APPROVAL")],
        issued=date(2026, 9, 1),
        expected_return=date(2026, 9, 15),
        cover=cover,
    )
    assert result.cover_id == "CT-2026-Tanzim-1"
    assert result.sheet_name == "TRANSMITTAL"
    wb = load_workbook(path)
    assert wb.sheetnames == ["TRANSMITTAL"]
    working = wb["TRANSMITTAL"]
    assert working["A2"].value == 1
    assert working["A15"].value == "2026-Tanzim-1-1"
    assert working["C4"].value == DOC_CONTROL_FROM
    assert working["C12"].value.date() == date(2026, 9, 1)
    assert working["D12"].value.date() == date(2026, 9, 15)
    wb.close()
    inspect = inspect_client_book(path, "2026-Tanzim")
    assert inspect.next_number == 1
    assert inspect.filed_tabs == ()


def test_refuses_wrong_job_book(tmp_path: Path) -> None:
    path = tmp_path / "CT-2026-075.xlsx"
    wb = empty_client_workbook()
    wb["TRANSMITTAL"]["A12"] = "2026-075"
    wb.save(path)
    wb.close()
    try:
        inspect_client_book(path, "2026-Tanzim")
        raise AssertionError("should refuse")
    except LogError as exc:
        assert "2026-075" in str(exc)


def test_file_real_template_copy_if_sandbox_exists(tmp_path: Path) -> None:
    # Filing a real .xlsm goes through Excel COM; skip in pytest (close the CT book first).
    return


def test_file_writes_pep_cover_and_return_date(tmp_path: Path) -> None:
    path = tmp_path / "CT-2026-Tanzim.xlsx"
    empty_client_workbook().save(path)
    pep = tmp_path / "2026-075 Project Execution Plan Rev2.xlsx"
    cover = PepCover(
        path=pep,
        from_address=DOC_CONTROL_FROM,
        to_line="glen.philips@interpipeline.com; rick.jondreau@outlook.com",
        cc_line="breydon@eliteintegrityservices.com",
        project_description=(
            "IPL | Loc: Kerrobert SK, 02-34-033-22-W3 | Ref. Tag: TK9 | PO#: 4000072534 | WO#/MOC#: N/A"
        ),
        client="IPL",
        site="Kerrobert SK, 02-34-033-22-W3",
        tank_tag="TK9",
        po="4000072534",
        wo="",
    )
    file_client_transmittal(
        path,
        "2026-Tanzim",
        [LogLine("2026-Tanzim-1-1", "A", "Drawing-1", "APPROVAL")],
        issued=date(2026, 9, 1),
        expected_return=date(2026, 9, 15),
        cover=cover,
    )
    wb = load_workbook(path)
    filed = wb["1"]
    assert filed["C4"].value == DOC_CONTROL_FROM
    assert filed["C6"].value == cover.to_line
    assert filed["C8"].value == cover.cc_line
    assert filed["A10"].value == cover.project_description
    assert filed["C12"].value.date() == date(2026, 9, 1)
    assert filed["D12"].value.date() == date(2026, 9, 15)
    working = wb["TRANSMITTAL"]
    assert working["C12"].value is None
    assert working["D12"].value is None
    wb.close()


def test_parse_dates() -> None:
    assert parse_issued_date("2026-09-01") == date(2026, 9, 1)
    assert parse_issued_date("") == date.today()
    assert parse_expected_return("") == "N/A"
    assert parse_expected_return("As soon as able") == "As soon as able"
    assert parse_expected_return("2026-09-15") == date(2026, 9, 15)
