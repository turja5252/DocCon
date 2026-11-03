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
        lambda _site, _email, _token, _current, nxt, _options=(): reverted.append(nxt.key),
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
    steps: list[str] = []
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
        on_step=steps.append,
    )
    assert steps == [
        "jira_check",
        "log_check",
        "jira_write",
        "file",
        "pdf",
        "zip",
        "outlook",
        "eddi",
    ]
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


def _client_pack(monkeypatch, tmp_path: Path, drawing_pdf: Path):
    from doccon.match import PdfHit

    _succeeding_file(monkeypatch, tmp_path)
    drawing_pdf.write_bytes(b"%PDF-drawing")
    return [
        MatchedRow(
            drawing=_drawing(),
            pdf=PdfHit(path=drawing_pdf, drawing_id="2026-Tanzim-1-1", rev="A"),
            confidence="High",
        )
    ]


def test_confirm_leaves_an_oversized_zip_off_the_draft(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    rows = _client_pack(monkeypatch, tmp_path, tmp_path / "2026-Tanzim-1-1 REV A.pdf")
    monkeypatch.setattr(confirm, "snapshot_eddi", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("doccon.pack_mail.MAIL_ATTACH_LIMIT_BYTES", 8)
    mailed: dict = {}
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **kwargs: mailed.update(kwargs))
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[],
        book=tmp_path / "CT-2026-Tanzim.xlsm",
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=rows,
        job_folder=tmp_path,
    )
    names = [Path(str(item)).name for item in mailed["attachments"]]
    assert names == ["CT-2026-Tanzim-1.pdf"]
    assert "too large to attach" in mailed["body"]
    assert "CT-2026-Tanzim-1.zip" in mailed["body"]
    assert "Share" in result.attach_note
    assert (tmp_path / "CT-2026-Tanzim-1.zip").is_file()


def test_confirm_retries_with_the_form_when_outlook_refuses_the_zip(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    rows = _client_pack(monkeypatch, tmp_path, tmp_path / "2026-Tanzim-1-1 REV A.pdf")
    monkeypatch.setattr(confirm, "snapshot_eddi", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args, **_kwargs: "")
    calls: list[dict] = []

    def fake_draft(**kwargs):
        calls.append(kwargs)
        if any(str(path).lower().endswith(".zip") for path in kwargs["attachments"]):
            raise LogError("The file is too large")

    monkeypatch.setattr(confirm, "display_outlook_draft", fake_draft)
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[],
        book=tmp_path / "CT-2026-Tanzim.xlsm",
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=rows,
        job_folder=tmp_path,
    )
    assert len(calls) == 2
    assert [Path(str(item)).name for item in calls[1]["attachments"]] == ["CT-2026-Tanzim-1.pdf"]
    assert "too large to attach" in calls[1]["body"]
    assert "Share" in result.attach_note
    assert (tmp_path / "CT-2026-Tanzim-1.zip").is_file()


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


def test_confirm_success_deletes_packed_dropped_copies(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.drop_pdfs import write_pdf_bytes_into_dropped
    from doccon.match import PdfHit

    _succeeding_file(monkeypatch, tmp_path)
    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    current = job / "2.0 Drafting" / "2.1 Tank Const DWG" / "2.1.1 Current PDF"
    current.mkdir(parents=True)
    real = current / "2026-Tanzim-1-2 REV 0.pdf"
    real.write_bytes(b"%PDF-current")
    monkeypatch.setattr(confirm, "snapshot_eddi", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args, **_kwargs: "")
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[],
        book=tmp_path / "CT-2026-Tanzim.xlsm",
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=[
            MatchedRow(
                drawing=_drawing(),
                pdf=PdfHit(
                    path=dropped,
                    drawing_id="2026-Tanzim-1-1",
                    rev="0",
                    email_dropped=True,
                ),
                confidence="High",
            ),
            MatchedRow(
                drawing=_drawing(key="P2024-2", drawing_id="2026-Tanzim-1-2", title="Drawing-2"),
                pdf=PdfHit(path=real, drawing_id="2026-Tanzim-1-2", rev="0"),
                confidence="High",
            ),
        ],
        job_folder=job,
    )
    assert result.cover_id == "CT-2026-Tanzim-1"
    assert not dropped.exists()
    assert real.is_file()


