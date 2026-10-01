# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Copy a shop pack into 1.0 Current IFC Drawings. The form goes in Transmittals."""
from __future__ import annotations

import shutil
from pathlib import Path

from doccon.client_log import LogError
from doccon.jobs import _folder_match_rank, job_folder_keys, local_team_dropbox_member_roots
from doccon.match import parse_pdf_stem

IFC_LIBRARY = "1.0 Current IFC Drawings"
ROOT_FOLDER = "Root"
TRANSMITTALS = "Transmittals"
MISSING_SHOP_FOLDER = (
    "Shop folder is not in 1.0 Current IFC Drawings yet. "
    "Locate shop folder… once the project engineer has created it. Nothing was written."
)


def shop_folder_choices(shop_root: Path) -> tuple[str, ...]:
    """Root plus the folders inside the shop job folder. Transmittals is not a drawing destination."""
    names = [ROOT_FOLDER]
    try:
        children = list(Path(shop_root).iterdir())
    except OSError:
        return (ROOT_FOLDER,)
    for child in sorted(children, key=lambda path: path.name.casefold()):
        if not child.is_dir() or child.name.casefold() == TRANSMITTALS.casefold():
            continue
        names.append(child.name)
    return tuple(names)


def find_shop_ifc_folder(
    job_number: str,
    job_folder: Path | None = None,
    remembered: Path | None = None,
    *,
    library: Path | None = None,
) -> Path | None:
    """The engineer's shop folder under 1.0 Current IFC Drawings.

    Remembers a Locate pick. Otherwise matches the Dropbox job folder name, then a
    child folder such as ``2026-059-1`` inside that parent. Does not create the folder.
    """
    if remembered is not None and Path(remembered).is_dir():
        return Path(remembered)
    job = job_number.strip()
    if not job:
        return None
    libraries = [library] if library is not None else _ifc_libraries(job_folder)
    for ifc in libraries:
        if ifc is None or not Path(ifc).is_dir():
            continue
        year = _year_bucket(Path(ifc), job)
        if year is None:
            continue
        found = _match_in_year(year, job, job_folder)
        if found is not None:
            return found
    return None


def place_shop_pdf(shop_root: Path, folder_label: str, source: Path) -> Path:
    """Copy one drawing into Root or a named subfolder. A newer rev replaces the older file."""
    dest_dir = _destination(shop_root, folder_label)
    if not dest_dir.is_dir():
        label = (folder_label or ROOT_FOLDER).strip() or ROOT_FOLDER
        raise LogError(f"{label} is not in {Path(shop_root).name}.")
    _remove_other_revs(dest_dir, source.name)
    dest = dest_dir / source.name
    shutil.copy2(source, dest)
    return dest


def place_shop_form(shop_root: Path, form: Path) -> Path:
    """Copy the ST pdf into Transmittals. Creates that folder only."""
    dest_dir = Path(shop_root) / TRANSMITTALS
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / form.name
    shutil.copy2(form, dest)
    return dest


def _destination(shop_root: Path, folder_label: str) -> Path:
    label = (folder_label or "").strip()
    if not label or label.casefold() == ROOT_FOLDER.casefold():
        return Path(shop_root)
    return Path(shop_root) / label


def _remove_other_revs(folder: Path, filename: str) -> None:
    drawing_id, _rev = parse_pdf_stem(Path(filename).stem)
    if not drawing_id:
        return
    try:
        children = list(folder.iterdir())
    except OSError:
        return
    for child in children:
        if not child.is_file() or child.suffix.casefold() != ".pdf":
            continue
        if child.name.casefold() == filename.casefold():
            continue
        other_id, _other_rev = parse_pdf_stem(child.stem)
        if other_id.casefold() == drawing_id.casefold():
            child.unlink(missing_ok=True)


def _ifc_libraries(hint: Path | None) -> list[Path]:
    found: list[Path] = []
    for member in local_team_dropbox_member_roots(hint):
        library = member / IFC_LIBRARY
        if library.is_dir():
            found.append(library)
    return found


def _year_bucket(library: Path, job_number: str) -> Path | None:
    year = job_number.strip()[:4]
    if not year.isdigit():
        return None
    try:
        children = list(library.iterdir())
    except OSError:
        return None
    for child in children:
        if child.is_dir() and child.name.startswith(year) and "ifc" in child.name.casefold():
            return child
    return None


def _match_in_year(year: Path, job_number: str, job_folder: Path | None) -> Path | None:
    try:
        children = [child for child in year.iterdir() if child.is_dir()]
    except OSError:
        return None
    folder_name = Path(job_folder).name.strip() if job_folder is not None else ""
    if folder_name:
        for child in children:
            if child.name.casefold() == folder_name.casefold():
                return _child_job_or_self(child, job_number)
    keys = job_folder_keys(job_number)
    ranked: list[tuple[int, Path]] = []
    for child in children:
        rank = _folder_match_rank(child.name, keys)
        if rank is not None:
            ranked.append((rank, child))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1].name.casefold()))
    best_rank = ranked[0][0]
    if sum(1 for rank, _path in ranked if rank == best_rank) > 1:
        return None
    return _child_job_or_self(ranked[0][1], job_number)


def _child_job_or_self(folder: Path, job_number: str) -> Path:
    """``2026-059-1`` inside ``2026-059 …`` is the shop folder for that child job."""
    exact = job_number.strip()
    if not exact:
        return folder
    try:
        children = [child for child in folder.iterdir() if child.is_dir()]
    except OSError:
        return folder
    for child in children:
        if _folder_match_rank(child.name, [exact]) is not None:
            return child
    return folder
