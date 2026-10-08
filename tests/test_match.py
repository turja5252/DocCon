# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.jobs import _is_job_folder, find_job_folder
from doccon.match import (
    MatchedRow,
    PdfHit,
    attach_pdfs,
    compact_drawing_id,
    match_keys,
    outgoing_rev_from_filename,
    pair_unmatched,
    parse_pdf_stem,
    scan_current_pdfs,
    wps_library_roots,
)
from doccon.register import DrawingRow


def test_parse_pdf_stem() -> None:
    drawing_id, rev = parse_pdf_stem("2026-075-STWD REV 0")
    assert drawing_id == "2026-075-STWD"
    assert rev == "0"


def test_parse_eis_procedure_stem() -> None:
    assert parse_pdf_stem("EIS-1 (Rev 4)") == ("EIS-1", "4")
    assert parse_pdf_stem("EIS-10 (REV 0)") == ("EIS-10", "0")
    assert parse_pdf_stem("EIS-12 (Rev.3)") == ("EIS-12", "3")
    assert parse_pdf_stem("EIS-13 (Rev. 1)") == ("EIS-13", "1")
    assert parse_pdf_stem("EIS-2-LT (Rev.0)") == ("EIS-2-LT", "0")
    assert parse_pdf_stem("EIS-6SS (Rev 0)") == ("EIS-6SS", "0")


def test_outgoing_rev_from_filename() -> None:
    assert outgoing_rev_from_filename("2026-075-STWD REV 0.pdf") == "0"
    assert outgoing_rev_from_filename("2025-124-1-TL REV 0.pdf") == "0"
    assert outgoing_rev_from_filename("ITP-2026-075-1-1 REV 0 Signed.pdf") == "0"
    assert outgoing_rev_from_filename("EIS-1 (Rev 4).pdf") == "4"
    assert outgoing_rev_from_filename("scan0042.pdf") == ""
    assert outgoing_rev_from_filename("") == ""


def test_compact_stair_id() -> None:
    assert compact_drawing_id("2026-075-1-STWD", "2026-075") == "2026-075-STWD"


def test_compact_leaves_numeric_sheet() -> None:
    assert compact_drawing_id("2026-096-1-1", "2026-096") == "2026-096-1-1"


def test_is_job_folder() -> None:
    assert _is_job_folder("2026-096 Borouge (103TK001 Manway)", "2026-096")
    assert not _is_job_folder("2026-0960 Extra", "2026-096")


def test_scan_skips_void(tmp_path: Path) -> None:
    current = tmp_path / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    void = current / "2.1.1.1 Void"
    current.mkdir(parents=True)
    void.mkdir()
    (current / "2026-075-STWD REV 0.pdf").write_bytes(b"%PDF")
    (void / "2026-075-STWD REV A.pdf").write_bytes(b"%PDF")
    hits = scan_current_pdfs(tmp_path)
    assert len(hits) == 1
    assert hits[0].rev == "0"


def test_attach_high_and_missing(tmp_path: Path) -> None:
    current = tmp_path / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    (current / "2026-075-STWD REV 0.pdf").write_bytes(b"%PDF")
    rows = [
        DrawingRow(
            key="P2024-1",
            summary="2026-075-1-STWD SPIRAL",
            drawing_id="2026-075-1-STWD",
            title="SPIRAL",
            status="IFC",
            job_number="2026-075",
            outgoing_rev="0",
            purpose="Info",
            parent_summary="Drawing Package",
        ),
        DrawingRow(
            key="P2024-2",
            summary="2026-075-1-ZZZ MISSING",
            drawing_id="2026-075-1-ZZZ",
            title="MISSING",
            status="To Do",
            job_number="2026-075",
            outgoing_rev="",
            purpose="",
            parent_summary="Drawing Package",
        ),
    ]
    matched, orphans = attach_pdfs(rows, tmp_path, "2026-075")
    assert matched[0].confidence == "High"
    assert matched[0].pdf is not None and matched[0].pdf.rev == "0"
    assert matched[1].confidence == "Missing"
    assert orphans == 0


