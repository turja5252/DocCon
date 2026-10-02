# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Calendar popup: type YYYY-MM-DD in the box, or click the dropdown to pick."""
from __future__ import annotations

import calendar
import contextlib
import tkinter as tk
from datetime import date
from tkinter import ttk

from doccon.theme import apply_theme

WEEKDAYS = ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa")


def parse_entry_date(text: str, *, default: date | None = None) -> date:
    token = (text or "").strip()
    fallback = default or date.today()
    if not token:
        return fallback
    try:
        return date.fromisoformat(token)
    except ValueError:
        return fallback


def month_weeks(year: int, month: int) -> list[list[int | None]]:
    cal = calendar.Calendar(firstweekday=6)
    weeks: list[list[int | None]] = []
    for week in cal.monthdayscalendar(year, month):
        weeks.append([day or None for day in week])
    return weeks


def set_entry_date(entry: ttk.Entry | ttk.Combobox | tk.Entry, value: date) -> None:
    text = value.isoformat()
    setter = getattr(entry, "set", None)
    if callable(setter):
        setter(text)
        return
    entry.delete(0, "end")
    entry.insert(0, text)


def popup_origin(anchor: tk.Misc, popup: tk.Misc) -> tuple[int, int]:
    """Put the popup on the same screen as the app, next to the date box.

    Do not clamp to ``winfo_screenwidth()`` — that is the primary monitor only
    and would send the calendar back to the screen where DocCon first opened.
    """
    popup.update_idletasks()
    ax = int(anchor.winfo_rootx())
    ay = int(anchor.winfo_rooty()) + int(anchor.winfo_height())
    pw = max(int(popup.winfo_reqwidth()), 1)
    ph = max(int(popup.winfo_reqheight()), 1)
    top = anchor.winfo_toplevel()
    left = int(top.winfo_rootx())
    top_y = int(top.winfo_rooty())
    right = left + max(int(top.winfo_width()), pw)
    bottom = top_y + max(int(top.winfo_height()), ph)
    x = ax
    y = ay
    if x + pw > right:
        x = right - pw
    if x < left:
        x = left
    if y + ph > bottom:
        y = ay - int(anchor.winfo_height()) - ph
    if y < top_y:
        y = top_y
    return x, y


class CalendarPopup(tk.Toplevel):
    _open: CalendarPopup | None = None

    def __init__(
        self,
        master: tk.Misc,
        *,
        initial: date,
        on_pick,
        on_na=None,
        anchor: tk.Misc | None = None,
        presets: tuple[tuple[str, object], ...] = (),
    ) -> None:
        previous = CalendarPopup._open
        if previous is not None:
            with contextlib.suppress(tk.TclError):
                previous.destroy()
        super().__init__(master)
        CalendarPopup._open = self
        self.withdraw()
        self.title("Pick a date")
        self.resizable(False, False)
        host = master.winfo_toplevel()
        self.transient(host)
        apply_theme(self)
        self._anchor = anchor or master
        self._on_pick = on_pick
        self._on_na = on_na
        self._presets = tuple(presets)
        self._year = initial.year
        self._month = initial.month
        self._selected = initial
        self._cells: list[ttk.Button] = []

        nav = ttk.Frame(self, padding=8)
        nav.pack(fill="x")
        ttk.Button(nav, text="<", width=3, command=self._prev).pack(side="left")
        self._title = ttk.Label(nav, width=18, anchor="center")
        self._title.pack(side="left", padx=8)
        ttk.Button(nav, text=">", width=3, command=self._next).pack(side="left")
        ttk.Button(nav, text="Today", command=self._today).pack(side="right")
        if on_na is not None:
            ttk.Button(nav, text="N/A", command=self._na).pack(side="right", padx=(0, 4))

        if self._presets:
            choices = ttk.Frame(self, padding=(8, 0, 8, 4))
            choices.pack(fill="x")
            for label, action in self._presets:
                ttk.Button(
                    choices,
                    text=str(label),
                    command=lambda fn=action: self._preset(fn),
                ).pack(side="left", padx=(0, 4))

        grid = ttk.Frame(self, padding=(8, 0, 8, 8))
        grid.pack()
        for col, name in enumerate(WEEKDAYS):
            ttk.Label(grid, text=name, width=4, anchor="center").grid(row=0, column=col)
        for row in range(6):
            for col in range(7):
                btn = ttk.Button(grid, width=4, command=lambda r=row, c=col: self._click(r, c))
                btn.grid(row=row + 1, column=col, padx=1, pady=1)
                self._cells.append(btn)
        self._days: list[int | None] = [None] * 42
        self._draw()
        self.bind("<Escape>", lambda _event: self.destroy())
        self._place()
        self.deiconify()
        self.lift()
        self.after(10, self._grab)

    def _place(self) -> None:
        with contextlib.suppress(tk.TclError):
            x, y = popup_origin(self._anchor, self)
            self.geometry(f"+{x}+{y}")

    def _grab(self) -> None:
        try:
            self._place()
            self.lift()
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass

    def _draw(self) -> None:
        self._title.configure(text=date(self._year, self._month, 1).strftime("%B %Y"))
        weeks = month_weeks(self._year, self._month)
        self._days = [None] * 42
        index = 0
        today = date.today()
        for week in weeks:
            for day in week:
                self._days[index] = day
                btn = self._cells[index]
                if day is None:
                    btn.configure(text="", state="disabled")
                else:
                    current = date(self._year, self._month, day)
                    mark = f"{day}"
                    if current == today:
                        mark = f"[{day}]"
                    btn.configure(text=mark, state="normal")
                index += 1
        while index < 42:
            self._days[index] = None
            self._cells[index].configure(text="", state="disabled")
            index += 1

    def _prev(self) -> None:
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._draw()

    def _next(self) -> None:
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._draw()

    def _today(self) -> None:
        self._choose(date.today())

    def _na(self) -> None:
        if self._on_na is not None:
            self._on_na()
        self.destroy()

    def _preset(self, action) -> None:
        action()
        self.destroy()

    def _click(self, row: int, col: int) -> None:
        day = self._days[row * 7 + col]
        if day is None:
            return
        self._choose(date(self._year, self._month, day))

    def destroy(self) -> None:
        if CalendarPopup._open is self:
            CalendarPopup._open = None
        super().destroy()

    def _choose(self, value: date) -> None:
        self._on_pick(value)
        self.destroy()


