# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

import pytest

from doccon.client_log import LogError
from doccon.field_place import find_field_folder, place_field_form, place_field_pdf


def _field(tmp_path: Path, job: str = "2024-003") -> Path:
    root = tmp_path / f"{job} Field Construction Folder"
    ifc = root / "2.0 IFC Drawings & Transmittals"
    ifc.mkdir(parents=True)
    (ifc / f"{job}-1-1 REV 0.pdf").write_bytes(b"old")
    return root


def test_finds_field_folder_by_job_number(tmp_path: Path) -> None:
    root = _field(tmp_path)
    found = find_field_folder("2024-003", library=tmp_path)
    assert found == root


def test_child_job_prefers_its_own_folder(tmp_path: Path) -> None:
    parent = _field(tmp_path, "2026-077")
    child = _field(tmp_path, "2026-077-1")
    found = find_field_folder("2026-077-1", library=tmp_path)
    assert found == child
    assert found != parent


def test_missing_field_folder_is_not_created(tmp_path: Path) -> None:
    assert find_field_folder("2026-Tanzim", library=tmp_path) is None
    assert not (tmp_path / "2026-Tanzim Field Construction Folder").exists()


def test_job_local_folder_wins(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    nested = job / "8.0 Field Construction Folder (2026-Tanzim)"
    (nested / "2.0 IFC Drawings & Transmittals").mkdir(parents=True)
    shared = _field(tmp_path, "2026-Tanzim")
    found = find_field_folder("2026-Tanzim", job, library=tmp_path)
    assert found == nested
    assert found != shared


def test_eight_folder_name_can_vary(tmp_path: Path) -> None:
    job = tmp_path / "2025-110"
    nested = job / "8.0 Field Construction"
    (nested / "2.0 IFC Drawings & Transmittals").mkdir(parents=True)
    found = find_field_folder("2025-110", job, library=tmp_path)
    assert found == nested


def test_two_eight_folders_are_not_guessed(tmp_path: Path) -> None:
    job = tmp_path / "2026-Tanzim"
    (job / "8.0 Construction").mkdir(parents=True)
    (job / "8.0 Field Construction Folder").mkdir()
    assert find_field_folder("2026-Tanzim", job, library=tmp_path) is None


def test_place_pdf_replaces_older_rev_and_form_goes_in_transmittals(tmp_path: Path) -> None:
    root = _field(tmp_path)
    source = tmp_path / "2024-003-1-1 REV 1.pdf"
    source.write_bytes(b"new")
    placed = place_field_pdf(root, source)
    ifc = root / "2.0 IFC Drawings & Transmittals"
    assert placed == ifc / "2024-003-1-1 REV 1.pdf"
    assert placed.read_bytes() == b"new"
    assert not (ifc / "2024-003-1-1 REV 0.pdf").exists()
    form = tmp_path / "FT-2024-003-3.pdf"
    form.write_bytes(b"form")
    copied = place_field_form(root, form)
    assert copied == ifc / "Transmittals" / "FT-2024-003-3.pdf"
    with pytest.raises(LogError):
        place_field_pdf(tmp_path / "empty", source)