def test_scan_finds_engineering_and_quality_pdfs(tmp_path: Path) -> None:
    (tmp_path / "1.0 Engineering").mkdir()
    (tmp_path / "1.0 Engineering" / "MR-2026-075-1-1 REV 0.pdf").write_bytes(b"%PDF")
    shop = tmp_path / "4.0 Quality" / "4.3 ITP & WO" / "6.3.1 Shop"
    shop.mkdir(parents=True)
    (shop / "ITP-2026-075-1-1 REV 0 Signed.pdf").write_bytes(b"%PDF")
    void = tmp_path / "4.0 Quality" / "4.3 ITP & WO" / "void"
    void.mkdir()
    (void / "ITP-2026-075-1-1 REV A.pdf").write_bytes(b"%PDF")
    (tmp_path / "4.0 Quality" / "4.7 Welding").mkdir(parents=True)
    (tmp_path / "4.0 Quality" / "4.7 Welding" / "WS-2026-075-1 REV A.pdf").write_bytes(b"%PDF")
    procedures = tmp_path / "4.0 Quality" / "4.4 Third Party Doc Shop" / "4.4.1 Weld Procedures"
    procedures.mkdir(parents=True)
    (procedures / "WPS-2026-075-1 REV 0.pdf").write_bytes(b"%PDF")
    hits = {hit.drawing_id: hit for hit in scan_current_pdfs(tmp_path)}
    assert "MR-2026-075-1-1" in hits
    assert "ITP-2026-075-1-1" in hits
    assert hits["ITP-2026-075-1-1"].rev.startswith("0")
    assert "WS-2026-075-1" in hits
    assert "WPS-2026-075-1" in hits
    assert all("void" not in hit.path.as_posix().casefold() for hit in hits.values())


def test_attach_itp_and_weld_summary(tmp_path: Path) -> None:
    shop = tmp_path / "4.0 Quality" / "4.3 ITP & WO" / "6.3.2 Field"
    shop.mkdir(parents=True)
    (shop / "ITP-2026-075-1-2 REV 0 Signed.pdf").write_bytes(b"%PDF")
    (tmp_path / "4.0 Quality" / "4.7 Welding").mkdir(parents=True)
    (tmp_path / "4.0 Quality" / "4.7 Welding" / "WS-2026-075-1 REV A.pdf").write_bytes(b"%PDF")
    rows = [
        DrawingRow(
            key="P2024-10",
            summary="ITP-2026-075-1-2 Field ITP",
            drawing_id="ITP-2026-075-1-2",
            title="Field ITP",
            status="To Do",
            job_number="2026-075",
            outgoing_rev="0",
            purpose="Info",
            parent_summary="QC",
        ),
        DrawingRow(
            key="P2024-11",
            summary="2026-075-1 Weld Summary",
            drawing_id="2026-075-1",
            title="Weld Summary",
            status="To Do",
            job_number="2026-075",
            outgoing_rev="A",
            purpose="Info",
            parent_summary="QC",
        ),
    ]
    matched, _orphans = attach_pdfs(rows, tmp_path, "2026-075")
    assert matched[0].confidence == "High"
    assert matched[0].pdf is not None and "ITP-2026-075-1-2" in matched[0].pdf.path.name
    assert matched[1].confidence == "High"
    assert matched[1].pdf is not None and matched[1].pdf.path.name.startswith("WS-")


def test_pair_and_apply_located_pdf(tmp_path: Path) -> None:
    from doccon.match import MatchedRow, apply_located_pdfs, pair_pdf
    from doccon.register import DrawingRow

    pdf = tmp_path / "2026-Tanzim-ITP REV 0.pdf"
    pdf.write_bytes(b"%PDF")
    row = MatchedRow(
        drawing=DrawingRow(
            key="P2024-9",
            summary="2026-Tanzim-ITP ITP-1",
            drawing_id="2026-Tanzim-ITP",
            title="ITP-1",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="",
            purpose="",
            parent_summary="QC",
        ),
        pdf=None,
        confidence="Missing",
    )
    paired = pair_pdf(row, pdf)
    assert paired.confidence == "High"
    assert paired.pdf is not None and paired.pdf.path == pdf
    restored = apply_located_pdfs([row], {"P2024-9": str(pdf)})
    assert restored[0].confidence == "High"
    skipped = apply_located_pdfs([row], {"P2024-9": str(tmp_path / "gone.pdf")})
    assert skipped[0].confidence == "Missing"


def test_match_keys_picks_eis_from_title() -> None:
    keys = match_keys("WPS", "2026-075", title="EIS-1 SMAW", summary="WPS EIS-1")
    assert "eis-1" in keys


def test_wps_library_roots_finds_shared_folder(monkeypatch, tmp_path: Path) -> None:
    dropbox = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    lib = dropbox / "4.4 QC" / "4.4.1 WPS&PQR"
    lib.mkdir(parents=True)
    job = dropbox / "2.1 Current Jobs" / "2026-Tanzim"
    job.mkdir(parents=True)
    monkeypatch.setattr("doccon.match.local_team_dropbox_member_roots", lambda hint=None: [dropbox])
    roots = wps_library_roots(hint=job)
    assert roots == [lib]


