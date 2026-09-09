# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Two-row drawing list: original Jira values, then Next dropdowns."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, replace
from tkinter import ttk

from doccon.match import MatchedRow
from doccon.register import DRAWING_STATUSES
from doccon.theme import BG, apply_theme, match_style

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
PURPOSE_VALUES = ("", "Approval", "Info", "Planned", "NA")
APPROVAL_VALUES = ("", "Approved", "Approved as Noted", "Rejected", "Revise and Resubmit")

FIELD_KEYS = (
    ("client_document_number", "Client dwg", (), 16),
    ("outgoing_rev", "Outgoing Rev", REV_VALUES, 10),
    ("purpose", "Purpose", PURPOSE_VALUES, 12),
    ("incoming_rev", "Incoming Rev", REV_VALUES, 10),
    ("approval", "Client stamp", APPROVAL_VALUES, 14),
    ("shop_ifc_rev", "Shop IFC", REV_VALUES, 10),
    ("field_ifc_rev", "Field IFC", REV_VALUES, 10),
)


@dataclass
class _Block:
    key: str
    include: tk.BooleanVar
    originals: dict[str, ttk.Label]
    nexts: dict[str, ttk.Combobox]
    drawing_label: ttk.Label
    title_label: ttk.Label
    status_label: ttk.Label
    status_next: ttk.Combobox
    match_label: ttk.Label
    pdf_label: ttk.Label


