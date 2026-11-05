# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Confirm: preflight everything, then Jira, then the transmittal file.

The Outlook draft opens before the dated EDDI prints. The EDDI is not attached,
so the operator can check the email while that last Excel step runs.

When the preview is still the letter being filed, Confirm saves the book the
preview filed and files the PDF it printed, so Excel does not start until the
EDDI. A drawing zip too large for the draft is written after the draft opens.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from doccon.client_log import (
    ClientBook,
    FileClientResult,
    LetterPreview,
    LogError,
    file_client_transmittal,
    inspect_book,
    letter_inputs,
)
from doccon.diag import log
from doccon.drop_pdfs import delete_pack_dropped_copies
from doccon.eddi import eddi_full_drawings, eddi_print_drawings, snapshot_eddi
from doccon.excel_pdf import export_sheet_pdf, place_filed_book, place_printed_pdf
from doccon.jira_client import (
    JiraError,
    apply_jira_updates,
    preflight_jira_updates,
    revert_drawing_update,
)
from doccon.kinds import CLIENT, FIELD, PREFIX, SHOP
from doccon.match import MatchedRow
from doccon.pack_mail import (
    attach_pdfs,
    attachment_note,
    display_outlook_draft,
    draft_body,
    draft_subject,
    load_mail_formats,
    mail_attachments,
    mail_kind_key,
    mail_pack_for_outlook,
    write_drawings_zip,
    zip_cannot_attach,
)
from doccon.pep import PepCover
from doccon.register import DrawingRow, FieldOption
from doccon.field_place import (
    IFC_DIR,
    MISSING_FIELD_FOLDER,
    field_destination,
    field_ifc_dir,
    place_field_form,
    place_field_pdf,
)
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
    full_drawings: list[DrawingRow] | None = None,
    eddi_contexts: dict[str, tuple[FieldOption, ...]] | None = None,
    extra_pdfs: list[Path] | None = None,
    shop_root: Path | None = None,
    shop_copies: list[tuple[Path, str]] | None = None,
    field_root: Path | None = None,
    field_copies: list[Path] | None = None,
    urgent: bool = False,
    skip_eddi: bool = False,
    keep_dropped: bool = False,
    letter: LetterPreview | None = None,
    on_step=None,
    mail=None,
    mail_subject: str = "",
    mail_body: str = "",
) -> ConfirmResult:
    """Check that every write can succeed, then Jira, then file. Abort leaves no tab.

    ``letter`` is the PDF Create transmittal showed. It is filed as the cover PDF
    when the book and the letter are unchanged; otherwise the filed tab prints again.
    """

    def step(name: str) -> None:
        log("INFO", "confirm", f"step={name}")
        if on_step is not None:
            on_step(name)

    if kind == SHOP and (shop_root is None or not Path(shop_root).is_dir()):
        raise LogError(MISSING_SHOP_FOLDER)
    if kind == SHOP:
        _preflight_shop_copies(Path(shop_root), shop_copies or [])
    if kind == FIELD and (field_root is None or not Path(field_root).is_dir()):
        raise LogError(MISSING_FIELD_FOLDER)
    if kind == FIELD:
        _preflight_field_copies(Path(field_root), field_copies or [])
    transitions: dict = {}
    if pairs:
        step("jira_check")
        transitions = preflight_jira_updates(site, email, token, pairs, eddi_contexts) or {}
    step("log_check")
    book_info = preflight_client_file(book, job, rows, kind, extra_pdfs)
    log_job = book_info.job_number
    jira_written = False
    filed = False
    cover_id = ""
    note = ""
    pdf_note = ""
    eddi_pending = not skip_eddi

    def record_eddi() -> str:
        """Print the dated EDDI and the Full EDDI once the transmittal is filed. Never raises."""
        nonlocal eddi_pending
        if not eddi_pending:
            return ""
        eddi_pending = False
        try:
            step("eddi")
            return eddi_snapshot_note(
                job_folder,
                job,
                eddi_drawings if eddi_drawings is not None else eddi_print_drawings(rows),
                issued,
                full_drawings if full_drawings is not None else eddi_full_drawings(rows),
                lambda: step("eddi_full"),
            )
        except Exception as exc:
            return f"EDDI: {exc}"

    try:
        if pairs:
            step("jira_write")
            apply_jira_updates(site, email, token, pairs, eddi_contexts, transitions=transitions)
            jira_written = True
        reuse = _reusable_letter(
            letter,
            book,
            letter_inputs(
                job,
                lines,
                issued=issued,
                expected_return=expected_return,
                cover=cover,
                kind=kind,
                urgent=urgent,
            ),
        )
        step("file")
        result = _file_from_preview(
            reuse,
            book,
            lines,
            cover_id=f"{PREFIX.get(kind, 'CT')}-{log_job}-{book_info.next_number}",
            tab=str(book_info.next_number),
        )
        if result is None:
            result = file_client_transmittal(
                book,
                log_job,
                lines,
                issued=issued,
                expected_return=expected_return,
                cover=cover,
                kind=kind,
                urgent=urgent,
            )
        filed = True
        cover_id = result.cover_id
        pdf_path = book.parent / f"{cover_id}.pdf"
        try:
            step("pdf")
            _print_letter(result, pdf_path, reuse)
            pdf_note = f"PDF: {pdf_path.name}"
        except LogError as exc:
            pdf_note = str(exc)
        zip_path: Path | None = None
        zip_exclude: Path | None = None
        zip_after_draft = False
        pdfs: list[Path] = []
        if kind == SHOP:
            try:
                step("shop")
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
        elif kind == FIELD:
            try:
                step("field")
                _copy_field_pack(Path(field_root), field_copies or [], pdf_path)
            except LogError as exc:
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, but could not copy the field PDFs. "
                    f"Do not Confirm again.\n{exc}",
                    cover_id=cover_id,
                    attach_note=attachment_note([]),
                    pdf_note=pdf_note,
                ) from exc
            pdf_note = f"{pdf_note}\nField copies: {Path(field_root).name}".strip()
        else:
            pdfs = attach_pdfs(rows, extra_pdfs or [])
            zip_path = book.parent / f"{cover_id}.zip"
            zip_exclude = pdf_path if pdf_path.is_file() else None
            # Too large for the draft even zipped: the draft opens first, then the zip.
            zip_after_draft = zip_cannot_attach(zip_exclude, pdfs)
            if zip_after_draft:
                log("INFO", "zip", f"{zip_path.name} cannot go on the draft; it is written after the draft opens")
            else:
                try:
                    step("zip")
                    write_drawings_zip(zip_path, pdfs, exclude=zip_exclude)
                except LogError as exc:
                    raise ConfirmDeliveryError(
                        f"Filed {cover_id} and wrote Jira, but could not zip the drawing PDFs. "
                        "Do not Confirm again. Attach the files in Outlook by hand.\n"
                        f"{exc}",
                        cover_id=cover_id,
                        attach_note=attachment_note([]),
                        pdf_note=pdf_note,
                    ) from exc
        cover_file = pdf_path if pdf_path.is_file() else None
        if zip_after_draft and zip_path is not None:
            files, held_zip = mail_attachments(cover_file, None), Path(zip_path).resolve()
        else:
            files, held_zip = mail_pack_for_outlook(cover_file, zip_path)
        note = attachment_note(files, held_zip=held_zip)

        def zip_late() -> None:
            """Write the zip the draft left off. Stored, not compressed: it is not mailed."""
            nonlocal note
            step("zip_after_draft")
            write_drawings_zip(Path(zip_path), pdfs, exclude=zip_exclude, store=True)
            note = attachment_note(files, held_zip=held_zip)

        if not files:
            raise ConfirmDeliveryError(
                f"Filed {cover_id} and wrote Jira, but there were no files to attach. "
                "Do not Confirm again. Attach the PDFs in Outlook by hand.",
                cover_id=cover_id,
                attach_note=note,
                pdf_note=pdf_note,
            )
        wording = load_mail_formats().get(mail_kind_key(kind), ("", ""))
        subject_template = mail_subject or wording[0]
        body_template = mail_body or wording[1]

        def open_draft(attach: list[Path], left_off: Path | None) -> None:
            display_outlook_draft(
                to_line=cover.to_line,
                cc_line=cover.cc_line,
                subject=draft_subject(cover_id, log_job, template=subject_template, facts=mail),
                body=draft_body(
                    cover_id=cover_id,
                    project=cover.project_description,
                    rows=rows,
                    job=log_job,
                    template=body_template,
                    facts=mail,
                    held_zip=left_off,
                ),
                attachments=attach,
                require_to=kind == CLIENT,
            )

        step("outlook")
        try:
            open_draft(files, held_zip)
        except LogError as exc:
            form_only = _form_without_zip(files, zip_path)
            if held_zip is not None or not form_only:
                detail = str(exc)
                if zip_after_draft:
                    # She mails it by hand, so the zip to share still has to exist.
                    try:
                        zip_late()
                    except LogError as zip_exc:
                        detail = f"{detail}\nCould not zip the drawing PDFs either: {zip_exc}"
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, but the Outlook draft did not open. "
                    f"Do not Confirm again.\n{detail}",
                    cover_id=cover_id,
                    attach_note=note,
                    pdf_note=pdf_note,
                ) from exc
            held_zip = Path(zip_path).resolve()
            files = form_only
            note = attachment_note(files, held_zip=held_zip)
            try:
                open_draft(files, held_zip)
            except LogError as retry_exc:
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, but the Outlook draft did not open. "
                    f"Do not Confirm again.\n{exc}",
                    cover_id=cover_id,
                    attach_note=note,
                    pdf_note=pdf_note,
                ) from retry_exc
        if zip_after_draft:
            try:
                zip_late()
            except LogError as exc:
                raise ConfirmDeliveryError(
                    f"Filed {cover_id} and wrote Jira, and the draft is open, but could not zip the "
                    "drawing PDFs. Do not Confirm again. Zip them by hand, share that zip, and paste "
                    f"the link into the draft before Send.\n{exc}",
                    cover_id=cover_id,
                    attach_note=note,
                    pdf_note=pdf_note,
                ) from exc
        pdf_note = _joined(pdf_note, record_eddi())
        if not keep_dropped:
            delete_pack_dropped_copies(rows)
        return ConfirmResult(
            cover_id=cover_id,
            attach_note=note,
            pdf_note=pdf_note,
            jira_written=jira_written,
        )
    except ConfirmDeliveryError as exc:
        if filed:
            exc.pdf_note = _joined(exc.pdf_note, record_eddi())
        raise
    except Exception as exc:
        if filed:
            pdf_note = _joined(pdf_note, record_eddi())
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


