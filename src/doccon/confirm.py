# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Confirm: preflight everything, then Jira, then the transmittal file."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from doccon.client_log import (
    ClientBook,
    LogError,
    file_client_transmittal,
    inspect_book,
)
from doccon.drop_pdfs import delete_pack_dropped_copies
from doccon.eddi import eddi_print_drawings, snapshot_eddi
from doccon.excel_pdf import export_sheet_pdf
from doccon.jira_client import (
    JiraError,
    apply_jira_updates,
    preflight_jira_updates,
    revert_drawing_update,
)
from doccon.kinds import CLIENT, SHOP
from doccon.match import MatchedRow
from doccon.pack_mail import (
    attach_pdfs,
    attachment_note,
    display_outlook_draft,
    draft_body,
    draft_subject,
    mail_attachments,
    write_drawings_zip,
)
from doccon.pep import PepCover
from doccon.register import DrawingRow, FieldOption
from doccon.shop_place import MISSING_SHOP_FOLDER, place_shop_form, place_shop_pdf


class ConfirmDeliveryError(LogError):
    """Jira and the Excel tab were saved; PDF or Outlook then failed."""

    def __init__(self, message: str, *, cover_id: str, attach_note: str, pdf_note: str) -> None:
        super().__init__(message)
        self.cover_id = cover_id
        self.attach_note = attach_note
        self.pdf_note = pdf_note


@dataclass(frozen=True)
class ConfirmResult:
    cover_id: str
    attach_note: str
    pdf_note: str
    jira_written: bool


def preflight_client_file(
    book: Path,
    job: str,
    rows: list[MatchedRow],
    kind: str = CLIENT,
    extra_pdfs: list[Path] | None = None,
) -> ClientBook:
    info = inspect_book(book, job, kind)
    tab = str(info.next_number)
    if tab in info.filed_tabs:
        raise LogError(
            f"{Path(book).name} already has a tab named {tab}. Confirm aborted; nothing was written."
        )
    extras = [Path(path) for path in (extra_pdfs or [])]
    missing = next((path for path in extras if not path.is_file()), None)
    if missing is not None:
        raise LogError(f"Missing {missing.name}. Confirm aborted; nothing was written.")
    if not attach_pdfs(rows, extras):
        raise LogError("No drawing PDFs to zip. Locate PDFs first. Confirm aborted; nothing was written.")
    return info


