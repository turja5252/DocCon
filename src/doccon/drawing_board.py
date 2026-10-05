# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Two-row drawing list: original Jira values, then Next editors (list / text / calendar)."""
from __future__ import annotations

import contextlib
import re
import tkinter as tk
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import messagebox, ttk

from doccon.date_picker import CalendarPopup, attach_calendar
from doccon.kinds import CLIENT, FIELD, SHOP
from doccon.dpi import pixel_scale
from doccon.drop_pdfs import dropped_pdf_filename
from doccon.match import (
    MatchedRow,
    is_dropped_pdf_path,
    pdf_address_text,
    pdf_address_tip,
    pdf_is_email_dropped,
)
from doccon.pack_state import PackExtra
from doccon.popups import install as _install_popups
from doccon.register import (
    APPROVAL_VALUES,
    DRAWING_STATUSES,
    EDDI_VALUES,
    DrawingRow,
    due_date_from_return_request,
    eddi_group_title,
    is_generic_eddi,
    normalize_option_key,
    pack_sort_key,
    summary_from_parts,
)
from doccon.settings import BOARD_LAYOUT_REV, load_settings, remember_board_col_px
from doccon.theme import (
    ACCENT,
    BG,
    BORDER,
    SELECT_BG,
    SELECT_RULE,
    FONT_SMALL,
    NAVY_MID,
    OK,
    PENDING_BG,
    SURFACE,
    apply_theme,
    match_style,
)

_install_popups()

# Convenience list when Jira editmeta does not send allowedValues (text schema or fetch missed).
# Option-schema rev fields use Jira's allowedValues. Now values still come from Load, not this list.
REV_VALUES = (
    "",
    "N/A",
    "A",
    "B",
    "C",
    "D",
    "E",
    *[str(n) for n in range(16)],
    "0A",
    "1A",
    "2A",
)
PURPOSE_VALUES = ("", "Approval", "Info", "Planned", "Construction", "NA")
SHOP_PURPOSE_VALUES = ("", "IFC", "IFI", "IFU", "Purchasing Only")
FIELD_PURPOSE_VALUES = ("", "IFC", "IFI")
# Filter-row pick follows the transmittal. Set packed to stays Jira Status.
PACK_PURPOSE = {
    CLIENT: ("purpose", "Submitted to Client For", PURPOSE_VALUES),
    SHOP: ("shop_purpose", "Submitted to Shop For", SHOP_PURPOSE_VALUES),
    FIELD: ("field_purpose", "Submitted to Field For", FIELD_PURPOSE_VALUES),
}
# Blank Now Outgoing Rev bumps to 0 (Elite IFC / numeric jobs such as 2026-075), not A.
BLANK_OUTGOING_REV = "0"


def row_key_for_y(bands: list[tuple[str, int, int]], y: int) -> str | None:
    """Map a screen (or canvas) y to the drawing row whose [top, bottom) band contains it."""
    point = int(y)
    for key, top, bottom in bands:
        if int(top) <= point < int(bottom):
            return key
    return None


def _next_alpha(token: str) -> str:
    """Step A→B→Z→AA, preserving the token's case."""
    chars = list(token)
    lower = token.islower()
    i = len(chars) - 1
    while i >= 0:
        current = chars[i]
        if current.lower() == "z":
            chars[i] = "a" if current.islower() else "A"
            i -= 1
            continue
        chars[i] = chr(ord(current) + 1)
        return "".join(chars)
    prefix = "a" if lower else "A"
    return prefix + "".join(chars)


def next_outgoing_rev(now: str) -> str:
    """Next Outgoing Rev after Jira Now. Does not invent a drawing-number scheme.

    Letters: A→B→C (case preserved). Numbers: 0→1→2. Blank Now → 0 (IFC numeric default).
    N/A is left as-is. Digit+letter tokens already on the board (0A) step the letter.
    Unknown shapes are left unchanged.
    """
    text = (now or "").strip()
    if not text:
        return BLANK_OUTGOING_REV
    if text.casefold() == "n/a":
        return text
    if text.isdigit():
        return str(int(text) + 1)
    if text.isalpha():
        return _next_alpha(text)
    match = re.fullmatch(r"(\d+)([A-Za-z]+)", text)
    if match:
        return match.group(1) + _next_alpha(match.group(2))
    return text


# key, title, values, width, kind (option=Combobox, text=Entry, date=Entry+calendar, eddi=Combobox)
FIELD_KEYS = (
    ("client_document_number", "Client Doc No.", (), 16, "text"),
    ("outgoing_rev", "Outgoing Rev", REV_VALUES, 12, "option"),
    ("purpose", "Submitted to Client For", PURPOSE_VALUES, 18, "option"),
    ("submission_date", "Submission Date", (), 12, "date"),
    ("return_request_date", "Return Request Date", (), 14, "date"),
    ("incoming_rev", "Incoming Rev", REV_VALUES, 12, "option"),
    ("approval", "Client Approval Status", APPROVAL_VALUES, 20, "option"),
    ("return_date", "Return Date", (), 12, "date"),
    ("shop_purpose", "Submitted to Shop For", SHOP_PURPOSE_VALUES, 18, "option"),
    ("shop_ifc_rev", "Shop Rev", REV_VALUES, 12, "option"),
    ("shop_ifc_date", "Shop Issue Date", (), 12, "date"),
    ("field_purpose", "Submitted to Field For", FIELD_PURPOSE_VALUES, 18, "option"),
    ("field_ifc_rev", "Field Rev", REV_VALUES, 12, "option"),
    ("field_ifc_date", "Field Issue Date", (), 12, "date"),
    ("eddi_status", "EDDI Status", EDDI_VALUES, 28, "eddi"),
)

# Pick from the list only (same as Status). Outgoing / Incoming Rev stay typeable after double-click.
PICK_ONLY_FIELDS = frozenset(
    {
        "purpose",
        "shop_purpose",
        "field_purpose",
        "approval",
        "shop_ifc_rev",
        "field_ifc_rev",
        "eddi_status",
    }
)
TYPEABLE_REV_FIELDS = frozenset({"outgoing_rev", "incoming_rev"})


def field_is_pick_only(field: str) -> bool:
    """True when Next is a readonly Combobox (Status or the 1.29 pick-only fields)."""
    return field == "status" or field in PICK_ONLY_FIELDS


def field_is_typeable_combo(field: str) -> bool:
    """Outgoing / Incoming Rev: ▼ picks; typing only after double-click."""
    return field in TYPEABLE_REV_FIELDS

# Two full rows, then back to the message loop. A long job then paints light
# shells in larger slices so the list is usable before every cell exists.
PAINT_BATCH = 2
SHELL_PAINT_BATCH = 8
PAINT_SLICE_MS = 1
# Full Next editors for the first screen. The rest stay a short line until scrolled into view.
VISIBLE_EDITORS = 12
SHELL_ROW_PX = 56
FROZEN_SYNC_MAX = 4
PACK_COL_INDEX = 0
DRAWING_COL_INDEX = 1
DESC_COL_INDEX = 2
STATUS_COL_INDEX = 3
MATCH_COL_INDEX = 4
PDF_COL_INDEX = 5
NON_JIRA_GROUP = "Non Jira"
EXTRA_EDIT_FIELDS = frozenset({"drawing_id", "title", "outgoing_rev"})
FIELD_COL_START = 6
BOARD_COLUMNS = FIELD_COL_START + len(FIELD_KEYS)
FROZEN_COLS = 2

JIRA_ID_TITLE = "JIRA ID"
HEADER_TITLES = (
    ("Pack", 0),
    (JIRA_ID_TITLE, 16),
    ("Description", 22),
    ("Status", 0),
    ("Match", 0),
    ("PDF", 0),
    *((title, width) for _field, title, _values, width, _kind in FIELD_KEYS),
)
COMBO_HEADER_COLS = frozenset(
    {STATUS_COL_INDEX}
    | {
        FIELD_COL_START + offset
        for offset, (_field, _title, _values, _width, kind) in enumerate(FIELD_KEYS)
        if kind in {"option", "eddi", "date"}
    }
)

CHAR_PX = 10
HEADING_PAD_PX = 16
COMBO_ARROW_PAD_PX = 22
PACK_PAD_PX = 8
SASH_PX = 4
MIN_COL_PX = 36
MAX_COL_PX = 720
HEADER_BG = "#E4EBF2"
WRAP_PAD_PX = 6 + SASH_PX + 4
# 1.31 prescribed defaults. Saved board_col_px can override after BOARD_LAYOUT_REV.
PACK_COL_PX = 48
JIRA_ID_COL_PX = 180
DESC_COL_PX = 240
PDF_COL_PX = 272


def no_return_status(status: str) -> bool:
    """IFI and IFC are issued for information. No return date is expected."""
    return (status or "").strip().casefold() in {"ifi", "ifc"}


def date_is_blank(value: str) -> bool:
    return (value or "").strip().casefold() in {"", "n/a", "na"}


def _field_pending(now: str, nxt: str, *, status: bool = False, date: bool = False) -> bool:
    next_value = (nxt or "").strip()
    now_value = (now or "").strip()
    if status:
        return bool(next_value) and next_value != now_value
    if date and date_is_blank(next_value) and date_is_blank(now_value):
        return False
    return next_value != now_value


def _option_now(values: tuple[str, ...] | list[str], now: str) -> str:
    """Now as the list option when this Next box is a dropdown; otherwise the Now text."""
    text = (now or "").strip()
    if not values:
        return text
    folded = text.casefold()
    for option in values:
        if str(option).strip().casefold() == folded:
            return str(option)
    return text


def _now_value(drawing: DrawingRow, field: str) -> str:
    if field == "title":
        return drawing.title or ""
    if field == "status":
        return drawing.status or ""
    return getattr(drawing, field, None) or ""


def _values_for_field(field: str) -> tuple[str, ...]:
    if field == "status":
        return DRAWING_STATUSES
    if field == "title":
        return ()
    for key, _title, values, _width, _kind in FIELD_KEYS:
        if key == field:
            return tuple(values)
    return ()


def with_now_option(values: tuple[str, ...] | list[str], now: str) -> tuple[str, ...]:
    """Keep Now on a Combobox list when Jira's current value is not in allowedValues."""
    options = tuple(values)
    text = (now or "").strip()
    if not text:
        return options
    folded = {str(option).strip().casefold() for option in options}
    if text.casefold() in folded:
        return options
    return options + (text,)


class NextEntry(ttk.Entry):
    """Plain Next cell: get/set like Combobox, no dropdown arrow.

    Idle state is readonly so a single click does not put a caret in the box.
    Double-click (or Tab) unlocks in-place edit. ``set()`` still writes.
    """

    def _with_write(self, action) -> None:
        was = "normal"
        with contextlib.suppress(tk.TclError):
            was = str(self.cget("state"))
        if was == "readonly":
            with contextlib.suppress(tk.TclError):
                self.configure(state="normal")
        try:
            action()
        finally:
            if was == "readonly":
                with contextlib.suppress(tk.TclError):
                    self.configure(state="readonly")

    def set(self, value: str) -> None:
        def write() -> None:
            ttk.Entry.delete(self, 0, "end")
            if value:
                ttk.Entry.insert(self, 0, value)

        self._with_write(write)


NextWidget = ttk.Combobox | NextEntry


def _grid_pad_y(info: dict) -> int:
    """Top + bottom pady for a grid cell, in pixels."""
    raw = info.get("pady", 0)
    if isinstance(raw, (tuple, list)) and len(raw) >= 2:
        try:
            return int(raw[0] or 0) + int(raw[1] or 0)
        except (TypeError, ValueError):
            return 0
    if isinstance(raw, str) and " " in raw.strip():
        parts = raw.split()
        try:
            return int(float(parts[0])) + int(float(parts[1]))
        except (TypeError, ValueError, IndexError):
            return 0
    try:
        value = int(float(raw or 0))
    except (TypeError, ValueError):
        return 0
    return value * 2


def header_pad_px(index: int) -> int:
    """Header text pad. Combobox / date columns add room for the ▼."""
    if index == PACK_COL_INDEX:
        return PACK_PAD_PX
    if index in COMBO_HEADER_COLS:
        return HEADING_PAD_PX + COMBO_ARROW_PAD_PX
    return HEADING_PAD_PX


def heading_floor_px() -> list[int]:
    """Minimum width so each heading stays on one line (header metrics, not field content)."""
    floors: list[int] = []
    for index, (title, _chars) in enumerate(HEADER_TITLES):
        if index == PACK_COL_INDEX:
            floors.append(PACK_COL_PX)
            continue
        floors.append(max(MIN_COL_PX, len(title) * CHAR_PX + header_pad_px(index)))
    return floors


def default_col_px() -> list[int]:
    """Pixel width per column: Pack slim, JIRA ID / Description / PDF reasonable, else headline."""
    widths = heading_floor_px()
    widths[PACK_COL_INDEX] = PACK_COL_PX
    widths[DRAWING_COL_INDEX] = max(widths[DRAWING_COL_INDEX], JIRA_ID_COL_PX)
    widths[DESC_COL_INDEX] = max(widths[DESC_COL_INDEX], DESC_COL_PX)
    widths[PDF_COL_INDEX] = max(widths[PDF_COL_INDEX], PDF_COL_PX)
    return widths


