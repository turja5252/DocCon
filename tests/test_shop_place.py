# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

import pytest

from doccon.client_log import LogError
from doccon.shop_place import (
    ROOT_FOLDER,
    find_shop_ifc_folder,
    place_shop_form,
    place_shop_pdf,
    shop_folder_choices,
)


def _library(tmp_path: Path) -> tuple[Path, Path]:
    library = tmp_path / "1.0 Current IFC Drawings"
    job = library / "2026-IFC Drawings" / "2026-075 IPL (Kerrobert Tank 9 Restoration)"
    (job / "1.0.1 MID Sheets").mkdir(parents=True)
    (job / "1.0.6 BOM").mkdir()
    (job / "2026-075-1-1 REV 0.pdf").write_bytes(b"old")
    return library, job


def test_finds_shop_folder_by_job_folder_name(tmp_path: Path) -> None:
    library, job = _library(tmp_path)
    dropbox = tmp_path / "2.1 Current Jobs" / job.name
    dropbox.mkdir(parents=True)
    found = find_shop_ifc_folder("2026-075", dropbox, library=library)
    assert found == job
    assert shop_folder_choices(found) == (ROOT_FOLDER, "1.0.1 MID Sheets", "1.0.6 BOM")


def test_child_job_uses_subfolder(tmp_path: Path) -> None:
    parent = tmp_path / "1.0 Current IFC Drawings" / "2026-IFC Drawings" / "2026-059 Paramount"
    child = parent / "2026-059-1"
    child.mkdir(parents=True)
    found = find_shop_ifc_folder("2026-059-1", parent, library=tmp_path / "1.0 Current IFC Drawings")
    assert found == child


def test_missing_shop_folder_is_not_created(tmp_path: Path) -> None:
    library = tmp_path / "1.0 Current IFC Drawings" / "2026-IFC Drawings"
    library.mkdir(parents=True)
    assert find_shop_ifc_folder("2026-077", tmp_path / "2026-077 Job", library=library.parent) is None


def test_place_pdf_in_root_replaces_older_rev_and_form_goes_in_transmittals(tmp_path: Path) -> None:
    _library_root, job = _library(tmp_path)
    source = tmp_path / "2026-075-1-1 REV 1.pdf"
    source.write_bytes(b"new")
    placed = place_shop_pdf(job, ROOT_FOLDER, source)
    assert placed.name == "2026-075-1-1 REV 1.pdf"
    assert placed.read_bytes() == b"new"
    assert not (job / "2026-075-1-1 REV 0.pdf").exists()
    bom = tmp_path / "BOM-2026-075-1.pdf"
    bom.write_bytes(b"bom")
    bom_dest = place_shop_pdf(job, "1.0.6 BOM", bom)
    assert bom_dest.parent.name == "1.0.6 BOM"
    form = tmp_path / "ST-2026-075-4.pdf"
    form.write_bytes(b"form")
    copied = place_shop_form(job, form)
    assert copied == job / "Transmittals" / "ST-2026-075-4.pdf"
    with pytest.raises(LogError):
        place_shop_pdf(job, "1.0.9 Missing", source)
