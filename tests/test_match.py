# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.jobs import _is_job_folder, find_job_folder
from doccon.match import attach_pdfs, compact_drawing_id, parse_pdf_stem, scan_current_pdfs
from doccon.register import DrawingRow


def test_parse_pdf_stem() -> None:
    drawing_id, rev = parse_pdf_stem("2026-075-STWD REV 0")
    assert drawing_id == "2026-075-STWD"
    assert rev == "0"


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


def test_find_job_folder_none_in_empty_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("doccon.jobs.Path.home", lambda: tmp_path)
    assert find_job_folder("2026-096") is None