def test_confirm_abort_does_not_delete_dropped_copies(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.drop_pdfs import write_pdf_bytes_into_dropped
    from doccon.match import PdfHit

    job = tmp_path / "2026-Tanzim"
    dropped = write_pdf_bytes_into_dropped(job, "2026-Tanzim-1-1 REV 0.pdf", b"%PDF-drop")
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "preflight_client_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LogError("blocked")),
    )
    monkeypatch.setattr(
        confirm, "apply_jira_updates", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("jira"))
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
            rows=[
                MatchedRow(
                    drawing=_drawing(),
                    pdf=PdfHit(
                        path=dropped,
                        drawing_id="2026-Tanzim-1-1",
                        rev="0",
                        email_dropped=True,
                    ),
                    confidence="High",
                )
            ],
        )
    assert dropped.is_file()


def test_field_confirm_copies_drawings_and_attaches_only_the_form(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.client_log import ClientBook, FileClientResult
    from doccon.kinds import FIELD
    from doccon.match import PdfHit

    field = tmp_path / "2026-Tanzim Field Construction Folder" / "2.0 IFC Drawings & Transmittals"
    field.mkdir(parents=True)
    (field / "2026-Tanzim-1-1 REV 0.pdf").write_bytes(b"old")
    drawing = tmp_path / "2026-Tanzim-1-1 REV 1.pdf"
    drawing.write_bytes(b"new")
    book = tmp_path / "FT-2026-Tanzim.xlsm"
    book.write_bytes(b"book")
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "preflight_client_file",
        lambda *_args, **_kwargs: ClientBook(
            path=book, job_number="2026-Tanzim", next_number=1, filed_tabs=()
        ),
    )
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        confirm,
        "file_client_transmittal",
        lambda *_args, **_kwargs: FileClientResult(
            book=book,
            cover_id="FT-2026-Tanzim-1",
            sheet_name="TRANSMITTAL",
            line_count=1,
            pdf_path=None,
        ),
    )
    monkeypatch.setattr(confirm, "export_sheet_pdf", lambda _book, _sheet, dest: Path(dest).write_bytes(b"%PDF"))
    monkeypatch.setattr(confirm, "snapshot_eddi", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args, **_kwargs: "")
    mailed: dict = {}
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **kwargs: mailed.update(kwargs))
    result = run_confirm_client_pack(
        site="https://example.atlassian.net",
        email="a@b.c",
        token="token",
        pairs=[],
        book=book,
        job="2026-Tanzim",
        lines=[],
        issued=date(2026, 9, 9),
        expected_return="N/A",
        cover=_cover(tmp_path / "pep.xlsx"),
        rows=[
            MatchedRow(
                drawing=_drawing(),
                pdf=PdfHit(path=drawing, drawing_id="2026-Tanzim-1-1", rev="1"),
                confidence="High",
            )
        ],
        kind=FIELD,
        field_root=field.parent,
        field_copies=[drawing],
    )
    names = [Path(str(item)).name for item in mailed.get("attachments") or []]
    assert names == ["FT-2026-Tanzim-1.pdf"]
    assert "Field copies:" in result.pdf_note
    assert (field / "2026-Tanzim-1-1 REV 1.pdf").read_bytes() == b"new"
    assert not (field / "2026-Tanzim-1-1 REV 0.pdf").exists()
    assert (field / "Transmittals" / "FT-2026-Tanzim-1.pdf").is_file()
    assert not (tmp_path / "FT-2026-Tanzim-1.zip").exists()


def test_field_confirm_aborts_when_the_folder_is_missing(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.kinds import FIELD

    wrote: list[str] = []
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **_kwargs: wrote.append("jira"))
    with pytest.raises(LogError, match="Field folder"):
        run_confirm_client_pack(
            site="https://example.atlassian.net",
            email="a@b.c",
            token="token",
            pairs=[],
            book=tmp_path / "FT-2026-Tanzim.xlsm",
            job="2026-Tanzim",
            lines=[],
            issued=date(2026, 9, 9),
            expected_return="N/A",
            cover=_cover(tmp_path / "pep.xlsx"),
            rows=[],
            kind=FIELD,
        )
    assert wrote == []


