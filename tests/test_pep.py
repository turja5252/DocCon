# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.pep import (
    DOC_CONTROL_FROM,
    SALES_DIR,
    PepError,
    email_line,
    empty_pep_workbook,
    find_pep,
    load_pep,
)


def _write_pep(
    path: Path,
    *,
    job: str = "2026-075",
    client: str = "IPL",
    site: str = "Kerrobert SK,  02-34-033-22-W3",
    tank: str = "TK9",
    po: object = 4000072534,
    wo: str = "",
    to_line: str = "glen.philips@interpipeline.com rick.jondreau@outlook.com",
    cc_line: str = "",
    pm: str = "Breydon",
    pe: str = "TBD",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = empty_pep_workbook()
    ws = wb["C-109.5"]
    ws["A1"] = job
    ws["C11"] = client
    ws["C13"] = po
    ws["C14"] = wo
    ws["C15"] = tank
    ws["C19"] = site
    ws["C35"] = pm
    ws["I35"] = pe
    ws["D50"] = to_line
    ws["D51"] = cc_line
    wb.save(path)
    wb.close()
    return path


def test_load_pep_formats_cover(tmp_path: Path) -> None:
    path = _write_pep(tmp_path / "2026-075 Project Execution Plan Rev2.xlsx")
    cover = load_pep(path)
    assert cover.from_address == DOC_CONTROL_FROM
    assert cover.to_line == "glen.philips@interpipeline.com; rick.jondreau@outlook.com"
    assert cover.cc_line == ""
    assert cover.project_description == (
        "IPL | Loc: Kerrobert SK, 02-34-033-22-W3 | Ref. Tag: TK9 | PO#: 4000072534 | WO#/MOC#: N/A"
    )


def test_email_line_keeps_addresses_only() -> None:
    assert email_line("Elite: Client Contact (PM) ; Blake Rancier; extra@x.com") == "extra@x.com"
    assert email_line("a@x.com; a@x.com, b@y.com") == "a@x.com; b@y.com"


def test_cc_keeps_emails_from_pep_cells(tmp_path: Path) -> None:
    path = _write_pep(
        tmp_path / "pep.xlsx",
        cc_line="cc@client.com",
        pm="Breydon breydon@eliteintegrityservices.com",
        pe="TBD",
    )
    cover = load_pep(path)
    assert cover.cc_line == "cc@client.com; breydon@eliteintegrityservices.com"


def test_blank_template_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "C-109.5 Project Execution Plan.xlsx"
    wb = empty_pep_workbook()
    wb["C-109.5"]["A1"] = "Insert Elite Job Number (i.e. 2019-001)"
    wb.save(path)
    wb.close()
    try:
        load_pep(path)
        raise AssertionError("should reject blank PEP")
    except PepError as exc:
        assert "blank" in str(exc).casefold()


def test_find_prefers_job_highest_rev_excel(tmp_path: Path) -> None:
    sales = tmp_path / SALES_DIR
    _write_pep(sales / "2026-075 Project Execution Plan Rev1.xlsx", to_line="old@x.com")
    wanted = _write_pep(sales / "2026-075 Project Execution Plan Rev2.xlsx")
    _write_pep(sales / "2026-096 Project Execution Plan.xlsx", job="2026-096", client="Borouge", to_line="other@x.com")
    found = find_pep(tmp_path, "2026-075", leftover_names=set())
    assert found == wanted


def test_sandbox_uses_copied_pep(tmp_path: Path) -> None:
    sales = tmp_path / SALES_DIR
    copied = _write_pep(sales / "2026-075 Project Execution Plan Rev2.xlsx")
    found = find_pep(tmp_path, "2026-Tanzim", leftover_names=set())
    assert found == copied


def test_template_leftover_pdf_is_not_auto_picked(tmp_path: Path) -> None:
    sales = tmp_path / SALES_DIR
    sales.mkdir(parents=True)
    leftover = sales / "2026-074 CNRL Lindbergh T-101 Repairs PEP.pdf"
    leftover.write_bytes(b"%PDF-1.4 leftover")
    found = find_pep(
        tmp_path,
        "2026-Tanzim",
        leftover_names={"2026-074 CNRL Lindbergh T-101 Repairs PEP.pdf"},
    )
    assert found is None


def test_load_real_075_pep_if_present() -> None:
    path = Path(
        r"c:\Users\TanzimNasir\Elite Integrity Serv Dropbox\Tanzim Nasir"
        r"\2.1 Current Jobs\2026-075 IPL (Kerrobert Tank 9 Restoration)"
        r"\7.0 Sales\2026-075 Project Execution Plan Rev2.xlsx"
    )
    if not path.is_file():
        return
    cover = load_pep(path)
    assert "glen.philips@interpipeline.com" in cover.to_line
    assert "rick.jondreau@outlook.com" in cover.to_line
    assert cover.client.strip().startswith("IPL")
    assert "4000072534" in cover.project_description
