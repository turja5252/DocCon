# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

import pytest

from doccon.client_log import LogError
from doccon.confirm import _copy_field_pack, _preflight_field_copies
from doccon.field_place import (
    field_folder_choices,
    find_field_folder,
    place_field_form,
    place_field_pdf,
)


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


def _job_field(tmp_path: Path) -> Path:
    """The 2026-118 shape: 2.0 and 5.0 under 8.0, 3.1–3.6 under 3.0, and a folder that is not a destination."""
    root = tmp_path / "8.0 Field Construction Folder (2026-118)"
    (root / "2.0 IFC Drawings & Transmittals").mkdir(parents=True)
    (root / "1.0 Something Else").mkdir()
    (root / "5.0 Weld Procedures & Welder Quals").mkdir()
    qc = root / "3.0 QC Forms & Reports"
    for name in (
        "3.1 QC Forms",
        "3.2  WID, Heat and RT Maps",
        "3.3 Completed QC Forms",
        "3.5 Painting-Coating Reports",
        "3.6 Insulation Reports",
    ):
        (qc / name).mkdir(parents=True)
    return root


def test_field_choices_are_two_the_qc_children_and_five(tmp_path: Path) -> None:
    root = _job_field(tmp_path)
    choices = field_folder_choices(root)
    assert choices[0] == "2.0 IFC Drawings & Transmittals"
    assert "3.1 QC Forms" in choices
    assert "3.2  WID, Heat and RT Maps" in choices
    assert "3.5 Painting-Coating Reports" in choices
    assert "5.0 Weld Procedures & Welder Quals" in choices
    assert "3.4 Third Party NDE" not in choices
    assert "3.0 QC Forms & Reports" not in choices
    assert "1.0 Something Else" not in choices


def test_picked_folder_gets_the_pdf_and_the_form_stays_in_two(tmp_path: Path) -> None:
    root = _job_field(tmp_path)
    source = tmp_path / "2026-118-1-1 REV 1.pdf"
    source.write_bytes(b"weld")
    (root / "5.0 Weld Procedures & Welder Quals" / "2026-118-1-1 REV 0.pdf").write_bytes(b"old")
    placed = place_field_pdf(root, source, "5.0 Weld Procedures & Welder Quals")
    assert placed.parent.name.startswith("5.0")
    assert placed.read_bytes() == b"weld"
    assert not (placed.parent / "2026-118-1-1 REV 0.pdf").exists()
    ifc = root / "2.0 IFC Drawings & Transmittals"
    assert not (ifc / source.name).exists()
    form = tmp_path / "FT-2026-118-1.pdf"
    form.write_bytes(b"form")
    _preflight_field_copies(root, [(source, "3.1 QC Forms")])
    _copy_field_pack(root, [(source, "3.1 QC Forms")], form)
    assert (root / "3.0 QC Forms & Reports" / "3.1 QC Forms" / source.name).read_bytes() == b"weld"
    assert (ifc / "Transmittals" / form.name).read_bytes() == b"form"
    with pytest.raises(LogError, match="3.4"):
        _preflight_field_copies(root, [(source, "3.4 Third Party NDE")])
