# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from datetime import date
from pathlib import Path

import pytest

from doccon.client_log import LogError, empty_client_workbook
from doccon.confirm import preflight_client_file, run_confirm_client_pack
from doccon.match import MatchedRow
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


def _cover(path: Path) -> PepCover:
    return PepCover(
        path=path,
        from_address=DOC_CONTROL_FROM,
        to_line="client@example.com",
        cc_line="",
        project_description="Test",
        client="Client",
        site="",
        tank_tag="",
        po="",
        wo="",
    )


def test_preflight_file_aborts_without_pdfs(tmp_path: Path) -> None:
    book = tmp_path / "CT-2026-Tanzim.xlsx"
    wb = empty_client_workbook()
    wb.save(book)
    rows = [MatchedRow(drawing=_drawing(), pdf=None, confidence="Missing")]
    with pytest.raises(LogError, match="nothing was written"):
        preflight_client_file(book, "2026-Tanzim", rows)


def test_confirm_preflight_does_not_write(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    wrote: list[str] = []
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "preflight_client_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LogError("blocked")),
    )
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **_kwargs: wrote.append("jira"))
    monkeypatch.setattr(
        confirm, "file_client_transmittal", lambda *_args, **_kwargs: wrote.append("file")
    )
    with pytest.raises(LogError, match="blocked"):
        run_confirm_client_pack(
            site="https://example.atlassian.net",
            email="a@b.c",
            token="token",
            pairs=[(_drawing(), _drawing(outgoing_rev="B"))],
            book=tmp_path / "CT-2026-Tanzim.xlsm",
            job="2026-Tanzim",
            lines=[],
            issued=date(2026, 9, 9),
            expected_return="N/A",
            cover=_cover(tmp_path / "pep.xlsx"),
            rows=[MatchedRow(drawing=_drawing(), pdf=None, confidence="Missing")],
        )
    assert wrote == []


def test_confirm_rolls_back_jira_if_file_fails(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.client_log import ClientBook

    reverted: list[str] = []
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "preflight_client_file",
        lambda *_args, **_kwargs: ClientBook(
            path=tmp_path / "CT-2026-Tanzim.xlsm",
            job_number="2026-Tanzim",
            next_number=1,
            filed_tabs=(),
        ),
    )
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "file_client_transmittal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LogError("excel busy")),
    )
    monkeypatch.setattr(
        confirm,
        "revert_drawing_update",
        lambda _site, _email, _token, _current, nxt: reverted.append(nxt.key),
    )
    with pytest.raises(LogError, match="excel busy"):
        run_confirm_client_pack(
            site="https://example.atlassian.net",
            email="a@b.c",
            token="token",
            pairs=[(_drawing(), _drawing(outgoing_rev="B"))],
            book=tmp_path / "CT-2026-Tanzim.xlsm",
            job="2026-Tanzim",
            lines=[],
            issued=date(2026, 9, 9),
            expected_return="N/A",
            cover=_cover(tmp_path / "pep.xlsx"),
            rows=[MatchedRow(drawing=_drawing(), pdf=None, confidence="Missing")],
        )
    assert reverted == ["P2024-1"]


def _succeeding_file(monkeypatch, tmp_path: Path):
    from doccon import confirm
    from doccon.client_log import ClientBook, FileClientResult

    book = tmp_path / "CT-2026-Tanzim.xlsm"
    book.write_bytes(b"book")
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "preflight_client_file",
        lambda *_args, **_kwargs: ClientBook(
            path=book,
            job_number="2026-Tanzim",
            next_number=1,
            filed_tabs=(),
        ),
    )
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "file_client_transmittal",
        lambda *_args, **_kwargs: FileClientResult(
            book=book,
            cover_id="CT-2026-Tanzim-1",
            sheet_name="TRANSMITTAL",
            line_count=1,
            pdf_path=None,
        ),
    )

    def fake_export(_book, _sheet, dest):
        Path(dest).write_bytes(b"%PDF")
        return Path(dest)

    monkeypatch.setattr(confirm, "export_sheet_pdf", fake_export)
    return book


def test_confirm_eddi_note_is_not_attached(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.eddi import EddiSnapshot
    from doccon.match import PdfHit

    _succeeding_file(monkeypatch, tmp_path)
    drawing_pdf = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
    drawing_pdf.write_bytes(b"%PDF")
    mailed: dict = {}
    seen: dict = {}

    def fake_snapshot(_folder, _job, drawings, _issued, **_kwargs):
        seen["count"] = len(drawings)
        pdf = tmp_path / "3.0 Doc Con" / "EDDI-2026-Tanzim-2026-09-09.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF")
        return EddiSnapshot(book=pdf.with_suffix(".xlsx"), pdf=pdf, updated_rows=len(drawings))

    monkeypatch.setattr(confirm, "snapshot_eddi", fake_snapshot)
    monkeypatch.setattr(
        confirm,
        "display_outlook_draft",
        lambda **kwargs: mailed.update(kwargs),
    )
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[(_drawing(), _drawing(outgoing_rev="B"))],
        book=tmp_path / "CT-2026-Tanzim.xlsm",
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=[
            MatchedRow(
                drawing=_drawing(),
                pdf=PdfHit(path=drawing_pdf, drawing_id="2026-Tanzim-1-1", rev="A"),
                confidence="High",
            )
        ],
        job_folder=tmp_path,
        eddi_drawings=[
            _drawing(),
            _drawing(key="P2024-3", drawing_id="EIS-1", title="WPS"),
        ],
    )
    assert seen["count"] == 2
    assert "EDDI-2026-Tanzim-2026-09-09.pdf" in result.pdf_note
    names = [Path(str(item)).name for item in mailed.get("attachments") or []]
    assert "EDDI-2026-Tanzim-2026-09-09.pdf" not in names
    assert "CT-2026-Tanzim-1.pdf" in names
    assert "CT-2026-Tanzim-1.zip" in names
    assert "2026-Tanzim-1-1 REV A.pdf" not in names
    zipped = tmp_path / "CT-2026-Tanzim-1.zip"
    from zipfile import ZipFile

    with ZipFile(zipped) as archive:
        assert "2026-Tanzim-1-1 REV A.pdf" in archive.namelist()
        assert "CT-2026-Tanzim-1.pdf" not in archive.namelist()


def test_confirm_eddi_failure_still_mails(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.match import PdfHit

    _succeeding_file(monkeypatch, tmp_path)
    drawing_pdf = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
    drawing_pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(
        confirm,
        "snapshot_eddi",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LogError("eddi locked")),
    )
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[(_drawing(), _drawing(outgoing_rev="B"))],
        book=tmp_path / "CT-2026-Tanzim.xlsm",
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=[
            MatchedRow(
                drawing=_drawing(),
                pdf=PdfHit(path=drawing_pdf, drawing_id="2026-Tanzim-1-1", rev="A"),
                confidence="High",
            )
        ],
        job_folder=tmp_path,
    )
    assert "eddi locked" in result.pdf_note
    assert result.jira_written

