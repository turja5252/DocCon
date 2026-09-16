# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""This-PC inbox for drop_host. Outlook bytes land here, then the parent pairs."""
from __future__ import annotations

import shutil
from pathlib import Path

from doccon.drop_pdfs import (
    DropSource,
    is_msg_filename,
    is_pdf_filename,
    is_pdf_source,
    safe_filename,
    unique_dest,
)
from doccon.paths import user_data_dir

INBOX_NAME = "inbox"


def inbox_dir() -> Path:
    return user_data_dir() / INBOX_NAME


def write_inbox_bytes(
    filename: str, data: bytes, *, folder: Path | None = None, used: set[str] | None = None
) -> Path:
    dest_dir = Path(folder) if folder is not None else inbox_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = safe_filename(filename)
    if not is_pdf_filename(name):
        name = f"{Path(name).stem or 'attachment'}.pdf"
    dest = unique_dest(dest_dir, name, used=used)
    dest.write_bytes(data)
    return dest


def copy_into_inbox(source: Path, *, folder: Path | None = None, used: set[str] | None = None) -> Path:
    src = Path(source)
    dest_dir = Path(folder) if folder is not None else inbox_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        if src.resolve().parent == dest_dir.resolve():
            if used is not None:
                used.add(src.name.casefold())
            return src
    except OSError:
        pass
    dest = unique_dest(dest_dir, src.name, used=used)
    try:
        shutil.copy2(src, dest)
    except OSError:
        dest.write_bytes(src.read_bytes())
    return dest


def stage_sources(sources: list[DropSource], *, folder: Path | None = None) -> list[Path]:
    """Write PDFs into the inbox. Skip .msg / non-PDF. Used only in drop_host."""
    dest_dir = Path(folder) if folder is not None else inbox_dir()
    pdfs: list[Path] = []
    used: set[str] = set()
    for src in sources:
        name = (src.name or "").strip() or (src.path.name if src.path is not None else "attachment")
        if is_msg_filename(name) or (src.path is not None and is_msg_filename(src.path.name)):
            continue
        data = src.data
        if data is None and src.path is not None:
            try:
                data = src.path.read_bytes()
            except OSError:
                data = None
        if not is_pdf_source(name, data):
            continue
        if data:
            write_name = name if is_pdf_filename(name) else f"{Path(name).stem or 'attachment'}.pdf"
            pdfs.append(write_inbox_bytes(write_name, data, folder=dest_dir, used=used))
            continue
        if src.path is not None:
            try:
                pdfs.append(copy_into_inbox(src.path, folder=dest_dir, used=used))
            except OSError:
                continue
    return pdfs