def _packed_row(tmp_path: Path) -> list[MatchedRow]:
    from doccon.match import PdfHit

    drawing_pdf = tmp_path / "2026-Tanzim-1-1 REV A.pdf"
    drawing_pdf.write_bytes(b"%PDF-drawing")
    return [
        MatchedRow(
            drawing=_drawing(),
            pdf=PdfHit(path=drawing_pdf, drawing_id="2026-Tanzim-1-1", rev="A"),
            confidence="High",
        )
    ]


def _confirm_client(tmp_path: Path, rows: list[MatchedRow], **kwargs):
    values = {
        "site": "https://example.atlassian.net",
        "email": "a@b.c",
        "token": "token",
        "pairs": [],
        "book": tmp_path / "CT-2026-Tanzim.xlsm",
        "job": "2026-Tanzim",
        "lines": [],
        "issued": date(2026, 9, 9),
        "expected_return": "N/A",
        "cover": _cover(tmp_path / "pep.xlsx"),
        "rows": rows,
        "job_folder": tmp_path,
    }
    values.update(kwargs)
    return run_confirm_client_pack(**values)


def test_confirm_opens_outlook_before_the_eddi(monkeypatch, tmp_path: Path) -> None:
    """The EDDI is not attached, so the draft does not wait for it."""
    from doccon import confirm

    _succeeding_file(monkeypatch, tmp_path)
    events: list[str] = []

    def fake_note(_folder, _job, _drawings, _issued):
        events.append("eddi")
        return "EDDI: EDDI 3.0 - 2026-Tanzim-2026-09-09.pdf"

    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: events.append("outlook"))
    monkeypatch.setattr(confirm, "eddi_snapshot_note", fake_note)
    monkeypatch.setattr(confirm, "delete_pack_dropped_copies", lambda _rows: events.append("delete dropped"))
    result = _confirm_client(tmp_path, _packed_row(tmp_path))
    assert events == ["outlook", "eddi", "delete dropped"]
    assert result.pdf_note.splitlines() == [
        "PDF: CT-2026-Tanzim-1.pdf",
        "EDDI: EDDI 3.0 - 2026-Tanzim-2026-09-09.pdf",
    ]


