# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import contextlib
import os
import sys
import threading
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from doccon import APP_DISPLAY_NAME, __version__
from doccon.client_log import (
    LogError,
    book_cover_for_job,
    cover_date_stamp,
    cover_issued_default,
    expected_return_from_issued,
    find_book,
    inspect_book,
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
from doccon.kinds import CLIENT, FIELD, LABELS, PREFIX, SHOP
from doccon.match import (
    LocatedPdf,
    MatchedRow,
    apply_located_pdfs,
    keep_located_pdfs,
    match_pdf_hits,
    outgoing_rev_from_filename,
    pair_pdf,
    pdf_is_email_dropped,
    scan_current_pdfs,
)
from doccon.outlook_contacts import OutlookContactsError, import_saved_emails_from_outlook
from doccon.pack_mail import draft_subject
from doccon.pack_state import (
    ClientPack,
    cover_recipients,
    load_client_pack,
    save_client_pack,
    with_cover_recipients,
)
from doccon.pep import DOC_CONTROL_FROM, SALES_DIR, PepCover, PepError, email_line, find_pep, load_pep
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
    save_settings,
)
from doccon.theme import (
    FOLDER,
    FONT,
    FONT_SMALL,
    FONT_TITLE,
    IDENTITY_MISSING,
    JIRA,
    NAVY,
    NAVY_MID,
    ThemeProgress,
    apply_theme,
    style_text,
)
from doccon.transmittal_books import adopt_transmittal_books
from doccon.watch_inbox import POLL_MS as WATCH_POLL_MS
from doccon.watch_inbox import InboxWatcher, plan_watch_hits