class DrawingBoard(ttk.Frame):
    def __init__(self, master: tk.Misc, *, on_open_pdf) -> None:
        super().__init__(master)
        apply_theme(self)
        self._on_open_pdf = on_open_pdf
        self._matches: dict[str, MatchedRow] = {}
        self._blocks: dict[str, _Block] = {}
        self._focus_key = ""
        self._batch_status: ttk.Combobox
        self._batch_fields: dict[str, ttk.Combobox] = {}
        self._batch_note: ttk.Label

        batch = ttk.LabelFrame(self, text="Batch Next — applies to Pack ticks only", padding=4)
        batch.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(batch, text="Pack all", command=lambda: self.set_pack(True)).pack(side="left")
        ttk.Button(batch, text="Pack none", command=lambda: self.set_pack(False)).pack(side="left", padx=(4, 8))
        ttk.Button(batch, text="Apply to Pack", style="Accent.TButton", command=self._apply_batch).pack(
            side="left", padx=(0, 8)
        )
        ttk.Label(batch, text="Status").pack(side="left")
        self._batch_status = ttk.Combobox(batch, width=20, values=("",) + DRAWING_STATUSES, state="readonly")
        self._batch_status.pack(side="left", padx=(2, 8))
        self._batch_status.set("")
        self._batch_fields = {}
        for field, title, values, width in FIELD_KEYS:
            ttk.Label(batch, text=title).pack(side="left")
            box = ttk.Combobox(batch, width=max(8, width - 2), values=values, state="normal")
            box.pack(side="left", padx=(2, 6))
            self._batch_fields[field] = box
        self._batch_note = ttk.Label(batch, text="Leave a box blank to skip that field.", style="Muted.TLabel")
        self._batch_note.pack(side="left", padx=8)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=(8, 0), pady=(0, 2))
        titles = (
            ("Pack", 5),
            ("", 5),
            ("Drawing", 18),
            ("Title", 22),
            ("Status", 22),
            ("Match", 8),
            ("PDF", 28),
            *( (title, width) for _field, title, _values, width in FIELD_KEYS ),
        )
        for col, (title, width) in enumerate(titles):
            ttk.Label(header, text=title, width=width, style="Header.TLabel").grid(
                row=0, column=col, sticky="w", padx=2
            )

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(body, highlightthickness=0, background=BG, borderwidth=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self._canvas.yview)
        self._inner = ttk.Frame(self._canvas, style="Board.TFrame")
        self._window = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=scroll.set)
        self._canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        scroll.pack(side="right", fill="y", pady=(0, 8), padx=(0, 8))
        self._inner.bind("<Configure>", lambda _event: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", self._stretch)
        self._canvas.bind("<Enter>", lambda _event: self._canvas.bind_all("<MouseWheel>", self._wheel))
        self._canvas.bind("<Leave>", lambda _event: self._canvas.unbind_all("<MouseWheel>"))

    def _stretch(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(self._window, width=event.width)

    def _wheel(self, event: tk.Event) -> None:
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        self._blocks.clear()
        self._matches.clear()
        self._focus_key = ""

    def set_rows(self, rows: list[MatchedRow], *, checked: set[str] | None = None) -> None:
        self.clear()
        want = checked
        for index, row in enumerate(rows):
            self._matches[row.drawing.key] = row
            include = want is None or row.drawing.key in want
            self._add_block(index, row, include=include)

    def _add_block(self, index: int, row: MatchedRow, *, include: bool) -> None:
        drawing = row.drawing
        top = 1 + index * 2
        next_row = top + 1
        pack = tk.BooleanVar(value=include)
        ttk.Checkbutton(self._inner, variable=pack).grid(row=top, column=0, rowspan=2, padx=2)
        ttk.Label(self._inner, text="Now", style="Now.TLabel").grid(row=top, column=1, sticky="e", padx=2)
        ttk.Label(self._inner, text="Next", style="Next.TLabel").grid(row=next_row, column=1, sticky="e", padx=2)
        drawing_label = ttk.Label(
            self._inner, text=drawing.drawing_id or drawing.key, width=18, style="Board.TLabel"
        )
        drawing_label.grid(row=top, column=2, sticky="w", padx=2)
        title_label = ttk.Label(
            self._inner, text=(drawing.title or drawing.summary)[:42], width=22, style="Board.TLabel"
        )
        title_label.grid(row=top, column=3, sticky="w", padx=2)
        status_label = ttk.Label(self._inner, text=drawing.status, width=22, style="Board.TLabel")
        status_label.grid(row=top, column=4, sticky="w", padx=2)
        status_next = ttk.Combobox(self._inner, width=20, values=DRAWING_STATUSES, state="readonly")
        status_next.set(drawing.status)
        status_next.grid(row=next_row, column=4, sticky="w", padx=2)
        status_next.bind("<Button-1>", lambda _event, key=drawing.key: self._set_focus(key))
        match_label = ttk.Label(
            self._inner, text=row.confidence, width=8, style=match_style(row.confidence)
        )
        match_label.grid(row=top, column=5, sticky="w", padx=2)
        pdf_name = row.pdf.path.name if row.pdf else ""
        pdf_label = ttk.Label(self._inner, text=pdf_name, width=28, style="Board.TLabel")
        pdf_label.grid(row=top, column=6, sticky="w", padx=2)
        pdf_label.bind("<Double-1>", lambda _event, key=drawing.key: self._on_open_pdf(key))
        for widget in (drawing_label, title_label, status_label, match_label, pdf_label):
            widget.bind("<Button-1>", lambda _event, key=drawing.key: self._set_focus(key))

        originals: dict[str, ttk.Label] = {}
        nexts: dict[str, ttk.Combobox] = {}
        for offset, (field, _title, values, width) in enumerate(FIELD_KEYS):
            col = 7 + offset
            current = getattr(drawing, field) or "—"
            original = ttk.Label(self._inner, text=current, width=width, style="Board.TLabel")
            original.grid(row=top, column=col, sticky="w", padx=2)
            originals[field] = original
            box = ttk.Combobox(self._inner, width=max(8, width - 1), values=values, state="normal")
            box.set(getattr(drawing, field) or "")
            box.grid(row=next_row, column=col, sticky="w", padx=2)
            box.bind("<Button-1>", lambda _event, key=drawing.key: self._set_focus(key))
            nexts[field] = box
        self._blocks[drawing.key] = _Block(
            key=drawing.key,
            include=pack,
            originals=originals,
            nexts=nexts,
            drawing_label=drawing_label,
            title_label=title_label,
            status_label=status_label,
            status_next=status_next,
            match_label=match_label,
            pdf_label=pdf_label,
        )

    def set_pack(self, checked: bool) -> None:
        for block in self._blocks.values():
            block.include.set(checked)

    def apply_next_to_pack(self, *, status: str = "", fields: dict[str, str] | None = None) -> int:
        updates = {key: value.strip() for key, value in (fields or {}).items() if value.strip()}
        status_value = (status or "").strip()
        if not status_value and not updates:
            return 0
        count = 0
        for key, block in self._blocks.items():
            if not block.include.get():
                continue
            if status_value:
                block.status_next.set(status_value)
            for field, value in updates.items():
                box = block.nexts.get(field)
                if box is not None:
                    box.set(value)
            count += 1
            self._set_focus(key)
        return count

    def _apply_batch(self) -> None:
        fields = {field: box.get() for field, box in self._batch_fields.items()}
        count = self.apply_next_to_pack(status=self._batch_status.get(), fields=fields)
        if count:
            self._batch_note.configure(text=f"Applied to {count} packed drawing(s).")
        else:
            self._batch_note.configure(text="Tick Pack and pick at least one Next value.")

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
        updates = {field: block.nexts[field].get().strip() for field, _title, _values, _width in FIELD_KEYS}
        status = block.status_next.get().strip() or row.drawing.status
        return replace(row, drawing=replace(row.drawing, status=status, **updates))

    def _set_focus(self, key: str) -> None:
        self._focus_key = key

    def focus_key(self, key: str) -> None:
        self._set_focus(key)

    def focused_row(self) -> MatchedRow | None:
        if self._focus_key:
            row = self._matches.get(self._focus_key)
            if row is not None:
                return row
        selected = self.selected_rows()
        return selected[0] if selected else None

    def apply_row(self, row: MatchedRow) -> None:
        drawing = row.drawing
        self._matches[drawing.key] = row
        block = self._blocks.get(drawing.key)
        if block is None:
            return
        block.drawing_label.configure(text=drawing.drawing_id or drawing.key)
        block.title_label.configure(text=(drawing.title or drawing.summary)[:42])
        block.status_label.configure(text=drawing.status)
        block.status_next.set(drawing.status)
        block.match_label.configure(text=row.confidence, style=match_style(row.confidence))
        block.pdf_label.configure(text=row.pdf.path.name if row.pdf else "")
        for field, _title, _values, _width in FIELD_KEYS:
            value = getattr(drawing, field) or ""
            block.originals[field].configure(text=value or "—")
            block.nexts[field].set(value)

    def pending_rows(self) -> list[MatchedRow]:
        pending: list[MatchedRow] = []
        for key, block in self._blocks.items():
            row = self._matches.get(key)
            if row is None:
                continue
            drawing = row.drawing
            changed = False
            nxt_status = block.status_next.get().strip()
            if nxt_status and nxt_status != (drawing.status or "").strip():
                changed = True
            if not changed:
                for field, _title, _values, _width in FIELD_KEYS:
                    nxt = block.nexts[field].get().strip()
                    if nxt != (getattr(drawing, field) or "").strip():
                        changed = True
                        break
            if changed:
                pending.append(self._with_next(row, block))
        return pending
