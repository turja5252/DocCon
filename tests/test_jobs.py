# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.jobs import (
    find_job_folder,
    job_folder_identity,
    job_folder_keys,
    localize_dropbox_path,
    resolve_job_folder,
    team_dropbox_tail,
)


def test_tail_strips_person_folder() -> None:
    stored = Path(
        r"C:\Users\SarahChan\Elite Integrity Serv Dropbox\Sarah Chan"
        r"\2.0 Current Jobs\2026-096 Borouge\2.0 Drafting\a.pdf"
    )
    tail = team_dropbox_tail(stored)
    assert tail is not None
    assert tail.parts[0] == "2.0 Current Jobs"
    assert "Sarah Chan" not in tail.parts


def test_localize_maps_sarah_path_onto_this_pc(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    local = tanzim / "2.1 Current Jobs" / "2026-096 Borouge" / "2.0 Drafting" / "a.pdf"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"%PDF")
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    sarah = (
        Path(r"C:\Users\SarahChan")
        / "Elite Integrity Serv Dropbox"
        / "Sarah Chan"
        / "2.0 Current Jobs"
        / "2026-096 Borouge"
        / "2.0 Drafting"
        / "a.pdf"
    )
    assert Path(localize_dropbox_path(str(sarah))) == local.resolve()


def test_find_job_folder_on_this_pc_person(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    job = tanzim / "2.1 Current Jobs" / "2026-096 Borouge (103TK001 Manway)"
    job.mkdir(parents=True)
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    assert find_job_folder("2026-096") == job


def test_job_folder_keys_stop_before_year() -> None:
    assert job_folder_keys("2026-049-1") == ["2026-049-1", "2026-049"]
    assert job_folder_keys("2026-049") == ["2026-049"]
    assert job_folder_keys("2026-Tanzim") == ["2026-Tanzim"]


def test_parent_job_folder_when_child_folder_missing(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    parent = tanzim / "2.1 Current Jobs" / "2026-049"
    parent.mkdir(parents=True)
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    assert find_job_folder("2026-049-1") == parent
    assert find_job_folder("2026-049-2") == parent
    assert "2026-049" in job_folder_identity(parent)
    assert "2.1 Current Jobs" in job_folder_identity(parent)


def test_exact_child_folder_wins_over_parent(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    bucket = tanzim / "2.1 Current Jobs"
    parent = bucket / "2026-049"
    exact = bucket / "2026-049-1"
    parent.mkdir(parents=True)
    exact.mkdir()
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    assert find_job_folder("2026-049-1") == exact
    assert find_job_folder("2026-049-2") == parent


def test_ambiguous_job_folders_are_not_picked(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    current = tanzim / "2.1 Current Jobs"
    done = tanzim / "2.1 Completed Jobs"
    (current / "2026-049").mkdir(parents=True)
    (done / "2026-049").mkdir(parents=True)
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    assert find_job_folder("2026-049-1") is None
    assert job_folder_identity(None) == "No Dropbox folder for this Job Number"


def test_remembered_folder_overrides_hunt(tmp_path: Path, monkeypatch) -> None:
    tanzim = tmp_path / "Elite Integrity Serv Dropbox" / "Tanzim Nasir"
    bucket = tanzim / "2.1 Current Jobs"
    hunted = bucket / "2026-049"
    picked = bucket / "picked-root"
    hunted.mkdir(parents=True)
    picked.mkdir()
    (picked / "3.0 Doc Con").mkdir()
    monkeypatch.setattr("doccon.jobs.local_team_dropbox_member_roots", lambda hint=None: [tanzim])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    from doccon.settings import remember_job_folder

    remember_job_folder("2026-049-1", picked)
    assert resolve_job_folder("2026-049-1") == picked.resolve()
    assert find_job_folder("2026-049-1") == hunted