def test_scan_shared_wps_library(monkeypatch, tmp_path: Path) -> None:
    dropbox = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    lib = dropbox / "4.4 QC" / "4.4.1 WPS&PQR"
    voids = lib / "VOIDS"
    old = lib / "Old Procedures"
    nested = lib / "ABSA Registered"
    for folder in (lib, voids, old, nested):
        folder.mkdir(parents=True, exist_ok=True)
    root_pdf = lib / "EIS-1 (Rev 4).pdf"
    root_pdf.write_bytes(b"%PDF")
    (lib / "EIS-10 (REV 0).pdf").write_bytes(b"%PDF")
    (voids / "EIS-1 (Rev 1).pdf").write_bytes(b"%PDF")
    (old / "EIS-1 (Rev 2).pdf").write_bytes(b"%PDF")
    (nested / "EIS-1 (Rev 3).pdf").write_bytes(b"%PDF")
    job = dropbox / "2.1 Current Jobs" / "2026-Tanzim"
    job.mkdir(parents=True)
    monkeypatch.setattr("doccon.match.wps_library_roots", lambda hint=None: [lib])
    hits = scan_current_pdfs(job)
    assert all("void" not in hit.path.as_posix().casefold() for hit in hits)
    assert all("Old Procedures" not in hit.path.parts for hit in hits)
    assert any(hit.path == root_pdf and hit.rev == "4" and hit.library for hit in hits)
    rows = [
        DrawingRow(
            key="P2024-20",
            summary="EIS-1 SMAW Procedure",
            drawing_id="EIS-1",
            title="SMAW Procedure",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="4",
            purpose="Info",
            parent_summary="Welding",
        )
    ]
    matched, orphans = attach_pdfs(rows, job, "2026-Tanzim")
    assert matched[0].pdf is not None and matched[0].pdf.path == root_pdf
    assert orphans == 0


def test_attach_wps_from_shared_library(monkeypatch, tmp_path: Path) -> None:
    lib = tmp_path / "4.4.1 WPS&PQR"
    lib.mkdir()
    (lib / "EIS-1 (Rev 4).pdf").write_bytes(b"%PDF")
    (lib / "EIS-10 (REV 0).pdf").write_bytes(b"%PDF")
    monkeypatch.setattr("doccon.match.wps_library_roots", lambda hint=None: [lib])
    job = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir" / "2.1 Current Jobs" / "2026-Tanzim"
    job.mkdir(parents=True)
    leftover = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    leftover.mkdir(parents=True)
    (leftover / "2026-075-ORPHAN REV 0.pdf").write_bytes(b"%PDF")
    rows = [
        DrawingRow(
            key="P2024-20",
            summary="EIS-1 SMAW Procedure",
            drawing_id="EIS-1",
            title="SMAW Procedure",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="4",
            purpose="Info",
            parent_summary="Welding",
        ),
        DrawingRow(
            key="P2024-21",
            summary="WPS Field weld procedure",
            drawing_id="WPS",
            title="EIS-1 SMAW",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="4",
            purpose="Info",
            parent_summary="Welding",
        ),
    ]
    matched, orphans = attach_pdfs(rows, job, "2026-Tanzim")
    assert matched[0].confidence == "High"
    assert matched[0].pdf is not None and matched[0].pdf.path.name == "EIS-1 (Rev 4).pdf"
    assert matched[1].confidence == "High"
    assert orphans == 1


def test_find_job_folder_none_in_empty_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("doccon.jobs.Path.home", lambda: tmp_path)
    assert find_job_folder("2026-096") is None


def test_pair_unmatched_keeps_a_file_already_on_the_row(tmp_path: Path) -> None:
    kept = tmp_path / "kept.pdf"
    kept.write_bytes(b"%PDF")
    hunt = tmp_path / "2026-Tanzim-1-2 REV 0.pdf"
    hunt.write_bytes(b"%PDF")
    located = MatchedRow(
        drawing=DrawingRow(
            key="P2024-1",
            summary="2026-Tanzim-1-1 Drawing",
            drawing_id="2026-Tanzim-1-1",
            title="Drawing",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="0",
            purpose="",
            parent_summary="Drawing Package",
        ),
        pdf=PdfHit(path=kept, drawing_id="2026-Tanzim-1-1", rev="0"),
        confidence="High",
    )
    missing = MatchedRow(
        drawing=DrawingRow(
            key="P2024-2",
            summary="2026-Tanzim-1-2 Drawing",
            drawing_id="2026-Tanzim-1-2",
            title="Drawing",
            status="To Do",
            job_number="2026-Tanzim",
            outgoing_rev="",
            purpose="",
            parent_summary="Drawing Package",
        ),
        pdf=None,
        confidence="Missing",
    )
    paired = pair_unmatched(
        [located, missing],
        [PdfHit(path=hunt, drawing_id="2026-Tanzim-1-2", rev="0")],
        "2026-Tanzim",
    )
    assert paired[0].pdf is not None and paired[0].pdf.path == kept
    assert paired[1].pdf is not None and paired[1].pdf.path == hunt
