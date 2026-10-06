# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from doccon import APP_DISPLAY_NAME, __version__
from doccon.client_log import (
    BookCover,
    LogError,
    book_cover_for_job,
    cover_date_stamp,
    cover_issued_default,
    expected_return_from_issued,
    find_book,
    inspect_book,
    lines_from_extras,
    lines_from_rows,
    parse_expected_return,
    parse_issued_date,
    pick_cover_fields,
    prepare_book,
)
from doccon.clip_paste import NO_PDF_ON_CLIPBOARD, clipboard_pdfs
from doccon.confirm import ConfirmDeliveryError, run_confirm_client_pack
from doccon.date_picker import attach_calendar, set_entry_date, set_na_text
from doccon.diag import log, log_session_start, open_log_folder
from doccon.drawing_board import DrawingBoard
from doccon.drop_pdfs import (
    LOAD_FIRST,
    NEED_FOLDER,
    NOT_EMAIL_DROPPED,
    NOT_PDF,
    apply_board_drop,
    apply_row_drop,
    delete_dropped_copy,
    ingest_sources,
    rename_email_dropped_pdf,
    replace_paired_pdf,
    resolve_drop_row_key,
    sources_from_paths,
    sweep_replaced_dropped_copies,
)
from doccon.eddi import eddi_print_drawings, snapshot_eddi
from doccon.jira_client import (
    JiraError,
    create_subtask,
    fetch_eddi_contexts,
    fetch_epic_copy,
    fetch_job_pack,
    fetch_job_pack_including,
    fetch_parent_tasks,
    fetch_rev_option_lists,
    fetch_subtask_eddi_options,
    ping,
    run_jira_register_update,
    update_eddi_status,
)
from doccon.jobs import job_folder_identity, resolve_job_folder
from doccon.kinds import CLIENT, FIELD, INCOMING, LABELS, PREFIX, SHOP
from doccon.log_layout import layout_for
from doccon.match import (
    LocatedPdf,
    MatchedRow,
    apply_located_pdfs,
    is_dropped_pdf_path,
    keep_located_pdfs,
    match_pdf_hits,
    outgoing_rev_from_filename,
    pair_pdf,
    pdf_is_email_dropped,
    scan_current_pdfs,  # noqa: F401  — tests patch this name
    scan_job_pdfs,
    scan_library_pdfs,
)
from doccon.outlook_contacts import OutlookContactsError, import_saved_emails_from_outlook
from doccon.pack_mail import (
    MAIL_KIND_LABELS,
    MAIL_MARKERS,
    default_mail_body,
    default_mail_subject,
    draft_subject,
    load_mail_formats,
    mail_kind_key,
    save_mail_formats,
)
from doccon.pack_state import (
    ClientPack,
    PackExtra,
    cover_recipients,
    blank_extra,
    document_no_for_file,
    extra_from_path,
    load_client_pack,
    save_client_pack,
    with_cover_recipients,
)
from doccon.pdf_preview import close_pdf_preview, open_pdf_preview
from doccon.pep import DOC_CONTROL_FROM, SALES_DIR, PepCover, PepError, email_line, find_pep, load_pep
from doccon.popups import bind_console
from doccon.popups import install as _install_popups
from doccon.popups import reveal_on_parent
from doccon.register import (
    MISSING_JIRA_PROJECT,
    DrawingRow,
    EddiConflict,
    EpicCopy,
    FieldOption,
    JobProject,
    PackageTask,
    eddi_conflicts,
    eddi_fix_options,
    eddi_option_labels,
    is_generic_eddi,
    jira_project_label,
    new_issue_id_error,
    new_issue_preflight_error,
)
from doccon.secrets import load_token, save_token
from doccon.settings import (
    AppSettings,
    append_email,
    load_settings,
    locate_start_dir,
    normalize_saved_emails,
    remember_job_folder,
    remember_locate_dir,
    remember_shop_folder,
    remembered_shop_folder,
    save_settings,
)
from doccon.shop_place import (
    MISSING_SHOP_FOLDER,
    find_shop_ifc_folder,
    shop_folder_choices,
)
from doccon.theme import (
    FOLDER,
    FONT,
    FONT_SMALL,
    FONT_TITLE,
    IDENTITY_MISSING,
    JIRA,
    LOAD_STEPS,
    NAVY,
    LoadButton,
    ThemeProgress,
    apply_theme,
    paint_load_percent,
    style_text,
)
from doccon.transmittal_books import adopt_transmittal_books
from doccon.watch_inbox import POLL_MS as WATCH_POLL_MS
from doccon.watch_inbox import InboxWatcher, plan_watch_hits

_install_popups()

NO_ROW_PDF = "No PDF for this row — use Locate…"
PACK_SAVE_MS = 1000
LOAD_CREEP_S = 0.45
CREATE_CREATED_MS = 700
CREATE_ISSUE_BTN = "Create new Jira Issue"
CREATE_TRANSMITTAL_BTN = "Create transmittal"
CREATE_EDDI_BTN = "Create EDDI"
SELECT_ROW_FIRST = (
    "That PDF does not match any drawing on this job by filename.\n\n"
    "It is in New PDFs. Click a drawing, then Assign. "
    "Include with pack when there is no Jira issue."
)


def _drop_path_token(path: Path | str) -> str:
    """Compare drop paths without Path.resolve() (Dropbox resolve can hang)."""
    return str(path).replace("/", "\\").strip().rstrip("\\").casefold()



def _os_open_path(path: Path) -> None:
    """Open a file with the OS default association (Adobe, Edge, Preview, …)."""
    target = os.fspath(path)
    if hasattr(os, "startfile"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    import subprocess

    if sys.platform == "darwin":
        subprocess.run(["open", target], check=False)
        return
    subprocess.run(["xdg-open", target], check=False)


def open_row_pdf(path: Path | str | None, *, opener=None) -> str | None:
    """Open the paired drawing PDF. Returns a short error, or None on success."""
    if path is None or not str(path).strip():
        return NO_ROW_PDF
    pdf = Path(path)
    if not pdf.is_file():
        return f"That PDF is not on disk: {pdf.name}"
    launch = opener if opener is not None else _os_open_path
    try:
        launch(pdf)
    except OSError as exc:
        return str(exc) or f"Could not open {pdf.name}."
    return None


def _session() -> tuple[AppSettings, str]:
    settings = load_settings()
    token = load_token(settings.email)
    return settings, token


class RenameDroppedDialog(tk.Toplevel):
    """Rename the email-dropped copy. Does not touch a Locate’d Dropbox PDF."""

    def __init__(self, master: tk.Misc, *, current: str, suggested: str) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Rename PDF")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        apply_theme(self)
        self.result: str | None = None
        self._suggested = (suggested or "").strip()
        ttk.Label(
            self,
            text="This name is what the client zip will use. Only the email-dropped copy is renamed.",
            wraplength=420,
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 6))
        self._var = tk.StringVar(value=self._suggested or current)
        entry = ttk.Entry(self, textvariable=self._var, width=56)
        entry.pack(fill="x", padx=12, pady=(0, 8))
        entry.focus_set()
        entry.selection_range(0, "end")
        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Rename", style="Accent.TButton", command=self._accept).pack(
            side="right", padx=(0, 8)
        )
        ttk.Button(buttons, text="Use drawing name", command=self._use_drawing).pack(side="left")
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        reveal_on_parent(self)

    def _use_drawing(self) -> None:
        if self._suggested:
            self._var.set(self._suggested)

    def _accept(self) -> None:
        self.result = self._var.get().strip()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class EddiConflictDialog(tk.Toplevel):
    """Pick one EDDI Status for issues that have more than one. Skip continues Load."""

    def __init__(self, master: tk.Misc, conflicts: list[EddiConflict]) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Multiple EDDI Status")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        apply_theme(self)
        self.result: dict[str, str] = {}
        self._picks: dict[str, ttk.Combobox] = {}
        fallback = ("",) + eddi_fix_options()
        ttk.Label(
            self,
            text=(
                "These issues have more than one EDDI Status. "
                "Pick one (groups 1–9). Update writes that option to Jira and reloads. "
                "Skip leaves them unchanged and continues Load."
            ),
            wraplength=640,
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 8))
        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill="both", expand=True)
        for item in conflicts:
            row = ttk.Frame(body)
            row.pack(fill="x", pady=4)
            ident = item.drawing_id or item.key
            ttk.Label(row, text=f"{ident}  {item.key}", font=FONT).pack(anchor="w")
            ttk.Label(
                row,
                text=item.summary or ident,
                style="Muted.TLabel",
            ).pack(anchor="w")
            ttk.Label(
                row,
                text="Current: " + "; ".join(item.options),
                style="Muted.TLabel",
            ).pack(anchor="w")
            choices = ("",) + item.allowed if item.allowed else fallback
            box = ttk.Combobox(row, width=48, values=choices, state="readonly")
            box.pack(anchor="w", pady=(2, 0))
            self._picks[item.key] = box
        buttons = ttk.Frame(self, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Skip — load anyway", command=self._skip).pack(side="right")
        ttk.Button(buttons, text="Update and reload", style="Accent.TButton", command=self._accept).pack(
            side="right", padx=(0, 8)
        )
        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.bind("<Escape>", lambda _event: self._skip())
        reveal_on_parent(self)

    def _accept(self) -> None:
        self.result = {
            key: box.get().strip() for key, box in self._picks.items() if box.get().strip()
        }
        self.destroy()

    def _skip(self) -> None:
        self.result = {}
        self.destroy()


class CreateIssueDialog(tk.Toplevel):
    """Create a Sub-task now. Job Number and Project Lead copy from the epic."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        epic_label: str,
        parents: list[PackageTask],
        eddi_options: tuple[FieldOption, ...],
        job_prefix: str,
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Create new Jira Issue")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        apply_theme(self)
        self.result: tuple[str, str, str, str] | None = None
        self._parent_by_label: dict[str, str] = {}
        parent_labels: list[str] = []
        for task in parents:
            label = (task.summary or task.key).strip() or task.key
            if label in self._parent_by_label:
                label = f"{task.summary}  {task.key}".strip()
            self._parent_by_label[label] = task.key
            parent_labels.append(label)
        ttk.Label(
            self,
            text=(
                "Creates a Sub-task in Jira now. Job Number and Project Lead copy from "
                f"{epic_label}. Reporter stays the signed-in user."
            ),
            wraplength=480,
            justify="left",
        ).pack(fill="x", padx=12, pady=(12, 8))
        body = ttk.Frame(self, padding=(12, 0, 12, 8))
        body.pack(fill="x")
        ttk.Label(body, text="Parent").pack(anchor="w")
        self._parent = ttk.Combobox(body, width=56, values=parent_labels, state="readonly")
        self._parent.pack(anchor="w", pady=(2, 8))
        if len(parent_labels) == 1:
            self._parent.set(parent_labels[0])
        ttk.Label(body, text="EDDI Status").pack(anchor="w")
        eddi_labels = tuple(option.label for option in eddi_options if option.label)
        self._eddi = ttk.Combobox(body, width=56, values=eddi_labels, state="readonly")
        self._eddi.pack(anchor="w", pady=(2, 8))
        ttk.Label(body, text="JIRA ID").pack(anchor="w")
        prefix = (job_prefix or "").strip()
        self._id = ttk.Entry(body, width=58)
        if prefix:
            self._id.insert(0, prefix if prefix.endswith("-") else f"{prefix}-")
        self._id.pack(anchor="w", pady=(2, 8))
        ttk.Label(body, text="Description").pack(anchor="w")
        self._desc = ttk.Entry(body, width=58)
        self._desc.pack(anchor="w", pady=(2, 8))
        ttk.Label(
            self,
            text="Generic (0) is not in the list. A blank JIRA ID, or one with a space, blocks Create.",
            style="Muted.TLabel",
            wraplength=480,
            justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))
        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Create", style="Accent.TButton", command=self._accept).pack(
            side="right", padx=(0, 8)
        )
        self._id.focus_set()
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        reveal_on_parent(self)

    def _accept(self) -> None:
        parent_key = self._parent_by_label.get(self._parent.get().strip(), "")
        eddi = self._eddi.get().strip()
        drawing_id = self._id.get().strip()
        description = self._desc.get().strip()
        error = new_issue_id_error(drawing_id)
        if not error and not parent_key:
            error = "Pick a Parent Task."
        if not error and not eddi:
            error = "Pick an EDDI Status (groups 1–9)."
        if not error and is_generic_eddi(eddi):
            error = "Pick an EDDI Status in groups 1–9. Generic is not listed."
        if error:
            messagebox.showerror("New issue", error, parent=self)
            return
        self.result = (parent_key, eddi, drawing_id, description)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class EmailWordingDialog(tk.Toplevel):
    """Client, Shop, and Field subject and body. One file in the Dropbox program folder."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Email wording")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        apply_theme(self)
        self._subjects: dict[str, ttk.Entry] = {}
        self._bodies: dict[str, tk.Text] = {}
        stored = load_mail_formats()
        intro = ttk.Frame(self, padding=(12, 12, 12, 4))
        intro.pack(fill="x")
        ttk.Label(
            intro,
            text="One wording for every PC. It is saved next to Elite DocCon in Dropbox, not on this computer.",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(intro, text=MAIL_MARKERS, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=12, pady=8)
        for key, title in MAIL_KIND_LABELS:
            page = ttk.Frame(book, padding=8)
            book.add(page, text=title)
            subject, body = stored.get(key, ("", ""))
            ttk.Label(page, text="Subject").pack(anchor="w")
            subject_box = ttk.Entry(page, width=64)
            subject_box.insert(0, subject.strip() or default_mail_subject())
            subject_box.pack(fill="x", pady=(2, 8))
            ttk.Label(page, text="Body").pack(anchor="w")
            body_box = tk.Text(page, width=64, height=12, wrap="word", font=FONT)
            body_box.insert("1.0", body if body.strip() else default_mail_body(key))
            body_box.pack(fill="both", expand=True, pady=(2, 4))
            ttk.Label(page, text=MAIL_MARKERS, style="Muted.TLabel").pack(anchor="w")
            self._subjects[key] = subject_box
            self._bodies[key] = body_box
        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side="right", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        reveal_on_parent(self)

    def _save(self) -> None:
        formats: dict[str, tuple[str, str]] = {}
        for key, _title in MAIL_KIND_LABELS:
            subject = self._subjects[key].get().strip()
            body = self._bodies[key].get("1.0", "end").replace("\r\n", "\n")
            formats[key] = (subject, body)
        try:
            path = save_mail_formats(formats)
        except OSError as exc:
            messagebox.showerror("Email wording", str(exc), parent=self)
            return
        messagebox.showinfo("Email wording", f"Saved for every PC.\n{path.name}", parent=self)
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.withdraw()
        self.title("Settings")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        apply_theme(self)

        settings = load_settings()
        pad = {"padx": 12, "pady": 6}
        ttk.Label(self, text="Jira connection", font=FONT_TITLE).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )
        ttk.Label(self, text="Site").grid(row=1, column=0, sticky="w", **pad)
        self.site = ttk.Entry(self, width=48)
        self.site.insert(0, settings.site)
        self.site.grid(row=1, column=1, **pad)

        ttk.Label(self, text="Email").grid(row=2, column=0, sticky="w", **pad)
        self.email = ttk.Entry(self, width=48)
        self.email.insert(0, settings.email)
        self.email.grid(row=2, column=1, **pad)

        ttk.Label(self, text="Project").grid(row=3, column=0, sticky="w", **pad)
        self.project = ttk.Entry(self, width=48)
        self.project.insert(0, settings.project_key)
        self.project.grid(row=3, column=1, **pad)

        ttk.Label(self, text="API token").grid(row=4, column=0, sticky="w", **pad)
        self.token = ttk.Entry(self, width=48, show="*")
        self.token.grid(row=4, column=1, **pad)
        hint = (
            "Already saved in Windows Credential Manager."
            if load_token(settings.email)
            else "Paste a token from id.atlassian.com. It is not stored in Dropbox."
        )
        ttk.Label(self, text=hint, style="Muted.TLabel").grid(row=5, column=1, sticky="w", padx=12, pady=(0, 4))

        book = ttk.LabelFrame(self, text="Saved TO / CC addresses", padding=8)
        book.grid(row=6, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 4))
        self._addresses = tk.Listbox(book, height=6, width=52, exportselection=False)
        scroll = ttk.Scrollbar(book, orient="vertical", command=self._addresses.yview)
        self._addresses.configure(yscrollcommand=scroll.set)
        self._addresses.grid(row=0, column=0, columnspan=3, sticky="ew")
        scroll.grid(row=0, column=3, sticky="ns")
        self._new_address = ttk.Entry(book, width=36)
        self._new_address.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 8))
        self._new_address.bind("<Return>", lambda _event: self._add_address())
        ttk.Button(book, text="Add", command=self._add_address).grid(row=1, column=1, pady=(8, 0), padx=(0, 8))
        ttk.Button(book, text="Remove", style="Danger.TButton", command=self._remove_address).grid(
            row=1, column=2, pady=(8, 0)
        )
        ttk.Button(book, text="Import from Outlook…", command=self._import_outlook).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        ttk.Label(
            book,
            text="This PC only. Import from Outlook… copies GAL and Contacts. Pick… adds one.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        book.columnconfigure(0, weight=1)
        self._fill_addresses(settings.saved_emails)

        pairs = ttk.Frame(self)
        pairs.grid(row=7, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 4))
        pairs.columnconfigure(0, weight=1)
        pairs.columnconfigure(1, weight=1)
        self._shop_to, self._shop_cc, self._shop_new = self._address_pair(
            pairs,
            0,
            "Shop transmittal TO / CC",
            "This PC only. Shop cover uses these when the ST letter has no TO or CC yet.",
            settings.shop_to,
            settings.shop_cc,
        )
        self._field_to, self._field_cc, self._field_new = self._address_pair(
            pairs,
            1,
            "Field transmittal TO / CC",
            "This PC only. Field cover uses these when the FT letter has no TO or CC yet.",
            settings.field_to,
            settings.field_cc,
        )

        buttons = ttk.Frame(self)
        buttons.grid(row=8, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 14))
        ttk.Button(buttons, text="Open log folder", command=self._open_log_folder).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Email wording…", command=self._email_wording).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Test connection", command=self._test).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side="left")
        reveal_on_parent(self)

    def _email_wording(self) -> None:
        EmailWordingDialog(self)

    def _address_pair(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        hint: str,
        to_emails: tuple[str, ...],
        cc_emails: tuple[str, ...],
    ) -> tuple[tk.Listbox, tk.Listbox, ttk.Entry]:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(frame, text="TO").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="CC").grid(row=0, column=1, sticky="w", padx=(8, 0))
        to_box = tk.Listbox(frame, height=4, width=24, exportselection=False)
        cc_box = tk.Listbox(frame, height=4, width=24, exportselection=False)
        to_box.grid(row=1, column=0, sticky="ew")
        cc_box.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        entry = ttk.Entry(frame, width=24)
        entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        entry.bind("<Return>", lambda _event, box=None: self._add_pair_address(entry, to_box, "to"))
        adds = ttk.Frame(frame)
        adds.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(adds, text="Add to TO", command=lambda: self._add_pair_address(entry, to_box, "to")).pack(
            side="left"
        )
        ttk.Button(
            adds, text="Add to CC", command=lambda: self._add_pair_address(entry, cc_box, "cc")
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            adds,
            text="Remove",
            style="Danger.TButton",
            command=lambda: self._remove_pair_address(to_box, cc_box),
        ).pack(side="left", padx=(8, 0))
        ttk.Label(frame, text=hint, style="Muted.TLabel", wraplength=280).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        self._fill_list(to_box, to_emails)
        self._fill_list(cc_box, cc_emails)
        return to_box, cc_box, entry

    def _open_log_folder(self) -> None:
        try:
            open_log_folder()
        except OSError as exc:
            messagebox.showerror("Settings", str(exc), parent=self)

    def _fill_list(self, box: tk.Listbox, emails: tuple[str, ...] | list[str]) -> None:
        box.delete(0, "end")
        for addr in emails:
            box.insert("end", addr)

    def _fill_addresses(self, emails: tuple[str, ...] | list[str]) -> None:
        self._fill_list(self._addresses, emails)

    def _list_emails(self, box: tk.Listbox) -> tuple[str, ...]:
        return normalize_saved_emails(list(box.get(0, "end")))

    def _listed_emails(self) -> tuple[str, ...]:
        return normalize_saved_emails(list(self._addresses.get(0, "end")))

    def _persist_addresses(self) -> None:
        current = load_settings()
        save_settings(replace(current, saved_emails=self._listed_emails()))

    def _add_address(self) -> None:
        added = normalize_saved_emails(self._new_address.get())
        if not added:
            messagebox.showerror("Settings", "Type an email address.", parent=self)
            return
        merged = normalize_saved_emails(list(self._listed_emails()) + list(added))
        self._fill_addresses(merged)
        self._new_address.delete(0, "end")
        self._persist_addresses()

    def _remove_address(self) -> None:
        selected = list(self._addresses.curselection())
        if not selected:
            messagebox.showinfo("Settings", "Select an address to remove.", parent=self)
            return
        remaining = [
            addr for index, addr in enumerate(self._listed_emails()) if index not in set(selected)
        ]
        self._fill_addresses(remaining)
        self._persist_addresses()

    def _add_pair_address(self, entry: ttk.Entry, box: tk.Listbox, _which: str) -> None:
        added = normalize_saved_emails(entry.get())
        if not added:
            messagebox.showerror("Settings", "Type an email address.", parent=self)
            return
        merged = normalize_saved_emails(list(self._list_emails(box)) + list(added))
        self._fill_list(box, merged)
        entry.delete(0, "end")

    def _remove_pair_address(self, to_box: tk.Listbox, cc_box: tk.Listbox) -> None:
        box = to_box if to_box.curselection() else cc_box
        selected = list(box.curselection())
        if not selected:
            messagebox.showinfo("Settings", "Select a TO or CC address to remove.", parent=self)
            return
        remaining = [addr for index, addr in enumerate(self._list_emails(box)) if index not in set(selected)]
        self._fill_list(box, remaining)

    def _add_field_address(self, which: str) -> None:
        box = self._field_to if which == "to" else self._field_cc
        self._add_pair_address(self._field_new, box, which)

    def _remove_field_address(self) -> None:
        self._remove_pair_address(self._field_to, self._field_cc)

    def _import_outlook(self, *, lister=None) -> None:
        self.configure(cursor="watch")
        self.update_idletasks()
        result = None
        error = ""
        try:
            result = import_saved_emails_from_outlook(lister=lister)
        except OutlookContactsError as exc:
            error = str(exc)
        finally:
            self.configure(cursor="")
        if error:
            messagebox.showerror("Settings", error, parent=self)
            return
        if result is None:
            return
        self._fill_addresses(result.saved_emails)
        if result.added:
            messagebox.showinfo(
                "Settings",
                f"Added {result.added} address(es) from Outlook. They stay on this PC, not Dropbox.",
                parent=self,
            )
            return
        messagebox.showinfo("Settings", "No new addresses from Outlook.", parent=self)

    def _read_form(self) -> tuple[AppSettings, str]:
        settings = AppSettings(
            site=self.site.get().strip(),
            email=self.email.get().strip(),
            project_key=self.project.get().strip(),
            saved_emails=self._listed_emails(),
            field_to=self._list_emails(self._field_to),
            field_cc=self._list_emails(self._field_cc),
            shop_to=self._list_emails(self._shop_to),
            shop_cc=self._list_emails(self._shop_cc),
            last_locate_dir=load_settings().last_locate_dir,
            board_col_px=load_settings().board_col_px,
            board_layout_rev=load_settings().board_layout_rev,
            job_folders=dict(load_settings().job_folders),
            shop_ifc_folders=dict(load_settings().shop_ifc_folders),
        )
        token = self.token.get().strip()
        return settings, token

    def _save(self) -> None:
        settings, token = self._read_form()
        if not settings.email:
            messagebox.showerror("Settings", "Email is required.", parent=self)
            return
        save_settings(settings)
        if token:
            try:
                save_token(settings.email, token)
            except ValueError as exc:
                messagebox.showerror("Settings", str(exc), parent=self)
                return
        elif not load_token(settings.email):
            messagebox.showerror("Settings", "Paste an API token once so DocCon can talk to Jira.", parent=self)
            return
        self.destroy()

    def _test(self) -> None:
        settings, token = self._read_form()
        secret = token or load_token(settings.email)
        if not settings.email or not secret:
            messagebox.showerror("Settings", "Email and API token are required to test.", parent=self)
            return
        try:
            name = ping(settings.site, settings.email, secret)
        except JiraError as exc:
            messagebox.showerror("Jira", str(exc), parent=self)
            return
        messagebox.showinfo("Jira", f"Connected as {name}.", parent=self)


class DocConApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        from doccon.dpi import apply_window_dpi

        apply_window_dpi(self)
        self.title(f"{APP_DISPLAY_NAME}  {__version__}")
        self.geometry("1680x820")
        self.minsize(1200, 640)
        apply_theme(self)
        bind_console(self)
        self._busy = False
        self._work = ""
        self._load_gen = 0
        self._load_note: tuple[int, str] | None = None
        self._load_mark: tuple[int, int, int, str] | None = None
        self._load_shown = 0
        self._load_cap = 0
        self._load_caption = ""
        self._load_creep = 0.0
        self._pending_rows: tuple | None = None
        self._pending_files: tuple | None = None
        self._book_covers: dict[str, BookCover] = {}
        self._pep_cover: PepCover | None = None
        self._cover_stamp: tuple[str, str, str] = ("", "", "")
        self._load_pump = ""
        self._matches: dict[str, MatchedRow] = {}
        self._job_folder: Path | None = None
        self._locate_dir = ""
        self._job_number = ""
        self._pep_path: Path | None = None
        self._cover_loading = False
        self._jira_loading = False
        self._located_pdfs: dict[str, LocatedPdf] = {}
        self._pack_extras: list[PackExtra] = []
        self._shop_root: Path | None = None
        self._job_project: JobProject | None = None
        self._eddi_contexts: dict[str, tuple[FieldOption, ...]] = {}
        self._open_path = _os_open_path
        self._pack_save_after = ""
        self._reloading_after_eddi_fix = False
        self._create_wait_key = ""
        self._create_focus_key = ""
        self._drop_hover_after = ""
        self._drop_hover_pt = (0, 0)
        self._watcher: InboxWatcher | None = None
        self._watch_after = ""
        self._new_pdfs: list[Path] = []
        self.kind = tk.StringVar(value=CLIENT)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-v>", self._on_paste_key, add="+")
        self.bind_all("<Control-V>", self._on_paste_key, add="+")
        log("INFO", "session", f"gui init pid={os.getpid()} paste + watched folder")

        chrome = tk.Frame(self, bg=NAVY, padx=12, pady=6)
        chrome.pack(fill="x")
        bar = tk.Frame(chrome, bg=NAVY)
        bar.pack(fill="x")
        tk.Label(
            bar,
            text=APP_DISPLAY_NAME,
            bg=NAVY,
            fg="#FFFFFF",
            font=FONT_SMALL,
        ).pack(side="left")
        tk.Label(
            bar,
            text=f"v{__version__}",
            bg=NAVY,
            fg="#9FB3C8",
            font=FONT_SMALL,
        ).pack(side="left", padx=(6, 12))
        ttk.Label(bar, text="Job Number", style="Brand.TLabel").pack(side="left")
        self.job = ttk.Entry(bar, width=16)
        self.job.pack(side="left", padx=(6, 4))
        self.job.bind("<Return>", lambda _event: self._load())
        self.load_btn = LoadButton(bar, self._load)
        self.load_btn.pack(side="left")

        kinds = tk.Frame(bar, bg=NAVY)
        kinds.pack(side="left", padx=(10, 0))
        for value in (CLIENT, SHOP, FIELD, INCOMING):
            ttk.Radiobutton(
                kinds,
                text=LABELS[value],
                value=value,
                variable=self.kind,
                command=self._kind_changed,
                style="Brand.TRadiobutton",
            ).pack(side="left", padx=(0, 6))
        self.shop_locate_btn = ttk.Button(
            bar, text="Locate shop folder…", style="Brand.TButton", command=self._locate_shop_folder
        )
        self.send_btn = ttk.Button(bar, text=CREATE_TRANSMITTAL_BTN, style="Accent.TButton", command=self._issue_pack)
        self.send_btn.pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Update Jira…", style="Brand.TButton", command=self._update_jira).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(bar, text=CREATE_EDDI_BTN, command=self._print_eddi).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Settings", style="Brand.TButton", command=self._settings).pack(side="right")
        self.status = ttk.Label(
            bar,
            text="Settings → paste Jira token, then Load a job.",
            style="BrandMuted.TLabel",
        )
        self.status.pack(side="left", padx=10)

        identity = tk.Frame(chrome, bg=NAVY)
        identity.pack(fill="x", pady=(6, 0))
        ttk.Button(
            identity,
            text="Paste PDF from email",
            style="Brand.TButton",
            command=self._paste_pdf,
        ).pack(side="right", padx=(8, 0))
        self._jira_bar, self._jira_title, self._jira_value = self._identity_chip(
            identity, "Jira", JIRA
        )
        self._folder_bar, self._folder_title, self._folder_value = self._identity_chip(
            identity, "Folder", FOLDER
        )
        ttk.Button(
            identity,
            text="Locate job folder…",
            style="Brand.TButton",
            command=self._locate_job_folder,
        ).pack(side="left", padx=(16, 0))
        self.new_issue_btn = ttk.Button(
            identity,
            text=CREATE_ISSUE_BTN,
            style="Brand.TButton",
            command=self._new_issue,
        )
        self.new_issue_btn.pack(side="left", padx=(8, 0))
        self.new_issue_btn.configure(state=tk.DISABLED)
        self._set_job_identity(None, None)
        self._load_meter = tk.Frame(chrome, bg=NAVY)
        self._progress = ThemeProgress(self._load_meter, manage_pack=False)
        self._progress.pack(fill="x")
        self._load_status = tk.Label(
            self._load_meter,
            text="",
            bg=NAVY,
            fg="#D9E2EC",
            font=FONT_SMALL,
            anchor="w",
            justify="left",
        )
        self._load_status.pack(fill="x", pady=(2, 0))

        dates = ttk.Frame(self, padding=(12, 4, 12, 4))
        dates.pack(fill="x")
        ttk.Label(dates, text="Date issued").pack(side="left")
        self.issued = ttk.Entry(dates, width=12)
        set_entry_date(self.issued, date.today())
        self.issued.pack(side="left", padx=(4, 8))
        attach_calendar(self.issued, parent=self, on_change=self._on_issued_change, allow_na=True)
        ttk.Label(dates, text="Expected return").pack(side="left")
        self.expected = ttk.Entry(dates, width=12)
        self._explicit_no_return = False
        set_na_text(self.expected)
        self.expected.pack(side="left", padx=(4, 0))
        attach_calendar(
            self.expected,
            parent=self,
            on_change=self._on_expected_return_change,
            allow_na=True,
            presets=(
                ("Urgent same day", lambda: self._apply_expected_preset(0)),
                ("Urgent +1", lambda: self._apply_expected_preset(1)),
                ("7 days", lambda: self._apply_expected_preset(7)),
                ("14 days", lambda: self._apply_expected_preset(14)),
                ("No return", self._apply_no_return),
            ),
        )
        ttk.Button(dates, text="Locate PEP…", command=self._locate_pep).pack(side="left", padx=(12, 0))
        ttk.Button(dates, text="Save", command=self._save_pack).pack(side="left", padx=(6, 0))
        self.pep_label = ttk.Label(dates, text="PEP: load a job", style="Muted.TLabel")
        self.pep_label.pack(side="left", padx=(8, 0))

        cover = ttk.LabelFrame(self, text="Cover (this pack)", padding=4)
        cover.pack(side="bottom", fill="x", padx=12, pady=(0, 4))
        ttk.Label(cover, text="FROM", style="CoverHead.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        to_head = ttk.Frame(cover)
        to_head.grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(to_head, text="TO", style="CoverHead.TLabel").pack(side="left")
        ttk.Button(to_head, text="Pick…", command=lambda: self._pick_cover_email("to")).pack(side="left", padx=(8, 0))
        cc_head = ttk.Frame(cover)
        cc_head.grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Label(cc_head, text="CC", style="CoverHead.TLabel").pack(side="left")
        ttk.Button(cc_head, text="Pick…", command=lambda: self._pick_cover_email("cc")).pack(side="left", padx=(8, 0))
        ttk.Label(cover, text="PROJECT", style="CoverHead.TLabel").grid(row=0, column=3, sticky="w")
        self.from_addr = ttk.Entry(cover, width=36)
        self.from_addr.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 2))
        self._set_from_address(DOC_CONTROL_FROM)
        self.to_box = tk.Text(cover, height=2, width=28, wrap="word")
        self.to_box.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 2))
        self.cc_box = tk.Text(cover, height=2, width=28, wrap="word")
        self.cc_box.grid(row=1, column=2, sticky="nsew", padx=(0, 8), pady=(0, 2))
        self.project_box = tk.Text(cover, height=2, width=28, wrap="word")
        self.project_box.grid(row=1, column=3, sticky="nsew", pady=(0, 2))
        for box in (self.to_box, self.cc_box, self.project_box):
            style_text(box)
        self.cover_hint = ttk.Label(
            cover,
            text="TO and CC are email addresses only. Pick… adds a saved address.",
            style="Muted.TLabel",
        )
        self.cover_hint.grid(row=2, column=0, columnspan=4, sticky="w")
        cover.columnconfigure(0, weight=1, minsize=200)
        for col in range(1, 4):
            cover.columnconfigure(col, weight=2, minsize=160)
        for box in (self.to_box, self.cc_box, self.project_box):
            box.bind("<FocusOut>", lambda _event: self._save_pack(quiet=True))
        self.issued.bind("<FocusOut>", lambda _event: self._on_issued_change())
        self.expected.bind("<FocusOut>", lambda _event: self._on_expected_return_change())

        body = ttk.Frame(self, padding=(6, 0, 6, 0))
        body.pack(fill="both", expand=True)
        self._new_pdf_bar = tk.Frame(body, bg=NAVY, highlightthickness=0, bd=0)
        tk.Label(
            self._new_pdf_bar,
            text="New PDFs",
            bg=NAVY,
            fg=FOLDER,
            font=FONT_SMALL,
        ).pack(side="left", padx=(8, 8), pady=2)
        self._new_pdf_list = tk.Listbox(
            self._new_pdf_bar,
            height=2,
            font=FONT_SMALL,
            activestyle="none",
            exportselection=False,
        )
        self._new_pdf_list.pack(side="left", fill="x", expand=True, pady=2)
        self._new_pdf_list.bind("<Double-Button-1>", lambda _event: self._assign_new_pdf())
        ttk.Button(
            self._new_pdf_bar,
            text="Assign to selected row",
            style="Brand.TButton",
            command=self._assign_new_pdf,
        ).pack(side="left", padx=8)
        ttk.Button(
            self._new_pdf_bar,
            text="Include with pack",
            style="Brand.TButton",
            command=self._include_new_pdf,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            self._new_pdf_bar,
            text="Dismiss",
            style="Brand.TButton",
            command=self._dismiss_new_pdf,
        ).pack(side="left", padx=(0, 10))
        self._pack_extra_bar = tk.Frame(body, bg=NAVY, highlightthickness=0, bd=0)
        tk.Label(
            self._pack_extra_bar,
            text="Non Jira",
            bg=NAVY,
            fg=FOLDER,
            font=FONT_SMALL,
        ).pack(side="left", padx=(8, 8), pady=2)
        ttk.Button(
            self._pack_extra_bar,
            text="Add row",
            style="Brand.TButton",
            command=self._add_blank_extra,
        ).pack(side="left", padx=8)
        ttk.Button(
            self._pack_extra_bar,
            text="Add PDF…",
            style="Add.TButton",
            command=self._add_pack_extra,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            self._pack_extra_bar,
            text="Remove",
            style="Danger.TButton",
            command=self._remove_pack_extra,
        ).pack(side="left", padx=(0, 10))
        self.board = DrawingBoard(
            body,
            on_open_pdf=self._open_pdf_key,
            on_locate_pdf=self._locate_pdf,
            on_preview_pdf=self._preview_pdf_key,
            on_rename_pdf=self._rename_pdf,
            cover_return_stamp=lambda: cover_date_stamp(self.expected.get()),
            cover_issued_stamp=lambda: cover_date_stamp(self.issued.get()),
            on_cancel_next=self._on_cancel_next,
            on_draft_change=self._schedule_pack_save,
            on_no_return=self._mark_cover_no_return,
        )
        self.board.pack(fill="both", expand=True)

    def _settings(self) -> None:
        SettingsDialog(self)

    def _field_default_lines(self) -> tuple[str, str]:
        settings = load_settings()
        return email_line("; ".join(settings.field_to)), email_line("; ".join(settings.field_cc))

    def _shop_default_lines(self) -> tuple[str, str]:
        settings = load_settings()
        return email_line("; ".join(settings.shop_to)), email_line("; ".join(settings.shop_cc))

    def _pick_cover_email(self, which: str) -> None:
        settings = load_settings()
        kind = self.kind.get()
        if kind == FIELD:
            emails = settings.field_to if which == "to" else settings.field_cc
            empty = "Add Field transmittal TO addresses in Settings first." if which == "to" else (
                "Add Field transmittal CC addresses in Settings first."
            )
        elif kind == SHOP:
            emails = settings.shop_to if which == "to" else settings.shop_cc
            empty = "Add Shop transmittal TO addresses in Settings first." if which == "to" else (
                "Add Shop transmittal CC addresses in Settings first."
            )
        else:
            emails = settings.saved_emails
            empty = "Save email addresses in Settings first."
        if not emails:
            messagebox.showinfo("Pick address", empty)
            return
        menu = tk.Menu(self, tearoff=0)
        for addr in emails:
            menu.add_command(label=addr, command=lambda value=addr: self._append_cover_email(which, value))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _append_cover_email(self, which: str, address: str) -> None:
        box = self.to_box if which == "to" else self.cc_box
        merged = append_email(self._email_value(box), address)
        self._set_text(box, merged)
        self._save_pack(quiet=True)

    def _kind_changed(self) -> None:
        self.send_btn.configure(text=CREATE_TRANSMITTAL_BTN, state="normal")
        if self.kind.get() == INCOMING:
            self.cover_hint.configure(
                text="Incoming stamps Return Date, Incoming Rev, and Client Approval Status on packed rows. Date issued is not written. Use Update Jira."
            )
            self.board.set_transmittal_kind(INCOMING)
            self._refresh_shop_place()
            self._refresh_cover_hint()
            return
        if self.kind.get() == CLIENT:
            self.cover_hint.configure(
                text="TO and CC are email addresses only. Add more with a semicolon."
            )
        elif self.kind.get() == FIELD:
            self.cover_hint.configure(
                text="Field TO and CC start from Settings when the FT letter is empty."
            )
        else:
            self.cover_hint.configure(
                text="Shop TO and CC start from Settings when the ST letter is empty."
            )
        self._show_kind_cover()
        if self.board.extras_painted():
            self.board.set_pack_extras(
                self._current_extras(), statuses=layout_for(self.kind.get()).statuses
            )
        self.board.set_transmittal_kind(self.kind.get())
        self._refresh_shop_place()
        self._refresh_cover_hint()

    def _show_kind_cover(self) -> None:
        kind = self.kind.get()
        pack = load_client_pack(self._job_folder, self._job_number) if self._job_number else None
        pack_to, pack_cc = cover_recipients(pack, kind)
        pep = self._pep_cover if kind == CLIENT else None
        field_to, field_cc = self._field_default_lines()
        shop_to, shop_cc = self._shop_default_lines()
        if kind not in self._book_covers and self._job_folder is not None and self._job_number:
            self._book_covers[kind] = BookCover()
            self._read_kind_cover_later(kind)
        chosen = pick_cover_fields(
            book=self._book_covers.get(kind, BookCover()),
            pack_to=pack_to,
            pack_cc=pack_cc,
            pack_project="",
            pep=pep,
            kind=kind,
            field_to=field_to,
            field_cc=field_cc,
            shop_to=shop_to,
            shop_cc=shop_cc,
        )
        self._cover_loading = True
        try:
            self._set_text(self.to_box, email_line(chosen.to_line))
            self._set_text(self.cc_box, email_line(chosen.cc_line))
        finally:
            self._cover_loading = False
        self._cover_stamp = self._cover_text_now()

    def _read_kind_cover_later(self, kind: str) -> None:
        """Read the letter off the window thread. A Dropbox xlsm must not freeze the click."""
        folder = self._job_folder
        job = self._job_number
        gen = self._load_gen

        def work() -> None:
            try:
                book = book_cover_for_job(folder, job, kind) if folder is not None else BookCover()
            except (OSError, KeyError, ValueError, TypeError):
                book = BookCover()

            def apply() -> None:
                if gen != self._load_gen or self._job_number != job:
                    return
                self._book_covers[kind] = book
                if self.kind.get() == kind:
                    self._fill_cover_if_untouched(kind)

            with contextlib.suppress(tk.TclError, RuntimeError):
                self.after(0, apply)

        threading.Thread(target=work, daemon=True).start()

    def _cover_suffix(self) -> str:
        kind = self.kind.get()
        if kind not in LABELS or self._job_folder is None or not self._job_number:
            return ""
        try:
            book = find_book(self._job_folder, self._job_number, kind)
        except (LogError, OSError):
            return ""
        if book is None:
            return ""
        return f"  |  {book.name}"

    def _pep_suffix(self) -> str:
        if self._pep_path is None:
            return "  |  PEP not found — Locate PEP…"
        return f"  |  PEP {self._pep_path.name}"

    def _sales_dir(self) -> Path | None:
        if self._job_folder is None:
            return None
        sales = self._job_folder / SALES_DIR
        return sales if sales.is_dir() else self._job_folder

    def _set_from_address(self, value: str) -> None:
        self.from_addr.configure(state="normal")
        self.from_addr.delete(0, "end")
        self.from_addr.insert(0, value or DOC_CONTROL_FROM)
        self.from_addr.configure(state="readonly")

    def _text_value(self, box: tk.Text) -> str:
        return box.get("1.0", "end").strip()

    def _email_value(self, box: tk.Text) -> str:
        return email_line(self._text_value(box))

    def _set_text(self, box: tk.Text, value: str) -> None:
        box.delete("1.0", "end")
        if value:
            box.insert("1.0", value)

    def _apply_cover_fields(self, cover: PepCover, *, overlay: ClientPack | None = None) -> None:
        self._cover_loading = True
        try:
            self._set_from_address(DOC_CONTROL_FROM)
            kind = self.kind.get()
            to_line, cc_line = cover_recipients(overlay, kind)
            if kind == CLIENT:
                if not to_line:
                    to_line = cover.to_line
                if not cc_line:
                    cc_line = cover.cc_line
            elif kind == FIELD:
                field_to, field_cc = self._field_default_lines()
                if not to_line:
                    to_line = field_to
                if not cc_line:
                    cc_line = field_cc
            elif kind == SHOP:
                shop_to, shop_cc = self._shop_default_lines()
                if not to_line:
                    to_line = shop_to
                if not cc_line:
                    cc_line = shop_cc
            to_line = email_line(to_line)
            cc_line = email_line(cc_line)
            project = (
                overlay.project_description
                if overlay and overlay.project_description
                else cover.project_description
            )
            self._set_text(self.to_box, to_line)
            self._set_text(self.cc_box, cc_line)
            self._set_text(self.project_box, project)
        finally:
            self._cover_loading = False
        self._stamp_packed_from_cover_dates()

    def _clear_cover_fields(self) -> None:
        self._cover_loading = True
        try:
            self._set_from_address(DOC_CONTROL_FROM)
            self._set_text(self.to_box, "")
            self._set_text(self.cc_box, "")
            self._set_text(self.project_box, "")
            self._write_cover_date_defaults()
        finally:
            self._cover_loading = False

    def _pack_from_console(self) -> ClientPack:
        existing = (
            load_client_pack(self._job_folder, self._current_job()) if self._job_folder else None
        )
        base = existing or ClientPack(job_number=self._current_job())
        pack = ClientPack(
            job_number=self._current_job(),
            pep_path=str(self._pep_path) if self._pep_path else "",
            issued=self.issued.get().strip(),
            expected=self.expected.get().strip(),
            to_line=base.to_line,
            cc_line=base.cc_line,
            shop_to=base.shop_to,
            shop_cc=base.shop_cc,
            field_to=base.field_to,
            field_cc=base.field_cc,
            project_description=self._text_value(self.project_box),
            selected_keys=self.board.selected_keys(),
            located_pdfs=dict(self._located_pdfs),
            next_edits=self.board.next_edits(),
            pack_extras=tuple(self._current_extras()),
            shop_folders=(
                self.board.shop_folder_picks()
                if self.board.shop_folders_open()
                else (existing.shop_folders if existing is not None else {})
            ),
            job_folder=str(self._job_folder) if self._job_folder else "",
        )
        return with_cover_recipients(
            pack,
            self.kind.get(),
            self._email_value(self.to_box),
            self._email_value(self.cc_box),
        )

    def _write_cover_date_defaults(self) -> None:
        set_entry_date(self.issued, date.fromisoformat(cover_issued_default()))
        set_na_text(self.expected)

    def _reset_cover_dates(self) -> None:
        """Date issued = today, Expected return = N/A. Does not stamp packed Next."""
        self._cover_loading = True
        try:
            self._write_cover_date_defaults()
        finally:
            self._cover_loading = False

    def _on_cancel_next(self) -> None:
        self._reset_cover_dates()
        self._save_pack(quiet=True)

    def _mark_cover_no_return(self) -> None:
        """Expected return shows N/A. A later focus-out must not put the old return date back."""
        self._explicit_no_return = True
        set_na_text(self.expected)

    def _apply_no_return(self) -> None:
        """This pack expects no document back. Stamps packed Return Request Date to N/A."""
        self._mark_cover_no_return()
        count = self.board.stamp_packed_no_return()
        if count:
            self._set_status(f"No return date on {count} packed drawing(s). Jira was not written.")
        else:
            self._set_status("No return date. Tick Pack to stamp it onto drawings.")
        self._save_pack(quiet=True)

    def _apply_expected_preset(self, days: int) -> None:
        """Set Expected return to Date issued plus calendar days. Does not write Jira."""
        stamp = expected_return_from_issued(self.issued.get(), days)
        set_entry_date(self.expected, date.fromisoformat(stamp))
        self._on_expected_return_change()

    def _stamp_packed_from_cover_dates(self) -> None:
        self.board.stamp_packed_cover_dates()

    def _on_issued_change(self) -> None:
        if not self._cover_loading:
            self.board.apply_cover_date_change("submission_date", cover_date_stamp(self.issued.get()))
        self._save_pack(quiet=True)

    def _on_expected_return_change(self) -> None:
        if not self._cover_loading:
            stamp = cover_date_stamp(self.expected.get())
            if not stamp and self._explicit_no_return:
                self._save_pack(quiet=True)
                return
            self._explicit_no_return = False
            self.board.apply_cover_date_change("return_request_date", stamp)
        self._save_pack(quiet=True)

    def _save_pack(self, quiet: bool = False, *, force: bool = False) -> bool:
        if self._cover_loading:
            return False
        if self._busy and not force:
            return False
        job = self._job_number.strip() if force and self._job_number else self._current_job()
        folder = self._ensure_job_folder(job) if job else None
        if not job or folder is None:
            if not quiet:
                messagebox.showinfo("Save", "Load a job first.")
            return False
        try:
            dest = save_client_pack(folder, self._pack_from_console())
        except OSError as exc:
            messagebox.showerror("Save", str(exc))
            return False
        if not quiet:
            messagebox.showinfo("Save", f"Saved {dest.relative_to(folder)}")
        return True

    def _cancel_pack_save(self) -> None:
        if self._pack_save_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._pack_save_after)
            self._pack_save_after = ""

    def _schedule_pack_save(self) -> None:
        if self._cover_loading or self._busy:
            return
        if not self._job_number or self._job_folder is None:
            return
        self._cancel_pack_save()
        try:
            self._pack_save_after = self.after(PACK_SAVE_MS, self._flush_pack_save)
        except tk.TclError:
            self._pack_save_after = ""

    def _flush_pack_save(self) -> None:
        self._pack_save_after = ""
        self._save_pack(quiet=True)

    def _save_loaded_pack(self) -> bool:
        """Write the job that is already on the board (not the Job Number box)."""
        if not self._job_number or self._job_folder is None:
            return False
        return self._save_pack(quiet=True, force=True)

    def _on_close(self) -> None:
        self._cancel_pack_save()
        self._save_loaded_pack()
        self._clear_drop_hover()
        self._stop_drop()
        close_pdf_preview()
        self.destroy()

    def destroy(self) -> None:
        self._cancel_pack_save()
        with contextlib.suppress(Exception):
            self._clear_drop_hover()
        self._stop_drop()
        close_pdf_preview()
        super().destroy()

    def _stop_watcher(self) -> None:
        if self._watch_after:
            with contextlib.suppress(Exception):
                self.after_cancel(self._watch_after)
            self._watch_after = ""
        self._watcher = None

    def _stop_drop(self) -> None:
        self._stop_watcher()

    def _restore_pack(self, folder: Path | None, job: str, cover: PepCover | None) -> None:
        pack = load_client_pack(folder, job)
        kind = self.kind.get()
        pack_to, pack_cc = cover_recipients(pack, kind)
        field_to, field_cc = self._field_default_lines()
        shop_to, shop_cc = self._shop_default_lines()
        chosen = pick_cover_fields(
            book=self._book_covers.get(kind, BookCover()),
            pack_to=pack_to,
            pack_cc=pack_cc,
            pack_project=pack.project_description if pack else "",
            pep=cover,
            kind=kind,
            field_to=field_to,
            field_cc=field_cc,
            shop_to=shop_to,
            shop_cc=shop_cc,
        )
        self._cover_loading = True
        try:
            self._set_from_address(DOC_CONTROL_FROM)
            self._set_text(self.to_box, email_line(chosen.to_line))
            self._set_text(self.cc_box, email_line(chosen.cc_line))
            self._set_text(self.project_box, chosen.project_description)
            self._cover_stamp = self._cover_text_now()
            self._write_cover_date_defaults()
            if pack is not None:
                self.board.apply_next_edits(pack.next_edits)
                self._pack_extras = list(pack.pack_extras)
            else:
                self._pack_extras = []
        finally:
            self._cover_loading = False
        self.board.set_pack_extras(self._pack_extras, statuses=layout_for(kind).statuses)
        self._show_pack_extras()

    def _cover_for_write(self) -> PepCover | None:
        kind = self.kind.get()
        to_line = self._email_value(self.to_box)
        if kind == CLIENT and not to_line:
            messagebox.showerror(
                LABELS[CLIENT],
                "TO needs at least one email address. Type it on Cover, or Locate PEP.",
            )
            return None
        pep: PepCover | None = None
        path = self._pep_path if self._pep_path is not None and self._pep_path.is_file() else None
        if path is not None:
            try:
                pep = load_pep(path)
            except PepError:
                pep = None
        folder = self._job_folder or Path(".")
        cover_path = pep.path if pep is not None else folder / "console-cover"
        return PepCover(
            path=cover_path,
            from_address=DOC_CONTROL_FROM,
            to_line=to_line,
            cc_line=self._email_value(self.cc_box),
            project_description=self._text_value(self.project_box),
            client=pep.client if pep else "",
            site=pep.site if pep else "",
            tank_tag=pep.tank_tag if pep else "",
            po=pep.po if pep else "",
            wo=pep.wo if pep else "",
        )

    def _set_pep(self, path: Path | None) -> None:
        self._pep_path = path
        if path is None:
            self.pep_label.configure(text="PEP: not found — Locate PEP…")
            return
        self.pep_label.configure(text=f"PEP: {path.name}")

    def _discover_pep(self, folder: Path | None, job: str) -> None:
        if folder is None or not job:
            self._set_pep(None)
            return
        try:
            found = find_pep(folder, job)
        except (OSError, PepError, ValueError):
            found = None
        self._set_pep(found)

    def _current_job(self) -> str:
        return (self._job_number or self.job.get()).strip()

    def _identity_chip(self, parent: tk.Misc, title: str, hue: str) -> tuple[tk.Frame, tk.Label, tk.Label]:
        chip = tk.Frame(parent, bg=NAVY)
        chip.pack(side="left", fill="x", expand=True)
        bar = tk.Frame(chip, bg=hue, width=4)
        bar.pack(side="left", fill="y", padx=(0, 8))
        bar.pack_propagate(False)
        body = tk.Frame(chip, bg=NAVY)
        body.pack(side="left", fill="x", expand=True)
        head = tk.Label(body, text=title, bg=NAVY, fg=hue, font=FONT_SMALL, anchor="w")
        head.pack(side="left")
        value = tk.Label(body, text="", bg=NAVY, fg="#FFFFFF", font=FONT_SMALL, anchor="w")
        value.pack(side="left", fill="x", expand=True, padx=(6, 0))
        return bar, head, value

    def _set_job_identity(
        self,
        project: JobProject | None,
        folder: Path | None,
        *,
        loading: bool = False,
        jira_error: bool = False,
    ) -> None:
        self._job_project = project
        if loading:
            self._jira_value.configure(text="Loading…", fg="#FFFFFF")
            self._folder_value.configure(text="Finding…", fg="#FFFFFF")
            return
        if jira_error:
            jira_text = "Could not load Jira Project"
            jira_fg = IDENTITY_MISSING
        else:
            jira_text = jira_project_label(project)
            jira_fg = IDENTITY_MISSING if project is None else "#FFFFFF"
        folder_text = job_folder_identity(folder)
        folder_fg = IDENTITY_MISSING if folder is None else "#FFFFFF"
        self._jira_value.configure(text=jira_text, fg=jira_fg)
        self._folder_value.configure(text=folder_text, fg=folder_fg)
        self._jira_title.configure(fg=JIRA)
        self._folder_title.configure(fg=FOLDER)
        self._jira_bar.configure(bg=JIRA)
        self._folder_bar.configure(bg=FOLDER)

    def _ensure_job_folder(self, job: str) -> Path | None:
        if job == self._job_number and self._job_folder is not None and self._job_folder.is_dir():
            return self._job_folder
        folder = resolve_job_folder(job)
        if folder is not None:
            self._job_folder = folder
        return folder

    def _locate_job_folder(self) -> None:
        job = self.job.get().strip() or self._current_job()
        if not job:
            messagebox.showinfo("Locate job folder", "Enter a Job Number first.")
            return
        start = locate_start_dir(str(self._job_folder) if self._job_folder else "")
        chosen = filedialog.askdirectory(
            title="Locate Dropbox job folder (the job root with 3.0 Doc Con)",
            initialdir=start or os.getcwd(),
        )
        if not chosen:
            return
        folder = Path(chosen)
        if not folder.is_dir():
            messagebox.showerror("Locate job folder", "That folder is not available.")
            return
        looks_like = (folder / "3.0 Doc Con").is_dir() or (folder / "2.0 Drafting").is_dir()
        if not looks_like and not messagebox.askyesno(
            "Locate job folder",
            (
                f"{folder.name} does not look like a job root "
                "(no 3.0 Doc Con or 2.0 Drafting).\nUse it anyway?"
            ),
        ):
            return
        remember_job_folder(job, folder)
        remember_locate_dir(folder)
        self._job_folder = folder
        self._reset_locate_to_job(folder)
        if not self._job_number:
            self._job_number = job
        self._set_job_identity(self._job_project, folder)
        self._set_status(
            f"Job folder: {job_folder_identity(folder)}. Click Load to match PDFs from this folder."
        )
        self._save_pack(quiet=True, force=True)

    def _set_new_issue_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "new_issue_btn"):
            return
        with contextlib.suppress(tk.TclError):
            self.new_issue_btn.configure(state=tk.NORMAL if enabled else tk.DISABLED)

    def _locate_pep(self) -> None:
        job = self._current_job()
        if not job:
            messagebox.showinfo("PEP", "Enter a Job Number and click Load first.")
            return
        self._ensure_job_folder(job)
        path = self._pick_pep()
        if path is None:
            return
        try:
            cover = load_pep(path)
        except PepError as exc:
            messagebox.showerror("PEP", str(exc))
            return
        self._set_pep(cover.path)
        self._apply_cover_fields(cover)
        self._save_pack(quiet=True)
        self._refresh_cover_hint()
        messagebox.showinfo(
            "PEP",
            f"Using {cover.path.name}. Edit TO / CC / project on Cover if this send differs.",
        )

    def _pick_pep(self) -> Path | None:
        start = self._sales_dir()
        chosen = filedialog.askopenfilename(
            title="Locate Project Execution Plan (PEP)",
            initialdir=str(start) if start is not None else os.getcwd(),
            filetypes=[
                ("Excel PEP", "*.xlsx"),
                ("Excel PEP", "*.xlsm"),
                ("PDF PEP", "*.pdf"),
                ("All files", "*.*"),
            ],
        )
        return Path(chosen) if chosen else None

    def _refresh_cover_hint(self) -> None:
        if self._busy or not self._job_number:
            return
        missing = sum(1 for row in self._matches.values() if row.confidence == "Missing")
        folder_label = self._job_folder.name if self._job_folder else "job folder not found"
        self._set_status(
            f"{self._job_number}: {len(self._matches)} drawing(s), {missing} missing PDF"
            f"  |  {folder_label}{self._cover_suffix()}{self._pep_suffix()}"
        )

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)
        if hasattr(self, "_load_status"):
            self._load_status.configure(text=text)

    def _load(self) -> None:
        if self._work in {"confirm", "eddi", "jira", "create"}:
            return
        job = self.job.get().strip()
        if not job:
            messagebox.showinfo("Load", "Enter a Job Number (for example 2026-Tanzim or 2026-075).")
            return
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            self._settings()
            return
        self.board.set_packed_only(False, refresh=False)
        skip_prior_save = self._reloading_after_eddi_fix
        self._reloading_after_eddi_fix = False
        wait_key = (self._create_wait_key or "").strip()
        self._flush_pack_save()
        if not skip_prior_save:
            self._save_loaded_pack()
        self._cancel_load()
        self._create_wait_key = ""
        if not wait_key:
            self._create_focus_key = ""
        self._load_gen += 1
        gen = self._load_gen
        self._busy = True
        self._work = "load"
        self._job_number = job
        self._job_folder = None
        self._locate_dir = ""
        self._job_project = None
        self._eddi_contexts = {}
        self._set_new_issue_enabled(False)
        self._new_pdfs.clear()
        self._show_new_pdfs()
        self._pack_extras = []
        self._show_pack_extras()
        kind_now = self.kind.get()
        self._load_shown = 0
        self._load_cap = 0
        self._load_caption = ""
        self._load_mark = None
        self._load_creep = time.monotonic()
        self.load_btn.start("Fetching Jira")
        self._start_progress("Fetching from Jira…" if wait_key else f"Loading {job}…")
        self._mark_load(4, 22, "Fetching Jira")
        self._set_job_identity(None, None, loading=True)
        with contextlib.suppress(tk.TclError):
            self.update_idletasks()

        def work() -> None:
            error: str | None = None
            rows: list = []
            project: JobProject | None = None
            rev_options: dict[str, tuple[str, ...]] = {}
            eddi_contexts: dict[str, tuple[FieldOption, ...]] = {}
            folder: Path | None = None
            folder_label = ""

            def on_jira_step(name: str) -> None:
                step = LOAD_STEPS.get(name)
                if step is not None:
                    self._post_load(gen, step[0], step[1], step[2])

            def jira_work() -> None:
                nonlocal error, rows, project, rev_options, eddi_contexts
                try:
                    if wait_key:
                        self._post_status(gen, "Fetching from Jira…")
                        rows, project = fetch_job_pack_including(
                            settings.site,
                            settings.email,
                            token,
                            job,
                            settings.project_key,
                            wait_key,
                            on_step=on_jira_step,
                        )
                    else:
                        self._post_status(gen, f"Fetching Jira for {job}…")
                        rows, project = fetch_job_pack(
                            settings.site,
                            settings.email,
                            token,
                            job,
                            settings.project_key,
                            on_step=on_jira_step,
                        )
                    if rows:
                        self._post_load(gen, *LOAD_STEPS["options"])
                        try:
                            rev_options = fetch_rev_option_lists(
                                settings.site, settings.email, token, rows[0].key
                            )
                        except (JiraError, OSError, ValueError, TypeError):
                            rev_options = {}
                        self._post_load(gen, *LOAD_STEPS["eddi"])
                        try:
                            eddi_contexts = fetch_eddi_contexts(
                                settings.site, settings.email, token, rows
                            )
                        except (JiraError, OSError, ValueError, TypeError):
                            eddi_contexts = {}
                except (JiraError, OSError, ValueError, TypeError) as exc:
                    error = str(exc)

            def folder_work() -> None:
                nonlocal folder, folder_label
                try:
                    self._post_status(gen, f"Finding {job} folder…")
                    found = resolve_job_folder(job)
                    folder = found
                    if found is None:
                        folder_label = "job folder not found"
                        return
                    folder_label = found.name
                except Exception:
                    folder = None
                    folder_label = "job folder not found"

            jira_thread = threading.Thread(target=jira_work, daemon=True)
            folder_thread = threading.Thread(target=folder_work, daemon=True)
            jira_thread.start()
            folder_thread.start()
            jira_thread.join()
            # The Dropbox hunt can sit on online-only folders. Paint from Jira
            # without waiting for it. A remembered folder is usually already done.
            if folder_thread.is_alive():
                self._post_rows(
                    gen, job, rows, error, "finding job folder…", 0, None, project, rev_options, {}, eddi_contexts
                )

                def when_folder() -> None:
                    folder_thread.join()
                    ready_located: dict = {}
                    if error is None and folder is not None:
                        ready_located = self._located_from_pack(folder, job, rows)
                        self._start_folder_files(gen, job, folder, kind_now)

                    def deliver(
                        located_pdfs: dict = ready_located,
                        label: str = folder_label,
                        found: Path | None = folder,
                    ) -> None:
                        self._attach_job_folder(gen, job, found, label, located_pdfs)

                    with contextlib.suppress(tk.TclError, RuntimeError):
                        self.after(0, deliver)

                threading.Thread(target=when_folder, daemon=True).start()
                return
            folder_thread.join()
            located = self._located_from_pack(folder, job, rows) if error is None else {}
            if error is None and folder is not None:
                self._start_folder_files(gen, job, folder, kind_now)
            self._post_rows(
                gen, job, rows, error, folder_label, 0, folder, project, rev_options, located, eddi_contexts
            )

        threading.Thread(target=work, daemon=True).start()

    def _located_from_pack(self, folder: Path | None, job: str, rows: list) -> dict:
        """Saved PDF paths from client-pack.json. Does not open Excel or walk PDFs."""
        if folder is None:
            return {}
        try:
            matched, _orphans = match_pdf_hits(rows, [], job)
            pack = load_client_pack(folder, job)
            previous_located = dict(pack.located_pdfs) if pack else {}
            matched = apply_located_pdfs(matched, previous_located)
            located = keep_located_pdfs(matched, previous_located)
            sweep_replaced_dropped_copies(matched, previous_located)
        except (OSError, ValueError, TypeError):
            return {}
        return located

    def _post_rows(
        self,
        gen: int,
        job: str,
        rows: list,
        error: str | None,
        folder_label: str,
        orphans: int,
        folder: Path | None,
        project,
        rev_options: dict,
        located: dict,
        eddi_contexts: dict,
    ) -> None:
        matched: list = []
        if error is None:
            self._post_load(gen, *LOAD_STEPS["match"])
            self._post_status(gen, f"Matching PDFs for {job}…")
            matched, _extra = match_pdf_hits(rows, [], job)
            with contextlib.suppress(OSError, ValueError, TypeError):
                matched = apply_located_pdfs(matched, located)
        self._pending_rows = (
            gen,
            job,
            matched,
            error,
            folder_label,
            orphans,
            folder,
            project,
            rev_options,
            located,
            eddi_contexts,
        )

    def _attach_job_folder(
        self,
        gen: int,
        job: str,
        folder: Path | None,
        folder_label: str,
        located: dict,
    ) -> None:
        """Folder hunt finished after the list was painted. Do not clobber typed Next."""
        if gen != self._load_gen or self._job_number != job:
            return
        self._job_folder = folder
        self._reset_locate_to_job(folder)
        self._set_job_identity(self._job_project, folder)
        self._located_pdfs.update(located)
        if self._matches:
            drawings = [row.drawing for row in self._matches.values()]
            matched, _orphans = match_pdf_hits(drawings, [], job)
            matched = apply_located_pdfs(matched, self._located_pdfs)
            for row in matched:
                self._matches[row.drawing.key] = row
                self.board.apply_pdf(row)
        if (
            folder is not None
            and self._work != "load"
            and not self.board.pending_rows()
            and self._cover_text_now() == self._cover_stamp
        ):
            self._restore_pack(folder, job, self._pep_cover)
        label = folder_label or (folder.name if folder is not None else "job folder not found")
        if self._work != "load":
            missing = sum(1 for row in self._matches.values() if row.confidence == "Missing")
            self._set_status(f"{job}: {len(self._matches)} drawing(s), {missing} missing PDF  |  {label}")

    def _start_folder_files(self, gen: int, job: str, folder: Path, kind: str) -> None:
        """PDF hunt, letter, and PEP stay off the window thread so clicks keep working."""

        def files() -> None:
            adopted_label = ""
            hits: list = []
            pep_path: Path | None = None
            pep_cover: PepCover | None = None
            book = BookCover()
            try:
                self._post_status(gen, f"Scanning PDFs in {folder.name}…")
                adopted = adopt_transmittal_books(folder, job)
                if adopted:
                    names = ", ".join(item.path.name for item in adopted)
                    adopted_label = f"  |  named {names}"
                hits = scan_job_pdfs(folder)
                self._post_folder_files(gen, job, hits, adopted_label, None, None, BookCover(), kind)
                try:
                    pep_path = find_pep(folder, job)
                except (OSError, PepError, ValueError):
                    pep_path = None
                if pep_path is not None:
                    try:
                        pep_cover = load_pep(pep_path)
                    except PepError:
                        pep_cover = None
                try:
                    book = book_cover_for_job(folder, job, kind)
                except (OSError, KeyError, ValueError, TypeError):
                    book = BookCover()
                library = scan_library_pdfs(folder)
                if library:
                    hits = [*hits, *library]
            except Exception as exc:
                log("WARN", "load", f"folder files {exc}")
            self._post_folder_files(gen, job, hits, adopted_label, pep_path, pep_cover, book, kind)

        threading.Thread(target=files, daemon=True).start()

    def _post_folder_files(
        self,
        gen: int,
        job: str,
        hits: list,
        adopted_label: str,
        pep_path: Path | None,
        pep_cover: PepCover | None,
        book: BookCover,
        kind: str,
    ) -> None:
        payload = (gen, job, hits, adopted_label, pep_path, pep_cover, book, kind)
        with contextlib.suppress(tk.TclError, RuntimeError):
            self.after(0, lambda item=payload: self._apply_folder_files(item))

    def _apply_folder_files(self, payload: tuple) -> None:
        gen, job, hits, adopted_label, pep_path, pep_cover, book, kind = payload
        if gen != self._load_gen or self._job_number != job:
            return
        if self._work == "load" or not self._matches or len(self.board._blocks) < len(self._matches):
            self._pending_files = payload
            return
        self._pending_files = None
        if not isinstance(book, BookCover):
            book = BookCover()
        self._book_covers[kind] = book
        drawings = [row.drawing for row in self._matches.values()]
        matched, orphans = match_pdf_hits(drawings, hits, job)
        matched = apply_located_pdfs(matched, self._located_pdfs)
        for row in matched:
            self._matches[row.drawing.key] = row
            self.board.apply_pdf(row)
        if isinstance(pep_cover, PepCover):
            self._pep_cover = pep_cover
        if pep_path is not None:
            self._set_pep(pep_path)
        if self.kind.get() == kind:
            self._fill_cover_if_untouched(kind)
        extra = f"  |  {orphans} extra PDF(s) not in Jira" if orphans else ""
        folder_name = self._job_folder.name if self._job_folder is not None else job
        missing = sum(1 for row in self._matches.values() if row.confidence == "Missing")
        self._set_status(
            f"{job}: {len(matched)} drawing(s), {missing} missing PDF  |  {folder_name}{adopted_label}{extra}"
        )

    def _cover_text_now(self) -> tuple[str, str, str]:
        return (
            self._email_value(self.to_box),
            self._email_value(self.cc_box),
            self._text_value(self.project_box),
        )

    def _fill_cover_if_untouched(self, kind: str) -> None:
        """Letter and PEP arrive after the list. Leave anything she already typed."""
        if self._cover_text_now() != self._cover_stamp:
            return
        pep = self._pep_cover if kind == CLIENT else None
        pack = load_client_pack(self._job_folder, self._job_number)
        pack_to, pack_cc = cover_recipients(pack, kind)
        field_to, field_cc = self._field_default_lines()
        shop_to, shop_cc = self._shop_default_lines()
        chosen = pick_cover_fields(
            book=self._book_covers.get(kind, BookCover()),
            pack_to=pack_to,
            pack_cc=pack_cc,
            pack_project=pack.project_description if pack else "",
            pep=pep,
            kind=kind,
            field_to=field_to,
            field_cc=field_cc,
            shop_to=shop_to,
            shop_cc=shop_cc,
        )
        self._cover_loading = True
        try:
            self._set_text(self.to_box, email_line(chosen.to_line))
            self._set_text(self.cc_box, email_line(chosen.cc_line))
            self._set_text(self.project_box, chosen.project_description)
        finally:
            self._cover_loading = False
        self._cover_stamp = self._cover_text_now()

    def _cancel_load(self) -> None:
        self.board.cancel_paint()
        self._pending_rows = None
        self._pending_files = None
        self._book_covers = {}
        self._load_note = None
        keep_meter = bool(self._create_wait_key) and self._progress.mode() != "idle"
        if not keep_meter:
            self._stop_progress()
        if self._work == "load":
            self._busy = False
            self._work = ""

    def _post_status(self, gen: int, text: str) -> None:
        """Worker threads only store text. The main-thread pump paints it."""
        self._load_note = (gen, text)

    def _post_load(self, gen: int, pct: int, cap: int, caption: str) -> None:
        """Worker threads store a Load step. The pump moves the button."""
        self._load_mark = (gen, int(pct), int(cap), caption)

    def _mark_load(self, pct: int, cap: int, caption: str) -> None:
        """Move the Load button forward. A later step never pulls the percent back."""
        pct = max(0, min(100, int(pct)))
        cap = max(0, min(100, int(cap)))
        if pct >= self._load_shown:
            self._load_shown = pct
            if caption:
                self._load_caption = caption
        if cap > self._load_cap:
            self._load_cap = cap
        if self._load_cap < self._load_shown:
            self._load_cap = self._load_shown
        self.load_btn.set_progress(self._load_shown, self._load_caption)
        if self._load_meter.winfo_manager():
            self._progress.set_determinate(self._load_shown, 100)

    def _creep_load(self) -> None:
        """Nudge the bar while a step has no finer count, so a long Jira call still moves."""
        if self._work != "load" or self._load_shown >= self._load_cap:
            return
        now = time.monotonic()
        if now - self._load_creep < LOAD_CREEP_S:
            return
        self._load_creep = now
        self._load_shown += 1
        self.load_btn.set_progress(self._load_shown, self._load_caption)
        if self._load_meter.winfo_manager():
            self._progress.set_determinate(self._load_shown, 100)

    def _pump_load_ui(self) -> None:
        self._load_pump = ""
        note = self._load_note
        if note:
            gen, text = note
            if gen == self._load_gen:
                self._set_status(text)
        mark = self._load_mark
        if mark is not None:
            gen, pct, cap, caption = mark
            if self._load_mark is mark:
                self._load_mark = None
            if gen == self._load_gen:
                self._mark_load(pct, cap, caption)
        self._creep_load()
        pending = self._pending_rows
        if pending is not None:
            self._pending_rows = None
            self._show_rows(*pending)
        if self._work == "load" or self._progress.mode() != "idle":
            with contextlib.suppress(tk.TclError, RuntimeError):
                self._load_pump = self.after(80, self._pump_load_ui)

    def _start_progress(self, text: str = "") -> None:
        if not self._load_meter.winfo_manager():
            self._load_meter.pack(fill="x", pady=(10, 0))
        if text:
            self._set_status(text)
        self._progress.start_indeterminate()
        self._pump_load_ui()
        with contextlib.suppress(tk.TclError):
            self.update_idletasks()

    def _paint_progress(self, done: int, total: int) -> None:
        if self.load_btn.busy():
            count = max(int(total), 0)
            painted = max(0, min(int(done), count)) if count else 0
            caption = f"Painting {painted} of {count}" if count else "Painting the list"
            pct = paint_load_percent(painted, count)
            self._mark_load(pct, pct, caption)
            return
        self._progress.set_determinate(done, total)

    def _stop_progress(self) -> None:
        if self._load_pump:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._load_pump)
            self._load_pump = ""
        self._progress.stop()
        self._load_meter.pack_forget()
        if hasattr(self, "_load_status"):
            self._load_status.configure(text="")
        if hasattr(self, "load_btn"):
            self.load_btn.finish()
        self._load_shown = 0
        self._load_cap = 0
        self._load_caption = ""
        self._load_mark = None

    def _show_rows(
        self,
        gen: int,
        job: str,
        matched: list[MatchedRow],
        error: str | None,
        folder_label: str,
        orphans: int,
        job_folder: Path | None = None,
        job_project: JobProject | None = None,
        rev_options: dict[str, tuple[str, ...]] | None = None,
        located: dict | None = None,
        eddi_contexts: dict[str, tuple[FieldOption, ...]] | None = None,
    ) -> None:
        if gen != self._load_gen:
            return
        close_pdf_preview()
        self._eddi_contexts = dict(eddi_contexts or {})
        self._matches = {}
        self._job_folder = job_folder
        self._reset_locate_to_job(job_folder)
        self._job_number = job
        self._set_job_identity(job_project, job_folder, jira_error=bool(error))
        self.board.cancel_paint()
        if error:
            self._busy = False
            self._work = ""
            self._create_focus_key = ""
            self._located_pdfs = {}
            self._set_pep(None)
            self._clear_cover_fields()
            self._set_new_issue_enabled(False)
            self._stop_progress()
            self._set_status("Load failed.")
            messagebox.showerror("Jira", error)
            return
        if self._resolve_eddi_conflicts([row.drawing for row in matched]):
            return
        self._located_pdfs = dict(located or {})
        missing = 0
        for row in matched:
            self._matches[row.drawing.key] = row
            if row.confidence == "Missing":
                missing += 1
        extra = f"  |  {orphans} extra PDF(s) not in Jira" if orphans else ""
        self._set_status(f"Painting 0 of {len(matched)} on {job}…")
        self.board.set_rev_options(rev_options)
        self.board.set_eddi_options(
            {key: eddi_option_labels(options) for key, options in self._eddi_contexts.items()}
        )
        self._paint_progress(0, max(len(matched), 1))

        def on_progress(done: int, count: int) -> None:
            if gen != self._load_gen:
                return
            self._paint_progress(done, count)
            self._set_status(f"Painting {done} of {count} on {job}…")

        def on_done() -> None:
            self._finish_load(gen, job, matched, missing, folder_label, extra)

        self.board.start_rows(matched, checked=set(), on_progress=on_progress, on_done=on_done)

    def _finish_load(
        self,
        gen: int,
        job: str,
        matched: list[MatchedRow],
        missing: int,
        folder_label: str,
        extra: str,
    ) -> None:
        if gen != self._load_gen:
            return
        self._busy = False
        self._work = ""
        self._mark_load(*LOAD_STEPS["cover"])
        self._set_status(f"{job}: cover dates N/A, Pack off…")
        self.after(1, lambda: self._finish_cover(gen, job, matched, missing, folder_label, extra))

    def _finish_cover(
        self,
        gen: int,
        job: str,
        matched: list[MatchedRow],
        missing: int,
        folder_label: str,
        extra: str,
    ) -> None:
        if gen != self._load_gen:
            return
        self._restore_pack(self._job_folder, job, None)
        self._save_pack(quiet=True, force=True)
        cover = self._cover_suffix()
        pep = self._pep_suffix()
        self._stop_progress()
        self._set_new_issue_enabled(True)
        focus = (self._create_focus_key or "").strip()
        self._create_focus_key = ""
        if focus:
            self.board.focus_key(focus)
        self._set_status(
            f"{job}: {len(matched)} drawing(s), {missing} missing PDF  |  {folder_label}{extra}{cover}{pep}"
        )
        self._refresh_shop_place()
        self._start_watcher()
        pending = self._pending_files
        if pending is not None:
            self._apply_folder_files(pending)

    def _reset_locate_to_job(self, folder: Path | None) -> None:
        """First Locate… after Load starts in this job's Dropbox folder, not the last PC folder."""
        if folder is not None and folder.is_dir():
            self._locate_dir = str(folder)
            return
        self._locate_dir = ""

    def _remember_pdf_folder(self, path: Path) -> None:
        """Keep Locate… in the folder just picked, until the next Load."""
        remember_locate_dir(path)
        folder = Path(path)
        if folder.is_file():
            folder = folder.parent
        if folder.is_dir():
            self._locate_dir = str(folder)

    def _picker_dir(self) -> str:
        token = (self._locate_dir or "").strip()
        if token and Path(token).is_dir():
            return token
        if self._job_folder is not None and self._job_folder.is_dir():
            return str(self._job_folder)
        return locate_start_dir(os.getcwd())

    def _selected_row(self) -> MatchedRow | None:
        return self.board.focused_row()

    def _selected_rows(self) -> list[MatchedRow]:
        return self.board.selected_rows()

    def _ask_eddi_fixes(self, conflicts: list[EddiConflict]) -> dict[str, str]:
        if threading.current_thread() is not threading.main_thread():
            log("WARN", "load", "EDDI fixer skipped: not on the UI thread")
            return {}
        dialog = EddiConflictDialog(self, conflicts)
        self.wait_window(dialog)
        return dict(dialog.result)

    def _resolve_eddi_conflicts(self, drawings: list[DrawingRow]) -> bool:
        """Prompt for multi-status EDDI. True when Jira was written and Load will re-run."""
        conflicts = eddi_conflicts(drawings, self._eddi_contexts)
        if not conflicts:
            return False
        self._set_status(f"{len(conflicts)} issue(s) have more than one EDDI Status…")
        picks = self._ask_eddi_fixes(conflicts)
        if not picks:
            return False
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            return False
        try:
            for key, status in picks.items():
                update_eddi_status(
                    settings.site,
                    settings.email,
                    token,
                    key,
                    status,
                    self._eddi_contexts.get(key, ()),
                )
        except (JiraError, OSError) as exc:
            messagebox.showerror("EDDI Status", str(exc))
            return False
        self._busy = False
        self._work = ""
        self._stop_progress()
        self._set_status("EDDI Status updated. Reloading…")
        self._reloading_after_eddi_fix = True
        self.after_idle(self._load)
        return True

    def _note_if_busy(self) -> bool:
        if not self._busy:
            return False
        self._set_status("Still loading this job. Clicks work again when the list is up.")
        return True

    def _new_issue(self) -> None:
        if self._note_if_busy():
            return
        job = self._current_job()
        if not job or not self._job_number:
            messagebox.showinfo("New issue", "Load a job first.")
            return
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            self._settings()
            return
        project = self._job_project
        if project is None or not (project.key or "").strip():
            messagebox.showinfo("New issue", f"{MISSING_JIRA_PROJECT}. Cannot create a Sub-task.")
            return
        self._busy = True
        self._work = "create"
        self._set_new_issue_enabled(False)
        self._start_progress("Loading new issue fields…")

        def work() -> None:
            error: str | None = None
            epic: EpicCopy | None = None
            parents: list[PackageTask] = []
            options: tuple[FieldOption, ...] = ()
            try:
                epic = fetch_epic_copy(settings.site, settings.email, token, project.key)
                if not (epic.job_number or "").strip():
                    error = "The Jira Project has no Job Number. Nothing was created."
                else:
                    parents = fetch_parent_tasks(
                        settings.site,
                        settings.email,
                        token,
                        job,
                        settings.project_key,
                        epic.key or project.key,
                    )
                    options = fetch_subtask_eddi_options(
                        settings.site, settings.email, token, settings.project_key
                    )
            except (JiraError, OSError, ValueError, TypeError) as exc:
                error = str(exc)
            self.after(
                0,
                lambda: self._new_issue_fields_ready(error, epic, parents, options, job),
            )

        threading.Thread(target=work, daemon=True).start()

    def _new_issue_fields_ready(
        self,
        error: str | None,
        epic: EpicCopy | None,
        parents: list[PackageTask],
        options: tuple[FieldOption, ...],
        job: str,
    ) -> None:
        self._stop_progress()
        self._busy = False
        self._work = ""
        self._set_new_issue_enabled(True)
        if error:
            messagebox.showerror("New issue", error)
            return
        if epic is None:
            messagebox.showerror("New issue", f"{MISSING_JIRA_PROJECT}. Cannot create a Sub-task.")
            return
        if not parents:
            messagebox.showinfo(
                "New issue",
                "No package Task under this Project. Create the parent Task in Jira first.",
            )
            return
        if not options:
            messagebox.showerror("New issue", "Jira sent no EDDI Status options for Sub-task.")
            return
        epic_label = jira_project_label(JobProject(key=epic.key, summary=epic.summary))
        dialog = CreateIssueDialog(
            self,
            epic_label=epic_label,
            parents=parents,
            eddi_options=options,
            job_prefix=epic.job_number or job,
        )
        self.wait_window(dialog)
        choice = dialog.result
        if choice is None:
            return
        parent_key, eddi_label, drawing_id, description = choice
        self._post_new_issue(parent_key, eddi_label, drawing_id, description, epic, options)

    def _post_new_issue(
        self,
        parent_key: str,
        eddi_label: str,
        drawing_id: str,
        description: str,
        epic: EpicCopy,
        options: tuple[FieldOption, ...],
    ) -> None:
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            return
        error = new_issue_preflight_error(
            drawing_id=drawing_id,
            parent_key=parent_key,
            eddi_label=eddi_label,
            job_number=epic.job_number,
            eddi_options=options,
        )
        if error:
            messagebox.showerror("New issue", error)
            return
        self._busy = True
        self._work = "create"
        self._set_new_issue_enabled(False)
        self._start_progress("Creating on Jira…")

        def work() -> None:
            key = ""
            err: str | None = None
            try:
                key = create_subtask(
                    settings.site,
                    settings.email,
                    token,
                    jira_project=settings.project_key,
                    parent_key=parent_key,
                    drawing_id=drawing_id,
                    description=description,
                    job_number=epic.job_number,
                    eddi_label=eddi_label,
                    eddi_options=options,
                    lead_account_ids=epic.lead_account_ids,
                )
            except (JiraError, OSError, ValueError, TypeError) as exc:
                err = str(exc)
            self.after(0, lambda: self._new_issue_written(err, key, drawing_id))

        threading.Thread(target=work, daemon=True).start()

    def _new_issue_written(self, error: str | None, key: str, drawing_id: str) -> None:
        if error:
            self._stop_progress()
            self._busy = False
            self._work = ""
            self._create_wait_key = ""
            self._create_focus_key = ""
            self._set_new_issue_enabled(True)
            messagebox.showerror("New issue", error)
            return
        self._load_note = None
        self._create_wait_key = key
        self._create_focus_key = key
        self._set_status(f"Created {drawing_id} ({key}).")
        log("INFO", "jira", f"created sub-task {key} id={drawing_id}")
        self.after(CREATE_CREATED_MS, self._reload_after_create)

    def _reload_after_create(self) -> None:
        if not (self._create_wait_key or "").strip():
            self._busy = False
            self._work = ""
            self._stop_progress()
            self._set_new_issue_enabled(bool(self._job_number))
            return
        self._work = ""
        self._load()
        if self._work != "load":
            self._busy = False
            self._stop_progress()
            self._create_wait_key = ""
            self._create_focus_key = ""
            self._set_new_issue_enabled(bool(self._job_number))

    def _print_eddi(self) -> None:
        if self._note_if_busy():
            return
        job = self._current_job()
        folder = self._ensure_job_folder(job) if job else None
        if not job:
            messagebox.showinfo("EDDI", "Enter a Job Number and click Load first.")
            return
        if folder is None:
            messagebox.showerror(
                "EDDI",
                f"No Dropbox job folder for {job}. Check Current Jobs, then Load again.",
            )
            return
        drawings = eddi_print_drawings(self.board.current_rows())
        if not self.board.current_rows():
            messagebox.showinfo("EDDI", "Load a job first.")
            return
        try:
            issued = parse_issued_date(self.issued.get())
        except LogError as exc:
            messagebox.showerror("EDDI", str(exc))
            return
        if not messagebox.askyesno(
            "EDDI?",
            (
                f"Print a dated copy of the EDDI form for {job} "
                f"({len(drawings)} row(s) with a matched PDF; "
                "Missing and Generic are omitted).\n"
                "Fills a snapshot in 3.0 Doc Con from the latest Next values. "
                "Does not change the live EDDI book.\n"
                "Does not file a transmittal, write Jira, or open Outlook."
            ),
        ):
            return
        self._busy = True
        self._work = "eddi"
        self._set_status(f"Printing EDDI for {job}…")

        def work() -> None:
            error: str | None = None
            note = ""
            try:
                snap = snapshot_eddi(folder, job, drawings, issued)
                note = snap.note
            except (LogError, OSError) as exc:
                error = str(exc)
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda e=error, n=note: self._eddi_printed(e, n))

        threading.Thread(target=work, daemon=True).start()

    def _eddi_printed(self, error: str | None, note: str) -> None:
        self._busy = False
        self._work = ""
        if error:
            self._set_status("EDDI failed.")
            messagebox.showerror("EDDI", error)
            return
        self._set_status(note)
        messagebox.showinfo("EDDI", f"{note}\nSaved in 3.0 Doc Con. Not attached to Outlook.")

    def _jira_change_note(self, rows: list[MatchedRow], *, packed: bool = False) -> str:
        if not rows:
            where = " on packed drawings" if packed else ""
            return f"\n\nNo Jira field or status changes{where}."
        extra = f"\n\nJira Next values will be written on {len(rows)} drawing(s):"
        for row in rows:
            current = self._matches.get(row.drawing.key)
            was = current.drawing.status if current is not None else "—"
            extra += (
                f"\n  {row.drawing.key}  {was} → {row.drawing.status}"
                f"  Out {row.drawing.outgoing_rev or '—'}"
                f"  Client Doc No. {row.drawing.client_document_number or '—'}"
            )
        return extra

    def _update_jira(self) -> None:
        if self._note_if_busy():
            return
        job = self._current_job()
        if not job or not self._matches:
            messagebox.showinfo("Update Jira", "Load a job first.")
            return
        pending = self.board.pending_rows()
        if not pending:
            messagebox.showinfo(
                "Update Jira",
                "No Next edits to write. Change a Next box, then Update Jira.\n"
                "Pack ticks are not required (those are for Confirm).",
            )
            return
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            self._settings()
            return
        extra = self._jira_change_note(pending)
        if not messagebox.askyesno(
            "Update Jira?",
            (
                f"Write Next values to Jira for {job} ({len(pending)} item(s)).\n"
                "Does not file a transmittal, print EDDI, or open Outlook.\n"
                "If a check fails, nothing is written."
                f"{extra}"
            ),
        ):
            return
        originals = {
            row.drawing.key: self._matches[row.drawing.key].drawing
            for row in pending
            if row.drawing.key in self._matches
        }
        pairs = [(originals.get(row.drawing.key, row.drawing), row.drawing) for row in pending]
        eddi_contexts = dict(self._eddi_contexts)
        self._busy = True
        self._work = "jira"
        self._start_progress()
        self._set_status(f"Updating Jira for {job}…")

        def work() -> None:
            error: str | None = None
            try:
                run_jira_register_update(
                    settings.site, settings.email, token, pairs, eddi_contexts
                )
            except (JiraError, OSError) as exc:
                error = str(exc)
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda e=error, rows=list(pending): self._jira_updated(e, rows))

        threading.Thread(target=work, daemon=True).start()

    def _jira_updated(self, error: str | None, rows: list[MatchedRow]) -> None:
        self._busy = False
        self._work = ""
        self._stop_progress()
        if error:
            self._set_status("Jira update failed.")
            messagebox.showerror("Update Jira", error)
            return
        for row in rows:
            self._apply_row(row)
        self._save_pack(quiet=True)
        self._refresh_cover_hint()
        self._set_status(f"Updated {len(rows)} item(s) in Jira.")
        messagebox.showinfo(
            "Jira updated",
            f"Jira has been updated.\n\nWrote {len(rows)} item(s). The list now shows what was written.",
        )

    def _issue_pack(self) -> None:
        if self._note_if_busy():
            return
        kind = self.kind.get()
        label = LABELS.get(kind, LABELS[CLIENT])
        if kind == INCOMING:
            messagebox.showinfo(
                label,
                "Incoming does not file a transmittal letter.\n"
                "Tick Pack, set Return Date, Incoming Rev, and Client Approval Status on the row under the filter, "
                "then Update Jira.",
            )
            return
        job = self._current_job()
        folder = self._ensure_job_folder(job) if job else None
        if not job:
            messagebox.showinfo(label, "Enter a Job Number and click Load first.")
            return
        if folder is None:
            messagebox.showerror(
                label,
                f"No Dropbox job folder for {job}. Check Current Jobs, then Load again.",
            )
            return
        rows = self._selected_rows()
        pack_extras = [item for item in self._current_extras() if item.packed]
        if not rows and not pack_extras:
            messagebox.showinfo(label, "Tick Pack on the drawings for this send.")
            return
        missing_extra = next((item for item in pack_extras if not Path(item.path).is_file()), None)
        if missing_extra is not None:
            who = (missing_extra.document_no or "").strip() or "A Non Jira row"
            messagebox.showerror(
                label,
                f"{who} has no PDF. Locate one, or Assign it from New PDFs.",
            )
            return
        try:
            book = prepare_book(folder, job, kind)
            info = inspect_book(book, job, kind)
        except (LogError, OSError) as exc:
            messagebox.showerror(label, str(exc))
            return
        try:
            issued = parse_issued_date(self.issued.get())
            expected = parse_expected_return(self.expected.get())
        except LogError as exc:
            messagebox.showerror(label, str(exc))
            return
        cover = self._cover_for_write()
        if cover is None:
            return
        packed_keys = {row.drawing.key for row in rows}
        jira_rows = [row for row in self.board.pending_rows() if row.drawing.key in packed_keys]
        eddi_drawings = eddi_print_drawings(self.board.current_rows())
        originals = {
            row.drawing.key: self._matches[row.drawing.key].drawing
            for row in jira_rows
            if row.drawing.key in self._matches
        }
        eddi_contexts = dict(self._eddi_contexts)
        settings, token = _session()
        if jira_rows and (not settings.email or not token):
            messagebox.showinfo("Settings", "Open Settings and save your Jira email and API token first.")
            self._settings()
            return
        names = "\n".join(f"  {row.drawing.drawing_id or row.drawing.key}" for row in rows)
        if pack_extras:
            extra_names = "\n".join(f"  {item.document_no} (no Jira)" for item in pack_extras)
            names = f"{names}\n{extra_names}".strip()
        extra = ""
        if info.filed_tabs:
            extra = f"\nThis book already has filed tabs: {', '.join(info.filed_tabs)}."
        missing = sum(1 for row in rows if row.pdf is None)
        if missing:
            extra += f"\n{missing} packed drawing(s) have no PDF and will not be attached."
        extra += self._jira_change_note(jira_rows, packed=True)
        expected_label = expected.isoformat() if isinstance(expected, date) else expected
        wording = load_mail_formats().get(mail_kind_key(kind), ("", ""))
        subject = draft_subject(info.cover_id, info.job_number, template=wording[0])
        cover_pdf = f"{info.cover_id}.pdf"
        shop_root: Path | None = None
        shop_copies: list[tuple[Path, str]] = []
        if kind == SHOP:
            self._refresh_shop_place()
            shop_root = self._shop_root
            if shop_root is None:
                messagebox.showerror(label, MISSING_SHOP_FOLDER)
                return
            picks = self.board.shop_folder_picks()
            for row in rows:
                if row.pdf is not None and row.pdf.path.is_file():
                    shop_copies.append((row.pdf.path, picks.get(row.drawing.key, "Root")))
            for item in pack_extras:
                shop_copies.append((Path(item.path), picks.get(item.id, "Root")))
        if kind == SHOP:
            file_line = (
                f"file {info.cover_id}, copy the drawings into the shop folder, "
                f"attach only the transmittal form, "
            )
            attach_line = (
                f"Attachments: {cover_pdf} only. Drawings are copied into {shop_root.name}, not zipped.\n"
            )
        else:
            file_line = (
                f"file {info.cover_id}, attach the transmittal PDF and a zip of the drawing PDFs, "
            )
            attach_line = (
                f"Attachments: {cover_pdf} plus {info.cover_id}.zip "
                f"(drawings only; not the transmittal form).\n"
            )
        if not messagebox.askyesno(
            "Confirm?",
            (
                f"One click: check that Jira and the log can be written, then update Jira, "
                f"{file_line}"
                f"open an Outlook draft from THIS PC.\n"
                f"If a check fails, nothing is written.\n\n"
                f"{book}\n\n"
                f"{names}{extra}\n\n"
                f"PEP: {cover.path.name}\n"
                f"FROM: {cover.from_address}\n"
                f"TO: {cover.to_line}\n"
                f"CC: {cover.cc_line or '(none)'}\n"
                f"{cover.project_description}\n"
                f"Date issued: {issued.isoformat()}\n"
                f"Expected return: {expected_label}\n"
                f"Subject: {subject}\n"
                f"{attach_line}"
                "Also prints a dated copy of the EDDI form "
                "(matched PDFs only, not only this pack; live book unchanged; not attached).\n\n"
                f"Close the {PREFIX[kind]} book first. Nothing is sent until you click Send in Outlook."
            ),
        ):
            return
        if not self._save_pack(quiet=True, force=True):
            return
        lines = lines_from_rows(rows, kind) + lines_from_extras(pack_extras, kind)
        extra_pdfs = [Path(item.path) for item in pack_extras]
        self._busy = True
        self._work = "confirm"
        self._job_number = job
        self._job_folder = folder
        self._set_status(f"Confirming {info.cover_id}…")

        def work() -> None:
            error: str | None = None
            cover_id = info.cover_id
            note = ""
            saved_attach = f"{info.cover_id}.pdf"
            jira_ok = False
            pairs = [
                (originals.get(row.drawing.key, row.drawing), row.drawing) for row in jira_rows
            ]
            try:
                result = run_confirm_client_pack(
                    site=settings.site,
                    email=settings.email,
                    token=token,
                    pairs=pairs,
                    book=book,
                    job=job,
                    lines=lines,
                    issued=issued,
                    expected_return=expected,
                    cover=cover,
                    rows=rows,
                    kind=kind,
                    job_folder=folder,
                    eddi_drawings=eddi_drawings,
                    eddi_contexts=eddi_contexts,
                    extra_pdfs=extra_pdfs,
                    shop_root=shop_root,
                    shop_copies=shop_copies,
                )
                cover_id = result.cover_id
                saved_attach = result.attach_note
                note = result.pdf_note
                jira_ok = result.jira_written
            except ConfirmDeliveryError as exc:
                error = str(exc)
                cover_id = exc.cover_id
                saved_attach = exc.attach_note
                note = exc.pdf_note
                jira_ok = True
            except (JiraError, LogError, OSError) as exc:
                error = str(exc)
            packed = list(jira_rows)
            self.after(
                0,
                lambda c=cover_id, e=error, n=note, z=saved_attach, f=folder, j=job, u=packed, ok=jira_ok: (
                    self._pack_issued(c, e, n, z, f, j, u, ok)
                ),
            )

        threading.Thread(target=work, daemon=True).start()

    def _pack_issued(
        self,
        cover: str,
        error: str | None,
        pdf_note: str,
        attach_note: str,
        folder: Path | None,
        job: str,
        jira_rows: list[MatchedRow] | None = None,
        jira_ok: bool = False,
    ) -> None:
        self._busy = False
        self._work = ""
        self._job_folder = folder
        self._job_number = job
        if jira_ok and jira_rows:
            for row in jira_rows:
                self._apply_row(row)
        if not error:
            self._consume_pack_extras()
        self._save_pack(quiet=True, force=True)
        self._refresh_cover_hint()
        label = LABELS.get(self.kind.get(), LABELS[CLIENT])
        extra = f"\n{pdf_note}" if pdf_note else ""
        jira_note = f"\nJira: {len(jira_rows)} drawing(s)." if jira_rows else "\nJira: no field changes."
        if error:
            self._set_status("Confirm failed.")
            if jira_ok:
                messagebox.showwarning(label, error + extra)
            else:
                messagebox.showerror(label, error + extra)
            return
        self._set_status(f"Confirmed {cover}.")
        messagebox.showinfo(
            label,
            f"Filed {cover}.{extra}{jira_note}\n{attach_note}\n"
            "Outlook draft is open from this PC's mailbox. Send it there.",
        )

    def _apply_row(self, row: MatchedRow) -> None:
        self._matches[row.drawing.key] = row
        self.board.apply_row(row)

    def _clear_drop_hover(self) -> None:
        if self._drop_hover_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._drop_hover_after)
            self._drop_hover_after = ""
        with contextlib.suppress(tk.TclError):
            self.configure(cursor="")
        self.board.set_drop_hover(None)

    def _on_paste_key(self, event) -> None:
        """Ctrl+V anywhere except a text box the operator is typing in."""
        widget = getattr(event, "widget", None)
        if isinstance(widget, tk.Text | tk.Entry | ttk.Entry):
            return
        self._paste_pdf()

    def _paste_pdf(self) -> None:
        """Outlook Copy on one or more attachments, then Paste PDF here."""
        log("INFO", "paste", "Paste PDF clicked")
        try:
            if self._note_if_busy():
                log("WARN", "paste", "ignored: console busy")
                return
            if not self._job_number or not self._matches:
                messagebox.showinfo("Paste PDF", LOAD_FIRST)
                return
            if self._job_folder is None:
                messagebox.showinfo("Paste PDF", NEED_FOLDER)
                return
            self._set_status("Reading the clipboard…")
            paths = clipboard_pdfs()
            log("INFO", "paste", f"clipboard pdfs={len(paths)}")
            if not paths:
                self._set_status("No PDF on the clipboard.")
                messagebox.showinfo("Paste PDF", NO_PDF_ON_CLIPBOARD)
                return
            self._ingest_pasted_pdfs(paths)
        except Exception as vis:
            log("WARN", "paste", f"paste {vis}")
            messagebox.showinfo("Paste PDF", NO_PDF_ON_CLIPBOARD)

    def _ingest_pasted_pdfs(self, paths: list[Path]) -> None:
        """One file or several: all wait in New PDFs. Assign pairs a drawing."""
        self._claim_inbox_paths(paths)
        self._park_pasted_batch(paths)

    def _park_pasted_batch(self, paths: list[Path]) -> None:
        """Multi Copy: stage every PDF, then Assign one by one. Do not pair the focused row."""
        if self._job_folder is None:
            messagebox.showinfo("Paste PDF", NEED_FOLDER)
            return
        try:
            staged, skipped = ingest_sources(self._job_folder, sources_from_paths(paths))
        except OSError as vis:
            messagebox.showerror("Paste PDF", str(vis) or "Could not copy those PDFs.")
            return
        extra = f"  ({skipped[0]})" if skipped else ""
        if not staged:
            messagebox.showinfo("Paste PDF", skipped[0] if skipped else NOT_PDF)
            return
        self._new_pdfs.extend(staged)
        self._show_new_pdfs()
        names = ", ".join(path.name for path in staged[:4])
        more = "…" if len(staged) > 4 else ""
        count = len(staged)
        noun = "PDF" if count == 1 else "PDFs"
        log("INFO", "paste", f"parked batch={count} in New PDFs: {names}")
        self._set_status(
            f"{count} {noun} in New PDFs: {names}{more} — Assign to a drawing, or Include with pack.{extra}"
        )

    def _claim_inbox_paths(self, paths: list[Path]) -> None:
        """Paste stages into the inbox, which the watcher also scans.

        Without this the operator's own paste came back ~1.5s later as a fresh
        'new PDF' and landed in the New PDFs strip, which looked like paste
        needing a second Assign step.
        """
        watcher = self._watcher
        if watcher is None:
            return
        for path in paths:
            watcher.mark_seen(path)
        log("INFO", "watch", f"claimed {len(paths)} staged file(s) from the watcher")

    def _start_watcher(self) -> None:
        """Watch Downloads / Desktop / inbox while a job is loaded. No COM, no Dropbox."""
        if self._watcher is None:
            self._watcher = InboxWatcher()
            log("INFO", "watch", f"watching {', '.join(str(f) for f in self._watcher.folders)}")
        self._arm_watch()

    def _arm_watch(self) -> None:
        if self._watch_after:
            return

        def tick() -> None:
            self._watch_after = ""
            try:
                self._poll_watch()
            except Exception as vis:
                log("WARN", "watch", f"poll {vis}")
            self._arm_watch()

        with contextlib.suppress(tk.TclError):
            self._watch_after = self.after(WATCH_POLL_MS, tick)

    def _poll_watch(self) -> None:
        watcher = self._watcher
        if watcher is None or self._busy:
            return
        if not self._job_number or not self._matches or self._job_folder is None:
            return
        found = watcher.poll()
        if not found:
            return
        names = ", ".join(path.name for path in found[:4])
        log("INFO", "watch", f"new pdfs={len(found)} names={names}")
        rows = list(self._matches.values())
        pairs, unmatched = plan_watch_hits(rows, found, self._job_number)
        paired = 0
        for key, path in pairs:
            row = self._matches.get(key)
            if row is None:
                continue
            try:
                staged, _skipped = ingest_sources(self._job_folder, sources_from_paths([path]))
            except OSError as vis:
                log("WARN", "watch", f"ingest {vis}")
                continue
            if not staged:
                continue
            updated, _leftover = apply_row_drop(row, staged, self._job_number)
            self._pair_located(updated, remember_folder=False, save=False)
            paired += 1
            log("INFO", "watch", f"paired row={key} pdf={staged[0].name}")
        if paired:
            self._save_pack(quiet=True)
            self._refresh_cover_hint()
        if unmatched:
            self._new_pdfs.extend(unmatched)
            self._show_new_pdfs()
        if paired and not unmatched:
            self._set_status(f"Picked up {paired} new PDF(s) from Downloads/Desktop.")
        elif unmatched:
            self._set_status(
                f"Picked up {paired} new PDF(s); {len(unmatched)} need a row — see New PDFs."
            )

    def _show_new_pdfs(self) -> None:
        self._new_pdf_list.delete(0, "end")
        for path in self._new_pdfs:
            self._new_pdf_list.insert("end", path.name)
        if not self._new_pdfs:
            with contextlib.suppress(tk.TclError):
                self._new_pdf_bar.pack_forget()
            return
        with contextlib.suppress(tk.TclError):
            if not self._new_pdf_bar.winfo_ismapped():
                before = self._pack_extra_bar if self._pack_extra_bar.winfo_ismapped() else self.board
                self._new_pdf_bar.pack(fill="x", pady=(0, 4), before=before)
        self._new_pdf_list.selection_clear(0, "end")
        self._new_pdf_list.selection_set(0)

    def _selected_new_pdf(self) -> int:
        try:
            picked = self._new_pdf_list.curselection()
        except tk.TclError:
            return -1
        if not picked:
            return -1
        index = int(picked[0])
        return index if 0 <= index < len(self._new_pdfs) else -1

    def _dismiss_new_pdf(self) -> None:
        index = self._selected_new_pdf()
        if index < 0:
            return
        dropped = self._new_pdfs.pop(index)
        log("INFO", "watch", f"dismissed {dropped.name}")
        self._show_new_pdfs()

    def _assign_new_pdf(self) -> None:
        index = self._selected_new_pdf()
        if index < 0:
            messagebox.showinfo("New PDFs", "Pick a PDF in the New PDFs list first.")
            return
        focus = self.board.explicit_focus_key()
        extra = self._extra_item(focus)
        if extra is not None:
            path = self._new_pdfs[index]
            if not path.is_file():
                messagebox.showinfo("New PDFs", f"Missing {path.name}.")
                return
            self._new_pdfs.pop(index)
            self._show_new_pdfs()
            self._replace_extra_file(extra, path)
            return
        key = self._paste_target_key()
        row = self._matches.get(key) if key else None
        if row is None:
            messagebox.showinfo(
                "New PDFs",
                "Click the drawing or Non Jira row you want this PDF on first.",
            )
            return
        if self._job_folder is None:
            messagebox.showinfo("New PDFs", NEED_FOLDER)
            return
        path = self._new_pdfs[index]
        try:
            staged, skipped = ingest_sources(self._job_folder, sources_from_paths([path]))
        except OSError as vis:
            messagebox.showerror("New PDFs", str(vis) or "Could not copy that PDF.")
            return
        if not staged:
            messagebox.showinfo("New PDFs", skipped[0] if skipped else NOT_PDF)
            return
        updated, _leftover = apply_row_drop(row, staged, self._job_number)
        self._pair_located(updated, remember_folder=False, save=True)
        self._new_pdfs.pop(index)
        self._show_new_pdfs()
        ident = updated.drawing.drawing_id or updated.drawing.key
        log("INFO", "watch", f"assigned {staged[0].name} row={updated.drawing.key}")
        self._set_status(f"Paired {staged[0].name} for {ident}.")

    def _show_pack_extras(self) -> None:
        if self._job_folder is None:
            with contextlib.suppress(tk.TclError):
                self._pack_extra_bar.pack_forget()
            return
        with contextlib.suppress(tk.TclError):
            if not self._pack_extra_bar.winfo_ismapped():
                self._pack_extra_bar.pack(fill="x", pady=(0, 4), before=self.board)

    def _current_extras(self) -> list[PackExtra]:
        if self.board.extras_painted():
            return self.board.pack_extras()
        return list(self._pack_extras)

    def _paint_extras(self, items: list[PackExtra]) -> None:
        self._pack_extras = list(items)
        self.board.set_pack_extras(items, statuses=layout_for(self.kind.get()).statuses)
        self._show_pack_extras()

    def _extra_path_taken(self, path: Path) -> bool:
        token = str(path).casefold()
        return any(item.path.casefold() == token for item in self._current_extras())

    def _add_pack_extra(self) -> None:
        if not self._job_number:
            messagebox.showinfo("Non Jira", "Enter a Job Number and click Load first.")
            return
        if self._job_folder is None:
            messagebox.showinfo("Non Jira", NEED_FOLDER)
            return
        chosen = filedialog.askopenfilename(
            title="Add a PDF with no Jira issue",
            initialdir=self._picker_dir(),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not chosen:
            return
        path = Path(chosen)
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            messagebox.showinfo("Non Jira", NOT_PDF)
            return
        if self._extra_path_taken(path):
            messagebox.showinfo("Non Jira", f"{path.name} is already on this pack.")
            return
        item = extra_from_path(path, kind=self.kind.get())
        self._remember_pdf_folder(path)
        self._show_extra(item)
        self._set_status(f"{item.document_no} is under Non Jira. No Jira issue.")

    def _add_blank_extra(self) -> None:
        if not self._job_number:
            messagebox.showinfo("Non Jira", "Enter a Job Number and click Load first.")
            return
        if self._job_folder is None:
            messagebox.showinfo("Non Jira", NEED_FOLDER)
            return
        item = blank_extra(kind=self.kind.get())
        self._show_extra(item)
        self._set_status(
            f"{item.document_no} is under Non Jira. Locate a PDF, or Assign one from New PDFs."
        )

    def _show_extra(self, item: PackExtra) -> None:
        self._paint_extras([*self._current_extras(), item])
        self.board.focus_key(item.id)
        self.board.reveal_key(item.id)
        self._save_pack(quiet=True)

    def _include_new_pdf(self) -> None:
        index = self._selected_new_pdf()
        if index < 0:
            messagebox.showinfo("Non Jira", "Pick a PDF in the New PDFs list first.")
            return
        if self._job_folder is None:
            messagebox.showinfo("Non Jira", NEED_FOLDER)
            return
        path = self._new_pdfs[index]
        if not path.is_file():
            messagebox.showinfo("Non Jira", f"Missing {path.name}.")
            return
        if self._extra_path_taken(path):
            messagebox.showinfo("Non Jira", f"{path.name} is already on this pack.")
            return
        item = extra_from_path(path, kind=self.kind.get())
        self._new_pdfs.pop(index)
        self._show_new_pdfs()
        waiting = self._extra_item(self.board.explicit_focus_key())
        if waiting is not None and not (waiting.path or "").strip():
            self._replace_extra_file(waiting, path)
            return
        self._show_extra(item)
        self._set_status(f"{item.document_no} is under Non Jira. No Jira issue.")

    def _remove_pack_extra(self) -> None:
        key = self.board.explicit_focus_key()
        items = self._current_extras()
        match = next((item for item in items if item.id == key), None)
        if match is None:
            messagebox.showinfo("Non Jira", "Click a Non Jira row first.")
            return
        self._paint_extras([item for item in items if item.id != key])
        self._save_pack(quiet=True)
        self._set_status(f"Removed {match.document_no} from this pack.")

    def _consume_pack_extras(self) -> None:
        """Create transmittal succeeded. Drop packed Non Jira rows and delete staged copies."""
        keep: list[PackExtra] = []
        for item in self._current_extras():
            if item.packed and item.email_dropped:
                delete_dropped_copy(item.path)
            if not item.packed:
                keep.append(item)
        self._paint_extras(keep)

    def _apply_drop(self, sources, root_x: int, root_y: int, *, strip_leftovers: bool = False) -> None:
        try:
            self._apply_drop_body(sources, root_x, root_y, strip_leftovers=strip_leftovers)
        except Exception as vis:
            log("WARN", "drop", f"apply {vis}")

    def _apply_drop_body(self, sources, root_x: int, root_y: int, *, strip_leftovers: bool = False) -> None:
        self._clear_drop_hover()
        names = ",".join((item.name or "?")[:80] for item in list(sources)[:6]) or "none"
        log("INFO", "drop", f"ingest names={names} count={len(list(sources))} pt={int(root_x)},{int(root_y)}")
        if self._busy:
            log("WARN", "drop", "ignored: console busy")
            return
        if not self._job_number or not self._matches:
            log("INFO", "drop", "fail: no job loaded")
            self.after(0, lambda: messagebox.showinfo("Paste PDF", LOAD_FIRST))
            return
        if self._job_folder is None:
            log("INFO", "drop", "fail: no job folder")
            self.after(0, lambda: messagebox.showinfo("Paste PDF", NEED_FOLDER))
            return
        try:
            pdfs, skipped = ingest_sources(self._job_folder, list(sources))
        except OSError as exc:
            msg = str(exc) or "Could not copy that PDF."
            log("WARN", "drop", f"ingest failed {msg}")
            self.after(0, lambda message=msg: messagebox.showerror("Paste PDF", message))
            return
        log(
            "INFO",
            "drop",
            f"ingest pdfs={len(pdfs)} skipped={skipped[0] if skipped else 'none'}",
        )
        self.after(
            0,
            lambda files=list(pdfs), notes=list(skipped), x=root_x, y=root_y, strip=strip_leftovers: (
                self._finish_drop(files, notes, x, y, strip_leftovers=strip)
            ),
        )

    def _finish_drop(
        self,
        pdfs: list[Path],
        skipped: list[str],
        root_x: int,
        root_y: int,
        *,
        strip_leftovers: bool = False,
    ) -> None:
        try:
            self._finish_drop_inner(pdfs, skipped, root_x, root_y, strip_leftovers=strip_leftovers)
        except Exception as vis:
            log("WARN", "drop", f"finish {vis}")

    def _row_ident(self, row: MatchedRow) -> str:
        """JIRA ID for the status line, falling back to the Jira issue key."""
        return (row.drawing.drawing_id or "").strip() or row.drawing.key

    def _paste_target_key(self) -> str:
        """Where an explicit paste lands: the clicked row, else a lone Pack tick.

        Deliberately strict. 'First of several packed rows' is a guess, and a
        wrong silent pair is worse than falling through to the filename match.
        """
        key = self.board.explicit_focus_key()
        if key and self._matches.get(key) is not None:
            return key
        packed = [item for item in self.board.selected_keys() if self._matches.get(item) is not None]
        if len(packed) == 1:
            return packed[0]
        return ""

    def _finish_drop_inner(
        self,
        pdfs: list[Path],
        skipped: list[str],
        root_x: int,
        root_y: int,
        *,
        strip_leftovers: bool = False,
    ) -> None:
        if not pdfs:
            note = skipped[0] if skipped else NOT_PDF
            log("INFO", "drop", f"fail: {note}")
            messagebox.showinfo("Paste PDF", note)
            return
        hit = None
        if int(root_x) >= 0 and int(root_y) >= 0:
            hit = self.board.row_key_at(root_x, root_y)
        hover = None
        hx, hy = self._drop_hover_pt
        if hx or hy:
            hover = self.board.row_key_at(hx, hy)
        if strip_leftovers:
            # Paste: only a real pick may claim the file.
            focused_key = self._paste_target_key() or None
        else:
            focused = self.board.focused_row()
            focused_key = focused.drawing.key if focused is not None else None
        key = (
            resolve_drop_row_key(focused_key, hit, hover)
            if int(root_x) < 0
            else resolve_drop_row_key(hit, hover)
        )
        leftover: list[Path] = []
        landed: list[tuple[str, str]] = []
        if key and self._matches.get(key) is not None:
            # An explicit selection always beats the filename guess.
            self.board.focus_key(key)
            updated, leftover = apply_row_drop(self._matches[key], pdfs, self._job_number)
            self._pair_located(updated, remember_folder=False, save=False)
            landed.append((self._row_ident(updated), self._paired_name(updated, pdfs)))
            log("INFO", "drop", f"paired selected row={key} leftover={len(leftover)}")
        else:
            rows = list(self._matches.values())
            updated_rows, leftover = apply_board_drop(rows, pdfs, self._job_number)
            dropped = {_drop_path_token(path) for path in pdfs}
            for row in updated_rows:
                if row.pdf is None:
                    continue
                if _drop_path_token(row.pdf.path) not in dropped:
                    continue
                self._pair_located(row, remember_folder=False, save=False)
                landed.append((self._row_ident(row), Path(row.pdf.path).name))
            log("INFO", "drop", f"paired board={len(landed)} leftover={len(leftover)}")
            leftover_key = resolve_drop_row_key(focused_key)
            if leftover and leftover_key and self._matches.get(leftover_key) is not None:
                self.board.focus_key(leftover_key)
                updated, leftover = apply_row_drop(self._matches[leftover_key], leftover, self._job_number)
                self._pair_located(updated, remember_folder=False, save=False)
                landed.append((self._row_ident(updated), self._paired_name(updated, pdfs)))
                log("INFO", "drop", f"paired selected={leftover_key} leftover={len(leftover)}")
        self._save_pack(quiet=True)
        self._refresh_cover_hint()
        extra = f"  ({skipped[0]})" if skipped else ""
        if leftover:
            self._park_new_pdfs(leftover, landed, extra)
            return
        self._set_status(f"Paired {self._landed_text(landed)}.{extra}")

    def _paired_name(self, row: MatchedRow, pdfs: list[Path]) -> str:
        if row.pdf is not None:
            return Path(row.pdf.path).name
        return pdfs[0].name if pdfs else "PDF"

    def _landed_text(self, landed: list[tuple[str, str]]) -> str:
        """`2026-Tanzim-1-1 REV A.pdf onto 2026-Tanzim-1-1` — filename and JIRA ID."""
        if not landed:
            return "0 PDF(s)"
        if len(landed) == 1:
            ident, name = landed[0]
            return f"{name} onto {ident}"
        shown = ", ".join(f"{name} onto {ident}" for ident, name in landed[:3])
        more = "…" if len(landed) > 3 else ""
        return f"{len(landed)} PDF(s): {shown}{more}"

    def _park_new_pdfs(
        self, leftover: list[Path], landed: list[tuple[str, str]], extra: str
    ) -> None:
        """Paste with nothing selected and no filename hit. Park, and say why."""
        self._new_pdfs.extend(leftover)
        self._show_new_pdfs()
        names = ", ".join(path.name for path in leftover[:4])
        log("INFO", "paste", f"parked {len(leftover)} in New PDFs: {names}")
        if landed:
            self._set_status(
                f"Paired {self._landed_text(landed)}; "
                f"{len(leftover)} in New PDFs — select a row, then Assign.{extra}"
            )
            return
        self._set_status(
            f"{names} did not match a row — Assign to a drawing, or Include with pack.{extra}"
        )
        messagebox.showinfo("Paste PDF", SELECT_ROW_FIRST)

    def _pair_located(self, row: MatchedRow, *, remember_folder: bool = True, save: bool = True) -> None:
        if row.pdf is None:
            return
        pdf_path = row.pdf.path
        self._located_pdfs[row.drawing.key] = LocatedPdf(
            path=str(pdf_path),
            email_dropped=bool(row.pdf.email_dropped),
        )
        if remember_folder:
            self._remember_pdf_folder(pdf_path)
        self._apply_row(row)
        rev = outgoing_rev_from_filename(pdf_path.name)
        if rev:
            self.board.stamp_outgoing_rev(row.drawing.key, rev)
        if save:
            self._save_pack(quiet=True)
            self._refresh_cover_hint()

    def _ask_rename_pdf(self, *, current: str, suggested: str) -> str | None:
        dialog = RenameDroppedDialog(self, current=current, suggested=suggested)
        self.wait_window(dialog)
        return dialog.result

    def _rename_pdf(self, key: str = "") -> None:
        if key:
            self.board.focus_key(key)
        row = self._matches.get(key) if key else None
        row = row or self._selected_row()
        if row is None or row.pdf is None:
            messagebox.showinfo("Rename PDF", "Paste a PDF onto this row first.")
            return
        if not pdf_is_email_dropped(row):
            messagebox.showinfo("Rename PDF", NOT_EMAIL_DROPPED)
            return
        current = row.pdf.path.name
        suggested = self.board.suggested_dropped_name(row.drawing.key) or current
        typed = self._ask_rename_pdf(current=current, suggested=suggested)
        if typed is None:
            return
        dest, error = rename_email_dropped_pdf(row.pdf.path, typed)
        if dest is None:
            messagebox.showerror("Rename PDF", error)
            return
        updated = pair_pdf(row, dest, email_dropped=True)
        self._matches[updated.drawing.key] = updated
        self._located_pdfs[updated.drawing.key] = LocatedPdf(
            path=str(dest),
            email_dropped=True,
        )
        self.board.apply_pdf(updated)
        rev = outgoing_rev_from_filename(dest.name)
        if rev:
            self.board.stamp_outgoing_rev(updated.drawing.key, rev)
        self._save_pack(quiet=True)
        self._refresh_cover_hint()
        self._set_status(f"Renamed to {dest.name} for {updated.drawing.drawing_id or updated.drawing.key}.")
        log("INFO", "drop", f"renamed dropped={dest.name} row={updated.drawing.key}")

    def _refresh_shop_place(self) -> None:
        if self.kind.get() != SHOP or not self._job_number:
            if self.shop_locate_btn.winfo_ismapped():
                self.shop_locate_btn.pack_forget()
            self._shop_root = None
            self.board.set_shop_folders(())
            return
        if not self.shop_locate_btn.winfo_ismapped():
            self.shop_locate_btn.pack(side="left", padx=(8, 0), before=self.send_btn)
        remembered = remembered_shop_folder(self._job_number)
        found = find_shop_ifc_folder(self._job_number, self._job_folder, remembered)
        self._shop_root = found
        if found is None:
            self.board.set_shop_folders(())
            return
        self.board.set_shop_folders(shop_folder_choices(found))
        pack = load_client_pack(self._job_folder, self._job_number)
        self.board.apply_shop_folder_picks(pack.shop_folders if pack is not None else {})

    def _locate_shop_folder(self) -> None:
        if not self._job_number:
            messagebox.showinfo("Shop folder", "Enter a Job Number and click Load first.")
            return
        start = self._shop_root or self._job_folder
        chosen = filedialog.askdirectory(
            title="Locate shop folder in 1.0 Current IFC Drawings",
            initialdir=str(start) if start is not None else self._picker_dir(),
        )
        if not chosen:
            return
        path = Path(chosen)
        if not path.is_dir():
            messagebox.showerror("Shop folder", "That folder is not available.")
            return
        remember_shop_folder(self._job_number, path)
        self._refresh_shop_place()
        self._set_status(f"Shop folder: {path.name}")

    def _locate_pdf(self, key: str = "") -> None:
        if key and self._extra_item(key) is not None:
            self._locate_pack_extra(key)
            return
        if key:
            self.board.focus_key(key)
        row = self._matches.get(key) if key else None
        row = row or self._selected_row()
        if row is None:
            messagebox.showinfo("Locate PDF", "Click a drawing first (or tick Pack on one).")
            return
        path = filedialog.askopenfilename(
            title="Locate PDF for this item",
            initialdir=self._picker_dir(),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        pdf_path = Path(path)
        if not pdf_path.is_file():
            messagebox.showerror("Locate PDF", "That file is not available.")
            return
        updated = replace_paired_pdf(row, pdf_path)
        self._pair_located(updated, remember_folder=True)
        self._set_status(f"Located {pdf_path.name} for {updated.drawing.drawing_id or updated.drawing.key}.")

    def _open_pdf_key(self, key: str) -> None:
        extra = self._extra_item(key)
        if extra is not None:
            error = open_row_pdf(Path(extra.path), opener=self._open_path)
            if error:
                messagebox.showerror("Open PDF", error)
            return
        self.board.focus_key(key)
        row = self._matches.get(key) or self.board.focused_row()
        if row is None:
            return
        path = row.pdf.path if row.pdf else None
        error = open_row_pdf(path, opener=self._open_path)
        if not error:
            return
        if path is None:
            messagebox.showinfo("Open PDF", error)
        else:
            messagebox.showerror("Open PDF", error)

    def _extra_item(self, key: str) -> PackExtra | None:
        token = (key or "").strip()
        if not token:
            return None
        return next((item for item in self._current_extras() if item.id == token), None)

    def _locate_pack_extra(self, key: str) -> None:
        current = self._extra_item(key)
        if current is None:
            return
        self.board.focus_key(key)
        chosen = filedialog.askopenfilename(
            title="Locate PDF for this item",
            initialdir=self._picker_dir(),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not chosen:
            return
        path = Path(chosen)
        if not path.is_file():
            messagebox.showerror("Locate PDF", "That file is not available.")
            return
        updated = self._replace_extra_file(current, path)
        self._remember_pdf_folder(path)
        self._set_status(f"Located {path.name} for {updated.document_no}.")

    def _replace_extra_file(self, current: PackExtra, path: Path) -> PackExtra:
        """Put a PDF on an existing Non Jira row. Locate and Assign both use this."""
        rev = outgoing_rev_from_filename(path.name) or current.rev
        updated = PackExtra(
            path=str(path),
            document_no=document_no_for_file(current.document_no, path),
            rev=rev,
            description=current.description,
            status=current.status,
            email_dropped=is_dropped_pdf_path(path),
            id=current.id,
            packed=current.packed,
        )
        self._paint_extras(
            [updated if item.id == current.id else item for item in self._current_extras()]
        )
        self.board.focus_key(current.id)
        self.board.reveal_key(current.id)
        self._save_pack(quiet=True)
        self._set_status(f"{path.name} is on {updated.document_no}.")
        return updated

    def _preview_pdf_key(self, key: str) -> None:
        extra = self._extra_item(key)
        if extra is not None:
            pdf = Path(extra.path)
            if not pdf.is_file():
                messagebox.showerror("Preview PDF", f"That PDF is not on disk: {pdf.name}")
                return
            heading = f"{extra.document_no}  ·  {pdf.name}"

            def on_grab(text: str, issue_key: str = key) -> bool:
                wrote = self.board.set_next_description(issue_key, text)
                if wrote:
                    self._set_status(f"Grabbed description onto {extra.document_no}.")
                    self._save_pack(quiet=True)
                return wrote

            open_pdf_preview(self, pdf, heading=heading, on_grab=on_grab)
            return
        self.board.focus_key(key)
        row = self._matches.get(key) or self.board.focused_row()
        if row is None:
            return
        path = row.pdf.path if row.pdf else None
        if path is None or not str(path).strip():
            messagebox.showinfo("Preview PDF", NO_ROW_PDF)
            return
        pdf = Path(path)
        if not pdf.is_file():
            messagebox.showerror("Preview PDF", f"That PDF is not on disk: {pdf.name}")
            return
        drawing = row.drawing
        heading = f"{drawing.drawing_id or drawing.key}  ·  {pdf.name}"

        def on_grab(text: str, issue_key: str = key) -> bool:
            wrote = self.board.set_next_description(issue_key, text)
            if wrote:
                ident = drawing.drawing_id or drawing.key
                self._set_status(f"Grabbed description onto {ident}.")
            return wrote

        open_pdf_preview(self, pdf, heading=heading, on_grab=on_grab)


def main() -> int:
    if "--paste" in sys.argv[1:]:
        from doccon.drop_host import main as helper_main

        return int(helper_main(sys.argv[1:]) or 0)
    log_session_start(step="session")
    log(
        "INFO",
        "session",
        "DocConApp init (Paste PDF + watched folder; no OLE overlay)",
    )
    app = DocConApp()
    app.mainloop()
    return 0
