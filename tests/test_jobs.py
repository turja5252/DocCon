# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.jobs import find_job_folder, localize_dropbox_path, team_dropbox_tail


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