def _as_layout_rev(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def merge_col_px(saved: object, layout_rev: object = None) -> list[int]:
    """Apply saved sash widths only when they match this layout revision.

    Missing or older ``board_layout_rev`` drops pre-1.31 fat columns (Description 564).
    """
    defaults = default_col_px()
    if _as_layout_rev(layout_rev) != BOARD_LAYOUT_REV:
        return defaults
    floors = heading_floor_px()
    if not isinstance(saved, (list, tuple)) or len(saved) != len(defaults):
        return defaults
    out: list[int] = []
    for index, raw in enumerate(saved):
        try:
            px = int(raw)
        except (TypeError, ValueError):
            px = defaults[index]
        out.append(max(floors[index], max(MIN_COL_PX, min(px, MAX_COL_PX))))
    return out


def row_matches_filter(row: MatchedRow, needle: str, extra: str = "") -> bool:
    """True when every typed token appears in drawing ID, description, or Jira key."""
    text = (needle or "").strip().casefold()
    if not text:
        return True
    drawing = row.drawing
    hay = " ".join(
        part
        for part in (
            drawing.key,
            drawing.drawing_id,
            drawing.title,
            drawing.summary,
            extra,
        )
        if part
    ).casefold()
    return all(token in hay for token in text.split())


class _Held:
    """Stand-in for a Next editor that has not been built yet."""

    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = "" if value is None else str(value)

    def cget(self, _key: str = "") -> str:
        return ""

    def configure(self, **_kwargs: object) -> None:
        return None

    def winfo_exists(self) -> int:
        return 0


class PackMark(tk.Label):
    """Pack select: empty box, teal tick when included. clam Checkbutton looks like a cross."""

    def __init__(self, master: tk.Misc, variable: tk.BooleanVar) -> None:
        super().__init__(
            master,
            text="",
            width=2,
            height=1,
            relief="solid",
            bd=2,
            highlightthickness=1,
            highlightbackground="#102A43",
            highlightcolor="#102A43",
            bg=SURFACE,
            fg=OK,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self._var = variable
        self.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *_args: self._refresh())
        self._refresh()

    def _toggle(self, _event: object | None = None) -> None:
        self._var.set(not bool(self._var.get()))

    def _refresh(self) -> None:
        on = bool(self._var.get())
        self.configure(text="✓" if on else "", bg="#D1FAE5" if on else SURFACE, fg=OK)


@dataclass
class _Block:
    key: str
    group: str
    include: tk.BooleanVar
    originals: dict[str, ttk.Label]
    nexts: dict[str, NextWidget | _Held]
    drawing_label: ttk.Label
    drawing_id_next: NextEntry | _Held
    title_label: ttk.Label
    title_next: NextEntry | _Held
    status_label: ttk.Label
    status_next: ttk.Combobox | _Held
    match_label: ttk.Label
    pdf_label: ttk.Label
    pdf_cell: tk.Frame
    pack_mark: PackMark
    locate_btn: ttk.Button | None
    rename_btn: ttk.Button | None
    open_btn: ttk.Button | None
    preview_btn: ttk.Button | None
    widgets: list[tk.Misc]
    # The four 1px separators (top/bottom × scrolling/frozen pane) that bracket this row.
    rules: tuple[tk.Frame, ...]
    shown: bool = True
    focused: bool = False
    extra: bool = False
    extra_path: str = ""
    extra_dropped: bool = False
    shop_folder: ttk.Combobox | None = None
    mounted: bool = True
    grid_top: int = 0


class DrawingBoard(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_open_pdf,
        on_locate_pdf=None,
        on_preview_pdf=None,
        on_rename_pdf=None,
        cover_return_stamp=None,
        cover_issued_stamp=None,
        on_cancel_next=None,
        on_draft_change=None,
        on_no_return=None,
    ) -> None:
        super().__init__(master)
        apply_theme(self)
        self._on_open_pdf = on_open_pdf
        self._on_locate_pdf = on_locate_pdf or on_open_pdf
        self._on_preview_pdf = on_preview_pdf
        self._on_rename_pdf = on_rename_pdf
        self._cover_stamps: dict[str, Callable[[], object]] = {}
        if cover_return_stamp is not None:
            self._cover_stamps["return_request_date"] = cover_return_stamp
        if cover_issued_stamp is not None:
            self._cover_stamps["submission_date"] = cover_issued_stamp
        self._cover_return_stamp = cover_return_stamp
        self._on_cancel_next = on_cancel_next
        self._on_draft_change = on_draft_change
        self._on_no_return = on_no_return
        self._matches: dict[str, MatchedRow] = {}
        self._blocks: dict[str, _Block] = {}
        self._focus_key = ""
        self._focus_painted = ""
        self._active_next: NextWidget | None = None
        self._batch_status: ttk.Combobox
        self._batch_fields: dict[str, NextWidget] = {}
        self._rev_options: dict[str, tuple[str, ...]] = {}
        self._eddi_options: dict[str, tuple[str, ...]] = {}
        self._batch_note: ttk.Label
        self._pack_status: ttk.Combobox
        self._pack_status_loading = False
        self._pack_purpose: ttk.Combobox
        self._pack_purpose_loading = False
        self._packed_only_btn: ttk.Button
        self._tip: tk.Toplevel | None = None
        self._tip_after = ""
        self._paint_after = ""
        self._paint_queue: deque[MatchedRow] = deque()
        self._paint_grid = 0
        self._paint_group: str | None = None
        self._paint_checked: set[str] | None = None
        self._paint_total = 0
        self._paint_done = 0
        self._defer_editors = False
        self._editor_count = 0
        self._mount_after = ""
        self._paint_on_progress = None
        self._paint_on_done = None
        self._suspend_layout = False
        saved = load_settings()
        self._col_px = merge_col_px(saved.board_col_px, saved.board_layout_rev)
        factor = pixel_scale(self)
        if factor > 1.02:
            self._col_px = [max(1, int(round(px * factor))) for px in self._col_px]
        self._header_labels: list[ttk.Label] = []
        self._header_wraps: list[tuple[int, ttk.Label]] = []
        self._group_headers: list[tuple[str, ttk.Label]] = []
        self._group_frozen: list[ttk.Label] = []
        self._drag_col: int | None = None
        self._drag_start_x = 0
        self._drag_start_w = 0
        self._syncing = False
        self._frozen_row_after = ""
        self._frozen_syncing = False
        self._frozen_passes = 0
        self._filter_var = tk.StringVar()
        self._filter_needle = ""
        self._filter_hidden = False
        self._jira_grid_end = 0
        self._extras_painted = False
        self._shop_choices: tuple[str, ...] = ()
        self._packed_only = tk.BooleanVar(value=False)
        self._pack_filter_after = ""
        self._drop_hover_key = ""

        self._find_bar = ttk.Frame(self)
        self._find_bar.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(self._find_bar, text="Filter").pack(side="left")
        self._filter = ttk.Entry(self._find_bar, textvariable=self._filter_var, width=22)
        self._filter.pack(side="left", padx=(8, 4))
        ttk.Button(self._find_bar, text="Find", command=self._run_filter).pack(side="left")
        ttk.Button(self._find_bar, text="Clear", style="Danger.TButton", command=self._clear_filter).pack(
            side="left", padx=(4, 8)
        )
        self._packed_only_btn = ttk.Button(self._find_bar, text="Packed only", command=self._toggle_packed_only)
        self._packed_only_btn.pack(side="left", padx=(0, 8))
        ttk.Button(self._find_bar, text="Pack none", command=lambda: self.set_pack(False)).pack(
            side="left", padx=(4, 4)
        )
        ttk.Button(self._find_bar, text="Cancel Next", style="Danger.TButton", command=self._cancel_next).pack(
            side="left", padx=(0, 8)
        )
        ttk.Label(self._find_bar, text="Set packed to").pack(side="left")
        self._pack_status = ttk.Combobox(
            self._find_bar, width=22, values=("",) + DRAWING_STATUSES, state="readonly"
        )
        self._pack_status.pack(side="left", padx=(4, 8))
        self._pack_status.bind("<<ComboboxSelected>>", self._on_pack_status_change)
        self._quiet_dropdown(self._pack_status)
        self._pack_purpose_kind = CLIENT
        self._pack_purpose_field = "purpose"
        self._pack_purpose_label = ttk.Label(self._find_bar, text="Submitted to Client For")
        self._pack_purpose_label.pack(side="left")
        self._pack_purpose = ttk.Combobox(
            self._find_bar, width=16, values=PURPOSE_VALUES, state="readonly"
        )
        self._pack_purpose.pack(side="left", padx=(4, 8))
        self._pack_purpose.bind("<<ComboboxSelected>>", self._on_pack_purpose_change)
        self._quiet_dropdown(self._pack_purpose)
        self._batch_toggle = ttk.Button(self._find_bar, text="Batch Next…", command=self._toggle_batch)
        self._batch_toggle.pack(side="left")
        self._filter_note = ttk.Label(self._find_bar, text="Type, then Find", style="Muted.TLabel")
        self._filter_note.pack(side="left", padx=(8, 0))
        self._batch_note = ttk.Label(self._find_bar, text="", style="Muted.TLabel")
        self._batch_note.pack(side="left", padx=(8, 0))
        self._filter.bind("<Return>", self._run_filter)
        self._filter.bind("<Escape>", self._clear_filter)

        self._batch_frame = ttk.LabelFrame(self, text="Batch Next — applies to Pack ticks only", padding=4)
        self._batch_open = False
        top = ttk.Frame(self._batch_frame)
        top.pack(fill="x")
        actions = ttk.Frame(top)
        actions.pack(side="left", fill="y")
        ttk.Button(actions, text="Apply to Pack", style="Accent.TButton", command=self._apply_batch).pack(
            side="left", padx=(0, 8)
        )
        ttk.Label(actions, text="Status").pack(side="left")
        self._batch_status = ttk.Combobox(actions, width=18, values=("",) + DRAWING_STATUSES, state="readonly")
        self._batch_status.pack(side="left", padx=(2, 8))
        self._quiet_dropdown(self._batch_status)

        fields_host = ttk.Frame(top)
        fields_host.pack(side="left", fill="x", expand=True)
        batch_canvas = tk.Canvas(fields_host, height=36, highlightthickness=0, background=BG, borderwidth=0)
        batch_h = ttk.Scrollbar(fields_host, orient="horizontal", command=batch_canvas.xview)
        batch_inner = ttk.Frame(batch_canvas)
        batch_win = batch_canvas.create_window((0, 0), window=batch_inner, anchor="nw")
        batch_canvas.configure(xscrollcommand=batch_h.set)
        batch_canvas.pack(fill="x", expand=True)
        batch_h.pack(fill="x")
        self._batch_fields = {}
        for field, title, values, width, kind in FIELD_KEYS:
            ttk.Label(batch_inner, text=title).pack(side="left")
            box_width = max(8, width - 2)
            if kind in {"text", "date"}:
                box: NextWidget = NextEntry(batch_inner, width=box_width)
                box.pack(side="left", padx=(2, 0) if kind == "date" else (2, 8))
                if kind == "date":
                    attach_calendar(box, parent=self)
            else:
                pick = field in PICK_ONLY_FIELDS
                box = ttk.Combobox(
                    batch_inner, width=box_width, values=values, state="readonly" if pick else "normal"
                )
                box.pack(side="left", padx=(2, 8))
                self._quiet_dropdown(box)
            self._batch_fields[field] = box

        def _batch_sync(_event=None) -> None:
            batch_canvas.configure(scrollregion=batch_canvas.bbox("all"))
            batch_canvas.itemconfigure(batch_win, height=max(batch_inner.winfo_reqheight(), 28))

        batch_inner.bind("<Configure>", _batch_sync)

        table = ttk.Frame(self)
        table.pack(fill="both", expand=True)
        table.rowconfigure(1, weight=1)
        table.columnconfigure(0, weight=1)
        self._header_canvas = tk.Canvas(table, height=28, highlightthickness=0, background=BG, borderwidth=0)
        self._canvas = tk.Canvas(table, highlightthickness=0, background=BG, borderwidth=0)
        vscroll = ttk.Scrollbar(table, orient="vertical", command=self._canvas.yview)
        self._hscroll = ttk.Scrollbar(table, orient="horizontal", command=self._xview)
        self._header = ttk.Frame(self._header_canvas, style="Header.TFrame")
        self._inner = ttk.Frame(self._canvas, style="Board.TFrame")
        self._freeze_header = tk.Frame(self._header_canvas, background=HEADER_BG, highlightthickness=0, bd=0)
        self._freeze_inner = tk.Frame(self._canvas, background=BG, highlightthickness=0, bd=0)
        self._header_window = self._header_canvas.create_window((0, 0), window=self._header, anchor="nw")
        self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._freeze_header_window = self._header_canvas.create_window(
            (0, 0), window=self._freeze_header, anchor="nw"
        )
        self._freeze_window = self._canvas.create_window((0, 0), window=self._freeze_inner, anchor="nw")
        self._vscroll = vscroll
        self._canvas.configure(yscrollcommand=self._on_yscroll, xscrollcommand=self._on_xscroll)
        self._inner.bind("<Button-1>", self._press_row_band, add="+")
        self._freeze_inner.bind("<Button-1>", self._press_row_band, add="+")
        self._header_canvas.grid(row=0, column=0, sticky="ew", padx=(8, 0), pady=(0, 0))
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 0))
        vscroll.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(0, 8), pady=(0, 0))
        self._hscroll.grid(row=2, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))
        self._header.bind("<Configure>", lambda _event: self._sync_scroll())
        self._inner.bind("<Configure>", lambda _event: self._schedule_frozen_row_sync())
        self._freeze_inner.bind("<Configure>", lambda _event: self._schedule_frozen_row_sync())
        self._canvas.bind("<Configure>", lambda event: self._sync_scroll(event.width))
        self._header_canvas.bind("<Configure>", lambda event: self._sync_scroll(event.width))
        self.bind("<Enter>", lambda _event: self._canvas.bind_all("<MouseWheel>", self._wheel))
        self.bind("<Leave>", lambda _event: self._canvas.unbind_all("<MouseWheel>"))
        self.bind_all("<Button-1>", self._on_global_press, add="+")
        self.bind_all("<Return>", self._on_global_return, add="+")
        self.bind_all("<KP_Enter>", self._on_global_return, add="+")
        self.bind_all("<Escape>", self._on_global_escape, add="+")
        self._draw_header()
        self._apply_col_sizes()

    def drop_target_widgets(self) -> list[tk.Misc]:
        """Fixed board HWNDs for OLE (canvas + inner panes). Not per-row children."""
        return [self, self._canvas, self._inner, self._freeze_inner, self._header_canvas]

    def row_bands(self) -> list[tuple[str, int, int]]:
        """Visible drawing rows as (key, root_y0, root_y1) for hit-testing a drop."""
        bands: list[tuple[str, int, int]] = []
        for key, block in self._blocks.items():
            if not block.shown:
                continue
            ys: list[int] = []
            for item in (block.drawing_label, block.pack_mark, block.title_next, block.pdf_cell):
                try:
                    ys.append(int(item.winfo_rooty()))
                    ys.append(int(item.winfo_rooty()) + max(int(item.winfo_height()), 1))
                except (tk.TclError, TypeError, ValueError, AttributeError):
                    continue
            if not ys:
                continue
            bands.append((key, min(ys), max(ys)))
        bands.sort(key=lambda item: item[1])
        return bands

    def set_drop_hover(self, key: str | None) -> None:
        """Cheap row outline so an Outlook drag does not feel like nothing."""
        token = key or ""
        if token == self._drop_hover_key:
            return
        self._drop_hover_key = token
        with contextlib.suppress(tk.TclError):
            self._canvas.delete("drop_hover")
        if not token:
            return
        block = self._blocks.get(token)
        if block is None:
            return
        try:
            canvas_root = int(self._canvas.winfo_rooty())
            y0 = int(block.drawing_label.winfo_rooty())
            y1 = y0 + max(int(block.drawing_label.winfo_height()), 8)
            with contextlib.suppress(tk.TclError):
                box = block.title_next
                y1 = max(y1, int(box.winfo_rooty()) + max(int(box.winfo_height()), 1))
            top = float(self._canvas.canvasy(y0 - canvas_root))
            bot = float(self._canvas.canvasy(y1 - canvas_root))
            width = max(int(self._canvas.winfo_width()), 8)
            self._canvas.create_rectangle(
                1,
                top,
                width - 1,
                bot,
                outline=ACCENT,
                width=2,
                fill="",
                tags="drop_hover",
            )
        except (tk.TclError, TypeError, ValueError, AttributeError):
            return

    def _on_yscroll(self, first: str, last: str) -> None:
        self._vscroll.set(first, last)
        self._schedule_mount()

    def _xview(self, *args) -> None:
        self._canvas.xview(*args)
        self._header_canvas.xview(*args)
        self._pin_frozen()

    def _on_xscroll(self, first: str, last: str) -> None:
        self._hscroll.set(first, last)
        self._header_canvas.xview_moveto(first)
        self._pin_frozen()

    def _frozen_width(self) -> int:
        return max(sum(self._col_px[:FROZEN_COLS]), 1)

    def _size_frozen(self) -> None:
        width = self._frozen_width()
        with contextlib.suppress(tk.TclError):
            self._canvas.itemconfigure(self._freeze_window, width=width)
            self._header_canvas.itemconfigure(self._freeze_header_window, width=width)

    def _pin_frozen(self) -> None:
        with contextlib.suppress(tk.TclError):
            self._canvas.coords(self._freeze_window, self._canvas.canvasx(0), 0)
            self._header_canvas.coords(self._freeze_header_window, self._header_canvas.canvasx(0), 0)
            self._canvas.tag_raise(self._freeze_window)
            self._header_canvas.tag_raise(self._freeze_header_window)

    def _schedule_frozen_row_sync(self) -> None:
        """Match freeze-pane row heights after wrap has a real requested size."""
        if (
            self._suspend_layout
            or self._frozen_row_after
            or self._frozen_syncing
            or self._frozen_passes >= FROZEN_SYNC_MAX
        ):
            return
        try:
            self._frozen_row_after = self.after_idle(self._run_frozen_row_sync)
        except tk.TclError:
            self._frozen_row_after = ""

    def _run_frozen_row_sync(self) -> None:
        self._frozen_row_after = ""
        if self._suspend_layout or self._frozen_syncing:
            return
        if self._frozen_passes >= FROZEN_SYNC_MAX:
            return
        self._frozen_syncing = True
        self._frozen_passes += 1
        try:
            # Do not call update_idletasks: nested idle + Configure/OLE freeze Load.
            self._sync_frozen_rows()
            self._sync_scroll()
        finally:
            self._frozen_syncing = False

    def _filter_grid_ids(self) -> tuple[set[int], set[int]]:
        """Tracked grid slaves, and which of them the filter is currently showing."""
        tracked: set[int] = set()
        shown: set[int] = set()
        visible_groups = {block.group for block in self._blocks.values() if block.shown}
        for block in self._blocks.values():
            for widget in block.widgets:
                tracked.add(id(widget))
                if block.shown:
                    shown.add(id(widget))
        for (group, label), freeze in zip(self._group_headers, self._group_frozen, strict=True):
            tracked.add(id(label))
            tracked.add(id(freeze))
            if group in visible_groups:
                shown.add(id(label))
                shown.add(id(freeze))
        return tracked, shown

    def _row_needed_height(
        self,
        frame: tk.Misc,
        row: int,
        *,
        tracked_ids: set[int],
        shown_ids: set[int],
    ) -> int:
        try:
            slaves = frame.grid_slaves(row=row)
        except tk.TclError:
            return 0
        height = 0
        for child in slaves:
            try:
                if id(child) in tracked_ids and id(child) not in shown_ids:
                    continue
                info = child.grid_info()
                if int(info.get("rowspan") or 1) > 1:
                    continue
                height = max(height, int(child.winfo_reqheight()) + _grid_pad_y(info))
            except (tk.TclError, TypeError, ValueError):
                continue
        return height

    def _sync_frozen_rows(self) -> bool:
        if self._suspend_layout:
            return False
        tracked_ids, shown_ids = self._filter_grid_ids()
        rows: set[int] = set()
        for frame in (self._freeze_inner, self._inner):
            try:
                _cols, nrows = frame.grid_size()
            except tk.TclError:
                continue
            rows.update(range(int(nrows)))
        changed = False
        for row in rows:
            height = max(
                self._row_needed_height(self._freeze_inner, row, tracked_ids=tracked_ids, shown_ids=shown_ids),
                self._row_needed_height(self._inner, row, tracked_ids=tracked_ids, shown_ids=shown_ids),
            )
            for frame in (self._freeze_inner, self._inner):
                try:
                    current = int(frame.grid_rowconfigure(row).get("minsize") or 0)
                except (tk.TclError, TypeError, ValueError):
                    continue
                if current != height:
                    frame.rowconfigure(row, minsize=height, weight=0)
                    changed = True
        return changed

    def _sync_scroll(self, canvas_width: int | None = None) -> None:
        if self._suspend_layout or self._syncing:
            return
        if self._drag_col is not None:
            self._sync_header_span(canvas_width)
            return
        self._syncing = True
        try:
            width = canvas_width if canvas_width is not None else self._canvas.winfo_width()
            if width <= 1:
                width = self._header_canvas.winfo_width()
            span = max(width, sum(self._col_px), 1)
            self._canvas.itemconfigure(self._window, width=span)
            self._header_canvas.itemconfigure(self._header_window, width=span)
            header_h = max(self._header.winfo_reqheight(), 24)
            self._header_canvas.configure(height=header_h, scrollregion=(0, 0, span, header_h))
            body = self._canvas.bbox("all")
            if body is None:
                self._canvas.configure(scrollregion=(0, 0, span, 1))
            else:
                self._canvas.configure(scrollregion=body)
            self._size_frozen()
            self._pin_frozen()
        finally:
            self._syncing = False

    def _sync_header_span(self, canvas_width: int | None = None) -> None:
        """Resize the heading strip without measuring the drawing grid."""
        if self._syncing:
            return
        self._syncing = True
        try:
            width = canvas_width if canvas_width is not None else self._header_canvas.winfo_width()
            if width <= 1:
                width = self._canvas.winfo_width()
            span = max(width, sum(self._col_px), 1)
            self._header_canvas.itemconfigure(self._header_window, width=span)
            header_h = max(self._header.winfo_reqheight(), 24)
            self._header_canvas.configure(height=header_h, scrollregion=(0, 0, span, header_h))
            self._size_frozen()
            self._pin_frozen()
        finally:
            self._syncing = False

    def _wheel(self, event: tk.Event) -> None:
        steps = int(-event.delta / 120)
        if event.state & 0x0001:
            self._xview("scroll", steps, "units")
        else:
            self._canvas.yview_scroll(steps, "units")

    def _wheel_keeps_dropdown(self, event: tk.Event) -> str:
        """Scroll the list. Do not step the dropdown under the pointer."""
        self._wheel(event)
        return "break"

    def _quiet_dropdown(self, box: ttk.Combobox) -> None:
        box.bind("<MouseWheel>", self._wheel_keeps_dropdown, add="+")

    def _apply_col_sizes(self, col: int | None = None) -> None:
        cols = range(len(self._col_px)) if col is None else (col,)
        for index in cols:
            px = self._col_px[index]
            self._header.columnconfigure(index, minsize=px, weight=0)
            self._inner.columnconfigure(index, minsize=px, weight=0)
            if index < FROZEN_COLS:
                self._freeze_header.columnconfigure(index, minsize=px, weight=0)
                self._freeze_inner.columnconfigure(index, minsize=px, weight=0)
        self._apply_header_wraps(col)
        if col is None or col in (DRAWING_COL_INDEX, DESC_COL_INDEX):
            self._apply_body_wraps(col)
        if not self._suspend_layout:
            if not self._frozen_syncing:
                self._frozen_passes = 0
            self._size_frozen()
            self._pin_frozen()
            self._schedule_frozen_row_sync()
        self._sync_scroll()

    def _wrap_px(self, col: int) -> int:
        return max(24, self._col_px[col] - WRAP_PAD_PX)

    def _apply_header_wraps(self, col: int | None = None) -> None:
        """Headings stay one line. Body JIRA ID / Description wrap to the column."""
        for wrap_col, label in self._header_wraps:
            if col is not None and wrap_col != col:
                continue
            try:
                if label.winfo_exists():
                    label.configure(wraplength=0)
            except tk.TclError:
                continue

    def _apply_body_wraps(self, col: int | None = None) -> None:
        draw_px = self._wrap_px(DRAWING_COL_INDEX)
        desc_px = self._wrap_px(DESC_COL_INDEX)
        for block in self._blocks.values():
            try:
                if col is None or col == DRAWING_COL_INDEX:
                    block.drawing_label.configure(wraplength=draw_px)
                if col is None or col == DESC_COL_INDEX:
                    block.title_label.configure(wraplength=desc_px)
            except tk.TclError:
                continue

    def _apply_header_col(self, col: int) -> None:
        px = self._col_px[col]
        self._header.columnconfigure(col, minsize=px, weight=0)
        if col < FROZEN_COLS:
            self._freeze_header.columnconfigure(col, minsize=px, weight=0)
            self._size_frozen()
        self._apply_header_wraps(col)
        self._sync_header_span()
        self._pin_frozen()

    def resize_column(self, col: int, px: int, *, persist: bool = False) -> None:
        if col < 0 or col >= len(self._col_px):
            return
        self._col_px[col] = max(MIN_COL_PX, min(int(px), MAX_COL_PX))
        self._apply_col_sizes(col)
        if persist:
            remember_board_col_px(self._col_px)

    def column_minsizes(self) -> list[int]:
        return [
            int(self._header.grid_columnconfigure(col)["minsize"] or 0) for col in range(BOARD_COLUMNS)
        ]

    def header_titles(self) -> list[str]:
        return [str(label.cget("text")) for label in self._header_labels]

    def _sash_press(self, col: int, event: tk.Event) -> None:
        self._drag_col = col
        self._drag_start_x = int(event.x_root)
        self._drag_start_w = self._col_px[col]

    def _sash_move(self, event: tk.Event) -> None:
        if self._drag_col is None:
            return
        delta = int(event.x_root) - self._drag_start_x
        px = max(MIN_COL_PX, min(self._drag_start_w + delta, MAX_COL_PX))
        if px == self._col_px[self._drag_col]:
            return
        self._col_px[self._drag_col] = px
        self._apply_header_col(self._drag_col)

    def _sash_release(self, _event: tk.Event | None = None) -> None:
        if self._drag_col is None:
            return
        col = self._drag_col
        self._drag_col = None
        self._apply_col_sizes(col)
        remember_board_col_px(self._col_px)

    def _sash_reset(self, col: int, _event: tk.Event | None = None) -> None:
        self._drag_col = None
        self.resize_column(col, default_col_px()[col], persist=True)

    def _place(self, widget: tk.Misc, row: int, col: int, **grid) -> None:
        widget.grid(row=row, column=col, sticky="nsew", padx=(6, SASH_PX), pady=1, **grid)

    def _field_values(self, field: str) -> tuple[str, ...]:
        override = self._rev_options.get(field)
        if override:
            return override
        return _values_for_field(field)

    def _eddi_values_for(self, key: str) -> tuple[str, ...]:
        """EDDI Status ▼ for one row: that issue's own Jira options, else the Elite list."""
        return self._eddi_options.get(key) or _values_for_field("eddi_status")

    def _shared_eddi_options(self) -> tuple[str, ...]:
        """Batch EDDI list: only options every listed issue's own context has."""
        if not self._eddi_options:
            return _values_for_field("eddi_status")
        lists = list(self._eddi_options.values())
        shared = [normalize_option_key(label) for label in lists[0]]
        for values in lists[1:]:
            folded = {normalize_option_key(label) for label in values}
            shared = [key for key in shared if key in folded]
        keep = set(shared)
        return tuple(label for label in lists[0] if normalize_option_key(label) in keep)

    def set_eddi_options(self, options: dict[str, tuple[str, ...]] | None) -> None:
        """Per-issue EDDI Status lists. Never offer another issue's context options."""
        self._eddi_options = {key: tuple(values) for key, values in (options or {}).items() if values}
        shared = self._shared_eddi_options()
        box = self._batch_fields.get("eddi_status")
        if isinstance(box, ttk.Combobox):
            box.configure(values=shared)
            if box.get().strip() and box.get().strip() not in shared:
                box.set("")
        for block in self._blocks.values():
            nxt = block.nexts.get("eddi_status")
            if isinstance(nxt, ttk.Combobox):
                row = self._matches.get(block.key)
                now = (row.drawing.eddi_status or "") if row is not None else ""
                nxt.configure(values=with_now_option(self._eddi_values_for(block.key), now))

    def set_rev_options(self, options: dict[str, tuple[str, ...]] | None) -> None:
        """Use Jira allowedValues for rev Comboboxes. Empty/omitted fields keep REV_VALUES."""
        self._rev_options = {key: tuple(values) for key, values in (options or {}).items() if values}
        for field, _title, defaults, _width, _kind in FIELD_KEYS:
            if field not in {"outgoing_rev", "incoming_rev", "shop_ifc_rev", "field_ifc_rev"}:
                continue
            values = self._rev_options.get(field) or tuple(defaults)
            box = self._batch_fields.get(field)
            if isinstance(box, ttk.Combobox):
                box.configure(values=values)
            for block in self._blocks.values():
                nxt = block.nexts.get(field)
                if isinstance(nxt, ttk.Combobox):
                    row = self._matches.get(block.key)
                    now = getattr(row.drawing, field, "") or "" if row is not None else ""
                    nxt.configure(values=with_now_option(values, now))

    def _next_box(
        self,
        row: int,
        col: int,
        *,
        values: tuple[str, ...] | list[str],
        initial: str,
        key: str,
        field: str,
        readonly: bool = False,
        kind: str = "option",
        host: tk.Misc | None = None,
    ) -> NextWidget:
        """Next editor in a colored cell. ttk fill is ignored on Windows, so the cell is yellow."""
        cell = tk.Frame(host if host is not None else self._inner, bg=SURFACE, highlightthickness=0, bd=0)
        cell.grid(row=row, column=col, sticky="nsew", padx=(6, SASH_PX), pady=1)
        if kind in {"text", "date"}:
            box: NextWidget = NextEntry(cell, width=1)
            box.set(initial)
            if kind == "date":
                box.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
                attach_calendar(
                    box,
                    parent=self,
                    on_change=lambda drawing=key: self._refresh_next_marks_key(drawing),
                    allow_na=(field == "return_request_date"),
                )
            else:
                box.pack(fill="both", expand=True, padx=2, pady=2)
        else:
            box = ttk.Combobox(
                cell,
                width=1,
                values=values,
                state="readonly",
            )
            box.set(initial)
            box.pack(fill="both", expand=True, padx=2, pady=2)
            self._quiet_dropdown(box)
        if isinstance(box, NextEntry):
            box.configure(state="readonly")
        box.bind("<Button-1>", lambda event, drawing=key: self._on_next_button1(event, drawing))
        if isinstance(box, NextEntry) or field_is_typeable_combo(field):
            box.bind("<Double-1>", self._on_next_double1)
            cell.bind("<Double-1>", lambda event, watched=box: self._on_next_double1(event, watched))
        box._doccon_cell = cell
        box._doccon_key = key
        box._doccon_field = field
        cell._doccon_key = key
        cell._doccon_field = field
        self._bind_restore_now(box, cell)
        return box

    def _on_next_button1(self, event: tk.Event, key: str) -> str | None:
        self._set_focus(key)
        widget = getattr(event, "widget", None)
        if isinstance(widget, NextEntry) and str(widget.cget("state")) == "readonly":
            return "break"
        return None

    def _on_next_double1(self, event: tk.Event, box: NextWidget | None = None) -> str:
        target = box if box is not None else self._board_next_from(getattr(event, "widget", None))
        if target is None and isinstance(getattr(event, "widget", None), NextEntry):
            target = event.widget  # type: ignore[assignment]
        if target is not None:
            self.enter_next_editor(target)
        return "break"

    def enter_next_editor(self, box: NextWidget) -> None:
        """Unlock in-place edit and put the caret in the box. Does not write Jira."""
        if not self._extra_field_editable(box):
            return
        self._unlock_for_edit(box)
        with contextlib.suppress(tk.TclError):
            box.focus_set()
            if isinstance(box, NextEntry):
                box.icursor("end")
        self._active_next = box
        key = getattr(box, "_doccon_key", None)
        if isinstance(key, str) and key:
            self._set_focus(key)

    def _extra_field_editable(self, box: object) -> bool:
        key = getattr(box, "_doccon_key", "")
        block = self._blocks.get(key) if isinstance(key, str) else None
        if block is None or not block.extra:
            return True
        field = str(getattr(box, "_doccon_field", ""))
        return field in EXTRA_EDIT_FIELDS

    def _unlock_for_edit(self, box: object) -> None:
        if isinstance(box, NextEntry):
            with contextlib.suppress(tk.TclError):
                box.configure(state="normal")
            return
        field = getattr(box, "_doccon_field", "")
        if isinstance(box, ttk.Combobox) and field_is_typeable_combo(str(field)):
            with contextlib.suppress(tk.TclError):
                box.configure(state="normal")

    def lock_next_editor(self, box: object) -> None:
        """Put a Next box back to idle (no caret). Pick-only lists stay readonly."""
        if isinstance(box, NextEntry):
            with contextlib.suppress(tk.TclError):
                box.configure(state="readonly")
            return
        if isinstance(box, ttk.Combobox):
            with contextlib.suppress(tk.TclError):
                box.configure(state="readonly")

    def _bind_restore_now(self, box: tk.Misc, cell: tk.Frame) -> None:
        """Right-click (and Undo) put Now back. Replaces the native Cut/Copy/Paste menu; Ctrl+V still pastes."""
        for widget in (box, cell):
            widget.bind("<Button-3>", self._on_restore_next, add="+")
            widget.bind("<ButtonRelease-3>", self._on_restore_next, add="+")
            widget.bind("<<ContextMenu>>", self._on_restore_next, add="+")
        box.bind("<<Undo>>", self._on_restore_next, add="+")
        box.bind("<App>", self._on_restore_next, add="+")

    def _next_cell(self, box: tk.Misc) -> tk.Frame | None:
        cell = getattr(box, "_doccon_cell", None)
        return cell if isinstance(cell, tk.Frame) else None

    def _clip_label(
        self,
        text: str,
        style: str = "Board.TLabel",
        *,
        wrap_col: int | None = None,
        parent: tk.Misc | None = None,
    ) -> ttk.Label:
        host = parent or self._inner
        if wrap_col is None:
            return ttk.Label(host, text=text, style=style, anchor="w", width=1)
        return ttk.Label(
            host,
            text=text,
            style=style,
            anchor="nw",
            justify="left",
            width=1,
            wraplength=self._wrap_px(wrap_col),
        )

    def _run_filter(self, _event: object | None = None) -> str:
        self.apply_filter()
        return "break"

    def _clear_filter(self, _event: object | None = None) -> str:
        self._filter_var.set("")
        self._filter_needle = ""
        self._refresh_filter()
        return "break"

    def apply_filter(self, text: str | None = None) -> None:
        if text is not None:
            self._filter_var.set(text)
        self._filter_needle = self._filter_var.get()
        self._refresh_filter()

    def packed_only(self) -> bool:
        return bool(self._packed_only.get())

    def set_packed_only(self, on: bool) -> None:
        """Show packed rows only when on. Combines with the text filter (packed ∩ match)."""
        wanted = bool(on)
        if bool(self._packed_only.get()) != wanted:
            self._packed_only.set(wanted)
        self._style_packed_only()
        self._refresh_filter()

    def _toggle_packed_only(self) -> None:
        self.set_packed_only(not bool(self._packed_only.get()))

    def _style_packed_only(self) -> None:
        on = bool(self._packed_only.get())
        try:
            self._packed_only_btn.configure(style="Brand.TButton" if on else "TButton")
        except tk.TclError:
            return

    def _cover_field_date(self, field: str) -> str:
        getter = self._cover_stamps.get(field)
        if getter is None:
            return ""
        return str(getter() or "").strip()

    def _cover_stamp_date(self) -> str:
        return self._cover_field_date("return_request_date")

    def _on_pack_tick(self, key: str = "") -> None:
        if key:
            self._stamp_pack_tick(key)
        self._notify_draft()
        if not bool(self._packed_only.get()) or self._suspend_layout:
            return
        if self._pack_filter_after:
            return
        try:
            self._pack_filter_after = self.after_idle(self._run_pack_filter)
        except tk.TclError:
            self._refresh_filter()

    def _stamp_pack_tick(self, key: str) -> None:
        block = self._blocks.get(key)
        if block is None or not block.include.get() or block.extra:
            return
        self.stamp_cover_dates_on_keys((key,))
        self.stamp_status_on_keys(self.pack_status(), (key,))
        self.stamp_purpose_on_keys(self.pack_purpose(), (key,), field=self._pack_purpose_field)

    def _run_pack_filter(self) -> None:
        self._pack_filter_after = ""
        self._refresh_filter()

    def _block_matches(self, block: _Block) -> bool:
        if bool(self._packed_only.get()) and not block.include.get():
            return False
        if block.extra:
            needle = self._filter_needle.strip().casefold()
            if not needle:
                return True
            blob = " ".join(
                (
                    block.drawing_id_next.get(),
                    block.title_next.get(),
                    block.status_next.get(),
                    Path(block.extra_path).name,
                )
            ).casefold()
            return needle in blob
        row = self._matches.get(block.key)
        if row is None:
            return False
        extra = ""
        try:
            extra = f"{block.drawing_id_next.get()} {block.title_next.get()}"
        except tk.TclError:
            extra = ""
        return row_matches_filter(row, self._filter_needle, extra=extra)

    def _refresh_filter(self) -> None:
        packed_only = bool(self._packed_only.get())
        needle = self._filter_needle.strip()
        if not self._blocks:
            self._filter_note.configure(text="No packed drawings" if packed_only else "Type, then Find")
            self._filter_hidden = False
            return
        if not needle and not packed_only and not self._filter_hidden:
            self._filter_note.configure(text="Type, then Find")
            return
        visible_groups: set[str] = set()
        shown = 0
        any_hidden = False
        self._suspend_layout = True
        try:
            for block in self._blocks.values():
                show = self._block_matches(block)
                if show:
                    shown += 1
                    visible_groups.add(block.group)
                else:
                    any_hidden = True
                if block.shown == show:
                    continue
                block.shown = show
                for widget in block.widgets:
                    try:
                        if show:
                            widget.grid()
                        else:
                            widget.grid_remove()
                    except tk.TclError:
                        continue
            for (group, label), freeze in zip(self._group_headers, self._group_frozen, strict=True):
                try:
                    if group in visible_groups:
                        label.grid()
                        freeze.grid()
                    else:
                        label.grid_remove()
                        freeze.grid_remove()
                except tk.TclError:
                    continue
        finally:
            self._suspend_layout = False
        self._filter_hidden = any_hidden
        packed_n = sum(1 for block in self._blocks.values() if block.include.get())
        total = len(self._blocks)
        if packed_only and not needle:
            self._filter_note.configure(text="No packed drawings" if shown == 0 else f"{shown} packed")
        elif packed_only and needle:
            self._filter_note.configure(text="No matches" if shown == 0 else f"{shown} of {packed_n} packed")
        elif not needle:
            self._filter_note.configure(text="Type, then Find")
        elif shown == 0:
            self._filter_note.configure(text="No matches")
        else:
            self._filter_note.configure(text=f"{shown} of {total}")
        self._frozen_passes = 0
        self._sync_frozen_rows()
        self._sync_scroll()
        self._schedule_frozen_row_sync()

    def _draw_header(self) -> None:
        for host in (self._header, self._freeze_header):
            for child in host.winfo_children():
                child.destroy()
        self._header_labels = []
        self._header_wraps = []
        for col, (title, _width) in enumerate(HEADER_TITLES):
            self._add_header_cell(self._header, col, title, remember=True)
            if col < FROZEN_COLS:
                self._add_header_cell(self._freeze_header, col, title, remember=False)

    def _add_header_cell(self, parent: tk.Misc, col: int, title: str, *, remember: bool) -> None:
        cell = tk.Frame(parent, background=HEADER_BG, highlightthickness=0, bd=0)
        cell.grid(row=0, column=col, sticky="nsew")
        if col == 0:
            tk.Frame(cell, width=1, background=BORDER, highlightthickness=0, bd=0).pack(side="left", fill="y")
        sash = tk.Frame(
            cell,
            width=SASH_PX,
            background=BORDER,
            cursor="sb_h_double_arrow",
            highlightthickness=0,
            bd=0,
        )
        sash.pack(side="right", fill="y")
        sash.bind("<Button-1>", lambda event, c=col: self._sash_press(c, event))
        sash.bind("<B1-Motion>", self._sash_move)
        sash.bind("<ButtonRelease-1>", self._sash_release)
        sash.bind("<Double-Button-1>", lambda event, c=col: self._sash_reset(c, event))
        label = ttk.Label(
            cell, text=title, style="Header.TLabel", anchor="w", justify="left", wraplength=0
        )
        label.pack(side="left", fill="both", expand=True, padx=(6, 2))
        if remember:
            self._header_labels.append(label)
            self._header_wraps.append((col, label))

    def _unmap_inner(self) -> None:
        """Keep the list off the canvas while rows are created so Tk does not relayout after each drawing."""
        for item in (self._window, self._freeze_window):
            with contextlib.suppress(tk.TclError):
                self._canvas.itemconfigure(item, window="")

    def _map_inner(self) -> None:
        try:
            self._canvas.itemconfigure(self._window, window=self._inner)
            self._canvas.itemconfigure(self._freeze_window, window=self._freeze_inner)
        except tk.TclError:
            self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
            self._freeze_window = self._canvas.create_window((0, 0), window=self._freeze_inner, anchor="nw")
        with contextlib.suppress(tk.TclError):
            self._canvas.tag_raise(self._freeze_window)
            self._header_canvas.tag_raise(self._freeze_header_window)
        self._size_frozen()
        self._pin_frozen()

    def cancel_paint(self) -> None:
        if self._paint_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._paint_after)
            self._paint_after = ""
        if self._frozen_row_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._frozen_row_after)
            self._frozen_row_after = ""
        if self._pack_filter_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._pack_filter_after)
            self._pack_filter_after = ""
        self._paint_queue = deque()
        self._paint_on_progress = None
        self._paint_on_done = None
        self._suspend_layout = False
        self._drag_col = None
        self._frozen_passes = 0
        self._frozen_syncing = False
        self._map_inner()

    def clear(self) -> None:
        self.cancel_paint()
        self._hide_tip()
        for host in (self._inner, self._freeze_inner):
            for child in host.winfo_children():
                child.destroy()
        self._blocks.clear()
        self._matches.clear()
        self._group_headers.clear()
        self._group_frozen.clear()
        # A repaint drops the band with the blocks it was painted on: no stale focused row.
        self._focus_key = ""
        self._focus_painted = ""
        self._filter_hidden = False
        self._jira_grid_end = 0
        self._extras_painted = False
        self._refresh_filter()
        self._sync_scroll()

    def set_rows(self, rows: list[MatchedRow], *, checked: set[str] | None = None) -> None:
        self._defer_editors = False
        self._begin_rows(rows, checked=checked)
        while self._paint_queue:
            self._paint_next()
        self._finish_paint()

    def start_rows(
        self,
        rows: list[MatchedRow],
        *,
        checked: set[str] | None = None,
        on_progress=None,
        on_done=None,
    ) -> None:
        self._defer_editors = True
        self._begin_rows(rows, checked=checked)
        self._paint_on_progress = on_progress
        self._paint_on_done = on_done
        if not self._paint_queue:
            self._finish_paint()
            return
        self._schedule_paint()

    def _begin_rows(self, rows: list[MatchedRow], *, checked: set[str] | None = None) -> None:
        self._set_batch_open(False)
        self._pack_status_loading = True
        self._pack_purpose_loading = True
        self._pack_status.set("")
        self._pack_purpose.set("")
        self._editor_count = 0
        self.clear()
        self._suspend_layout = True
        self._frozen_passes = 0
        self._unmap_inner()
        ordered = sorted(
            (row for row in rows if not is_generic_eddi(row.drawing.eddi_status)),
            key=lambda row: pack_sort_key(row.drawing),
        )
        self._paint_queue = deque(ordered)
        self._paint_checked = checked
        self._paint_grid = 0
        self._paint_group = None
        self._paint_total = len(ordered)
        self._paint_done = 0

    def _schedule_paint(self) -> None:
        try:
            self._paint_after = self.after(PAINT_SLICE_MS, self._paint_batch)
        except tk.TclError:
            self._paint_after = ""

    def _paint_batch(self) -> None:
        self._paint_after = ""
        count = PAINT_BATCH if self._editor_count < VISIBLE_EDITORS else SHELL_PAINT_BATCH
        for _ in range(count):
            if not self._paint_queue:
                break
            try:
                self._paint_next()
            except tk.TclError:
                continue
        if self._paint_on_progress is not None:
            self._paint_on_progress(self._paint_done, self._paint_total)
        if self._paint_queue:
            self._schedule_paint()
            return
        self._finish_paint()

    def _paint_next(self) -> None:
        if not self._paint_queue:
            return
        row = self._paint_queue.popleft()
        self._matches[row.drawing.key] = row
        include = self._paint_checked is None or row.drawing.key in self._paint_checked
        group = eddi_group_title(row.drawing.eddi_status)
        if group != self._paint_group:
            self._add_group_header(self._paint_grid, group)
            self._paint_grid += 1
            self._paint_group = group
        self._add_block(self._paint_grid, row, include=include)
        self._paint_grid += 4
        self._paint_done += 1

    def _finish_paint(self) -> None:
        self._paint_after = ""
        self._paint_queue = deque()
        self._jira_grid_end = self._paint_grid
        self._map_inner()
        self._suspend_layout = False
        self._frozen_passes = 0
        self._refresh_filter()
        self._apply_col_sizes()
        done = self._paint_on_done
        self._paint_on_progress = None
        self._paint_on_done = None
        if done is not None:
            done()
        self._schedule_mount()
        try:
            self.after_idle(self._clear_pack_status_loading)
            self.after_idle(self._clear_pack_purpose_loading)
        except tk.TclError:
            self._pack_status_loading = False
            self._pack_purpose_loading = False

    def _bind_overflow(self, widget: tk.Misc, get_text, min_chars: int) -> None:
        """Hover tip on clipped Now labels. Text Next boxes stay in-place (no copy window)."""
        if isinstance(widget, (NextEntry, ttk.Entry, ttk.Combobox, tk.Entry)):
            return
        widget.bind(
            "<Enter>",
            lambda _event, w=widget, getter=get_text, n=min_chars: self._schedule_tip(w, getter(), n),
        )
        widget.bind("<Leave>", lambda _event: self._hide_tip())

    def _schedule_tip(self, widget: tk.Misc, text: str, min_chars: int) -> None:
        self._hide_tip()
        full = (text or "").strip()
        if full in {"", "—"} or len(full) <= min_chars:
            return
        self._tip_after = self.after(350, lambda: self._show_tip(widget, full))

    def _hide_tip(self) -> None:
        if self._tip_after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._tip_after)
            self._tip_after = ""
        if self._tip is not None:
            with contextlib.suppress(tk.TclError):
                self._tip.destroy()
            self._tip = None

    def _show_tip(self, widget: tk.Misc, text: str) -> None:
        self._tip_after = ""
        if self._tip is not None:
            with contextlib.suppress(tk.TclError):
                self._tip.destroy()
            self._tip = None
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        with contextlib.suppress(tk.TclError):
            tip.wm_attributes("-topmost", True)
        tk.Label(
            tip,
            text=text,
            justify="left",
            wraplength=560,
            background=NAVY_MID,
            foreground="#FFFFFF",
            font=FONT_SMALL,
            padx=10,
            pady=8,
        ).pack()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip.geometry(f"+{x}+{y}")
        self._tip = tip

    def _add_group_header(self, grid_row: int, title: str) -> None:
        label = ttk.Label(self._inner, text=title, style="Group.TLabel", width=1, anchor="w")
        label.grid(
            row=grid_row,
            column=0,
            columnspan=BOARD_COLUMNS,
            sticky="ew",
            padx=2,
            pady=(8, 2),
        )
        freeze = ttk.Label(self._freeze_inner, text=title, style="Group.TLabel", width=1, anchor="w")
        freeze.grid(
            row=grid_row,
            column=0,
            columnspan=FROZEN_COLS,
            sticky="ew",
            padx=2,
            pady=(8, 2),
        )
        self._group_headers.append((title, label))
        self._group_frozen.append(freeze)

    def _hline(self, grid_row: int) -> tuple[tk.Frame, tk.Frame]:
        rest = tk.Frame(
            self._inner,
            height=1,
            background=BORDER,
            borderwidth=0,
            highlightthickness=0,
        )
        rest.grid(row=grid_row, column=0, columnspan=BOARD_COLUMNS, sticky="ew")
        freeze = tk.Frame(
            self._freeze_inner,
            height=1,
            background=BORDER,
            borderwidth=0,
            highlightthickness=0,
        )
        freeze.grid(row=grid_row, column=0, columnspan=FROZEN_COLS, sticky="ew")
        return rest, freeze

    def _add_shell(self, top: int, row: MatchedRow, *, include: bool) -> None:
        """Pack, id, and the Now labels. Next editors wait until the row is on screen."""
        drawing = row.drawing
        group = eddi_group_title(drawing.eddi_status)
        h_top, h_top_f = self._hline(top)
        now_row = top + 1
        next_row = top + 2
        pack = tk.BooleanVar(value=include)
        pack_mark = PackMark(self._freeze_inner, pack)
        pack_mark.grid(row=now_row, column=PACK_COL_INDEX, rowspan=2, padx=(4, SASH_PX), pady=4)
        drawing_label = self._clip_label(
            drawing.drawing_id or drawing.key,
            wrap_col=DRAWING_COL_INDEX,
            parent=self._freeze_inner,
        )
        self._place(drawing_label, now_row, DRAWING_COL_INDEX)
        title_label = self._clip_label(drawing.title or "—", wrap_col=DESC_COL_INDEX)
        self._place(title_label, now_row, DESC_COL_INDEX)
        status_label = self._clip_label(drawing.status)
        self._place(status_label, now_row, STATUS_COL_INDEX)
        match_label = self._clip_label(row.confidence, match_style(row.confidence))
        self._place(match_label, now_row, MATCH_COL_INDEX)
        pdf_cell = tk.Frame(self._inner, bg=BG, highlightthickness=0, bd=0)
        pdf_label = ttk.Label(pdf_cell, text=pdf_address_text(row), style="Board.TLabel", anchor="w")
        pdf_label.pack(fill="both", expand=True, padx=2, pady=1)
        self._place(pdf_cell, now_row, PDF_COL_INDEX)
        # Field Now labels wait until the row is on screen. A long job should not
        # build a cell for every column of every drawing before the first click.
        originals: dict[str, ttk.Label] = {}
        for frame in (self._inner, self._freeze_inner):
            frame.rowconfigure(now_row, minsize=SHELL_ROW_PX // 2, weight=0)
            frame.rowconfigure(next_row, minsize=SHELL_ROW_PX // 2, weight=0)
        h_bot, h_bot_f = self._hline(top + 3)
        nexts: dict[str, NextWidget | _Held] = {
            field: _Held(getattr(drawing, field) or "") for field, _t, _v, _w, _k in FIELD_KEYS
        }
        widgets: list[tk.Misc] = [
            h_top,
            h_top_f,
            pack_mark,
            drawing_label,
            title_label,
            status_label,
            match_label,
            pdf_cell,
            *originals.values(),
            h_bot,
            h_bot_f,
        ]
        self._blocks[drawing.key] = _Block(
            key=drawing.key,
            group=group,
            include=pack,
            originals=originals,
            nexts=nexts,
            drawing_label=drawing_label,
            drawing_id_next=_Held(drawing.drawing_id or ""),
            title_label=title_label,
            title_next=_Held(drawing.title or ""),
            status_label=status_label,
            status_next=_Held(drawing.status or ""),
            match_label=match_label,
            pdf_label=pdf_label,
            pdf_cell=pdf_cell,
            pack_mark=pack_mark,
            locate_btn=None,
            rename_btn=None,
            open_btn=None,
            preview_btn=None,
            widgets=widgets,
            rules=(h_top, h_top_f, h_bot, h_bot_f),
            mounted=False,
            grid_top=top,
        )
        pack.trace_add("write", lambda *_args, drawing_key=drawing.key: self._on_pack_tick(drawing_key))
        self._bind_row_select(
            [
                drawing_label,
                title_label,
                status_label,
                match_label,
                pdf_label,
                pdf_cell,
                pack_mark,
                *originals.values(),
                h_top,
                h_top_f,
                h_bot,
                h_bot_f,
            ],
            drawing.key,
        )

    def _bind_row_select(self, widgets: list[tk.Misc], key: str) -> None:
        """A click anywhere in the row, between its two lines, selects that drawing."""
        for widget in widgets:
            if widget is None:
                continue
            widget.bind("<Button-1>", lambda _event, row_key=key: self._focus_and_mount(row_key), add="+")

    def _press_row_band(self, event: tk.Event) -> None:
        frame = getattr(event, "widget", None)
        key = self._band_key(frame, int(getattr(event, "y", 0)))
        if key:
            self._focus_and_mount(key)

    def _band_key(self, frame: tk.Misc | None, y: int) -> str | None:
        frozen = frame is self._freeze_inner
        for key, block in self._blocks.items():
            if not block.shown or len(block.rules) < 4:
                continue
            top_line = block.rules[1] if frozen else block.rules[0]
            bot_line = block.rules[3] if frozen else block.rules[2]
            try:
                top = int(top_line.winfo_y())
                bot = int(bot_line.winfo_y()) + max(int(bot_line.winfo_height()), 1)
            except (tk.TclError, AttributeError, ValueError):
                continue
            if top <= y <= bot:
                return key
        return None

    def _focus_and_mount(self, key: str) -> None:
        self._mount_key(key)
        self._set_focus(key)

    def _mount_key(self, key: str) -> None:
        block = self._blocks.get(key)
        if block is not None:
            self._mount_block(block)

    def _mount_block(self, block: _Block) -> None:
        if block.mounted:
            return
        row = self._matches.get(block.key)
        if row is None:
            return
        top = block.grid_top
        include = bool(block.include.get())
        focused = block.focused or self._focus_key == block.key
        for widget in list(block.widgets):
            with contextlib.suppress(tk.TclError, AttributeError):
                widget.destroy()
        self._blocks.pop(block.key, None)
        self._add_block(top, row, include=include, force=True)
        fresh = self._blocks.get(row.drawing.key)
        if fresh is not None and focused:
            fresh.focused = True
            self._style_row_focus(fresh)

    def _schedule_mount(self) -> None:
        if self._mount_after or not self._defer_editors:
            return
        try:
            self._mount_after = self.after_idle(self._mount_visible)
        except tk.TclError:
            self._mount_after = ""

    def _block_top(self, block: _Block) -> float | None:
        """Pixel y of a shell inside the list. Grid index times a fixed height misses real rows."""
        for widget in (block.drawing_label, block.pdf_cell, block.title_label):
            if widget is None:
                continue
            try:
                return float(widget.winfo_y())
            except (tk.TclError, AttributeError, ValueError):
                continue
        return None

    def _mount_visible(self) -> None:
        self._mount_after = ""
        try:
            self._inner.update_idletasks()
            y0 = float(self._canvas.canvasy(0))
            height = max(int(self._canvas.winfo_height()), 1)
        except tk.TclError:
            return
        low = max(0.0, y0 - 200)
        high = y0 + height + 400
        built = 0
        more = False
        for block in list(self._blocks.values()):
            if block.mounted or block.extra:
                continue
            y = self._block_top(block)
            if y is None:
                continue
            # A shell that has not been laid out yet still reports y=0. Do not treat that as row 1.
            if y == 0.0 and block.grid_top > 4:
                continue
            if not (low <= y <= high):
                continue
            self._mount_block(block)
            built += 1
            if built >= 6:
                more = True
                break
        if more:
            self._schedule_mount()

    def _add_block(self, top: int, row: MatchedRow, *, include: bool, force: bool = False) -> None:
        defer = not force and self._defer_editors and self._editor_count >= VISIBLE_EDITORS
        if defer:
            self._add_shell(top, row, include=include)
            return
        self._editor_count += 1
        drawing = row.drawing
        group = eddi_group_title(drawing.eddi_status)
        h_top, h_top_f = self._hline(top)
        now_row = top + 1
        next_row = top + 2
        pack = tk.BooleanVar(value=include)
        pack_mark = PackMark(self._freeze_inner, pack)
        pack_mark.grid(row=now_row, column=PACK_COL_INDEX, rowspan=2, padx=(4, SASH_PX), pady=4)
        drawing_label = self._clip_label(
            drawing.drawing_id or drawing.key,
            wrap_col=DRAWING_COL_INDEX,
            parent=self._freeze_inner,
        )
        self._place(drawing_label, now_row, DRAWING_COL_INDEX)
        drawing_id_next = self._next_box(
            next_row,
            DRAWING_COL_INDEX,
            values=(),
            initial=drawing.drawing_id or "",
            key=drawing.key,
            field="drawing_id",
            kind="text",
            host=self._freeze_inner,
        )
        title_text = drawing.title or ""
        title_label = self._clip_label(title_text or "—", wrap_col=DESC_COL_INDEX)
        self._place(title_label, now_row, DESC_COL_INDEX)
        title_next = self._next_box(
            next_row,
            DESC_COL_INDEX,
            values=(),
            initial=title_text,
            key=drawing.key,
            field="title",
            kind="text",
        )
        status_label = self._clip_label(drawing.status)
        self._place(status_label, now_row, STATUS_COL_INDEX)
        status_next = self._next_box(
            next_row,
            STATUS_COL_INDEX,
            values=DRAWING_STATUSES,
            initial=drawing.status,
            key=drawing.key,
            field="status",
            readonly=True,
            kind="option",
        )
        match_label = self._clip_label(row.confidence, match_style(row.confidence))
        self._place(match_label, now_row, MATCH_COL_INDEX)
        pdf_cell, pdf_label = self._pdf_address_cell(row)
        self._place(pdf_cell, now_row, PDF_COL_INDEX)
        pdf_label.bind("<Double-1>", lambda _event, key=drawing.key: self._on_open_pdf(key))
        pdf_actions = ttk.Frame(self._inner, style="Board.TFrame")
        locate_btn = ttk.Button(
            pdf_actions,
            text="Locate…",
            style="Locate.TButton",
            width=8,
            command=lambda key=drawing.key: self._on_locate_pdf(key),
        )
        rename_btn = ttk.Button(
            pdf_actions,
            text="Rename…",
            style="Locate.TButton",
            width=8,
            command=lambda key=drawing.key: self._rename_pdf(key),
        )
        open_btn = ttk.Button(
            pdf_actions,
            text="Open",
            style="Locate.TButton",
            width=5,
            command=lambda key=drawing.key: self._on_open_pdf(key),
        )
        preview_btn = ttk.Button(
            pdf_actions,
            text="Preview",
            style="Locate.TButton",
            width=7,
            command=lambda key=drawing.key: self._preview_pdf(key),
        )
        locate_btn.pack(side="left", padx=(0, 4))
        open_btn.pack(side="left", padx=(0, 4))
        preview_btn.pack(side="left")
        shop_folder = self._make_shop_picker(pdf_actions)
        pdf_state = "normal" if row.pdf else "disabled"
        open_btn.configure(state=pdf_state)
        preview_btn.configure(state=pdf_state)
        self._place(pdf_actions, next_row, PDF_COL_INDEX)
        self._bind_overflow(drawing_label, lambda w=drawing_label: str(w.cget("text")), 12)
        self._bind_overflow(title_label, lambda w=title_label: str(w.cget("text")), 12)
        self._bind_overflow(pdf_label, lambda key=drawing.key: self._pdf_tip_text(key), 12)

        originals: dict[str, ttk.Label] = {}
        nexts: dict[str, NextWidget] = {}
        for offset, (field, _title, values, _width, kind) in enumerate(FIELD_KEYS):
            col = FIELD_COL_START + offset
            current = getattr(drawing, field) or "—"
            original = self._clip_label(current)
            self._place(original, now_row, col)
            originals[field] = original
            now_text = getattr(drawing, field) or ""
            base = self._eddi_values_for(drawing.key) if kind == "eddi" else self._field_values(field)
            list_values = with_now_option(base, now_text) if kind in {"option", "eddi"} else values
            box = self._next_box(
                next_row,
                col,
                values=list_values,
                initial=now_text,
                key=drawing.key,
                field=field,
                kind=kind,
                readonly=field in PICK_ONLY_FIELDS,
            )
            nexts[field] = box
            self._bind_overflow(original, lambda w=original: str(w.cget("text")), 8)
        h_bot, h_bot_f = self._hline(top + 3)
        next_cells = [
            cell
            for box in (drawing_id_next, title_next, status_next, *nexts.values())
            if (cell := self._next_cell(box)) is not None
        ]
        self._bind_row_select(
            [
                drawing_label,
                title_label,
                status_label,
                match_label,
                pdf_label,
                pdf_cell,
                pdf_actions,
                pack_mark,
                *originals.values(),
                *next_cells,
                h_top,
                h_top_f,
                h_bot,
                h_bot_f,
            ],
            drawing.key,
        )
        widgets: list[tk.Misc] = [
            h_top,
            h_top_f,
            pack_mark,
            drawing_label,
            title_label,
            status_label,
            match_label,
            pdf_cell,
            pdf_actions,
            *originals.values(),
            *next_cells,
            h_bot,
            h_bot_f,
        ]
        self._blocks[drawing.key] = _Block(
            key=drawing.key,
            group=group,
            include=pack,
            originals=originals,
            nexts=nexts,
            drawing_label=drawing_label,
            drawing_id_next=drawing_id_next,
            title_label=title_label,
            title_next=title_next,
            status_label=status_label,
            status_next=status_next,
            match_label=match_label,
            pdf_label=pdf_label,
            pdf_cell=pdf_cell,
            pack_mark=pack_mark,
            locate_btn=locate_btn,
            rename_btn=rename_btn,
            open_btn=open_btn,
            preview_btn=preview_btn,
            widgets=widgets,
            rules=(h_top, h_top_f, h_bot, h_bot_f),
            shop_folder=shop_folder,
            mounted=True,
            grid_top=top,
        )
        pack.trace_add("write", lambda *_args, drawing_key=drawing.key: self._on_pack_tick(drawing_key))
        self._watch_next(self._blocks[drawing.key])
        self._style_pdf_rename(self._blocks[drawing.key], row)
        if drawing.key == self._focus_key:
            self._focus_painted = drawing.key
            self._style_row_focus(self._blocks[drawing.key])

    def _make_shop_picker(self, parent: tk.Misc) -> ttk.Combobox:
        from doccon.shop_place import ROOT_FOLDER

        box = ttk.Combobox(parent, width=18, state="readonly", values=self._shop_choices)
        box.set(ROOT_FOLDER)
        self._quiet_dropdown(box)
        if self._shop_choices:
            box.pack(side="left", padx=(8, 0))
        box.bind("<<ComboboxSelected>>", lambda _event: self._notify_draft(), add="+")
        return box

    def set_shop_folders(self, choices: tuple[str, ...]) -> None:
        """Show a Root / subfolder pick on every row. Empty hides it (not a shop pack)."""
        from doccon.shop_place import ROOT_FOLDER

        self._shop_choices = tuple(choices)
        for block in self._blocks.values():
            box = block.shop_folder
            if box is None:
                continue
            if not self._shop_choices:
                if str(box.winfo_manager()) == "pack":
                    box.pack_forget()
                continue
            current = (box.get() or ROOT_FOLDER).strip() or ROOT_FOLDER
            box.configure(values=self._shop_choices)
            box.set(current if current in self._shop_choices else ROOT_FOLDER)
            if str(box.winfo_manager()) != "pack":
                box.pack(side="left", padx=(8, 0))

    def apply_shop_folder_picks(self, picks: dict[str, str]) -> None:
        from doccon.shop_place import ROOT_FOLDER

        for key, block in self._blocks.items():
            box = block.shop_folder
            if box is None or not self._shop_choices:
                continue
            label = (picks.get(key) or ROOT_FOLDER).strip() or ROOT_FOLDER
            box.set(label if label in self._shop_choices else ROOT_FOLDER)

    def shop_folders_open(self) -> bool:
        return bool(self._shop_choices)

    def shop_folder_picks(self) -> dict[str, str]:
        from doccon.shop_place import ROOT_FOLDER

        picks: dict[str, str] = {}
        if not self._shop_choices:
            return picks
        for block in self._blocks.values():
            box = block.shop_folder
            if box is None:
                continue
            label = (box.get() or "").strip()
            if label and label.casefold() != ROOT_FOLDER.casefold():
                picks[block.key] = label
        return picks

    def extras_painted(self) -> bool:
        return self._extras_painted

    def pack_extras(self) -> list[PackExtra]:
        items: list[PackExtra] = []
        for block in self._blocks.values():
            if not block.extra:
                continue
            items.append(
                PackExtra(
                    path=block.extra_path,
                    document_no=block.drawing_id_next.get().strip(),
                    rev=block.nexts["outgoing_rev"].get().strip(),
                    description=block.title_next.get().strip(),
                    status=block.status_next.get().strip(),
                    email_dropped=block.extra_dropped,
                    id=block.key,
                    packed=bool(block.include.get()),
                )
            )
        return items

    def set_pack_extras(self, items: list[PackExtra], *, statuses: tuple[str, ...]) -> None:
        """Paint Non Jira rows under the EDDI groups. Does not write Jira."""
        self._suspend_layout = True
        try:
            self._clear_extra_blocks()
            if items:
                self._paint_extra_blocks(items, statuses)
        finally:
            self._suspend_layout = False
        self._extras_painted = True
        self._refresh_filter()
        self._sync_scroll()

    def _clear_extra_blocks(self) -> None:
        for key, block in list(self._blocks.items()):
            if not block.extra:
                continue
            for widget in block.widgets:
                with contextlib.suppress(tk.TclError):
                    widget.destroy()
            del self._blocks[key]
        headers: list[tuple[str, ttk.Label]] = []
        frozen: list[ttk.Label] = []
        for pair, freeze in zip(self._group_headers, self._group_frozen, strict=True):
            group, label = pair
            if group == NON_JIRA_GROUP:
                with contextlib.suppress(tk.TclError):
                    label.destroy()
                    freeze.destroy()
                continue
            headers.append(pair)
            frozen.append(freeze)
        self._group_headers = headers
        self._group_frozen = frozen

    def _paint_extra_blocks(self, items: list[PackExtra], statuses: tuple[str, ...]) -> None:
        grid = self._jira_grid_end
        self._add_group_header(grid, NON_JIRA_GROUP)
        grid += 1
        for item in items:
            self._add_extra_block(grid, item, statuses)
            grid += 4

    def _add_extra_block(self, top: int, item: PackExtra, statuses: tuple[str, ...]) -> None:
        key = item.id or item.path
        h_top, h_top_f = self._hline(top)
        now_row = top + 1
        next_row = top + 2
        pack = tk.BooleanVar(value=item.packed)
        pack_mark = PackMark(self._freeze_inner, pack)
        pack_mark.grid(row=now_row, column=PACK_COL_INDEX, rowspan=2, padx=(4, SASH_PX), pady=4)
        drawing_label = self._clip_label(item.document_no, wrap_col=DRAWING_COL_INDEX, parent=self._freeze_inner)
        self._place(drawing_label, now_row, DRAWING_COL_INDEX)
        drawing_id_next = self._next_box(
            next_row,
            DRAWING_COL_INDEX,
            values=(),
            initial=item.document_no,
            key=key,
            field="drawing_id",
            kind="text",
            host=self._freeze_inner,
        )
        title_label = self._clip_label(item.description or "—", wrap_col=DESC_COL_INDEX)
        self._place(title_label, now_row, DESC_COL_INDEX)
        title_next = self._next_box(
            next_row,
            DESC_COL_INDEX,
            values=(),
            initial=item.description,
            key=key,
            field="title",
            kind="text",
        )
        status_label = self._clip_label(item.status or "—")
        self._place(status_label, now_row, STATUS_COL_INDEX)
        status_next = self._next_box(
            next_row,
            STATUS_COL_INDEX,
            values=statuses,
            initial=item.status if item.status in statuses else (statuses[0] if statuses else ""),
            key=key,
            field="status",
            readonly=True,
            kind="option",
        )
        match_label = self._clip_label(NON_JIRA_GROUP)
        self._place(match_label, now_row, MATCH_COL_INDEX)
        pdf_name = Path(item.path).name
        pdf_cell, pdf_label = self._pdf_address_cell_text(pdf_name)
        self._place(pdf_cell, now_row, PDF_COL_INDEX)
        pdf_label.bind("<Double-1>", lambda _event, extra_key=key: self._on_open_pdf(extra_key))
        pdf_actions = ttk.Frame(self._inner, style="Board.TFrame")
        locate_btn = ttk.Button(
            pdf_actions,
            text="Locate…",
            style="Locate.TButton",
            width=8,
            command=lambda extra_key=key: self._on_locate_pdf(extra_key),
        )
        rename_btn = ttk.Button(pdf_actions, text="Rename…", style="Locate.TButton", width=8)
        open_btn = ttk.Button(
            pdf_actions,
            text="Open",
            style="Locate.TButton",
            width=5,
            command=lambda extra_key=key: self._on_open_pdf(extra_key),
        )
        preview_btn = ttk.Button(
            pdf_actions,
            text="Preview",
            style="Locate.TButton",
            width=7,
            command=lambda extra_key=key: self._preview_pdf(extra_key),
        )
        locate_btn.pack(side="left", padx=(0, 4))
        open_btn.pack(side="left", padx=(0, 4))
        preview_btn.pack(side="left")
        shop_folder = self._make_shop_picker(pdf_actions)
        pdf_state = "normal" if Path(item.path).is_file() else "disabled"
        open_btn.configure(state=pdf_state)
        preview_btn.configure(state=pdf_state)
        self._place(pdf_actions, next_row, PDF_COL_INDEX)
        originals: dict[str, ttk.Label] = {}
        nexts: dict[str, NextWidget] = {}
        for offset, (field, _title, values, _width, kind) in enumerate(FIELD_KEYS):
            col = FIELD_COL_START + offset
            initial = item.rev if field == "outgoing_rev" else ""
            original = self._clip_label(initial or "—")
            self._place(original, now_row, col)
            originals[field] = original
            list_values = values if field == "outgoing_rev" else ()
            box = self._next_box(
                next_row,
                col,
                values=list_values,
                initial=initial,
                key=key,
                field=field,
                kind=kind,
                readonly=field in PICK_ONLY_FIELDS,
            )
            if field not in EXTRA_EDIT_FIELDS:
                with contextlib.suppress(tk.TclError):
                    box.configure(state="disabled")
            nexts[field] = box
        h_bot, h_bot_f = self._hline(top + 3)
        next_cells = [
            cell
            for box in (drawing_id_next, title_next, status_next, *nexts.values())
            if (cell := self._next_cell(box)) is not None
        ]
        widgets: list[tk.Misc] = [
            h_top,
            h_top_f,
            pack_mark,
            drawing_label,
            title_label,
            status_label,
            match_label,
            pdf_cell,
            pdf_actions,
            *originals.values(),
            *next_cells,
            h_bot,
            h_bot_f,
        ]
        self._blocks[key] = _Block(
            key=key,
            group=NON_JIRA_GROUP,
            include=pack,
            originals=originals,
            nexts=nexts,
            drawing_label=drawing_label,
            drawing_id_next=drawing_id_next,
            title_label=title_label,
            title_next=title_next,
            status_label=status_label,
            status_next=status_next,
            match_label=match_label,
            pdf_label=pdf_label,
            pdf_cell=pdf_cell,
            pack_mark=pack_mark,
            locate_btn=locate_btn,
            rename_btn=rename_btn,
            open_btn=open_btn,
            preview_btn=preview_btn,
            widgets=widgets,
            rules=(h_top, h_top_f, h_bot, h_bot_f),
            extra=True,
            extra_path=item.path,
            extra_dropped=item.email_dropped,
            shop_folder=shop_folder,
        )
        pack.trace_add("write", lambda *_args, drawing_key=key: self._on_pack_tick(drawing_key))
        self._bind_row_select(widgets, key)
        self._watch_next(self._blocks[key])

    def _pdf_address_cell_text(self, text: str) -> tuple[tk.Frame, ttk.Label]:
        cell = tk.Frame(self._inner, bg=SURFACE, highlightthickness=0, bd=0)
        label = ttk.Label(cell, text=text, style="Board.TLabel", anchor="w")
        label.pack(fill="both", expand=True, padx=4, pady=2)
        return cell, label

    def set_pack(self, checked: bool) -> None:
        filtering = bool(self._filter_needle.strip())
        for block in self._blocks.values():
            if filtering and not self._block_matches(block):
                continue
            block.include.set(checked)

    def _list_value_allowed(self, block: _Block, field: str, value: str) -> bool:
        if field not in PICK_ONLY_FIELDS:
            return True
        box = block.nexts.get(field)
        if box is None:
            return False
        try:
            options = [str(item) for item in box.cget("values")]
        except tk.TclError:
            options = [str(item) for item in _values_for_field(field)]
        folded = {opt.strip().casefold() for opt in options}
        return value.strip().casefold() in folded

    def _apply_next_to_block(
        self, block: _Block, *, status: str = "", fields: dict[str, str] | None = None
    ) -> None:
        """Set Next on one row (same dirty/yellow path as Apply to Pack). Does not write Jira.

        Does not move the focused row: a batch stamp, a cover-date pack tick, and a Load
        restore are not the operator pointing at a drawing, and `explicit_focus_key` is
        what a paste lands on.
        """
        if not block.mounted:
            self._mount_block(block)
            fresh = self._blocks.get(block.key)
            if fresh is None:
                return
            block = fresh
        status_value = (status or "").strip()
        if status_value:
            block.status_next.set(status_value)
        for field, value in (fields or {}).items():
            if not self._list_value_allowed(block, field, value):
                continue
            box = block.nexts.get(field)
            if box is not None:
                box.set(value)
        self._refresh_next_marks(block)

    def stamp_outgoing_rev(self, key: str, rev: str) -> bool:
        """Set Next Outgoing Rev from a paired PDF filename. Does not write Jira or move focus."""
        value = (rev or "").strip()
        if not value:
            return False
        block = self._blocks.get((key or "").strip())
        if block is None:
            return False
        self._apply_next_to_block(block, fields={"outgoing_rev": value})
        return True

    def apply_next_to_pack(self, *, status: str = "", fields: dict[str, str] | None = None) -> int:
        updates = {key: value.strip() for key, value in (fields or {}).items() if value.strip()}
        status_value = (status or "").strip()
        if not status_value and not updates:
            return 0
        count = 0
        for block in self._blocks.values():
            if not block.include.get() or block.extra:
                continue
            self._apply_next_to_block(block, status=status_value, fields=updates)
            count += 1
        if no_return_status(status_value):
            self.stamp_packed_date("return_request_date", "N/A")
            self._signal_no_return()
        return count

    def stamp_date_on_keys(self, field: str, date: str, keys: tuple[str, ...]) -> int:
        """Set a Next date field on those packed rows. Blank does not clear. Does not write Jira."""
        value = (date or "").strip()
        if not value:
            return 0
        count = 0
        for key in keys:
            block = self._blocks.get(key)
            if block is None or not block.include.get():
                continue
            self._apply_next_to_block(block, fields={field: value})
            count += 1
        return count

    def stamp_packed_date(self, field: str, date: str) -> int:
        """Set a Next date field on every packed row. Blank does not clear. Does not write Jira."""
        value = (date or "").strip()
        if not value:
            return 0
        return self.apply_next_to_pack(fields={field: value})

    def stamp_cover_dates_on_keys(self, keys: tuple[str, ...]) -> int:
        """Copy each cover date getter onto those packed rows. Blank getters skip that field."""
        stamped = 0
        for field in self._cover_stamps:
            stamped += self.stamp_date_on_keys(field, self._cover_field_date(field), keys)
        return stamped

    def stamp_packed_cover_dates(self) -> int:
        """Re-stamp every cover date onto currently packed rows. Blank does not clear."""
        packed = tuple(key for key, block in self._blocks.items() if block.include.get())
        return self.stamp_cover_dates_on_keys(packed)

    def restore_packed_next_field(self, field: str) -> int:
        """Copy Now onto this Next field for packed rows only. Does not write Jira."""
        count = 0
        for key, block in self._blocks.items():
            if not block.include.get():
                continue
            if self.restore_next_field(key, field):
                count += 1
        return count

    def apply_cover_date_change(self, field: str, date: str) -> int:
        """Stamp a calendar day onto packed Next, or restore Now when cover is blank/N/A.

        Pack-tick stamping still skips blank (does not wipe). This path is the cover box
        changing: N/A is a right-click-undo of that date field on packed rows only.
        Does not write Jira.
        """
        value = (date or "").strip()
        if not value or value.casefold() == "n/a":
            return self.restore_packed_next_field(field)
        return self.stamp_packed_date(field, value)

    def stamp_return_request_on_keys(self, date: str, keys: tuple[str, ...]) -> int:
        """Set Next Return Request Date on those packed rows. Blank does not clear. Does not write Jira."""
        return self.stamp_date_on_keys("return_request_date", date, keys)

    def stamp_packed_return_request(self, date: str) -> int:
        """Set Next Return Request Date on every packed row. Blank does not clear. Does not write Jira."""
        return self.stamp_packed_date("return_request_date", date)

    def stamp_packed_no_return(self) -> int:
        """Mark packed Next Return Request Date as N/A. Does not write Jira."""
        count = self.stamp_packed_date("return_request_date", "N/A")
        self._signal_no_return()
        return count

    def _signal_no_return(self) -> None:
        hook = self._on_no_return
        if hook is not None:
            hook()

    def _on_row_status_picked(self, block: _Block) -> None:
        """Picking IFI or IFC on one row clears that row's return date. Does not write Jira."""
        if not no_return_status(block.status_next.get()):
            return
        box = block.nexts.get("return_request_date")
        if box is not None:
            box.set("N/A")
        self._refresh_next_marks(block)

    def stamp_packed_submission_date(self, date: str) -> int:
        """Set Next Submission Date on every packed row. Blank does not clear. Does not write Jira."""
        return self.stamp_packed_date("submission_date", date)

    def bump_packed_revs(self) -> int:
        """Set Next Outgoing Rev to the step after each packed row's Now. Does not write Jira."""
        count = 0
        for key, block in self._blocks.items():
            if not block.include.get() or block.extra:
                continue
            row = self._matches.get(key)
            box = block.nexts.get("outgoing_rev")
            if row is None or box is None:
                continue
            box.set(next_outgoing_rev(row.drawing.outgoing_rev))
            self._refresh_next_marks(block)
            count += 1
        return count

    def set_packed_rev(self, rev: str) -> int:
        """Stamp Next Outgoing Rev on every packed row. 0 is allowed from any letter. Does not write Jira."""
        value = (rev or "").strip()
        if not value:
            return 0
        return self.apply_next_to_pack(fields={"outgoing_rev": value})

    def pack_status(self) -> str:
        try:
            return (self._pack_status.get() or "").strip()
        except tk.TclError:
            return ""

    def set_pack_status(self, status: str, *, stamp: bool = True) -> int:
        """Set filter-row Status. stamp writes packed Next, or restores Now when blank."""
        value = (status or "").strip()
        self._pack_status_loading = True
        try:
            self._pack_status.set(value)
        finally:
            if stamp:
                self._pack_status_loading = False
            else:
                try:
                    self.after_idle(self._clear_pack_status_loading)
                except tk.TclError:
                    self._pack_status_loading = False
        if not stamp:
            return 0
        return self.apply_pack_status_change(value)

    def _clear_pack_status_loading(self) -> None:
        self._pack_status_loading = False

    def set_packed_status(self, status: str) -> int:
        """Stamp Next Status on every packed row. Blank does not clear. Does not write Jira."""
        value = (status or "").strip()
        if not value:
            return 0
        return self.apply_next_to_pack(status=value)

    def stamp_status_on_keys(self, status: str, keys: tuple[str, ...]) -> int:
        """Set Next Status on those packed rows. Blank does not clear. Does not write Jira."""
        value = (status or "").strip()
        if not value:
            return 0
        count = 0
        for key in keys:
            block = self._blocks.get(key)
            if block is None or not block.include.get():
                continue
            self._apply_next_to_block(block, status=value)
            count += 1
        if no_return_status(value):
            self.stamp_date_on_keys("return_request_date", "N/A", keys)
        return count

    def apply_pack_status_change(self, status: str) -> int:
        """Stamp packed Next Status, or restore Now when Set packed to is blank.

        Pack-tick stamping still skips blank (does not wipe). This path is the filter
        box changing: blank is a right-click-undo of Status on packed rows only.
        Does not write Jira.
        """
        value = (status or "").strip()
        if not value:
            return self.restore_packed_next_field("status")
        return self.set_packed_status(value)

    def _on_pack_status_change(self, _event: object | None = None) -> None:
        if self._pack_status_loading:
            return
        value = self.pack_status()
        count = self.apply_pack_status_change(value)
        if value and count:
            note = f"Set Status to {value} on {count} packed drawing(s)."
            if no_return_status(value):
                note += " Return Request Date is N/A."
            self._batch_note.configure(text=f"{note} Jira was not written.")
            return
        if value:
            self._batch_note.configure(text="Tick Pack — Status will stamp onto packed drawings.")
            return
        if count:
            self._batch_note.configure(text="Packed Status restored to Now.")

    def set_transmittal_kind(self, kind: str) -> None:
        """Point the filter dropdown at Client, Shop, or Field. Does not stamp or restore Next."""
        spec = PACK_PURPOSE.get((kind or "").strip(), PACK_PURPOSE[CLIENT])
        field, title, values = spec
        if field == self._pack_purpose_field and kind == self._pack_purpose_kind:
            return
        self._pack_purpose_kind = kind if kind in PACK_PURPOSE else CLIENT
        self._pack_purpose_field = field
        self._pack_purpose_label.configure(text=title)
        self._pack_purpose_loading = True
        try:
            self._pack_purpose.configure(values=values)
            self._pack_purpose.set("")
        finally:
            self._pack_purpose_loading = False

    def pack_purpose_field(self) -> str:
        return self._pack_purpose_field

    def pack_purpose(self) -> str:
        try:
            return (self._pack_purpose.get() or "").strip()
        except tk.TclError:
            return ""

    def set_pack_purpose(self, purpose: str, *, stamp: bool = True) -> int:
        """Set the filter-row Submitted to Client For. stamp writes packed Next."""
        value = (purpose or "").strip()
        self._pack_purpose_loading = True
        try:
            self._pack_purpose.set(value)
        finally:
            if stamp:
                self._pack_purpose_loading = False
            else:
                try:
                    self.after_idle(self._clear_pack_purpose_loading)
                except tk.TclError:
                    self._pack_purpose_loading = False
        if not stamp:
            return 0
        return self.apply_pack_purpose_change(value)

    def _clear_pack_purpose_loading(self) -> None:
        self._pack_purpose_loading = False

    def _pack_purpose_title(self) -> str:
        try:
            return str(self._pack_purpose_label.cget("text") or "Submitted to Client For")
        except tk.TclError:
            return "Submitted to Client For"

    def stamp_purpose_on_keys(
        self, purpose: str, keys: tuple[str, ...], *, field: str = ""
    ) -> int:
        """Set that Next list on those packed rows. Blank does not clear."""
        value = (purpose or "").strip()
        target = (field or self._pack_purpose_field or "purpose").strip()
        if not value:
            return 0
        count = 0
        for key in keys:
            block = self._blocks.get(key)
            if block is None or not block.include.get() or block.extra:
                continue
            self._apply_next_to_block(block, fields={target: value})
            count += 1
        return count

    def apply_pack_purpose_change(self, purpose: str) -> int:
        """Stamp packed Next for the filter list, or restore Now when the pick is blank."""
        value = (purpose or "").strip()
        target = self._pack_purpose_field or "purpose"
        if not value:
            count = 0
            for key, block in self._blocks.items():
                if not block.include.get() or block.extra:
                    continue
                if self.restore_next_field(key, target):
                    count += 1
            return count
        return self.apply_next_to_pack(fields={target: value})

    def _on_pack_purpose_change(self, _event: object | None = None) -> None:
        if self._pack_purpose_loading:
            return
        value = self.pack_purpose()
        title = self._pack_purpose_title()
        count = self.apply_pack_purpose_change(value)
        if value and count:
            self._batch_note.configure(
                text=f"Set {title} to {value} on {count} packed drawing(s). Jira was not written."
            )
            return
        if value:
            self._batch_note.configure(
                text=f"Tick Pack — {title} will stamp onto packed drawings."
            )
            return
        if count:
            self._batch_note.configure(text=f"Packed {title} restored to Now.")

    def _next_widget(self, block: _Block, field: str) -> NextWidget | None:
        if field == "drawing_id":
            return block.drawing_id_next
        if field == "title":
            return block.title_next
        if field == "status":
            return block.status_next
        return block.nexts.get(field)

    def _restore_target(self, widget: object) -> tuple[str, str] | None:
        current: object | None = widget
        for _ in range(8):
            if current is None:
                return None
            key = getattr(current, "_doccon_key", None)
            field = getattr(current, "_doccon_field", None)
            if isinstance(key, str) and key and isinstance(field, str) and field:
                return key, field
            current = getattr(current, "master", None)
        return None

    def restore_next_field(self, key: str, field: str) -> bool:
        """Copy this field's Now value onto Next. Does not write Jira."""
        block = self._blocks.get(key)
        row = self._matches.get(key)
        if block is None or row is None:
            return False
        box = self._next_widget(block, field)
        if box is None:
            return False
        now = _option_now(self._field_values(field), _now_value(row.drawing, field))
        try:
            current = box.get()
        except tk.TclError:
            return False
        if current != now:
            box.set(now)
        self._refresh_next_marks(block)
        return True

    def _on_restore_next(self, event: tk.Event) -> str:
        target = self._restore_target(getattr(event, "widget", None))
        if target is None:
            return "break"
        key, field = target
        self._set_focus(key)
        self.restore_next_field(key, field)
        return "break"

    def revert_next(self) -> int:
        """Copy Now (Jira) back onto every Next field on every listed row. Does not write Jira.

        Pack ticks stay. Cover Date issued / Expected return are reset by the console hook.
        """
        count = 0
        for key, row in list(self._matches.items()):
            if key not in self._blocks:
                continue
            self.apply_row(row)
            count += 1
        self._batch_status.set("")
        self.set_pack_status("", stamp=False)
        self.set_pack_purpose("", stamp=False)
        for box in self._batch_fields.values():
            box.set("")
        return count

    def _run_cancel_next_hook(self) -> None:
        hook = self._on_cancel_next
        if hook is not None:
            hook()

    def _cancel_next(self) -> None:
        pending = len(self.pending_rows())
        if pending == 0:
            self.revert_next()
            self._run_cancel_next_hook()
            self._batch_note.configure(text="Next already matches Now.")
            return
        if not messagebox.askyesno(
            "Cancel Next?",
            f"Throw away Next edits on {pending} drawing(s) and put Now back on every field?\n"
            "Jira is not written. Pack ticks stay. Date issued goes back to today. "
            "Expected return goes back to N/A.",
            parent=self.winfo_toplevel(),
        ):
            return
        self.revert_next()
        self._run_cancel_next_hook()
        self._batch_note.configure(text=f"Cancelled Next on {pending} drawing(s). Jira was not written.")

    def _toggle_batch(self) -> None:
        self._set_batch_open(not self._batch_open)

    def _set_batch_open(self, shown: bool) -> None:
        self._batch_open = bool(shown)
        if self._batch_open:
            if not self._batch_frame.winfo_manager():
                self._batch_frame.pack(fill="x", padx=8, pady=(0, 4), after=self._find_bar)
            self._batch_toggle.configure(text="Hide batch")
        else:
            self._batch_frame.pack_forget()
            self._batch_toggle.configure(text="Batch Next…")

    def _apply_batch(self) -> None:
        fields = {field: box.get() for field, box in self._batch_fields.items()}
        count = self.apply_next_to_pack(status=self._batch_status.get(), fields=fields)
        if count:
            self._batch_note.configure(text=f"Applied to {count} packed drawing(s).")
        else:
            self._batch_note.configure(text="Tick Pack and pick at least one Next value.")

    def next_edits(self) -> dict[str, dict[str, str]]:
        """Dirty Next fields keyed by Jira issue key. Empty when Next matches Now."""
        edits: dict[str, dict[str, str]] = {}
        for key, block in self._blocks.items():
            if not block.mounted:
                continue
            row = self._matches.get(key)
            if row is None:
                continue
            drawing = row.drawing
            dirty: dict[str, str] = {}
            try:
                ident = block.drawing_id_next.get().strip()
                title = block.title_next.get().strip()
                status = block.status_next.get().strip()
            except tk.TclError:
                continue
            if ident != (drawing.drawing_id or "").strip():
                dirty["drawing_id"] = ident
            if title != (drawing.title or "").strip():
                dirty["title"] = title
            if status and status != (drawing.status or "").strip():
                dirty["status"] = status
            for field, _title, _values, _width, _kind in FIELD_KEYS:
                try:
                    nxt = block.nexts[field].get().strip()
                except tk.TclError:
                    continue
                if nxt != (getattr(drawing, field) or "").strip():
                    dirty[field] = nxt
            if dirty:
                edits[key] = dirty
        return edits

    def apply_next_edits(self, edits: dict[str, dict[str, str]] | None) -> int:
        """Reapply saved Next on listed rows. Skip keys no longer on the job. Does not write Jira."""
        if not edits:
            return 0
        by_drawing: dict[str, str] = {}
        for key, row in self._matches.items():
            ident = (row.drawing.drawing_id or "").strip()
            if ident and ident not in by_drawing:
                by_drawing[ident] = key
        applied = 0
        for ident, fields in edits.items():
            if not isinstance(fields, dict):
                continue
            key = ident if ident in self._blocks else by_drawing.get(str(ident).strip(), "")
            block = self._blocks.get(key)
            if block is None:
                continue
            status = str(fields.get("status") or "")
            title = fields.get("title")
            ident = fields.get("drawing_id")
            payload = {
                name: str(value)
                for name, value in fields.items()
                if name not in {"status", "title", "drawing_id"}
            }
            if ident is not None:
                block.drawing_id_next.set(str(ident))
            if title is not None:
                block.title_next.set(str(title))
            self._apply_next_to_block(block, status=status, fields=payload)
            applied += 1
        return applied

    def current_rows(self) -> list[MatchedRow]:
        """Every listed row with Next values applied. Pack ticks do not matter."""
        rows: list[MatchedRow] = []
        for key, block in self._blocks.items():
            row = self._matches.get(key)
            if row is not None:
                rows.append(self._with_next(row, block))
        return rows

    def selected_keys(self) -> tuple[str, ...]:
        return tuple(key for key, block in self._blocks.items() if block.include.get())

    def selected_rows(self) -> list[MatchedRow]:
        rows: list[MatchedRow] = []
        for key, block in self._blocks.items():
            if not block.include.get():
                continue
            row = self._matches.get(key)
            if row is not None:
                rows.append(self._with_next(row, block))
        return rows

    def _with_next(self, row: MatchedRow, block: _Block) -> MatchedRow:
        updates = {field: block.nexts[field].get().strip() for field, _title, _values, _width, _kind in FIELD_KEYS}
        updates["due_date"] = due_date_from_return_request(
            row.drawing.due_date,
            row.drawing.return_request_date,
            updates.get("return_request_date", ""),
        )
        status = block.status_next.get().strip() or row.drawing.status
        ident = block.drawing_id_next.get().strip()
        title = block.title_next.get().strip()
        # JIRA ID and Description are two halves of one Jira field, so compose once here.
        summary = summary_from_parts(ident, title)
        return replace(
            row,
            drawing=replace(
                row.drawing,
                status=status,
                drawing_id=ident,
                title=title,
                summary=summary,
                **updates,
            ),
        )

    def _set_focus(self, key: str) -> None:
        token = (key or "").strip()
        if token == self._focus_key:
            return
        self._focus_key = token
        # Only the row that lost the band and the row that gained it repaint. Never the list.
        for touched in (self._focus_painted, token):
            block = self._blocks.get(touched)
            if block is not None:
                self._style_row_focus(block)
        self._focus_painted = token

    def _style_row_focus(self, block: _Block) -> None:
        """Band the focused drawing so the operator sees where Ctrl+V will land.

        The Now labels carry the band and the 1px rules bracket the block, both in the
        frozen pane (Pack / JIRA ID) and the scrolling pane, so it survives a sideways
        scroll with no sync loop. Next cells keep their own white / PENDING amber: the
        band must never be mistaken for a dirty Next, or make one harder to read.
        """
        on = block.key == self._focus_key
        if on == block.focused:
            return
        block.focused = on
        want = "Focus.TLabel" if on else "Board.TLabel"
        for label in (block.drawing_label, block.title_label, block.status_label, *block.originals.values()):
            with contextlib.suppress(tk.TclError):
                if str(label.cget("style")) != want:
                    label.configure(style=want)
        row = self._matches.get(block.key)
        if row is not None:
            with contextlib.suppress(tk.TclError):
                block.match_label.configure(style=match_style(row.confidence, focused=on))
            self._style_pdf_address(block, row)
        rule = SELECT_RULE if on else BORDER
        for line in block.rules:
            with contextlib.suppress(tk.TclError):
                if str(line.cget("background")) != rule:
                    line.configure(background=rule)

    def focus_key(self, key: str) -> None:
        self._set_focus(key)

    def explicit_focus_key(self) -> str:
        """The row the operator actually clicked. A Pack tick is not a cursor.

        `focused_row` falls back to the first packed row, which is fine for a
        positional drop but must never decide where an explicit paste lands.
        """
        key = (self._focus_key or "").strip()
        return key if key and key in self._matches else ""

    def focused_row(self) -> MatchedRow | None:
        if self._focus_key:
            row = self._matches.get(self._focus_key)
            if row is not None:
                return row
        selected = self.selected_rows()
        return selected[0] if selected else None

    def row_key_at(self, root_x: int, root_y: int) -> str | None:
        """Jira issue key for the drawing under a screen point, or None (board drop)."""
        try:
            widget = self.winfo_containing(int(root_x), int(root_y))
        except (tk.TclError, TypeError, ValueError):
            widget = None
        owners: dict[int, str] = {}
        for key, block in self._blocks.items():
            items = [
                *block.widgets,
                block.locate_btn,
                block.rename_btn,
                block.open_btn,
                block.preview_btn,
                block.pack_mark,
                block.drawing_id_next,
                block.title_next,
                block.status_next,
                *block.nexts.values(),
            ]
            for item in items:
                if item is None:
                    continue
                owners[id(item)] = key
        current: object | None = widget
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            key = owners.get(id(current))
            if key:
                return key
            if current is self:
                break
            current = getattr(current, "master", None)
        return row_key_for_y(self.row_bands(), int(root_y))

    def _pdf_tip_text(self, key: str) -> str:
        row = self._matches.get(key)
        return pdf_address_tip(row) if row is not None else ""

    def _pdf_address_cell(self, row: MatchedRow) -> tuple[tk.Frame, ttk.Label]:
        dropped = pdf_is_email_dropped(row)
        fill = PENDING_BG if dropped else BG
        cell = tk.Frame(self._inner, bg=fill, highlightthickness=0, bd=0)
        label = ttk.Label(
            cell,
            text=pdf_address_text(row),
            style="Pending.TLabel" if dropped else "Board.TLabel",
            anchor="w",
            width=1,
        )
        label.pack(fill="both", expand=True, padx=2, pady=1)
        return cell, label

    def _style_pdf_address(self, block: _Block, row: MatchedRow) -> None:
        # email dropped outranks the focus band: the bypass must stay unmistakably amber.
        if pdf_is_email_dropped(row):
            fill, want = PENDING_BG, "Pending.TLabel"
        elif block.focused:
            fill, want = SELECT_BG, "Focus.TLabel"
        else:
            fill, want = BG, "Board.TLabel"
        if str(block.pdf_cell.cget("bg")) != fill:
            block.pdf_cell.configure(bg=fill)
        block.pdf_label.configure(text=pdf_address_text(row), style=want)

    def _style_pdf_open_preview(self, block: _Block, row: MatchedRow) -> None:
        state = "normal" if row.pdf else "disabled"
        block.open_btn.configure(state=state)
        block.preview_btn.configure(state=state)

    def _preview_pdf(self, key: str) -> None:
        if self._on_preview_pdf is None:
            return
        self._on_preview_pdf(key)

    def set_next_description(self, key: str, text: str) -> bool:
        """Write Next Description (yellow until Confirm). Empty or unusable text is ignored."""
        from doccon.pdf_grab import clean_grabbed_text, grabbed_text_is_usable

        block = self._blocks.get((key or "").strip())
        if block is None:
            return False
        cleaned = clean_grabbed_text(text)
        if not grabbed_text_is_usable(cleaned):
            return False
        block.title_next.set(cleaned)
        self._refresh_next_marks(block)
        return True

    def _style_pdf_rename(self, block: _Block, row: MatchedRow) -> None:
        """Rename… only for an email-dropped DocCon/dropped copy. Locate’d Dropbox files never get it."""
        path = None if row.pdf is None else row.pdf.path
        show = pdf_is_email_dropped(row) and path is not None and is_dropped_pdf_path(path)
        if show:
            if str(block.rename_btn.winfo_manager()) != "pack":
                block.rename_btn.pack(side="left", padx=(0, 4), after=block.locate_btn)
            block.rename_btn.configure(state="normal")
            return
        if str(block.rename_btn.winfo_manager()) == "pack":
            block.rename_btn.pack_forget()

    def apply_pdf(self, row: MatchedRow) -> None:
        """Update the paired PDF without restoring Next from Now."""
        drawing = row.drawing
        self._matches[drawing.key] = row
        block = self._blocks.get(drawing.key)
        if block is None:
            return
        if not block.mounted:
            block.match_label.configure(text=row.confidence, style=match_style(row.confidence))
            block.pdf_label.configure(text=pdf_address_text(row))
            return
        block.match_label.configure(
            text=row.confidence, style=match_style(row.confidence, focused=block.focused)
        )
        self._style_pdf_address(block, row)
        self._style_pdf_open_preview(block, row)
        self._style_pdf_rename(block, row)

    def suggested_dropped_name(self, key: str) -> str:
        """`{JIRA ID} REV {Outgoing Rev}.pdf` from Next (else Now)."""
        block = self._blocks.get((key or "").strip())
        row = self._matches.get((key or "").strip())
        drawing_id = ""
        rev = ""
        if block is not None:
            drawing_id = str(block.drawing_id_next.get() or "").strip()
            box = block.nexts.get("outgoing_rev")
            if box is not None:
                rev = str(box.get() or "").strip()
        if not drawing_id and row is not None:
            drawing_id = (row.drawing.drawing_id or "").strip()
        if not rev and row is not None:
            rev = (row.drawing.outgoing_rev or "").strip()
        return dropped_pdf_filename(drawing_id, rev)

    def _rename_pdf(self, key: str) -> None:
        if self._on_rename_pdf is None:
            return
        self._on_rename_pdf(key)

    def apply_row(self, row: MatchedRow) -> None:
        drawing = row.drawing
        self._matches[drawing.key] = row
        block = self._blocks.get(drawing.key)
        if block is None:
            return
        if not block.mounted:
            block.drawing_label.configure(text=drawing.drawing_id or drawing.key)
            block.drawing_id_next.set(drawing.drawing_id or "")
            block.title_label.configure(text=drawing.title or "—")
            block.title_next.set(drawing.title or "")
            block.status_label.configure(text=drawing.status)
            block.status_next.set(drawing.status)
            block.match_label.configure(text=row.confidence, style=match_style(row.confidence))
            block.pdf_label.configure(text=pdf_address_text(row))
            for field, _title, _values, _width, _kind in FIELD_KEYS:
                value = getattr(drawing, field) or ""
                if field in block.originals:
                    block.originals[field].configure(text=value or "—")
                held = block.nexts.get(field)
                if held is not None:
                    held.set(value)
            return
        block.drawing_label.configure(text=drawing.drawing_id or drawing.key)
        block.drawing_id_next.set(drawing.drawing_id or "")
        block.title_label.configure(text=drawing.title or "—")
        block.title_next.set(drawing.title or "")
        block.status_label.configure(text=drawing.status)
        block.status_next.set(drawing.status)
        block.match_label.configure(text=row.confidence, style=match_style(row.confidence, focused=block.focused))
        self._style_pdf_address(block, row)
        self._style_pdf_open_preview(block, row)
        self._style_pdf_rename(block, row)
        for field, _title, _values, _width, _kind in FIELD_KEYS:
            value = getattr(drawing, field) or ""
            block.originals[field].configure(text=value or "—")
            block.nexts[field].set(value)
        self._refresh_next_marks(block)

    def _is_board_next(self, widget: object) -> bool:
        return isinstance(widget, (NextEntry, ttk.Combobox)) and bool(getattr(widget, "_doccon_field", None))

    def _board_next_from(self, widget: object) -> NextWidget | None:
        current: object | None = widget
        for _ in range(8):
            if current is None:
                return None
            if self._is_board_next(current):
                return current  # type: ignore[return-value]
            current = getattr(current, "master", None)
        return None

    def _calendar_is_open(self) -> bool:
        popup = CalendarPopup._open
        if popup is None:
            return False
        try:
            return bool(popup.winfo_exists())
        except tk.TclError:
            return False

    def _widget_in_calendar(self, widget: object) -> bool:
        popup = CalendarPopup._open
        if popup is None or widget is None:
            return False
        current: object | None = widget
        for _ in range(12):
            if current is None:
                return False
            if current is popup:
                return True
            current = getattr(current, "master", None)
        return False

    def _combobox_popdown(self, box: ttk.Combobox) -> str:
        try:
            return str(box.tk.call("ttk::combobox::PopdownWindow", str(box)))
        except tk.TclError:
            return ""

    def _combobox_list_open(self, box: object) -> bool:
        if not isinstance(box, ttk.Combobox):
            return False
        popdown = self._combobox_popdown(box)
        if not popdown:
            return False
        try:
            return bool(int(box.tk.eval(f"winfo ismapped {popdown}")))
        except (tk.TclError, ValueError):
            return False

    def _widget_in_popdown(self, widget: object, box: object) -> bool:
        if widget is None:
            return False
        try:
            path = str(widget)
        except tk.TclError:
            return False
        if isinstance(box, ttk.Combobox):
            popdown = self._combobox_popdown(box)
            if popdown and (path == popdown or path.startswith(f"{popdown}.")):
                return True
        return "popdown" in path.casefold()

    def _click_stays_in_editor(self, box: object, widget: object) -> bool:
        if widget is None or box is None:
            return False
        if self._widget_in_calendar(widget) or self._widget_in_popdown(widget, box):
            return True
        cell = self._next_cell(box) if isinstance(box, tk.Misc) else None
        current: object | None = widget
        for _ in range(10):
            if current is None:
                break
            if current is box or current is cell:
                return True
            current = getattr(current, "master", None)
        return False

    def _close_combobox_list(self, box: object) -> None:
        if not isinstance(box, ttk.Combobox):
            return
        with contextlib.suppress(tk.TclError):
            box.tk.call("ttk::combobox::Unpost", box)

    def _commit_next_box(self, box: object) -> None:
        key = getattr(box, "_doccon_key", None)
        if isinstance(key, str) and key:
            self._refresh_next_marks_key(key)

    def _focus_board(self) -> None:
        for host in (self._canvas, self):
            try:
                host.focus_set()
                return
            except tk.TclError:
                continue

    def leave_next_editor(self, box: tk.Misc | None = None) -> None:
        """Commit the Next value and take the caret out of the box. Does not write Jira.

        Does not move to another cell. Escape restores Now first, then calls this.
        """
        target = box if box is not None else self._active_next
        self._close_combobox_list(target)
        if target is not None:
            self._commit_next_box(target)
            self.lock_next_editor(target)
        self._active_next = None
        self._focus_board()

    def _restore_and_leave(self, box: object) -> None:
        target = self._restore_target(box)
        if target is not None:
            self.restore_next_field(*target)
        self.leave_next_editor(box if isinstance(box, tk.Misc) else None)

    def _on_next_focus_in(self, event: tk.Event) -> None:
        box = self._board_next_from(getattr(event, "widget", None))
        if box is None:
            return
        self._unlock_for_edit(box)
        self._active_next = box
        key = getattr(box, "_doccon_key", None)
        if isinstance(key, str) and key:
            self._set_focus(key)

    def _on_next_focus_out(self, event: tk.Event) -> None:
        box = self._board_next_from(getattr(event, "widget", None)) or getattr(event, "widget", None)

        def later(watched: object = box) -> None:
            if isinstance(watched, ttk.Combobox) and self._combobox_list_open(watched):
                return
            if self._calendar_is_open():
                return
            try:
                focused = self.focus_get()
            except tk.TclError:
                focused = None
            if self._click_stays_in_editor(watched, focused) or focused is watched:
                return
            if self._board_next_from(focused) is watched:
                return
            if self._active_next is watched:
                self._active_next = None
            key = getattr(watched, "_doccon_key", None)
            if isinstance(key, str) and key:
                self._refresh_next_marks_key(key)

        self.after_idle(later)

    def _on_next_return(self, event: tk.Event) -> str | None:
        box = getattr(event, "widget", None)
        if not self._is_board_next(box):
            return None
        if isinstance(box, ttk.Combobox) and self._combobox_list_open(box):
            self.after_idle(lambda watched=box: self.leave_next_editor(watched))
            return None
        self.leave_next_editor(box)
        return "break"

    def _on_next_escape(self, event: tk.Event) -> str:
        self._restore_and_leave(getattr(event, "widget", None))
        return "break"

    def _event_is_for_active_next(self, widget: object) -> bool:
        box = self._active_next
        if box is None:
            return False
        if widget is None:
            return True
        if widget is self._filter:
            return False
        return self._click_stays_in_editor(box, widget) or widget is box

    def _on_global_press(self, event: tk.Event) -> None:
        box = self._active_next
        if box is None:
            return
        widget = getattr(event, "widget", None)
        if self._calendar_is_open() and self._widget_in_calendar(widget):
            return
        if self._click_stays_in_editor(box, widget):
            return
        if self._is_board_next(widget):
            return
        self.leave_next_editor(box)

    def _on_global_return(self, event: tk.Event) -> str | None:
        if self._calendar_is_open():
            return None
        box = self._active_next
        widget = getattr(event, "widget", None)
        if box is None or not self._event_is_for_active_next(widget):
            return None
        if isinstance(box, ttk.Combobox) and self._combobox_list_open(box):
            self.after_idle(lambda watched=box: self.leave_next_editor(watched))
            return None
        self.leave_next_editor(box)
        return "break"

    def _on_global_escape(self, event: tk.Event) -> str | None:
        if self._calendar_is_open():
            return None
        box = self._active_next
        widget = getattr(event, "widget", None)
        if box is None or not self._event_is_for_active_next(widget):
            return None
        self._restore_and_leave(box)
        return "break"

    def _watch_next(self, block: _Block) -> None:
        def ping(_event: object = None) -> None:
            self.after_idle(lambda watched=block: self._refresh_next_marks(watched))

        for box in (block.drawing_id_next, block.title_next, block.status_next, *block.nexts.values()):
            var = tk.StringVar(value=box.get())
            box.configure(textvariable=var)
            box._doccon_var = var
            var.trace_add("write", lambda *_args, watched=block: self._refresh_next_marks(watched))
            box.bind("<KeyRelease>", ping, add="+")
            box.bind("<FocusIn>", self._on_next_focus_in, add="+")
            box.bind("<FocusOut>", self._on_next_focus_out, add="+")
            box.bind("<<ComboboxSelected>>", ping, add="+")
            box.bind("<Return>", self._on_next_return, add="+")
            box.bind("<KP_Enter>", self._on_next_return, add="+")
            box.bind("<Escape>", self._on_next_escape, add="+")
        block.status_next.bind(
            "<<ComboboxSelected>>",
            lambda _event, watched=block: self._on_row_status_picked(watched),
            add="+",
        )

    def _refresh_next_marks_key(self, key: str) -> None:
        block = self._blocks.get(key)
        if block is not None:
            self._refresh_next_marks(block)

    def _refresh_next_marks(self, block: _Block) -> None:
        if block.extra:
            self._notify_draft()
            return
        row = self._matches.get(block.key)
        if row is None:
            return
        drawing = row.drawing
        self._style_next(block.status_next, _field_pending(drawing.status, block.status_next.get(), status=True))
        self._style_next(block.drawing_id_next, _field_pending(drawing.drawing_id, block.drawing_id_next.get()))
        self._style_next(block.title_next, _field_pending(drawing.title, block.title_next.get()))
        for field, _title, _values, _width, kind in FIELD_KEYS:
            box = block.nexts.get(field)
            if box is not None:
                self._style_next(
                    box,
                    _field_pending(
                        getattr(drawing, field) or "",
                        box.get(),
                        date=kind == "date",
                    ),
                )
        self._notify_draft()

    def _notify_draft(self) -> None:
        if self._suspend_layout:
            return
        hook = self._on_draft_change
        if hook is not None:
            hook()

    def _style_next(self, box: NextWidget, changed: bool) -> None:
        fill = PENDING_BG if changed else SURFACE
        cell = self._next_cell(box)
        if cell is not None and str(cell.cget("bg")) != fill:
            cell.configure(bg=fill)
        if isinstance(box, ttk.Combobox):
            want = "Pending.TCombobox" if changed else "TCombobox"
            fallback = "TCombobox"
        else:
            want = "Pending.TEntry" if changed else "TEntry"
            fallback = "TEntry"
        current = str(box.cget("style") or fallback)
        if current in {"", "."}:
            current = fallback
        if current != want:
            box.configure(style=want)

    def pending_rows(self) -> list[MatchedRow]:
        pending: list[MatchedRow] = []
        for key, block in self._blocks.items():
            if block.extra or not block.mounted:
                continue
            row = self._matches.get(key)
            if row is None:
                continue
            drawing = row.drawing
            changed = False
            nxt_status = block.status_next.get().strip()
            if nxt_status and nxt_status != (drawing.status or "").strip():
                changed = True
            if not changed and block.drawing_id_next.get().strip() != (drawing.drawing_id or "").strip():
                changed = True
            if not changed and block.title_next.get().strip() != (drawing.title or "").strip():
                changed = True
            if not changed:
                for field, _title, _values, _width, kind in FIELD_KEYS:
                    nxt = block.nexts[field].get().strip()
                    now = (getattr(drawing, field) or "").strip()
                    if kind == "date" and date_is_blank(nxt) and date_is_blank(now):
                        continue
                    if nxt != now:
                        changed = True
                        break
            if changed:
                pending.append(self._with_next(row, block))
        return pending
