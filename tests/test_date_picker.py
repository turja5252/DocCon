# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import tkinter as tk
from datetime import date
from tkinter import ttk

import pytest

from doccon.date_picker import (
    CalendarPopup,
    attach_calendar,
    bind_date_picker,
    month_weeks,
    parse_entry_date,
    popup_origin,
)
from doccon.drawing_board import FIELD_KEYS, DrawingBoard
from doccon.match import MatchedRow
from doccon.register import DrawingRow


def test_month_weeks_sunday_start() -> None:
    weeks = month_weeks(2026, 9)
    assert weeks[0][0] is None
    assert weeks[0][2] == 1
    assert weeks[-1][3] == 30


def test_parse_entry_date_iso_or_today() -> None:
    assert parse_entry_date("2026-09-15") == date(2026, 9, 15)
    assert parse_entry_date("") == date.today()
    assert parse_entry_date("nope", default=date(2026, 1, 1)) == date(2026, 1, 1)


def test_dropdown_not_text_opens_calendar() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        box = ttk.Combobox(root, width=12)
        box.pack()
        root.update_idletasks()
        bind_date_picker(box, parent=root)
        box.event_generate("<Button-1>", x=2, y=8)
        root.update_idletasks()
        assert CalendarPopup._open is None
        width = max(box.winfo_width(), box.winfo_reqwidth())
        box.event_generate("<Button-1>", x=max(width - 4, 1), y=8)
        root.update_idletasks()
        assert CalendarPopup._open is not None
        assert CalendarPopup._open.title() == "Pick a date"
    finally:
        root.destroy()


def test_every_pack_date_field_opens_on_click() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        date_fields = [field for field, _title, _values, _width, kind in FIELD_KEYS if kind == "date"]
        assert date_fields == [
            "submission_date",
            "return_request_date",
            "return_date",
            "shop_ifc_date",
            "field_ifc_date",
        ]
        board = DrawingBoard(
            root,
            on_open_pdf=lambda _key: None,
        )
        board.set_rows(
            [
                MatchedRow(
                    drawing=DrawingRow(
                        key="P2024-1",
                        summary="2026-Tanzim-1-1 Drawing-1",
                        drawing_id="2026-Tanzim-1-1",
                        title="Drawing-1",
                        status="To Do",
                        job_number="2026-Tanzim",
                        outgoing_rev="A",
                        purpose="Info",
                        parent_summary="Drawing Package",
                    ),
                    pdf=None,
                    confidence="Missing",
                )
            ]
        )
        block = board._blocks["P2024-1"]
        opened = None
        for field in date_fields:
            box = block.nexts[field]
            assert not isinstance(box, ttk.Combobox)
            btn = getattr(box, "_doccon_calendar", None)
            assert isinstance(btn, ttk.Button)
            batch = board._batch_fields[field]
            assert not isinstance(batch, ttk.Combobox)
            assert isinstance(getattr(batch, "_doccon_calendar", None), ttk.Button)
            if opened is None:
                opened = btn
        opened.invoke()
        root.update_idletasks()
        assert CalendarPopup._open is not None
        CalendarPopup._open.destroy()
    finally:
        root.destroy()


def test_attach_calendar_adds_dropdown_button() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        host = ttk.Frame(root)
        host.pack()
        entry = ttk.Entry(host)
        entry.pack(side="left")
        btn = attach_calendar(entry, parent=host, allow_na=True)
        assert isinstance(btn, ttk.Button)
        assert "<Button-1>" not in entry.bind()
        entry.event_generate("<Button-1>", x=2, y=8)
        root.update_idletasks()
        assert CalendarPopup._open is None
        btn.invoke()
        root.update_idletasks()
        assert CalendarPopup._open is not None
        assert CalendarPopup._open.title() == "Pick a date"
    finally:
        root.destroy()


def test_expected_calendar_has_na() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    root.withdraw()
    try:
        picked: list[str] = []
        popup = CalendarPopup(
            root,
            initial=date(2026, 9, 9),
            on_pick=lambda _v: None,
            on_na=lambda: picked.append("N/A"),
        )
        labels = []
        for child in popup.winfo_children():
            for inner in child.winfo_children():
                if isinstance(inner, ttk.Button):
                    labels.append(str(inner.cget("text")))
        assert "N/A" in labels
        assert "Today" in labels
        popup._na()
        assert picked == ["N/A"]
    finally:
        root.destroy()


def test_calendar_follows_the_app_window() -> None:
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk is not available")
    try:
        root.geometry("480x240+280+180")
        box = ttk.Entry(root)
        box.pack()
        root.update_idletasks()
        popup = CalendarPopup(
            root,
            initial=date(2026, 9, 9),
            on_pick=lambda _v: None,
            anchor=box,
        )
        root.update_idletasks()
        x, y = popup_origin(box, popup)
        assert popup.geometry().endswith(f"+{x}+{y}")
        assert x >= int(root.winfo_rootx()) - 8
        assert y >= int(root.winfo_rooty()) - 8
    finally:
        root.destroy()