def set_na_text(entry: ttk.Entry | ttk.Combobox | tk.Entry) -> None:
    setter = getattr(entry, "set", None)
    if callable(setter):
        setter("N/A")
        return
    entry.delete(0, "end")
    entry.insert(0, "N/A")


ARROW_PX = 24


def attach_calendar(
    entry: ttk.Entry | tk.Entry,
    *,
    on_change=None,
    parent: tk.Misc | None = None,
    allow_na: bool = False,
    presets: tuple[tuple[str, object], ...] = (),
) -> ttk.Button:
    host = parent or entry.winfo_toplevel()
    opener = _calendar_opener(
        entry, parent=host, on_change=on_change, allow_na=allow_na, presets=presets
    )
    btn = ttk.Button(entry.master, text="▾", width=2, command=opener)
    try:
        btn.pack(side="left", after=entry, padx=(2, 8))
    except tk.TclError:
        btn.pack(side="left", padx=(2, 8))
    entry._doccon_calendar = btn
    return btn


def bind_date_picker(
    box: ttk.Combobox | ttk.Entry | tk.Entry,
    *,
    parent: tk.Misc,
    on_change=None,
    allow_na: bool = False,
) -> None:
    opener = _calendar_opener(box, parent=parent, on_change=on_change, allow_na=allow_na)

    def on_click(event) -> str | None:
        width = max(event.widget.winfo_width(), event.widget.winfo_reqwidth())
        arrow = max(ARROW_PX, width // 6)
        if width <= arrow:
            return None
        if event.x >= width - arrow:
            opener()
            return "break"
        return None

    if isinstance(box, ttk.Combobox):
        box.bind("<Button-1>", on_click, add="+")
    # Entry text stays editable. Cover dates get a ▾ button from attach_calendar.


def _calendar_opener(
    box: ttk.Combobox | ttk.Entry | tk.Entry,
    *,
    parent: tk.Misc,
    on_change,
    allow_na: bool,
    presets: tuple[tuple[str, object], ...] = (),
):
    def pick() -> None:
        current = parse_entry_date(box.get())

        def chosen(value: date) -> None:
            set_entry_date(box, value)
            if on_change is not None:
                on_change()

        def na() -> None:
            set_na_text(box)
            if on_change is not None:
                on_change()

        CalendarPopup(
            parent,
            initial=current,
            on_pick=chosen,
            on_na=na if allow_na else None,
            anchor=box,
            presets=presets,
        )

    return pick