NO_ROW_PDF = "No PDF for this row — use Locate…"
PACK_SAVE_MS = 1000
CREATE_CREATED_MS = 700
CREATE_ISSUE_BTN = "Create new Jira Issue"
CREATE_TRANSMITTAL_BTN = "Create transmittal"
CREATE_EDDI_BTN = "Create EDDI"
SELECT_ROW_FIRST = (
    "That PDF does not match any drawing on this job by filename.\n\n"
    "Click the drawing row you want, then Paste PDF — the selected row always wins. "
    "Several files wait in New PDFs: click a row, pick one, then Assign to selected row."
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


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
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
        ttk.Button(book, text="Remove", command=self._remove_address).grid(row=1, column=2, pady=(8, 0))
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

        buttons = ttk.Frame(self)
        buttons.grid(row=7, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 14))
        ttk.Button(buttons, text="Open log folder", command=self._open_log_folder).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Test connection", command=self._test).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side="left")

    def _open_log_folder(self) -> None:
        try:
            open_log_folder()
        except OSError as exc:
            messagebox.showerror("Settings", str(exc), parent=self)

    def _fill_addresses(self, emails: tuple[str, ...] | list[str]) -> None:
        self._addresses.delete(0, "end")
        for addr in emails:
            self._addresses.insert("end", addr)

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
            last_locate_dir=load_settings().last_locate_dir,
            board_col_px=load_settings().board_col_px,
            board_layout_rev=load_settings().board_layout_rev,
            job_folders=dict(load_settings().job_folders),
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
        self.title(f"{APP_DISPLAY_NAME}  {__version__}")
        self.geometry("1680x820")
        self.minsize(1200, 640)
        apply_theme(self)
        self._busy = False
        self._work = ""
        self._load_gen = 0
        self._load_note: tuple[int, str] | None = None
        self._pending_rows: tuple | None = None
        self._load_pump = ""
        self._matches: dict[str, MatchedRow] = {}
        self._job_folder: Path | None = None
        self._job_number = ""
        self._pep_path: Path | None = None
        self._cover_loading = False
        self._jira_loading = False
        self._located_pdfs: dict[str, LocatedPdf] = {}
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
        ttk.Button(bar, text="Load", style="Brand.TButton", command=self._load).pack(side="left")

        kinds = tk.Frame(bar, bg=NAVY)
        kinds.pack(side="left", padx=(10, 0))
        for value in (CLIENT, SHOP, FIELD):
            ttk.Radiobutton(
                kinds,
                text=LABELS[value],
                value=value,
                variable=self.kind,
                command=self._kind_changed,
                style="Brand.TRadiobutton",
            ).pack(side="left", padx=(0, 6))
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
            text="Paste PDF",
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
        self.new_issue_btn = tk.Button(
            identity,
            text=CREATE_ISSUE_BTN,
            command=self._new_issue,
            bg=NAVY_MID,
            fg="#FFFFFF",
            activebackground="#334E68",
            activeforeground="#FFFFFF",
            disabledforeground="#9FB3C8",
            font=FONT_SMALL,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=0,
            cursor="hand2",
            justify="center",
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
        set_na_text(self.expected)
        self.expected.pack(side="left", padx=(4, 0))
        attach_calendar(
            self.expected, parent=self, on_change=self._on_expected_return_change, allow_na=True
        )
        for label, days in (
            ("Urgent same day", 0),
            ("Urgent +1", 1),
            ("7 days", 7),
            ("14 days", 14),
        ):
            ttk.Button(
                dates,
                text=label,
                command=lambda offset=days: self._apply_expected_preset(offset),
            ).pack(side="left", padx=(2, 0))
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
            text="Dismiss",
            style="Brand.TButton",
            command=self._dismiss_new_pdf,
        ).pack(side="left", padx=(0, 10))
        self.board = DrawingBoard(
            body,
            on_open_pdf=self._open_pdf_key,
            on_locate_pdf=self._locate_pdf,
            on_rename_pdf=self._rename_pdf,
            cover_return_stamp=lambda: cover_date_stamp(self.expected.get()),
            cover_issued_stamp=lambda: cover_date_stamp(self.issued.get()),
            on_cancel_next=self._on_cancel_next,
            on_draft_change=self._schedule_pack_save,
        )
        self.board.pack(fill="both", expand=True)

    def _settings(self) -> None:
        SettingsDialog(self)

    def _pick_cover_email(self, which: str) -> None:
        emails = load_settings().saved_emails
        if not emails:
            messagebox.showinfo("Pick address", "Save email addresses in Settings first.")
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
        if self.kind.get() == CLIENT:
            self.cover_hint.configure(
                text="TO and CC are email addresses only. Add more with a semicolon."
            )
        else:
            self.cover_hint.configure(
                text="Shop/Field TO and CC come from that ST/FT letter if Sarah already filled them."
            )
        self._show_kind_cover()
        self._refresh_cover_hint()

    def _show_kind_cover(self) -> None:
        kind = self.kind.get()
        pack = load_client_pack(self._job_folder, self._job_number) if self._job_number else None
        pack_to, pack_cc = cover_recipients(pack, kind)
        pep = None
        if kind == CLIENT and self._pep_path is not None and self._pep_path.is_file():
            try:
                pep = load_pep(self._pep_path)
            except PepError:
                pep = None
        chosen = pick_cover_fields(
            book=book_cover_for_job(self._job_folder, self._job_number, kind),
            pack_to=pack_to,
            pack_cc=pack_cc,
            pack_project="",
            pep=pep,
            kind=kind,
        )
        self._cover_loading = True
        try:
            self._set_text(self.to_box, email_line(chosen.to_line))
            self._set_text(self.cc_box, email_line(chosen.cc_line))
        finally:
            self._cover_loading = False

    def _cover_suffix(self) -> str:
        kind = self.kind.get()
        if kind not in LABELS or self._job_folder is None or not self._job_number:
            return ""
        try:
            book = find_book(self._job_folder, self._job_number, kind)
            if book is None:
                return ""
            info = inspect_book(book, self._job_number, kind)
        except (LogError, OSError):
            return ""
        return f"  |  next {info.cover_id} ({book.name})"

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
            self.board.apply_cover_date_change(
                "return_request_date", cover_date_stamp(self.expected.get())
            )
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
        self.destroy()

    def destroy(self) -> None:
        self._cancel_pack_save()
        with contextlib.suppress(Exception):
            self._clear_drop_hover()
        self._stop_drop()
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
        chosen = pick_cover_fields(
            book=book_cover_for_job(folder, job, kind),
            pack_to=pack_to,
            pack_cc=pack_cc,
            pack_project=pack.project_description if pack else "",
            pep=cover,
            kind=kind,
        )
        self._cover_loading = True
        try:
            self._set_from_address(DOC_CONTROL_FROM)
            self._set_text(self.to_box, email_line(chosen.to_line))
            self._set_text(self.cc_box, email_line(chosen.cc_line))
            self._set_text(self.project_box, chosen.project_description)
            self._write_cover_date_defaults()
            if pack is not None:
                self.board.apply_next_edits(pack.next_edits)
        finally:
            self._cover_loading = False

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
        self._job_project = None
        self._eddi_contexts = {}
        self._set_new_issue_enabled(False)
        self._new_pdfs.clear()
        self._show_new_pdfs()
        self._start_progress("Fetching from Jira…" if wait_key else f"Loading {job}…")
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
            hits: list = []
            folder_label = ""
            orphans = 0
            matched: list[MatchedRow] = []
            located: dict = {}

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
                        )
                    else:
                        self._post_status(gen, f"Fetching Jira for {job}…")
                        rows, project = fetch_job_pack(
                            settings.site, settings.email, token, job, settings.project_key
                        )
                    if rows:
                        try:
                            rev_options = fetch_rev_option_lists(
                                settings.site, settings.email, token, rows[0].key
                            )
                        except (JiraError, OSError, ValueError, TypeError):
                            rev_options = {}
                        try:
                            eddi_contexts = fetch_eddi_contexts(
                                settings.site, settings.email, token, rows
                            )
                        except (JiraError, OSError, ValueError, TypeError):
                            eddi_contexts = {}
                except (JiraError, OSError, ValueError, TypeError) as exc:
                    error = str(exc)

            def folder_work() -> None:
                nonlocal folder, hits, folder_label
                try:
                    self._post_status(gen, f"Finding {job} folder…")
                    found = resolve_job_folder(job)
                    folder = found
                    if found is None:
                        folder_label = "job folder not found"
                        return
                    adopted = adopt_transmittal_books(found, job)
                    folder_label = found.name
                    if adopted:
                        names = ", ".join(item.path.name for item in adopted)
                        folder_label = f"{found.name}  |  named {names}"
                    self._post_status(gen, f"Scanning PDFs in {found.name}…")
                    hits = scan_current_pdfs(found)
                except Exception:
                    hits = []

            jira_thread = threading.Thread(target=jira_work, daemon=True)
            folder_thread = threading.Thread(target=folder_work, daemon=True)
            jira_thread.start()
            folder_thread.start()
            jira_thread.join()
            folder_thread.join()
            if error is None:
                self._post_status(gen, f"Matching PDFs for {job}…")
                matched, orphans = match_pdf_hits(rows, hits, job)
                try:
                    self._post_status(gen, f"Restoring pack for {job}…")
                    pack = load_client_pack(folder, job)
                    previous_located = dict(pack.located_pdfs) if pack else {}
                    matched = apply_located_pdfs(matched, previous_located)
                    located = keep_located_pdfs(matched, previous_located)
                    sweep_replaced_dropped_copies(matched, previous_located)
                except (OSError, ValueError, TypeError):
                    located = {}
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

        threading.Thread(target=work, daemon=True).start()

    def _cancel_load(self) -> None:
        self.board.cancel_paint()
        self._pending_rows = None
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

    def _pump_load_ui(self) -> None:
        self._load_pump = ""
        note = self._load_note
        if note:
            gen, text = note
            if gen == self._load_gen:
                self._set_status(text)
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
        self._eddi_contexts = dict(eddi_contexts or {})
        self._matches = {}
        self._job_folder = job_folder
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
        painted = max(len(matched), 1)
        self._paint_progress(painted, painted)
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
        self._discover_pep(self._job_folder, job)
        pep_cover = None
        if self._pep_path is not None and self._pep_path.is_file():
            try:
                pep_cover = load_pep(self._pep_path)
            except PepError:
                pep_cover = None
        self._restore_pack(self._job_folder, job, pep_cover)
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
        self._start_watcher()

    def _picker_dir(self) -> str:
        fallback = str(self._job_folder) if self._job_folder is not None else os.getcwd()
        return locate_start_dir(fallback)

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

    def _new_issue(self) -> None:
        if self._busy:
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
        if self._busy:
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
        if self._busy:
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
            "Update Jira",
            f"Wrote {len(rows)} item(s) to Jira. Now shows what was written.\n"
            "No transmittal, EDDI, or Outlook.",
        )

    def _issue_pack(self) -> None:
        if self._busy:
            return
        kind = self.kind.get()
        label = LABELS.get(kind, LABELS[CLIENT])
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
        if not rows:
            messagebox.showinfo(label, "Tick Pack on the drawings for this send.")
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
        extra = ""
        if info.filed_tabs:
            extra = f"\nThis book already has filed tabs: {', '.join(info.filed_tabs)}."
        missing = sum(1 for row in rows if row.pdf is None)
        if missing:
            extra += f"\n{missing} packed drawing(s) have no PDF and will not be attached."
        extra += self._jira_change_note(jira_rows, packed=True)
        expected_label = expected.isoformat() if isinstance(expected, date) else expected
        subject = draft_subject(info.cover_id, job)
        cover_pdf = f"{info.cover_id}.pdf"
        if not messagebox.askyesno(
            "Confirm?",
            (
                f"One click: check that Jira and the log can be written, then update Jira, "
                f"file {info.cover_id}, attach the transmittal PDF and a zip of the drawing PDFs, "
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
                f"Attachments: {cover_pdf} plus {info.cover_id}.zip "
                f"(drawings only; not the transmittal form).\n"
                "Also prints a dated copy of the EDDI form "
                "(matched PDFs only, not only this pack; live book unchanged; not attached).\n\n"
                f"Close the {PREFIX[kind]} book first. Nothing is sent until you click Send in Outlook."
            ),
        ):
            return
        if not self._save_pack(quiet=True, force=True):
            return
        lines = lines_from_rows(rows, kind)
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
            if self._busy:
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
        """One file still pairs the selected row. Two or more wait in New PDFs for Assign."""
        self._claim_inbox_paths(paths)
        if len(paths) > 1:
            self._park_pasted_batch(paths)
            return
        self._apply_drop(sources_from_paths(paths), -1, -1, strip_leftovers=True)

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
        log("INFO", "paste", f"parked batch={len(staged)} in New PDFs: {names}")
        self._set_status(
            f"{len(staged)} PDF(s) waiting in New PDFs: {names}{more} — click a row, then Assign.{extra}"
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
                self._new_pdf_bar.pack(fill="x", pady=(0, 4), before=self.board)
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
        key = self._paste_target_key()
        row = self._matches.get(key) if key else None
        if row is None:
            messagebox.showinfo("New PDFs", "Click the drawing row you want this PDF on first.")
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
        self._set_status(f"{names} did not match a row — select a drawing row, then Paste PDF.{extra}")
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
            remember_locate_dir(pdf_path)
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

    def _locate_pdf(self, key: str = "") -> None:
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
