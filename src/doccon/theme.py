# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Console look: navy chrome, light cards, Segoe UI. ttk clam so colors actually apply."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

NAVY = "#102A43"
NAVY_MID = "#243B53"
ACCENT = "#0F766E"
ACCENT_HOVER = "#0D9488"
BG = "#F3F5F8"
SURFACE = "#FFFFFF"
BORDER = "#D9E2EC"
TEXT = "#102A43"
MUTED = "#627D98"
OK = "#0F766E"
BAD = "#B42318"
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_HEADER = ("Segoe UI", 8, "bold")


def apply_theme(root: tk.Misc) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    try:
        root.configure(background=BG)
    except tk.TclError:
        pass
    root.option_add("*Font", FONT)
    root.option_add("*TCombobox*Listbox.font", FONT)
    root.option_add("*TCombobox*Listbox.background", SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)

    style.configure(".", background=BG, foreground=TEXT, font=FONT, borderwidth=0)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("Board.TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Hint.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Header.TLabel", background=BG, foreground=MUTED, font=FONT_HEADER)
    style.configure("Now.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Next.TLabel", background=BG, foreground=ACCENT, font=FONT_SMALL)
    style.configure("Board.TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Ok.TLabel", background=BG, foreground=OK, font=FONT_BOLD)
    style.configure("Bad.TLabel", background=BG, foreground=BAD, font=FONT_BOLD)

    style.configure(
        "TLabelframe",
        background=BG,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        relief="solid",
        borderwidth=1,
        padding=8,
    )
    style.configure("TLabelframe.Label", background=BG, foreground=NAVY, font=FONT_BOLD)

    style.configure(
        "TButton",
        background="#E4EBF2",
        foreground=TEXT,
        font=FONT,
        padding=(12, 6),
        bordercolor=BORDER,
        lightcolor="#E4EBF2",
        darkcolor=BORDER,
        relief="raised",
        borderwidth=1,
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("disabled", "#EEF2F6"), ("pressed", "#D0D9E3"), ("active", "#D7E0EA")],
        foreground=[("disabled", MUTED)],
    )
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=(14, 7),
        bordercolor=ACCENT,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", "#9FB3C8"), ("pressed", "#0B5F5A"), ("active", ACCENT_HOVER)],
        foreground=[("disabled", "#E8EEF4")],
        bordercolor=[("disabled", "#9FB3C8"), ("pressed", "#0B5F5A"), ("active", ACCENT_HOVER)],
    )
    style.configure(
        "Brand.TButton",
        background=NAVY_MID,
        foreground="#FFFFFF",
        font=FONT,
        padding=(12, 6),
        bordercolor=NAVY_MID,
        lightcolor=NAVY_MID,
        darkcolor=NAVY_MID,
    )
    style.map(
        "Brand.TButton",
        background=[("active", "#334E68"), ("pressed", "#0B1F33")],
        bordercolor=[("active", "#334E68")],
    )

    style.configure(
        "TEntry",
        fieldbackground=SURFACE,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=5,
    )
    style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
    style.configure(
        "TCombobox",
        fieldbackground=SURFACE,
        background=SURFACE,
        foreground=TEXT,
        arrowcolor=NAVY,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE), ("!disabled", SURFACE)],
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
    )
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure(
        "TRadiobutton",
        background=BG,
        foreground=TEXT,
        font=FONT,
        indicatorcolor=SURFACE,
    )
    style.configure(
        "Brand.TRadiobutton",
        background=NAVY,
        foreground="#D9E2EC",
        font=FONT,
        indicatorcolor=NAVY,
    )
    style.map(
        "Brand.TRadiobutton",
        background=[("active", NAVY), ("selected", NAVY)],
        foreground=[("selected", "#FFFFFF"), ("!selected", "#BCCCDC")],
    )
    style.configure(
        "Brand.TLabel",
        background=NAVY,
        foreground="#D9E2EC",
        font=FONT,
    )
    style.configure("BrandMuted.TLabel", background=NAVY, foreground="#9FB3C8", font=FONT_SMALL)
    style.configure("TScrollbar", background=BG, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED)
    style.configure("Vertical.TScrollbar", background="#D9E2EC", troughcolor=BG)
    return style


def style_text(widget: tk.Text) -> None:
    widget.configure(
        background=SURFACE,
        foreground=TEXT,
        insertbackground=TEXT,
        relief="flat",
        borderwidth=1,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
        font=FONT,
        padx=8,
        pady=6,
    )


def match_style(confidence: str) -> str:
    if confidence == "High":
        return "Ok.TLabel"
    if confidence == "Missing":
        return "Bad.TLabel"
    return "Board.TLabel"
