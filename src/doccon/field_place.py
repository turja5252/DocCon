# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Copy a field pack into the job's Field Construction folder. No per-row folder pick."""
from __future__ import annotations

import shutil
from pathlib import Path

from doccon.client_log import LogError
from doccon.jobs import job_folder_keys, local_team_dropbox_member_roots
from doccon.match import parse_pdf_stem

IFC_DIR = "2.0 IFC Drawings & Transmittals"
TRANSMITTALS = "Transmittals"
FIELD_SUFFIX = " Field Construction Folder"
NESTED_FIELD = "8.0 Field Construction Folder"
MISSING_FIELD_FOLDER = (
    "Field folder is not on Dropbox yet. "
    "Locate field folder… once it exists. Nothing was written."
)


def field_ifc_dir(field_root: Path) -> Path:
    """Drawings live in 2.0. Locating that folder itself is the same place."""
    root = Path(field_root)
    if root.name.casefold() == IFC_DIR.casefold():
        return root
    return root / IFC_DIR


def find_field_folder(
    job_number: str,
    job_folder: Path | None = None,
    remembered: Path | None = None,
    *,
    library: Path | None = None,
) -> Path | None:
    """``{job} Field Construction Folder`` on this PC. Does not create it.

    An exact child job wins over the parent folder. A remembered Locate pick wins
    over the hunt. A job-local ``8.0 Field Construction Folder`` wins over the hunt.
    """
    if remembered is not None and Path(remembered).is_dir():
        return Path(remembered)
    job = job_number.strip()
    if not job:
        return None
    if job_folder is not None:
        nested = Path(job_folder) / NESTED_FIELD
        if nested.is_dir():
            return nested
    keys = job_folder_keys(job)
    roots = [library] if library is not None else local_team_dropbox_member_roots(job_folder)
    ranked: list[tuple[int, Path]] = []
    for root in roots:
        if root is None or not Path(root).is_dir():
            continue
        try:
            children = [child for child in Path(root).iterdir() if child.is_dir()]
        except OSError:
            continue
        for child in children:
            rank = _field_rank(child.name, keys)
            if rank is not None:
                ranked.append((rank, child))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1].name.casefold()))
    best = ranked[0][0]
    if sum(1 for rank, _path in ranked if rank == best) > 1:
        return None
    return ranked[0][1]


def place_field_pdf(field_root: Path, source: Path) -> Path:
    """Copy one drawing into 2.0. A newer rev replaces the older file."""
    dest_dir = field_ifc_dir(field_root)
    if not dest_dir.is_dir():
        raise LogError(f"{IFC_DIR} is not in {Path(field_root).name}.")
    _remove_other_revs(dest_dir, source.name)
    dest = dest_dir / source.name
    shutil.copy2(source, dest)
    return dest


def place_field_form(field_root: Path, form: Path) -> Path:
    """Copy the FT pdf into Transmittals under 2.0. Creates that folder only."""
    ifc = field_ifc_dir(field_root)
    if not ifc.is_dir():
        raise LogError(f"{IFC_DIR} is not in {Path(field_root).name}.")
    dest_dir = ifc / TRANSMITTALS
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / form.name
    shutil.copy2(form, dest)
    return dest


def _field_rank(name: str, keys: list[str]) -> int | None:
    token = name.strip()
    for index, key in enumerate(keys):
        if token.casefold() == f"{key}{FIELD_SUFFIX}".casefold():
            return index
    return None


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
