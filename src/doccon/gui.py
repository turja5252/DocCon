# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import os
import threading
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from doccon import APP_DISPLAY_NAME, __version__
from doccon.client_log import (
    LogError,
    file_client_transmittal,
    find_client_book,
    inspect_client_book,
    lines_from_rows,
    parse_expected_return,
    parse_issued_date,
    prepare_client_book,
)
from doccon.date_picker import attach_calendar
from doccon.drawing_board import DrawingBoard
from doccon.excel_pdf import export_sheet_pdf
from doccon.jira_client import JiraError, apply_drawing_update, fetch_drawings, ping, update_summary
from doccon.jobs import find_job_folder
from doccon.kinds import CLIENT, FIELD, LABELS, SHOP
from doccon.match import MatchedRow, PdfHit, attach_pdfs, parse_pdf_stem
from doccon.pack_mail import (
    display_outlook_draft,
    draft_body,
    draft_subject,
    pack_files,
    write_pack_zip,
)
from doccon.pack_state import ClientPack, load_client_pack, save_client_pack
from doccon.pep import DOC_CONTROL_FROM, SALES_DIR, PepCover, PepError, email_line, find_pep, load_pep
from doccon.register import adopted_summary, parse_summary
from doccon.secrets import load_token, save_token
from doccon.settings import AppSettings, load_settings, save_settings
from doccon.theme import FONT_SMALL, FONT_TITLE, NAVY, apply_theme, style_text
from doccon.transmittal_books import adopt_transmittal_books


