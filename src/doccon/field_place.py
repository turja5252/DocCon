# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Copy a field pack into the job's Field Construction folder.

Each drawing picks 2.0, a 3.1–3.6 folder, or 5.0. The FT form stays in 2.0 Transmittals.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from doccon.client_log import LogError
from doccon.jobs import job_folder_keys, local_team_dropbox_member_roots
from doccon.match import parse_pdf_stem

IFC_DIR = "2.0 IFC Drawings & Transmittals"
TRANSMITTALS = "Transmittals"
# 3.0 itself is not a destination. Its children 3.1–3.6 are.
FIELD_PREFIXES = ("2.0", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "5.0")
FIELD_SUFFIX = " Field Construction Folder"
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
    """The job's ``8.0…`` folder, otherwise ``{job} Field Construction Folder``.

    Inside the loaded job, a folder whose name starts with ``8.0`` is the field
    folder. ``2.0 IFC Drawings & Transmittals`` lives in that folder. A remembered
    Locate pick wins. An exact child job wins over the parent name at the Dropbox root.
    """
    if remembered is not None and Path(remembered).is_dir():
        return Path(remembered)
    job = job_number.strip()
    if not job:
        return None
    if job_folder is not None:
        nested = _job_eight_folder(job_folder)
        if nested is not None:
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


def _prefix_match(name: str, prefix: str) -> bool:
    token = name.strip().casefold()
    head = prefix.casefold()
    return token == head or token.startswith(head + " ") or token.startswith(head + ".")


def _field_home(field_root: Path) -> Path:
    """The 8.0 folder. A Locate pick of 2.0 itself still counts."""
    root = Path(field_root)
    if _prefix_match(root.name, "2.0"):
        return root.parent
    return root


def _child_dirs(folder: Path) -> list[Path]:
    try:
        return [child for child in Path(folder).iterdir() if child.is_dir()]
    except OSError:
        return []


def field_folder_choices(field_root: Path) -> tuple[str, ...]:
    """2.0, the 3.1–3.6 folders that exist, and 5.0. Missing numbers stay off the list."""
    home = _field_home(field_root)
    children = _child_dirs(home)
    qc = next((child for child in children if _prefix_match(child.name, "3.0")), None)
    qc_children = _child_dirs(qc) if qc is not None else []
    names: list[str] = []
    for prefix in FIELD_PREFIXES:
        pool = qc_children if prefix.startswith("3.") else children
        match = next((child for child in pool if _prefix_match(child.name, prefix)), None)
        if match is not None:
            names.append(match.name)
    return tuple(names)


def field_default_label(choices: tuple[str, ...]) -> str:
    """Drawings start in 2.0, which is where every field PDF went before the pick."""
    for name in choices:
        if _prefix_match(name, "2.0"):
            return name
    return IFC_DIR


def field_destination(field_root: Path, folder_label: str = "") -> Path:
    """The folder a drawing is copied into. A blank label is 2.0."""
    home = _field_home(field_root)
    label = (folder_label or "").strip()
    ifc = home / IFC_DIR
    if not label or _prefix_match(label, "2.0") or label.casefold() == ifc.name.casefold():
        return ifc
    children = _child_dirs(home)
    qc = next((child for child in children if _prefix_match(child.name, "3.0")), None)
    pools = [children]
    if qc is not None:
        pools.append(_child_dirs(qc))
    for pool in pools:
        for child in pool:
            if child.name.casefold() == label.casefold():
                return child
    return home / label


def place_field_pdf(field_root: Path, source: Path, folder_label: str = "") -> Path:
    """Copy one drawing into the picked field folder. A newer rev replaces the older file."""
    dest_dir = field_destination(field_root, folder_label)
    if not dest_dir.is_dir():
        label = (folder_label or "").strip() or IFC_DIR
        raise LogError(f"{label} is not in {Path(field_root).name}.")
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


def _job_eight_folder(job_folder: Path) -> Path | None:
    """The field folder inside the job. The name starts with ``8.0``."""
    try:
        children = [
            child
            for child in Path(job_folder).iterdir()
            if child.is_dir() and child.name.casefold().startswith("8.0")
        ]
    except OSError:
        return None
    if not children:
        return None
    with_drawings = [child for child in children if (child / IFC_DIR).is_dir()]
    pool = with_drawings or children
    if len(pool) == 1:
        return pool[0]
    return None


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
