# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Calendar popup for Date issued / Expected return."""
from __future__ import annotations

import calendar
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


def set_entry_date(entry: ttk.Entry | tk.Entry, value: date) -> None:
    entry.delete(0, "end")
    entry.insert(0, value.isoformat())


class CalendarPopup(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, initial: date, on_pick) -> None:
        super().__init__(master)
        self.title("Pick a date")
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        apply_theme(self)
        self._on_pick = on_pick
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
        self.after(10, self._grab)

    def _grab(self) -> None:
        try:
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

    def _click(self, row: int, col: int) -> None:
        day = self._days[row * 7 + col]
        if day is None:
            return
        self._choose(date(self._year, self._month, day))

    def _choose(self, value: date) -> None:
        self._on_pick(value)
        self.destroy()


def attach_calendar(entry: ttk.Entry | tk.Entry, *, on_change=None, parent: tk.Misc | None = None) -> None:
    host = parent or entry.master

    def pick() -> None:
        current = parse_entry_date(entry.get())

        def chosen(value: date) -> None:
            set_entry_date(entry, value)
            if on_change is not None:
                on_change()

        CalendarPopup(host, initial=current, on_pick=chosen)

    def today() -> None:
        set_entry_date(entry, date.today())
        if on_change is not None:
            on_change()

    ttk.Button(host, text="Today", command=today).pack(side="left", padx=(0, 4))
    ttk.Button(host, text="Calendar…", command=pick).pack(side="left")