def run_confirm_client_pack(
    *,
    site: str,
    email: str,
    token: str,
    pairs: list[tuple[DrawingRow, DrawingRow]],
    book: Path,
    job: str,
    lines,
    issued: date,
    expected_return: date | str | None,
    cover: PepCover,
    rows: list[MatchedRow],
    kind: str = CLIENT,
    job_folder: Path | None = None,
    eddi_drawings: list[DrawingRow] | None = None,
    eddi_contexts: dict[str, tuple[FieldOption, ...]] | None = None,
    extra_pdfs: list[Path] | None = None,
    shop_root: Path | None = None,
    shop_copies: list[tuple[Path, str]] | None = None,
) -> ConfirmResult:
    """Check that every write can succeed, then Jira, then file. Abort leaves no tab."""
    if kind == SHOP and (shop_root is None or not Path(shop_root).is_dir()):
        raise LogError(MISSING_SHOP_FOLDER)
    if kind == SHOP:
        _preflight_shop_copies(Path(shop_root), shop_copies or [])
    if pairs:
        preflight_jira_updates(site, email, token, pairs, eddi_contexts)
    log_job = preflight_client_file(book, job, rows, kind, extra_pdfs).job_number
    jira_written = False
    filed = False
    cover_id = ""
    note = ""
    pdf_note = ""
    try:
        if pairs:
            apply_jira_updates(site, email, token, pairs, eddi_contexts)
            jira_written = True
        result = file_client_transmittal(
            book,
            log_job,
            lines,
            issued=issued,
            expected_return=expected_return,
            cover=cover,
            kind=kind,
        )
        filed = True
        cover_id = result.cover_id
        pdf_path = book.parent / f"{cover_id}.pdf"
        try:
            export_sheet_pdf(result.book, result.sheet_name, pdf_path)
            pdf_note = f"PDF: {pdf_path.name}"
        except LogError as exc:
            pdf_note = str(exc)
        eddi_note = _eddi_snapshot_note(
            job_folder,
            job,
            eddi_drawings if eddi_drawings is not None else eddi_print_drawings(rows),
            issued,
        )
        if eddi_note:
            pdf_note = f"{pdf_note}\n{eddi_note}".strip() if pdf_note else eddi_note
        zip_path: Path | None = None
        if kind == SHOP:
            try:
                _copy_shop_pack(Path(shop_root), shop_copies or [], pdf_path)
            except LogError as exc:
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, but could not copy the shop PDFs. "
                    f"Do not Confirm again.\n{exc}",
                    cover_id=cover_id,
                    attach_note=attachment_note([]),
                    pdf_note=pdf_note,
                ) from exc
            pdf_note = f"{pdf_note}\nShop copies: {Path(shop_root).name}".strip()
        else:
            pdfs = attach_pdfs(rows, extra_pdfs or [])
            zip_path = book.parent / f"{cover_id}.zip"
            try:
                write_drawings_zip(
                    zip_path,
                    pdfs,
                    exclude=pdf_path if pdf_path.is_file() else None,
                )
            except LogError as exc:
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, but could not zip the drawing PDFs. "
                    "Do not Confirm again. Attach the files in Outlook by hand.\n"
                    f"{exc}",
                    cover_id=cover_id,
                    attach_note=attachment_note([]),
                    pdf_note=pdf_note,
                ) from exc
        files = mail_attachments(pdf_path if pdf_path.is_file() else None, zip_path)
        note = attachment_note(files)
        if not files:
            raise ConfirmDeliveryError(
                f"Filed {cover_id} and wrote Jira, but there were no files to attach. "
                "Do not Confirm again. Attach the PDFs in Outlook by hand.",
                cover_id=cover_id,
                attach_note=note,
                pdf_note=pdf_note,
            )
        display_outlook_draft(
            to_line=cover.to_line,
            cc_line=cover.cc_line,
            subject=draft_subject(cover_id, log_job),
            body=draft_body(
                cover_id=cover_id,
                project=cover.project_description,
                rows=rows,
            ),
            attachments=files,
            require_to=kind == CLIENT,
        )
        delete_pack_dropped_copies(rows)
        return ConfirmResult(
            cover_id=cover_id,
            attach_note=note,
            pdf_note=pdf_note,
            jira_written=jira_written,
        )
    except ConfirmDeliveryError:
        raise
    except Exception as exc:
        if filed:
            raise ConfirmDeliveryError(
                f"Filed {cover_id} and wrote Jira, but the pack did not finish. "
                f"Do not Confirm again.\n{exc}",
                cover_id=cover_id,
                attach_note=note or attachment_note([]),
                pdf_note=pdf_note,
            ) from exc
        if jira_written:
            try:
                _rollback_jira(site, email, token, pairs, eddi_contexts)
            except JiraError as rev:
                raise JiraError(f"{exc}\n{rev}") from exc
        raise


def _rollback_jira(
    site: str,
    email: str,
    token: str,
    pairs: list[tuple[DrawingRow, DrawingRow]],
    eddi_contexts: dict[str, tuple[FieldOption, ...]] | None = None,
) -> None:
    errors: list[str] = []
    for current, nxt in reversed(pairs):
        key = (nxt.key or current.key or "").strip()
        try:
            revert_drawing_update(
                site, email, token, current, nxt, (eddi_contexts or {}).get(key, ())
            )
        except JiraError as exc:
            errors.append(f"{nxt.key or current.key}: {exc}")
    if errors:
        raise JiraError(
            "Confirm aborted and the transmittal was not filed, but Jira rollback failed: "
            + "; ".join(errors)
        )


def _preflight_shop_copies(shop_root: Path, copies: list[tuple[Path, str]]) -> None:
    from doccon.shop_place import ROOT_FOLDER

    for source, label in copies:
        if not Path(source).is_file():
            raise LogError(f"Missing {Path(source).name}. Confirm aborted; nothing was written.")
        folder = (label or ROOT_FOLDER).strip() or ROOT_FOLDER
        dest = shop_root if folder.casefold() == ROOT_FOLDER.casefold() else shop_root / folder
        if not dest.is_dir():
            raise LogError(f"{folder} is not in {shop_root.name}. Confirm aborted; nothing was written.")


def _copy_shop_pack(shop_root: Path, copies: list[tuple[Path, str]], form: Path) -> None:
    for source, label in copies:
        place_shop_pdf(shop_root, label, Path(source))
    if form.is_file():
        place_shop_form(shop_root, form)


def _eddi_snapshot_note(
    job_folder: Path | None,
    job: str,
    drawings: list[DrawingRow],
    issued: date,
) -> str:
    if job_folder is None:
        return "EDDI: skipped (job folder not found)."
    try:
        snap = snapshot_eddi(
            job_folder,
            job,
            drawings,
            issued,
        )
        return snap.note
    except LogError as exc:
        return f"EDDI: {exc}"
    except OSError as exc:
        return f"EDDI: {exc}"
    except Exception as exc:
        return f"EDDI: {exc}"