def _form_without_zip(files: list[Path], zip_path: Path | None) -> list[Path]:
    """The transmittal form, when the zip was part of a failed Outlook attach."""
    if zip_path is None or not Path(zip_path).is_file():
        return []
    held = str(Path(zip_path).resolve()).casefold()
    form = [path for path in files if str(Path(path).resolve()).casefold() != held]
    if len(form) == len(files):
        return []
    return form


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


def _field_copy(item: Path | tuple) -> tuple[Path, str]:
    if isinstance(item, tuple):
        label = str(item[1]).strip() if len(item) > 1 else ""
        return Path(item[0]), label
    return Path(item), ""


def _preflight_field_copies(field_root: Path, copies: list[Path] | list[tuple[Path, str]]) -> None:
    if not field_ifc_dir(field_root).is_dir():
        raise LogError(f"{IFC_DIR} is not in {field_root.name}. Confirm aborted; nothing was written.")
    for item in copies:
        source, label = _field_copy(item)
        if not source.is_file():
            raise LogError(f"Missing {source.name}. Confirm aborted; nothing was written.")
        if not label:
            continue
        dest = field_destination(field_root, label)
        if not dest.is_dir():
            raise LogError(f"{label} is not in {field_root.name}. Confirm aborted; nothing was written.")


def _copy_field_pack(field_root: Path, copies: list[Path] | list[tuple[Path, str]], form: Path) -> None:
    for item in copies:
        source, label = _field_copy(item)
        place_field_pdf(field_root, source, label)
    if form.is_file():
        place_field_form(field_root, form)


