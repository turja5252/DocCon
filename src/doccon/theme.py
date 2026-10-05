# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Console look: navy chrome, light cards, Segoe UI. ttk clam so colors actually apply."""
from __future__ import annotations

import contextlib
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
# Identity chips on the navy bar: Jira (Atlassian blue) vs Dropbox/folder (Elite teal).
JIRA = "#4C9AFF"
FOLDER = "#2DD4BF"
IDENTITY_MISSING = "#FCA5A5"
PENDING_BG = "#FEF3C7"
PENDING_BORDER = "#E8B86D"
# Keyboard focus inside a text cell stays teal. The selected row is a darker orange.
# PENDING_BG stays the pale yellow, so a dirty Next still reads as an edit.
FOCUS_BG = "#D5EFEB"
FOCUS_RULE = ACCENT
SELECT_BG = "#E07A2F"
SELECT_RULE = "#9A3412"
# Scrollbar: pale thumb on a slate trough so the slider is findable on navy and board BG.
SCROLL_TROUGH = "#486581"
SCROLL_THUMB = "#D9E2EC"
SCROLL_THUMB_HOVER = "#F0F4F8"
SCROLL_ARROW = "#102A43"
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")


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
    style.configure("Header.TFrame", background="#E4EBF2")
    style.configure(
        "Header.TLabel",
        background="#E4EBF2",
        foreground=MUTED,
        font=FONT_SMALL,
        padding=(2, 6),
    )
    style.configure(
        "Group.TLabel",
        background=NAVY_MID,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=(8, 5),
    )
    style.configure("CoverHead.TLabel", background=BG, foreground=MUTED, font=FONT_BOLD)
    style.configure("Now.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Next.TLabel", background=BG, foreground=ACCENT, font=FONT_SMALL)
    style.configure("Board.TLabel", background=BG, foreground=TEXT, font=FONT)
    style.configure("Pending.TLabel", background=PENDING_BG, foreground=TEXT, font=FONT)
    style.configure("Ok.TLabel", background=BG, foreground=OK, font=FONT_BOLD)
    style.configure("Bad.TLabel", background=BG, foreground=BAD, font=FONT_BOLD)
    style.configure("Focus.TLabel", background=SELECT_BG, foreground=TEXT, font=FONT)
    style.configure("FocusOk.TLabel", background=SELECT_BG, foreground=OK, font=FONT_BOLD)
    style.configure("FocusBad.TLabel", background=SELECT_BG, foreground=BAD, font=FONT_BOLD)

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
        bordercolor="#9FB3C8",
        lightcolor="#FFFFFF",
        darkcolor="#9FB3C8",
        relief="solid",
        borderwidth=2,
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("disabled", "#EEF2F6"), ("pressed", "#D0D9E3"), ("active", "#FFFFFF")],
        foreground=[("disabled", MUTED)],
        bordercolor=[("disabled", BORDER), ("active", ACCENT), ("pressed", "#0B5F5A")],
        lightcolor=[("disabled", BORDER), ("active", "#5EEAD4"), ("pressed", ACCENT)],
        darkcolor=[("disabled", BORDER), ("active", ACCENT), ("pressed", "#0B5F5A")],
    )
    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=(14, 7),
        bordercolor="#115E59",
        lightcolor="#5EEAD4",
        darkcolor="#115E59",
        borderwidth=2,
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", "#9FB3C8"), ("pressed", "#0B5F5A"), ("active", ACCENT_HOVER)],
        foreground=[("disabled", "#E8EEF4")],
        bordercolor=[("disabled", "#9FB3C8"), ("pressed", "#0B5F5A"), ("active", "#CCFBF1")],
        lightcolor=[("disabled", "#9FB3C8"), ("pressed", "#5EEAD4"), ("active", "#ECFDF5")],
        darkcolor=[("disabled", "#9FB3C8"), ("pressed", "#0B5F5A"), ("active", "#99F6E4")],
    )
    style.configure(
        "Brand.TButton",
        background=NAVY_MID,
        foreground="#FFFFFF",
        font=FONT,
        padding=(12, 6),
        bordercolor="#7DD3FC",
        lightcolor="#BAE6FD",
        darkcolor="#0369A1",
        borderwidth=2,
    )
    style.map(
        "Brand.TButton",
        background=[("disabled", "#334E68"), ("active", "#334E68"), ("pressed", "#0B1F33")],
        foreground=[("disabled", "#9FB3C8")],
        bordercolor=[("disabled", "#486581"), ("active", "#E0F2FE"), ("pressed", "#7DD3FC")],
        lightcolor=[("disabled", "#486581"), ("active", "#F0F9FF"), ("pressed", "#BAE6FD")],
        darkcolor=[("disabled", "#334E68"), ("active", "#38BDF8"), ("pressed", "#0369A1")],
    )
    style.configure(
        "Danger.TButton",
        background=BAD,
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=(12, 6),
        bordercolor="#7F1D1D",
        lightcolor="#FECACA",
        darkcolor="#7F1D1D",
        borderwidth=2,
    )
    style.map(
        "Danger.TButton",
        background=[("disabled", "#E8C4C0"), ("pressed", "#7F1D1D"), ("active", "#DC2626")],
        foreground=[("disabled", "#FFFFFF")],
        bordercolor=[("disabled", "#E8C4C0"), ("pressed", "#7F1D1D"), ("active", "#FEE2E2")],
        lightcolor=[("disabled", "#E8C4C0"), ("pressed", "#FECACA"), ("active", "#FFF1F2")],
        darkcolor=[("disabled", "#E8C4C0"), ("pressed", "#7F1D1D"), ("active", "#FCA5A5")],
    )
    style.configure(
        "Add.TButton",
        background="#166534",
        foreground="#FFFFFF",
        font=FONT_BOLD,
        padding=(12, 6),
        bordercolor="#14532D",
        lightcolor="#BBF7D0",
        darkcolor="#14532D",
        borderwidth=2,
    )
    style.map(
        "Add.TButton",
        background=[("disabled", "#9FB3C8"), ("pressed", "#14532D"), ("active", "#15803D")],
        foreground=[("disabled", "#FFFFFF")],
        bordercolor=[("disabled", "#9FB3C8"), ("pressed", "#14532D"), ("active", "#DCFCE7")],
        lightcolor=[("disabled", "#9FB3C8"), ("pressed", "#BBF7D0"), ("active", "#F0FDF4")],
        darkcolor=[("disabled", "#9FB3C8"), ("pressed", "#14532D"), ("active", "#86EFAC")],
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
    style.map(
        "TEntry",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        fieldbackground=[("focus", FOCUS_BG)],
        background=[("focus", FOCUS_BG)],
    )
    style.configure(
        "Pending.TEntry",
        fieldbackground=PENDING_BG,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=PENDING_BORDER,
        lightcolor=PENDING_BORDER,
        darkcolor=PENDING_BORDER,
        padding=5,
    )
    style.map(
        "Pending.TEntry",
        fieldbackground=[("focus", PENDING_BG), ("!disabled", PENDING_BG)],
        bordercolor=[("focus", "#D97706"), ("!focus", PENDING_BORDER)],
        lightcolor=[("focus", PENDING_BG), ("!focus", PENDING_BORDER)],
        darkcolor=[("focus", PENDING_BG), ("!focus", PENDING_BORDER)],
    )
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
        fieldbackground=[("focus", FOCUS_BG), ("readonly", SURFACE), ("!disabled", SURFACE)],
        background=[("focus", FOCUS_BG), ("readonly", SURFACE), ("!disabled", SURFACE)],
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
    )
    style.configure(
        "Pending.TCombobox",
        fieldbackground=PENDING_BG,
        background=PENDING_BG,
        foreground=TEXT,
        arrowcolor=NAVY,
        bordercolor=PENDING_BORDER,
        lightcolor=PENDING_BORDER,
        darkcolor=PENDING_BORDER,
        padding=4,
    )
    style.map(
        "Pending.TCombobox",
        fieldbackground=[
            ("readonly", PENDING_BG),
            ("disabled", PENDING_BG),
            ("focus", PENDING_BG),
            ("active", PENDING_BG),
            ("pressed", PENDING_BG),
            ("!disabled", PENDING_BG),
        ],
        background=[
            ("readonly", PENDING_BG),
            ("focus", PENDING_BG),
            ("active", PENDING_BG),
            ("!disabled", PENDING_BG),
        ],
        bordercolor=[("focus", "#D97706"), ("!focus", PENDING_BORDER)],
        lightcolor=[("focus", PENDING_BG), ("!focus", PENDING_BORDER)],
        darkcolor=[("focus", PENDING_BG), ("!focus", PENDING_BORDER)],
    )
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure(
        "Locate.TButton",
        background=SURFACE,
        foreground=NAVY,
        font=FONT_SMALL,
        padding=(8, 2),
        bordercolor="#9FB3C8",
        lightcolor="#FFFFFF",
        darkcolor="#9FB3C8",
        borderwidth=2,
    )
    style.map(
        "Locate.TButton",
        background=[("disabled", "#EEF2F6"), ("active", FOCUS_BG), ("pressed", "#D0D9E3")],
        foreground=[("disabled", MUTED)],
        bordercolor=[("disabled", BORDER), ("active", ACCENT), ("pressed", "#0B5F5A")],
        lightcolor=[("disabled", BORDER), ("active", "#5EEAD4"), ("pressed", ACCENT)],
        darkcolor=[("disabled", BORDER), ("active", ACCENT), ("pressed", "#0B5F5A")],
    )
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
    style.configure("BrandJira.TLabel", background=NAVY, foreground=JIRA, font=FONT_SMALL)
    style.configure("BrandFolder.TLabel", background=NAVY, foreground=FOLDER, font=FONT_SMALL)
    style.configure(
        "TScrollbar",
        background=SCROLL_THUMB,
        troughcolor=SCROLL_TROUGH,
        bordercolor=SCROLL_TROUGH,
        arrowcolor=SCROLL_ARROW,
        lightcolor=SCROLL_THUMB,
        darkcolor=SCROLL_TROUGH,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "TScrollbar",
        background=[("active", SCROLL_THUMB_HOVER), ("pressed", "#FFFFFF")],
        arrowcolor=[("disabled", MUTED)],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=SCROLL_THUMB,
        troughcolor=SCROLL_TROUGH,
        bordercolor=SCROLL_TROUGH,
        arrowcolor=SCROLL_ARROW,
        lightcolor=SCROLL_THUMB,
        darkcolor=SCROLL_TROUGH,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", SCROLL_THUMB_HOVER), ("pressed", "#FFFFFF")],
    )
    style.configure(
        "Vertical.TScrollbar",
        background=SCROLL_THUMB,
        troughcolor=SCROLL_TROUGH,
        bordercolor=SCROLL_TROUGH,
        arrowcolor=SCROLL_ARROW,
        lightcolor=SCROLL_THUMB,
        darkcolor=SCROLL_TROUGH,
        relief="flat",
        borderwidth=1,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", SCROLL_THUMB_HOVER), ("pressed", "#FFFFFF")],
    )
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=NAVY_MID,
        background=ACCENT,
        bordercolor=NAVY,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=4,
        borderwidth=0,
        relief="flat",
    )
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


