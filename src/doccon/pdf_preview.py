# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""PDF preview window: zoom, pan, draw a box, grab Description. Not a console pane."""
from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

import pymupdf

from doccon.pdf_grab import (
    canvas_box_to_page_rect,
    grabbed_text_is_usable,
    text_from_page_clip,
)
from doccon.theme import ACCENT, apply_theme

ZOOM_MIN = 0.4
ZOOM_MAX = 4.0
ZOOM_STEP = 1.25
GRAB_HINT = "Draw a box to grab Description. Wheel zooms. Middle-drag pans."
MAX_PIX_EDGE = 3600


class PdfPreviewDialog(tk.Toplevel):
    """One preview at a time. Preview on another row retargets this window."""

    _open: PdfPreviewDialog | None = None

    def __init__(
        self,
        master: tk.Misc,
        path: Path,
        *,
        heading: str = "",
        on_grab: Callable[[str], bool] | None = None,
    ) -> None:
        previous = PdfPreviewDialog._open
        if previous is not None:
            with contextlib.suppress(tk.TclError):
                previous.destroy()
        super().__init__(master)
        PdfPreviewDialog._open = self
        self.title("Preview PDF")
        self.geometry("920x720")
        self.minsize(640, 480)
        host = master.winfo_toplevel()
        self.transient(host)
        apply_theme(self)
        self._on_grab = on_grab
        self._doc: pymupdf.Document | None = None
        self._path: Path | None = None
        self._page = 0
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._photo: tk.PhotoImage | None = None
        self._pix_size = (0, 0)
        self._matrix_zoom = 1.0
        self._page_size = (1.0, 1.0)
        self._busy = False
        self._panning = False
        self._boxing = False
        self._box_origin = (0, 0)
        self._last_pan = (0, 0)
        self._resize_job: object | None = None

        chrome = ttk.Frame(self, padding=(10, 8, 10, 4))
        chrome.pack(fill="x")
        self._heading = ttk.Label(chrome, text=heading or path.name, wraplength=700)
        self._heading.pack(side="left", fill="x", expand=True)
        ttk.Button(chrome, text="Close", command=self.destroy, width=8).pack(side="right")

        tools = ttk.Frame(self, padding=(10, 0, 10, 4))
        tools.pack(fill="x")
        ttk.Button(tools, text="Fit", width=4, command=self._zoom_fit).pack(side="left")
        ttk.Button(tools, text="−", width=3, command=lambda: self._zoom_by(1 / ZOOM_STEP)).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(tools, text="+", width=3, command=lambda: self._zoom_by(ZOOM_STEP)).pack(
            side="left", padx=(4, 0)
        )
        ttk.Button(tools, text="<", width=3, command=lambda: self._page_delta(-1)).pack(side="left", padx=(12, 0))
        self._page_label = ttk.Label(tools, text="page 1/1", width=12, anchor="center")
        self._page_label.pack(side="left", padx=4)
        ttk.Button(tools, text=">", width=3, command=lambda: self._page_delta(1)).pack(side="left")
        hint = ttk.Label(tools, text=GRAB_HINT)
        hint.pack(side="left", padx=(16, 0))

        hold = ttk.Frame(self, padding=(10, 4, 10, 8))
        hold.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(hold, background="#1B2733", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self._status = tk.StringVar(value=GRAB_HINT)
        ttk.Label(self, textvariable=self._status, padding=(10, 0, 10, 8)).pack(fill="x")

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda _e: self._zoom_by(ZOOM_STEP))
        self.canvas.bind("<Button-5>", lambda _e: self._zoom_by(1 / ZOOM_STEP))
        self.canvas.bind("<ButtonPress-1>", self._on_box_press)
        self.canvas.bind("<B1-Motion>", self._on_box_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_box_release)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_press)
        self.canvas.bind("<B2-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_release)
        self.canvas.bind("<ButtonPress-3>", self._on_pan_press)
        self.canvas.bind("<B3-Motion>", self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_pan_release)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._load(path, heading=heading)
        self.deiconify()
        self.lift()

    def retarget(
        self,
        path: Path,
        *,
        heading: str = "",
        on_grab: Callable[[str], bool] | None = None,
    ) -> None:
        self._on_grab = on_grab
        self._load(path, heading=heading)
        self.lift()

    def destroy(self) -> None:
        if PdfPreviewDialog._open is self:
            PdfPreviewDialog._open = None
        self._close_doc()
        with contextlib.suppress(tk.TclError):
            super().destroy()

    def _close_doc(self) -> None:
        handle = self._doc
        self._doc = None
        self._path = None
        if handle is not None:
            with contextlib.suppress(Exception):
                handle.close()

    def _load(self, path: Path, *, heading: str = "") -> None:
        self._close_doc()
        self._page = 0
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self._photo = None
        target = Path(path)
        self._heading.configure(text=heading or target.name)
        try:
            self._doc = pymupdf.open(target)
            self._path = target
        except Exception as exc:
            self._doc = None
            self.canvas.delete("all")
            self._status.set(f"Could not open: {exc}")
            return
        self.render()

    def _page_delta(self, delta: int) -> None:
        handle = self._doc
        if handle is None or handle.page_count < 1:
            return
        self._page = max(0, min(handle.page_count - 1, self._page + int(delta)))
        self._pan_x = 0
        self._pan_y = 0
        self.render()

    def _zoom_by(self, factor: float) -> None:
        self._zoom = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * float(factor)))
        self.render()

    def _zoom_fit(self) -> None:
        self._zoom = 1.0
        self._pan_x = 0
        self._pan_y = 0
        self.render()

    def render(self) -> None:
        if self._busy:
            return
        handle = self._doc
        if handle is None:
            return
        self._busy = True
        try:
            count = handle.page_count
            if count < 1:
                self.canvas.delete("all")
                self._status.set("That PDF has no pages.")
                return
            idx = max(0, min(count - 1, self._page))
            self._page = idx
            max_w = max(self.canvas.winfo_width(), 200)
            max_h = max(self.canvas.winfo_height(), 180)
            page_obj = handle[idx]
            fit = min(
                max_w / max(page_obj.rect.width, 1),
                max_h / max(page_obj.rect.height, 1),
                1.6,
            )
            fit = max(fit, 0.2)
            zoom = fit * float(self._zoom)
            edge = max(page_obj.rect.width, page_obj.rect.height) * zoom
            if edge > MAX_PIX_EDGE:
                zoom *= MAX_PIX_EDGE / edge
            pix = page_obj.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            photo = tk.PhotoImage(data=pix.tobytes("ppm"))
            self._photo = photo
            self._pix_size = (int(pix.width), int(pix.height))
            self._matrix_zoom = float(zoom)
            self._page_size = (float(page_obj.rect.width), float(page_obj.rect.height))
            self.canvas.delete("all")
            self.canvas.create_image(
                max_w // 2 + int(self._pan_x),
                max_h // 2 + int(self._pan_y),
                image=photo,
                anchor="center",
                tags=("preview_page",),
            )
            name = self._path.name if self._path is not None else "PDF"
            self._page_label.configure(text=f"page {idx + 1}/{count}")
            self._status.set(f"{name}  ·  page {idx + 1}/{count}  ·  zoom {self._zoom:.0%}  ·  {GRAB_HINT}")
        except Exception as exc:
            self.canvas.delete("all")
            self._status.set(f"Could not preview: {exc}")
        finally:
            self._busy = False

    def _schedule_render(self) -> None:
        if self._resize_job is not None:
            with contextlib.suppress(tk.TclError):
                self.after_cancel(self._resize_job)  # type: ignore[arg-type]
        self._resize_job = self.after(180, self.render)

    def _on_configure(self, _event: object | None = None) -> None:
        if self._doc is None:
            return
        self._schedule_render()

    def _on_wheel(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if getattr(event, "delta", 0) > 0:
            self._zoom_by(ZOOM_STEP)
        elif getattr(event, "delta", 0) < 0:
            self._zoom_by(1 / ZOOM_STEP)

    def _on_pan_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._panning = True
        self._last_pan = (event.x, event.y)
        self.canvas.configure(cursor="fleur")

    def _on_pan_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._panning:
            return
        dx = event.x - self._last_pan[0]
        dy = event.y - self._last_pan[1]
        self._pan_x += dx
        self._pan_y += dy
        self._last_pan = (event.x, event.y)
        self.canvas.move("preview_page", dx, dy)

    def _on_pan_release(self, _event: tk.Event) -> None:  # type: ignore[type-arg]
        self._panning = False
        self.canvas.configure(cursor="crosshair")

    def _on_box_press(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        self._boxing = True
        self._box_origin = (event.x, event.y)
        self.canvas.delete("grab-box")

    def _on_box_drag(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._boxing:
            return
        self.canvas.delete("grab-box")
        x0, y0 = self._box_origin
        self.canvas.create_rectangle(
            x0,
            y0,
            event.x,
            event.y,
            outline=ACCENT,
            width=2,
            dash=(4, 2),
            tags="grab-box",
        )

    def _on_box_release(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not self._boxing:
            return
        self._boxing = False
        self.canvas.delete("grab-box")
        self._grab_box(self._box_origin[0], self._box_origin[1], event.x, event.y)

    def _image_center(self) -> tuple[float, float] | None:
        items = self.canvas.find_withtag("preview_page")
        if not items:
            return None
        coords = self.canvas.coords(items[0])
        if len(coords) < 2:
            return None
        return (float(coords[0]), float(coords[1]))

    def _grab_box(self, x0: float, y0: float, x1: float, y1: float) -> None:
        handle = self._doc
        center = self._image_center()
        if handle is None or center is None:
            return
        box = canvas_box_to_page_rect(
            x0,
            y0,
            x1,
            y1,
            center=center,
            pix_size=self._pix_size,
            zoom=self._matrix_zoom,
            page_size=self._page_size,
        )
        if box is None:
            return
        self._status.set("Reading box…")
        self.update_idletasks()
        try:
            page_obj = handle[self._page]
            grabbed = text_from_page_clip(page_obj, pymupdf.Rect(*box))
        except Exception as exc:
            self._status.set(f"Could not read that box: {exc}")
            return
        if not grabbed_text_is_usable(grabbed):
            self._status.set("No text in that box.")
            return
        hook = self._on_grab
        wrote = True
        if hook is not None:
            wrote = bool(hook(grabbed))
        if wrote:
            self._status.set(f"Description: {grabbed}")
        else:
            self._status.set("Could not write Description.")


def open_pdf_preview(
    master: tk.Misc,
    path: Path,
    *,
    heading: str = "",
    on_grab: Callable[[str], bool] | None = None,
) -> PdfPreviewDialog:
    """Open or retarget the single Preview window."""
    existing = PdfPreviewDialog._open
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.retarget(path, heading=heading, on_grab=on_grab)
                return existing
        except tk.TclError:
            PdfPreviewDialog._open = None
    return PdfPreviewDialog(master, path, heading=heading, on_grab=on_grab)


def close_pdf_preview() -> None:
    existing = PdfPreviewDialog._open
    if existing is None:
        return
    with contextlib.suppress(tk.TclError):
        existing.destroy()
