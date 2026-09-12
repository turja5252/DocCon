# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from pathlib import Path

from doccon.kinds import CLIENT, FIELD, SHOP
from doccon.pack_state import (
    PACK_SCHEMA,
    ClientPack,
    cover_recipients,
    load_client_pack,
    pack_path,
    save_client_pack,
    with_cover_recipients,
)


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
        located_pdfs={"P2024-15578": str(tmp_path / "sheet.pdf")},
        next_edits={"P2024-15578": {"outgoing_rev": "B", "status": "IFI"}},
    )
    dest = save_client_pack(tmp_path, pack)
    assert dest == pack_path(tmp_path)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded == pack


def test_cover_recipients_stay_per_kind() -> None:
    pack = ClientPack(
        job_number="2026-Tanzim",
        to_line="client@example.com",
        cc_line="pm@x.com",
    )
    shop = with_cover_recipients(pack, SHOP, "", "")
    field = with_cover_recipients(shop, FIELD, "foreman@x.com", "")
    assert cover_recipients(field, CLIENT) == ("client@example.com", "pm@x.com")
    assert cover_recipients(field, SHOP) == ("", "")
    assert cover_recipients(field, FIELD) == ("foreman@x.com", "")


def test_missing_pack_is_none(tmp_path: Path) -> None:
    assert load_client_pack(tmp_path, "2026-Tanzim") is None
    assert load_client_pack(None, "2026-Tanzim") is None


def test_round_trip_next_edits(tmp_path: Path) -> None:
    pack = ClientPack(
        job_number="2026-Tanzim",
        next_edits={
            "P2024-15578": {
                "status": "IFI",
                "title": "Drawing-1 revised",
                "outgoing_rev": "B",
                "client_document_number": "CNRL-T-101",
                "submission_date": "2026-09-11",
                "eddi_status": "1 - Fabrication Drawings - EDDI",
            }
        },
    )
    dest = save_client_pack(tmp_path, pack)
    raw = dest.read_text(encoding="utf-8")
    assert "token" not in raw.casefold()
    assert '"schema_version"' in raw
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.schema_version == PACK_SCHEMA
    assert loaded.next_edits == pack.next_edits
    assert loaded.selected_keys == ()


def test_load_skips_junk_next_edits(tmp_path: Path) -> None:
    dest = pack_path(tmp_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        '{"job_number": "2026-Tanzim", "next_edits": {"P2024-1": {"outgoing_rev": "C"}, "": {}, "x": "nope"}}\n',
        encoding="utf-8",
    )
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.next_edits == {"P2024-1": {"outgoing_rev": "C"}}