def _joined(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _reusable_letter(
    letter: LetterPreview | None,
    book: Path,
    inputs: tuple,
) -> LetterPreview | None:
    """The preview PDF, when it is the letter Confirm is about to file. Checked before filing."""
    if letter is None:
        return None
    try:
        reason = letter.stale_reason(book, inputs)
    except Exception as exc:
        reason = f"could not compare ({exc})"
    if reason:
        log("INFO", "letter", f"printing again at Confirm: {reason}")
        return None
    return letter


def _file_from_preview(
    letter: LetterPreview | None,
    book: Path,
    lines,
    *,
    cover_id: str,
    tab: str,
) -> FileClientResult | None:
    """Save the book the preview filed, so Excel does not file the same tab again.

    ``letter`` has already passed _reusable_letter: same book, unchanged since the
    preview, same letter. It must also have filed the tab this book files next.
    None means file in Excel.
    """
    if letter is None or letter.filed_book is None or not letter.sheet_name:
        return None
    if letter.cover_id != cover_id or letter.sheet_name != tab:
        log(
            "INFO",
            "file",
            f"filing in Excel: book files {cover_id} tab {tab}, "
            f"preview filed {letter.cover_id} tab {letter.sheet_name}",
        )
        return None
    filed = Path(letter.filed_book)
    if not filed.is_file():
        log("INFO", "file", "filing in Excel: the preview's filed book is gone")
        return None
    try:
        place_filed_book(filed, Path(book))
    except LogError:
        raise
    except OSError as exc:
        if not Path(book).is_file():
            raise LogError(f"Could not save {Path(book).name}.\n{exc}") from exc
        log("WARN", "file", f"could not reuse the preview's filed book, filing in Excel: {exc}")
        return None
    return FileClientResult(
        book=Path(book),
        cover_id=letter.cover_id,
        sheet_name=letter.sheet_name,
        line_count=len(lines),
        pdf_path=None,
    )


def _print_letter(result: FileClientResult, pdf_path: Path, letter: LetterPreview | None) -> None:
    """File the preview PDF when it matches the filed tab; otherwise print the tab."""
    if letter is not None and letter.cover_id != result.cover_id:
        log(
            "INFO",
            "letter",
            f"printing again at Confirm: filed {result.cover_id}, preview was {letter.cover_id}",
        )
        letter = None
    if letter is not None:
        try:
            place_printed_pdf(letter.pdf, pdf_path)
            return
        except LogError:
            # The cover PDF in the folder is locked. Printing again would hit the same lock.
            raise
        except Exception as exc:
            log("WARN", "letter", f"could not reuse the preview, printing again: {exc}")
    export_sheet_pdf(result.book, result.sheet_name, pdf_path)


def eddi_snapshot_note(
    job_folder: Path | None,
    job: str,
    drawings: list[DrawingRow],
    issued: date,
    full_drawings: list[DrawingRow] | None = None,
    on_full=None,
) -> str:
    """Print the dated EDDI and the Full EDDI. Never raises; the note says what happened."""
    if job_folder is None:
        return "EDDI: skipped (job folder not found)."
    try:
        snap = snapshot_eddi(
            job_folder,
            job,
            drawings,
            issued,
            full_drawings=full_drawings,
            on_full=on_full,
        )
        return snap.note
    except LogError as exc:
        return f"EDDI: {exc}"
    except OSError as exc:
        return f"EDDI: {exc}"
    except Exception as exc:
        return f"EDDI: {exc}"