def test_confirm_prints_the_eddi_when_the_draft_does_not_open(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.confirm import ConfirmDeliveryError

    _succeeding_file(monkeypatch, tmp_path)
    printed: list[str] = []

    def no_outlook(**_kwargs):
        raise LogError("Outlook is not running")

    def fake_note(_folder, _job, _drawings, _issued):
        printed.append("eddi")
        return "EDDI: printed"

    monkeypatch.setattr(confirm, "display_outlook_draft", no_outlook)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", fake_note)
    with pytest.raises(ConfirmDeliveryError) as caught:
        _confirm_client(tmp_path, _packed_row(tmp_path))
    assert printed == ["eddi"]
    assert "EDDI: printed" in caught.value.pdf_note
    assert caught.value.cover_id == "CT-2026-Tanzim-1"


def test_confirm_prints_no_eddi_when_skipped(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    _succeeding_file(monkeypatch, tmp_path)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(
        confirm, "eddi_snapshot_note", lambda *_args: (_ for _ in ()).throw(AssertionError("eddi"))
    )
    steps: list[str] = []
    result = _confirm_client(tmp_path, _packed_row(tmp_path), skip_eddi=True, on_step=steps.append)
    assert "eddi" not in steps
    assert result.pdf_note == "PDF: CT-2026-Tanzim-1.pdf"


def _letter(tmp_path: Path, book: Path, **changes):
    from doccon.client_log import LetterPreview, book_stamp, letter_inputs
    from doccon.kinds import CLIENT

    pdf = tmp_path / "preview" / "CT-preview.pdf"
    pdf.parent.mkdir(exist_ok=True)
    pdf.write_bytes(b"%PDF-preview")
    return LetterPreview(
        pdf=pdf,
        cover_id=changes.get("cover_id", "CT-2026-Tanzim-1"),
        kind=CLIENT,
        book=book,
        stamp=book_stamp(book),
        inputs=letter_inputs(
            "2026-Tanzim",
            changes.get("lines", []),
            issued=date(2026, 9, 9),
            expected_return="N/A",
            cover=_cover(tmp_path / "pep.xlsx"),
            kind=CLIENT,
            urgent=False,
        ),
        filed_book=changes.get("filed_book"),
        sheet_name=changes.get("sheet_name", ""),
    )


def _count_exports(monkeypatch) -> list[str]:
    from doccon import confirm

    printed: list[str] = []

    def fake_export(_book, sheet, dest):
        printed.append(sheet)
        Path(dest).write_bytes(b"%PDF-printed")
        return Path(dest)

    monkeypatch.setattr(confirm, "export_sheet_pdf", fake_export)
    return printed


def test_confirm_files_the_letter_the_preview_printed(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    book = _succeeding_file(monkeypatch, tmp_path)
    printed = _count_exports(monkeypatch)
    mailed: dict = {}
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **kwargs: mailed.update(kwargs))
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    letter = _letter(tmp_path, book)
    result = _confirm_client(tmp_path, _packed_row(tmp_path), letter=letter)
    assert printed == []
    assert (tmp_path / "CT-2026-Tanzim-1.pdf").read_bytes() == b"%PDF-preview"
    assert letter.pdf.is_file()
    assert result.pdf_note == "PDF: CT-2026-Tanzim-1.pdf"
    names = [Path(str(item)).name for item in mailed["attachments"]]
    assert names == ["CT-2026-Tanzim-1.pdf", "CT-2026-Tanzim-1.zip"]


@pytest.mark.parametrize(
    "stale",
    ["book changed", "letter changed", "other cover number", "preview gone", "other book"],
)
def test_confirm_prints_again_when_the_preview_is_not_that_letter(monkeypatch, tmp_path: Path, stale: str) -> None:
    from doccon import confirm
    from doccon.client_log import LogLine

    book = _succeeding_file(monkeypatch, tmp_path)
    printed = _count_exports(monkeypatch)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    if stale == "letter changed":
        letter = _letter(tmp_path, book, lines=[LogLine("2026-Tanzim-1-1", "A", "Drawing-1", "APPROVAL")])
    elif stale == "other cover number":
        letter = _letter(tmp_path, book, cover_id="CT-2026-Tanzim-2")
    elif stale == "other book":
        other = tmp_path / "other" / book.name
        other.parent.mkdir()
        other.write_bytes(b"book")
        letter = _letter(tmp_path, other)
    else:
        letter = _letter(tmp_path, book)
    if stale == "book changed":
        book.write_bytes(b"book saved by someone else after the preview")
    if stale == "preview gone":
        letter.pdf.unlink()
    _confirm_client(tmp_path, _packed_row(tmp_path), letter=letter)
    assert printed == ["TRANSMITTAL"]
    assert (tmp_path / "CT-2026-Tanzim-1.pdf").read_bytes() == b"%PDF-printed"


def test_confirm_reports_a_locked_cover_pdf_when_reusing_the_preview(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.excel_pdf import EXCEL_PDF_LOCKED

    book = _succeeding_file(monkeypatch, tmp_path)
    printed = _count_exports(monkeypatch)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")

    def locked(_source, _dest, **_kwargs):
        raise PermissionError(13, "The process cannot access the file", None, 32)

    monkeypatch.setattr("doccon.excel_pdf.place_file", locked)
    result = _confirm_client(tmp_path, _packed_row(tmp_path), letter=_letter(tmp_path, book))
    assert printed == []
    assert EXCEL_PDF_LOCKED in result.pdf_note


def _filed_copy(tmp_path: Path) -> Path:
    """The book the preview filed, in its own folder."""
    filed = tmp_path / "preview" / "CT-2026-Tanzim.xlsm"
    filed.parent.mkdir(exist_ok=True)
    filed.write_bytes(b"book with tab 1 filed by the preview")
    return filed


def _no_excel_filing(monkeypatch) -> None:
    from doccon import confirm

    def file_in_excel(*_args, **_kwargs):
        raise AssertionError("Confirm filed the book in Excel again")

    monkeypatch.setattr(confirm, "file_client_transmittal", file_in_excel)


def test_confirm_saves_the_book_the_preview_filed(monkeypatch, tmp_path: Path) -> None:
    """No Excel at Confirm: the preview's filed copy becomes the book."""
    from doccon import confirm

    book = _succeeding_file(monkeypatch, tmp_path)
    _no_excel_filing(monkeypatch)
    printed = _count_exports(monkeypatch)
    mailed: dict = {}
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **kwargs: mailed.update(kwargs))
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    filed = _filed_copy(tmp_path)
    letter = _letter(tmp_path, book, filed_book=filed, sheet_name="1")
    steps: list[str] = []
    result = _confirm_client(tmp_path, _packed_row(tmp_path), letter=letter, on_step=steps.append)
    assert book.read_bytes() == b"book with tab 1 filed by the preview"
    assert filed.is_file()
    assert printed == []
    assert (tmp_path / "CT-2026-Tanzim-1.pdf").read_bytes() == b"%PDF-preview"
    assert result.cover_id == "CT-2026-Tanzim-1"
    assert steps[:3] == ["log_check", "file", "pdf"]
    names = [Path(str(item)).name for item in mailed["attachments"]]
    assert names == ["CT-2026-Tanzim-1.pdf", "CT-2026-Tanzim-1.zip"]


def test_confirm_files_in_excel_when_the_book_changed_after_the_preview(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    book = _succeeding_file(monkeypatch, tmp_path)
    printed = _count_exports(monkeypatch)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    letter = _letter(tmp_path, book, filed_book=_filed_copy(tmp_path), sheet_name="1")
    book.write_bytes(b"book saved by someone else after the preview")
    _confirm_client(tmp_path, _packed_row(tmp_path), letter=letter)
    assert book.read_bytes() == b"book saved by someone else after the preview"
    assert printed == ["TRANSMITTAL"]


@pytest.mark.parametrize("why", ["copy gone", "other tab"])
def test_confirm_files_in_excel_when_the_preview_book_cannot_be_used(monkeypatch, tmp_path: Path, why: str) -> None:
    from doccon import confirm

    book = _succeeding_file(monkeypatch, tmp_path)
    _count_exports(monkeypatch)
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    filed = _filed_copy(tmp_path)
    letter = _letter(tmp_path, book, filed_book=filed, sheet_name="2" if why == "other tab" else "1")
    if why == "copy gone":
        filed.unlink()
    excel: list[str] = []
    real = confirm.file_client_transmittal

    def file_in_excel(*args, **kwargs):
        excel.append("excel")
        return real(*args, **kwargs)

    monkeypatch.setattr(confirm, "file_client_transmittal", file_in_excel)
    _confirm_client(tmp_path, _packed_row(tmp_path), letter=letter)
    assert excel == ["excel"]
    assert book.read_bytes() == b"book"


def test_confirm_rolls_back_jira_when_the_book_is_locked(monkeypatch, tmp_path: Path) -> None:
    """Saving the preview's book onto an open book aborts like an Excel filing would."""
    from doccon import confirm
    from doccon.excel_pdf import BOOK_LOCKED

    book = _succeeding_file(monkeypatch, tmp_path)
    _no_excel_filing(monkeypatch)
    reverted: list[str] = []
    monkeypatch.setattr(
        confirm,
        "revert_drawing_update",
        lambda _site, _email, _token, _current, nxt, _options=(): reverted.append(nxt.key),
    )

    def locked(_source, _dest, **_kwargs):
        raise PermissionError(13, "The process cannot access the file", None, 32)

    monkeypatch.setattr("doccon.excel_pdf.place_file", locked)
    letter = _letter(tmp_path, book, filed_book=_filed_copy(tmp_path), sheet_name="1")
    with pytest.raises(LogError) as caught:
        _confirm_client(
            tmp_path,
            _packed_row(tmp_path),
            letter=letter,
            pairs=[(_drawing(), _drawing(outgoing_rev="B"))],
        )
    assert BOOK_LOCKED.splitlines()[1] in str(caught.value)
    assert reverted == ["P2024-1"]
    assert book.read_bytes() == b"book"


def test_confirm_hands_the_preflight_transitions_to_the_write(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm

    _succeeding_file(monkeypatch, tmp_path)
    kept = {"P2024-1": [{"id": "31", "name": "Send", "to": "OFA"}]}
    seen: dict = {}
    monkeypatch.setattr(confirm, "preflight_jira_updates", lambda *_args, **_kwargs: kept)
    monkeypatch.setattr(confirm, "apply_jira_updates", lambda *_args, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: None)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args: "")
    _confirm_client(tmp_path, _packed_row(tmp_path), pairs=[(_drawing(), _drawing(status="OFA"))])
    assert seen["transitions"] == kept


def _big_pack(monkeypatch, tmp_path: Path, limit: int) -> list[MatchedRow]:
    """A 12-byte drawing and a 4-byte form against a tiny mail limit."""
    from doccon import confirm

    rows = _client_pack(monkeypatch, tmp_path, tmp_path / "2026-Tanzim-1-1 REV A.pdf")
    monkeypatch.setattr(confirm, "eddi_snapshot_note", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("doccon.pack_mail.MAIL_ATTACH_LIMIT_BYTES", limit)
    return rows


def test_confirm_opens_the_draft_before_a_zip_too_large_to_attach(monkeypatch, tmp_path: Path) -> None:
    from zipfile import ZIP_STORED, ZipFile

    from doccon import confirm

    rows = _big_pack(monkeypatch, tmp_path, limit=8)
    zip_path = tmp_path / "CT-2026-Tanzim-1.zip"
    at_draft: dict = {}

    def draft(**kwargs):
        at_draft.update(kwargs)
        at_draft["zip existed"] = zip_path.exists()

    monkeypatch.setattr(confirm, "display_outlook_draft", draft)
    steps: list[str] = []
    result = _confirm_client(tmp_path, rows, on_step=steps.append)
    assert at_draft["zip existed"] is False
    assert [Path(str(item)).name for item in at_draft["attachments"]] == ["CT-2026-Tanzim-1.pdf"]
    assert "CT-2026-Tanzim-1.zip" in at_draft["body"]
    assert steps[-3:] == ["outlook", "zip_after_draft", "eddi"]
    assert "zip" not in steps
    with ZipFile(zip_path) as archive:
        [member] = archive.infolist()
        assert member.filename == "2026-Tanzim-1-1 REV A.pdf"
        assert member.compress_type == ZIP_STORED
    assert "Share" in result.attach_note
    assert f"({zip_path.stat().st_size / (1024 * 1024):.1f} MB)" in result.attach_note


def test_confirm_zips_first_when_the_pack_might_fit(monkeypatch, tmp_path: Path) -> None:
    """Half the drawings plus the form is under the limit, so the zip is measured first."""
    from zipfile import ZIP_DEFLATED, ZipFile

    from doccon import confirm

    rows = _big_pack(monkeypatch, tmp_path, limit=12)
    mailed: dict = {}
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **kwargs: mailed.update(kwargs))
    steps: list[str] = []
    result = _confirm_client(tmp_path, rows, on_step=steps.append)
    assert steps.index("zip") < steps.index("outlook")
    assert "zip_after_draft" not in steps
    with ZipFile(tmp_path / "CT-2026-Tanzim-1.zip") as archive:
        assert archive.infolist()[0].compress_type == ZIP_DEFLATED
    assert [Path(str(item)).name for item in mailed["attachments"]] == ["CT-2026-Tanzim-1.pdf"]
    assert "Share" in result.attach_note


def test_confirm_still_writes_the_large_zip_when_the_draft_does_not_open(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.confirm import ConfirmDeliveryError

    rows = _big_pack(monkeypatch, tmp_path, limit=8)
    printed: list[str] = []

    def no_outlook(**_kwargs):
        raise LogError("Outlook is not running")

    def fake_note(*_args):
        printed.append("eddi")
        return "EDDI: printed"

    monkeypatch.setattr(confirm, "display_outlook_draft", no_outlook)
    monkeypatch.setattr(confirm, "eddi_snapshot_note", fake_note)
    with pytest.raises(ConfirmDeliveryError) as caught:
        _confirm_client(tmp_path, rows)
    assert (tmp_path / "CT-2026-Tanzim-1.zip").is_file()
    assert "Outlook draft did not open" in str(caught.value)
    assert "Share" in caught.value.attach_note
    assert printed == ["eddi"]


def test_confirm_reports_a_large_zip_that_fails_after_the_draft(monkeypatch, tmp_path: Path) -> None:
    from doccon import confirm
    from doccon.confirm import ConfirmDeliveryError

    rows = _big_pack(monkeypatch, tmp_path, limit=8)
    opened: list[str] = []
    monkeypatch.setattr(confirm, "display_outlook_draft", lambda **_kwargs: opened.append("draft"))

    def no_zip(*_args, **_kwargs):
        raise LogError("disk full")

    monkeypatch.setattr(confirm, "write_drawings_zip", no_zip)
    with pytest.raises(ConfirmDeliveryError) as caught:
        _confirm_client(tmp_path, rows)
    assert opened == ["draft"]
    assert "the draft is open" in str(caught.value)
    assert "disk full" in str(caught.value)