def match_style(confidence: str, *, focused: bool = False) -> str:
    if confidence == "High":
        return "FocusOk.TLabel" if focused else "Ok.TLabel"
    if confidence == "Missing":
        return "FocusBad.TLabel" if focused else "Bad.TLabel"
    return "Focus.TLabel" if focused else "Board.TLabel"


class ThemeProgress(tk.Canvas):
    """Load meter on navy chrome. Slate trough + teal fill so it is findable (not a 4px hairline)."""

    BAR_H = 10
    PAD_Y = 4
    TRACK = SCROLL_TROUGH
    FILL = FOLDER

    def __init__(self, master: tk.Misc, *, manage_pack: bool = True) -> None:
        super().__init__(
            master,
            height=self.BAR_H + self.PAD_Y * 2,
            highlightthickness=0,
            bd=0,
            bg=NAVY,
        )
        self._manage_pack = manage_pack
        self._mode = "idle"
        self._value = 0.0
        self._pulse = 0.0
        self._after = ""
        self.bind("<Configure>", lambda _event: self._draw())

    def start_indeterminate(self) -> None:
        self._cancel()
        self._mode = "indeterminate"
        self._pulse = 0.0
        self._show()
        self._tick()

    def set_determinate(self, done: int, total: int) -> None:
        self._cancel()
        self._mode = "determinate"
        self._value = 0.0 if total <= 0 else min(1.0, max(0.0, done / float(total)))
        self._show()
        self._draw()

    def stop(self) -> None:
        self._cancel()
        self._mode = "idle"
        self._value = 0.0
        self.delete("all")
        if self._manage_pack:
            self.pack_forget()

    def fraction(self) -> float:
        return self._value

    def mode(self) -> str:
        return self._mode

    def _show(self) -> None:
        if self._manage_pack and not self.winfo_ismapped():
            self.pack(fill="x", pady=(8, 0))

    def _cancel(self) -> None:
        if self._after:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._after)
            self._after = ""

    def _tick(self) -> None:
        if self._mode != "indeterminate":
            return
        self._pulse = (self._pulse + 0.035) % 1.0
        self._draw()
        self._after = self.after(32, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        if self._mode == "idle":
            return
        width = max(int(self.winfo_width()), 2)
        height = int(self.cget("height"))
        mid = height / 2
        self._capsule(0, width, mid, self.TRACK)
        track = width
        if self._mode == "determinate":
            fill = track * self._value
            if fill > 1:
                self._capsule(0, fill, mid, self.FILL)
            return
        span = max(track * 0.28, 64)
        travel = max(track - span, 1)
        phase = 1.0 - abs(2.0 * self._pulse - 1.0)
        left = travel * phase
        self._capsule(left, left + span, mid, self.FILL)

    def _capsule(self, x0: float, x1: float, y: float, color: str) -> None:
        if x1 <= x0:
            return
        pad = self.BAR_H / 2
        left = x0 + pad
        right = x1 - pad
        if right <= left:
            self.create_oval(x0, y - pad, x1, y + pad, fill=color, outline="")
            return
        self.create_line(left, y, right, y, fill=color, width=self.BAR_H, capstyle=tk.ROUND)