def _session() -> tuple[AppSettings, str]:
    settings = load_settings()
    token = load_token(settings.email)
    return settings, token


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.title("Jira settings")
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

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", padx=12, pady=(8, 14))
        ttk.Button(buttons, text="Test connection", command=self._test).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side="left")

    def _read_form(self) -> tuple[AppSettings, str]:
        settings = AppSettings(
            site=self.site.get().strip(),
            email=self.email.get().strip(),
            project_key=self.project.get().strip(),
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
        self._matches: dict[str, MatchedRow] = {}
        self._job_folder: Path | None = None
        self._job_number = ""
        self._pep_path: Path | None = None
        self._cover_loading = False
        self._jira_loading = False
        self.kind = tk.StringVar(value=CLIENT)

        chrome = tk.Frame(self, bg=NAVY, padx=16, pady=12)
        chrome.pack(fill="x")
        title_row = tk.Frame(chrome, bg=NAVY)
        title_row.pack(fill="x")
        tk.Label(
            title_row,
            text=APP_DISPLAY_NAME,
            bg=NAVY,
            fg="#FFFFFF",
            font=FONT_TITLE,
        ).pack(side="left")
        tk.Label(
            title_row,
            text=f"v{__version__}",
            bg=NAVY,
            fg="#9FB3C8",
            font=FONT_SMALL,
        ).pack(side="left", padx=(10, 0), pady=(4, 0))
        ttk.Button(title_row, text="Settings", style="Brand.TButton", command=self._settings).pack(side="right")

        bar = tk.Frame(chrome, bg=NAVY)
        bar.pack(fill="x", pady=(12, 0))
        ttk.Label(bar, text="Job Number", style="Brand.TLabel").pack(side="left")
        self.job = ttk.Entry(bar, width=18)
        self.job.pack(side="left", padx=8)
        self.job.bind("<Return>", lambda _event: self._load())
        ttk.Button(bar, text="Load", style="Brand.TButton", command=self._load).pack(side="left")
        ttk.Button(bar, text="Match PDF…", style="Brand.TButton", command=self._match_pdf).pack(
            side="left", padx=(8, 0)
        )

        kinds = tk.Frame(bar, bg=NAVY)
        kinds.pack(side="left", padx=16)
        for value in (CLIENT, SHOP, FIELD):
            ttk.Radiobutton(
                kinds,
                text=LABELS[value],
                value=value,
                variable=self.kind,
                command=self._kind_changed,
                style="Brand.TRadiobutton",
            ).pack(side="left", padx=(0, 8))
        self.send_btn = ttk.Button(bar, text="Confirm…", style="Accent.TButton", command=self._issue_pack)
        self.send_btn.pack(side="left", padx=(8, 0))
        self.status = ttk.Label(
            bar,
            text="Settings → paste Jira token, then Load a job. Client first.",
            style="BrandMuted.TLabel",
        )
        self.status.pack(side="left", padx=16)

        meta = ttk.Frame(self, padding=(16, 10, 16, 6))
        meta.pack(fill="x")
        ttk.Label(meta, text="Date issued").pack(side="left")
        issued_box = ttk.Frame(meta)
        issued_box.pack(side="left", padx=(4, 12))
        self.issued = ttk.Entry(issued_box, width=12)
        self.issued.insert(0, date.today().isoformat())
        self.issued.pack(side="left", padx=(0, 4))
        attach_calendar(self.issued, parent=issued_box, on_change=lambda: self._save_pack(quiet=True))
        ttk.Label(meta, text="Expected return").pack(side="left")
        expected_box = ttk.Frame(meta)
        expected_box.pack(side="left", padx=(4, 8))
        self.expected = ttk.Entry(expected_box, width=14)
        self.expected.pack(side="left", padx=(0, 4))
        attach_calendar(self.expected, parent=expected_box, on_change=lambda: self._save_pack(quiet=True))
        ttk.Button(expected_box, text="N/A", command=self._expected_na).pack(side="left", padx=(4, 0))
        ttk.Button(meta, text="Locate PEP…", command=self._locate_pep).pack(side="left", padx=(16, 0))
        ttk.Button(meta, text="Save", command=self._save_pack).pack(side="left", padx=(8, 0))
        self.pep_label = ttk.Label(meta, text="PEP: load a job", style="Muted.TLabel")
        self.pep_label.pack(side="left", padx=12)

        hint = ttk.Label(
            self,
            style="Hint.TLabel",
            text=(
                "Open the job, tick Pack, use Batch Next to set many drawings at once, or edit a row. "
                "Date issued / Expected return have Today and a calendar. Confirm writes Jira, files the pack, "
                "and opens Outlook. Nothing is sent until you click Send in Outlook."
            ),
        )
        hint.pack(side="bottom", fill="x", padx=16, pady=(0, 10))

        cover = ttk.LabelFrame(self, text="Cover (this pack)", padding=10)
        cover.pack(side="bottom", fill="x", padx=16, pady=(0, 6))
        ttk.Label(cover, text="FROM", style="Header.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(cover, text="TO", style="Header.TLabel").grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(cover, text="CC", style="Header.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Label(cover, text="PROJECT", style="Header.TLabel").grid(row=0, column=3, sticky="w")
        self.from_addr = ttk.Entry(cover)
        self.from_addr.grid(row=1, column=0, sticky="new", padx=(0, 8), pady=(0, 4))
        self._set_from_address(DOC_CONTROL_FROM)
        self.to_box = tk.Text(cover, height=3, wrap="word")
        self.to_box.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 4))
        self.cc_box = tk.Text(cover, height=3, wrap="word")
        self.cc_box.grid(row=1, column=2, sticky="nsew", padx=(0, 8), pady=(0, 4))
        self.project_box = tk.Text(cover, height=3, wrap="word")
        self.project_box.grid(row=1, column=3, sticky="nsew", pady=(0, 4))
        for box in (self.to_box, self.cc_box, self.project_box):
            style_text(box)
        ttk.Label(
            cover,
            text="TO and CC are email addresses only. Add more with a semicolon.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, columnspan=4, sticky="w")
        for col in range(4):
            cover.columnconfigure(col, weight=1)
        cover.rowconfigure(1, weight=1)
        for box in (self.to_box, self.cc_box, self.project_box):
            box.bind("<FocusOut>", lambda _event: self._save_pack(quiet=True))
        self.issued.bind("<FocusOut>", lambda _event: self._save_pack(quiet=True))
        self.expected.bind("<FocusOut>", lambda _event: self._save_pack(quiet=True))

        body = ttk.Frame(self, padding=(8, 0, 8, 0))
        body.pack(fill="both", expand=True)
        self.board = DrawingBoard(body, on_open_pdf=self._open_pdf_key)
        self.board.pack(fill="both", expand=True)

    def _settings(self) -> None:
        SettingsDialog(self)

    def _kind_changed(self) -> None:
        kind = self.kind.get()
        if kind == CLIENT:
            self.send_btn.configure(text="Confirm…", state="normal")
        else:
            self.send_btn.configure(text=f"{LABELS[kind]} (later)", state="disabled")
        self._refresh_cover_hint()

    def _expected_na(self) -> None:
        self.expected.delete(0, "end")
        self.expected.insert(0, "N/A")
        self._save_pack(quiet=True)

    def _cover_suffix(self) -> str:
        if self.kind.get() != CLIENT or self._job_folder is None or not self._job_number:
            return ""
        try:
            book = find_client_book(self._job_folder, self._job_number)
            if book is None:
                return ""
            info = inspect_client_book(book, self._job_number)
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
            to_line = email_line(overlay.to_line) if overlay else ""
            if not to_line:
                to_line = email_line(cover.to_line)
            cc_line = email_line(overlay.cc_line) if overlay else ""
            if not cc_line:
                cc_line = email_line(cover.cc_line)
            project = (
                overlay.project_description
                if overlay and overlay.project_description
                else cover.project_description
            )
            self._set_text(self.to_box, to_line)
            self._set_text(self.cc_box, cc_line)
            self._set_text(self.project_box, project)
            if overlay and overlay.issued:
                self.issued.delete(0, "end")
                self.issued.insert(0, overlay.issued)
            if overlay and overlay.expected:
                self.expected.delete(0, "end")
                self.expected.insert(0, overlay.expected)
        finally:
            self._cover_loading = False

    def _clear_cover_fields(self) -> None:
        self._cover_loading = True
        try:
            self._set_from_address(DOC_CONTROL_FROM)
            self._set_text(self.to_box, "")
            self._set_text(self.cc_box, "")
            self._set_text(self.project_box, "")
        finally:
            self._cover_loading = False

    def _pack_from_console(self) -> ClientPack:
        return ClientPack(
            job_number=self._current_job(),
            pep_path=str(self._pep_path) if self._pep_path else "",
            issued=self.issued.get().strip(),
            expected=self.expected.get().strip(),
            to_line=self._email_value(self.to_box),
            cc_line=self._email_value(self.cc_box),
            project_description=self._text_value(self.project_box),
            selected_keys=self.board.selected_keys(),
        )

    def _save_pack(self, quiet: bool = False, *, force: bool = False) -> bool:
        if self._cover_loading:
            return False
        if self._busy and not force:
            return False
        job = self._current_job()
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

    def _restore_pack(self, folder: Path | None, job: str, cover: PepCover | None) -> None:
        pack = load_client_pack(folder, job)
        if cover is None:
            if pack:
                self._cover_loading = True
                try:
                    self._set_from_address(DOC_CONTROL_FROM)
                    self._set_text(self.to_box, email_line(pack.to_line))
                    self._set_text(self.cc_box, email_line(pack.cc_line))
                    self._set_text(self.project_box, pack.project_description)
                    if pack.issued:
                        self.issued.delete(0, "end")
                        self.issued.insert(0, pack.issued)
                    if pack.expected:
                        self.expected.delete(0, "end")
                        self.expected.insert(0, pack.expected)
                finally:
                    self._cover_loading = False
            else:
                self._clear_cover_fields()
            return
        self._apply_cover_fields(cover, overlay=pack)

    def _cover_for_write(self) -> PepCover | None:
        to_line = self._email_value(self.to_box)
        if not to_line:
            messagebox.showerror(
                "Client Transmittal",
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

    def _ensure_job_folder(self, job: str) -> Path | None:
        if self._job_folder is not None and self._job_folder.is_dir():
            return self._job_folder
        folder = find_job_folder(job)
        if folder is not None:
            self._job_folder = folder
        return folder

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

    def _load(self) -> None:
        if self._busy:
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
        self._busy = True
        self._job_number = job
        self._set_status(f"Loading {job}…")

        def work() -> None:
            error: str | None = None
            matched: list[MatchedRow] = []
            folder_label = ""
            orphans = 0
            folder: Path | None = None
            try:
                rows = fetch_drawings(settings.site, settings.email, token, job, settings.project_key)
                folder = find_job_folder(job)
                if folder is None:
                    folder_label = "job folder not found"
                    matched, orphans = attach_pdfs(rows, None, job)
                else:
                    adopted = adopt_transmittal_books(folder, job)
                    folder_label = folder.name
                    if adopted:
                        names = ", ".join(item.path.name for item in adopted)
                        folder_label = f"{folder.name}  |  named {names}"
                    matched, orphans = attach_pdfs(rows, folder, job)
            except JiraError as exc:
                error = str(exc)
            self.after(
                0,
                lambda m=matched, e=error, f=folder_label, o=orphans, p=folder: self._show_rows(job, m, e, f, o, p),
            )

        threading.Thread(target=work, daemon=True).start()

    def _show_rows(
        self,
        job: str,
        matched: list[MatchedRow],
        error: str | None,
        folder_label: str,
        orphans: int,
        job_folder: Path | None = None,
    ) -> None:
        self._busy = False
        self._matches = {}
        self._job_folder = job_folder
        self._job_number = job
        self.board.clear()
        if error:
            self._set_pep(None)
            self._clear_cover_fields()
            self._set_status("Load failed.")
            messagebox.showerror("Jira", error)
            return
        missing = 0
        for row in matched:
            self._matches[row.drawing.key] = row
            if row.confidence == "Missing":
                missing += 1
        extra = f"  |  {orphans} extra PDF(s) not in Jira" if orphans else ""
        self._discover_pep(job_folder, job)
        pep_cover = None
        if self._pep_path is not None and self._pep_path.is_file():
            try:
                pep_cover = load_pep(self._pep_path)
            except PepError:
                pep_cover = None
        self._restore_pack(job_folder, job, pep_cover)
        pack = load_client_pack(job_folder, job)
        checked: set[str] | None = None
        if pack and pack.selected_keys:
            wanted = {key for key in pack.selected_keys if key in self._matches}
            if wanted:
                checked = wanted
        self.board.set_rows(matched, checked=checked)
        self._save_pack(quiet=True)
        cover = self._cover_suffix()
        pep = self._pep_suffix()
        self._set_status(
            f"{job}: {len(matched)} drawing(s), {missing} missing PDF  |  {folder_label}{extra}{cover}{pep}"
        )

    def _picker_dir(self) -> str:
        if self._job_folder is None:
            return os.getcwd()
        drafting = self._job_folder / "2.0 Drafting"
        if drafting.is_dir():
            for folder in drafting.rglob("*"):
                if folder.is_dir() and "current pdf" in folder.name.casefold() and "void" not in folder.name.casefold():
                    return str(folder)
            return str(drafting)
        return str(self._job_folder)

    def _selected_row(self) -> MatchedRow | None:
        return self.board.focused_row()

    def _selected_rows(self) -> list[MatchedRow]:
        return self.board.selected_rows()

    def _issue_pack(self) -> None:
        if self._busy:
            return
        kind = self.kind.get()
        if kind != CLIENT:
            messagebox.showinfo(
                LABELS[kind],
                f"{LABELS[kind]} comes after Client is right. Leave this on Client Transmittal.",
            )
            return
        job = self._current_job()
        folder = self._ensure_job_folder(job) if job else None
        if not job:
            messagebox.showinfo("Client Transmittal", "Enter a Job Number and click Load first.")
            return
        if folder is None:
            messagebox.showerror(
                "Client Transmittal",
                f"No Dropbox job folder for {job}. Check Current Jobs, then Load again.",
            )
            return
        rows = self._selected_rows()
        if not rows:
            messagebox.showinfo("Client Transmittal", "Tick Pack on the drawings for this send.")
            return
        try:
            book = prepare_client_book(folder, job)
            info = inspect_client_book(book, job)
        except (LogError, OSError) as exc:
            messagebox.showerror("Client Transmittal", str(exc))
            return
        try:
            issued = parse_issued_date(self.issued.get())
            expected = parse_expected_return(self.expected.get())
        except LogError as exc:
            messagebox.showerror("Client Transmittal", str(exc))
            return
        cover = self._cover_for_write()
        if cover is None:
            return
        packed_keys = {row.drawing.key for row in rows}
        jira_rows = [row for row in self.board.pending_rows() if row.drawing.key in packed_keys]
        originals = {
            row.drawing.key: self._matches[row.drawing.key].drawing
            for row in jira_rows
            if row.drawing.key in self._matches
        }
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
            extra += f"\n{missing} packed drawing(s) have no PDF and will be left out of the zip."
        if jira_rows:
            extra += f"\n\nJira Next values will be written on {len(jira_rows)} drawing(s):"
            for row in jira_rows:
                current = originals.get(row.drawing.key)
                was = current.status if current is not None else "—"
                extra += (
                    f"\n  {row.drawing.key}  {was} → {row.drawing.status}"
                    f"  Out {row.drawing.outgoing_rev or '—'}"
                    f"  Client dwg {row.drawing.client_document_number or '—'}"
                )
        else:
            extra += "\n\nNo Jira field or status changes on packed drawings."
        expected_label = expected.isoformat() if isinstance(expected, date) else expected
        subject = draft_subject(info.cover_id, job)
        zip_name = f"{info.cover_id}.zip"
        if not messagebox.askyesno(
            "Confirm?",
            (
                f"One click: update Jira, fill TRANSMITTAL, file {info.cover_id}, zip the pack, "
                f"open an Outlook draft from the mailbox signed into THIS PC (not doc.control).\n\n"
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
                f"Zip: {zip_name}\n\n"
                "Close the CT book first. Nothing is sent until you click Send in Outlook."
            ),
        ):
            return
        if not self._save_pack(quiet=True, force=True):
            return
        lines = lines_from_rows(rows)
        self._busy = True
        self._job_number = job
        self._job_folder = folder
        self._set_status(f"Confirming {info.cover_id}…")

        def work() -> None:
            error: str | None = None
            cover_id = info.cover_id
            note = ""
            saved_zip = zip_name
            jira_ok = False
            try:
                for row in jira_rows:
                    current = originals.get(row.drawing.key, row.drawing)
                    apply_drawing_update(settings.site, settings.email, token, current, row.drawing)
                jira_ok = True
                result = file_client_transmittal(
                    book,
                    job,
                    lines,
                    issued=issued,
                    expected_return=expected,
                    cover=cover,
                )
                cover_id = result.cover_id
                saved_zip = f"{cover_id}.zip"
                pdf_path = book.parent / f"{cover_id}.pdf"
                try:
                    export_sheet_pdf(result.book, result.sheet_name, pdf_path)
                    note = f"PDF: {pdf_path.name}"
                except LogError as exc:
                    note = str(exc)
                files = pack_files(rows, pdf_path if pdf_path.is_file() else None)
                if not files:
                    raise LogError("No PDFs to zip. Match drawing PDFs first.")
                zip_path = book.parent / saved_zip
                write_pack_zip(zip_path, files)
                saved_zip = zip_path.name
                display_outlook_draft(
                    to_line=cover.to_line,
                    cc_line=cover.cc_line,
                    subject=draft_subject(cover_id, job),
                    body=draft_body(
                        cover_id=cover_id,
                        project=cover.project_description,
                        rows=rows,
                        zip_name=saved_zip,
                    ),
                    attachments=[zip_path],
                )
            except (JiraError, LogError, OSError) as exc:
                error = str(exc)
            self.after(
                0,
                lambda c=cover_id, e=error, n=note, z=saved_zip, f=folder, j=job, u=list(jira_rows), ok=jira_ok: self._pack_issued(
                    c, e, n, z, f, j, u, ok
                ),
            )

        threading.Thread(target=work, daemon=True).start()

    def _pack_issued(
        self,
        cover: str,
        error: str | None,
        pdf_note: str,
        zip_name: str,
        folder: Path | None,
        job: str,
        jira_rows: list[MatchedRow] | None = None,
        jira_ok: bool = False,
    ) -> None:
        self._busy = False
        self._job_folder = folder
        self._job_number = job
        if jira_ok and jira_rows:
            for row in jira_rows:
                self._apply_row(row)
        self._save_pack(quiet=True, force=True)
        self._refresh_cover_hint()
        extra = f"\n{pdf_note}" if pdf_note else ""
        jira_note = f"\nJira: {len(jira_rows)} drawing(s)." if jira_rows else "\nJira: no field changes."
        if error:
            self._set_status("Confirm failed.")
            messagebox.showerror("Client Transmittal", error + extra)
            return
        self._set_status(f"Confirmed {cover}.")
        messagebox.showinfo(
            "Client Transmittal",
            f"Filed {cover}.{extra}{jira_note}\nZip: {zip_name}\nOutlook draft is open from this PC's mailbox. Send it there.",
        )

    def _apply_row(self, row: MatchedRow) -> None:
        self._matches[row.drawing.key] = row
        self.board.apply_row(row)

    def _match_pdf(self) -> None:
        row = self._selected_row()
        if row is None:
            messagebox.showinfo("Match PDF", "Click a drawing first (or tick Pack on one).")
            return
        path = filedialog.askopenfilename(
            title="Match PDF to this Jira drawing",
            initialdir=self._picker_dir(),
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        pdf_path = Path(path)
        drawing_id, rev = parse_pdf_stem(pdf_path.stem)
        if not drawing_id:
            messagebox.showerror("Match PDF", "Could not read a drawing number from that filename.")
            return
        new_summary = adopted_summary(row.drawing.summary, drawing_id)
        message = (
            f"Pair {row.drawing.key} with:\n{pdf_path.name}\n\n"
            f"Jira summary will become:\n{new_summary}"
        )
        if not messagebox.askyesno("Adopt name on Jira?", message):
            return
        settings, token = _session()
        if not settings.email or not token:
            messagebox.showerror("Settings", "Jira email and token are required.")
            return
        try:
            update_summary(settings.site, settings.email, token, row.drawing.key, new_summary)
        except JiraError as exc:
            messagebox.showerror("Jira", str(exc))
            return
        drawing = replace(
            row.drawing,
            summary=new_summary,
            drawing_id=drawing_id,
            title=parse_summary(new_summary)[1],
        )
        hit = PdfHit(path=pdf_path, drawing_id=drawing_id, rev=rev)
        self._apply_row(MatchedRow(drawing=drawing, pdf=hit, confidence="High"))
        self._set_status(f"Jira {drawing.key} summary updated to {drawing_id}.")

    def _open_pdf_key(self, key: str) -> None:
        self.board.focus_key(key)
        row = self._matches.get(key) or self.board.focused_row()
        if row is None:
            return
        if row.pdf is None:
            self._match_pdf()
            return
        try:
            os.startfile(row.pdf.path)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("PDF", str(exc))


def main() -> int:
    app = DocConApp()
    app.mainloop()
    return 0
