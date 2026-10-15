# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import subprocess
from pathlib import Path

import pytest

from doccon.office_preview import OfficePreviewError, can_preview, office_to_preview_pdf


def test_preview_covers_pdf_excel_and_word() -> None:
    assert can_preview(Path("drawing.pdf"))
    assert can_preview(Path("calc.xlsx"))
    assert can_preview(Path("book.xlsm"))
    assert can_preview(Path("letter.docx"))
    assert can_preview(Path("old.doc"))
    assert not can_preview(Path("mail.msg"))
    assert not can_preview(None)


def test_a_pdf_opens_without_office(tmp_path: Path) -> None:
    pdf = tmp_path / "drawing.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert office_to_preview_pdf(pdf) == pdf


def test_excel_preview_is_printed_once_and_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "calc.xlsx"
    source.write_bytes(b"not a real workbook")
    cache = tmp_path / "cache"
    cache.mkdir()
    calls: list[list[str]] = []

    def fake_run(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        dest = Path(argv[argv.index("-Dest") + 1])
        dest.write_bytes(b"%PDF-1.4 preview")
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("doccon.office_preview.preview_cache_dir", lambda: cache)
    monkeypatch.setattr("doccon.office_preview._run", fake_run)
    first = office_to_preview_pdf(source)
    second = office_to_preview_pdf(source)
    assert first == second
    assert first.read_bytes().startswith(b"%PDF-")
    assert len(calls) == 1
    assert "excel" in calls[0]


def test_missing_word_is_a_short_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "letter.docx"
    source.write_bytes(b"not a real document")
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr("doccon.office_preview.preview_cache_dir", lambda: cache)

    def fake_run(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "80040154 Class not registered")

    monkeypatch.setattr("doccon.office_preview._run", fake_run)
    with pytest.raises(OfficePreviewError, match="Word needs to be installed"):
        office_to_preview_pdf(source)
