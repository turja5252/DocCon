# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.pack_state import load_client_pack, pack_path, save_client_pack, ClientPack


def test_round_trip_pack(tmp_path: Path) -> None:
    pack = ClientPack(
        job_number="2026-Tanzim",
        pep_path=str(tmp_path / "pep.xlsx"),
        issued="2026-09-08",
        expected="N/A",
        to_line="client@example.com",
        cc_line="pm@eliteintegrityservices.com",
        project_description="Client | Loc: Site",
        selected_keys=("P2024-15578",),
    )
    dest = save_client_pack(tmp_path, pack)
    assert dest == pack_path(tmp_path)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded == pack


def test_missing_pack_is_none(tmp_path: Path) -> None:
    assert load_client_pack(tmp_path, "2026-Tanzim") is None
    assert load_client_pack(None, "2026-Tanzim") is None
