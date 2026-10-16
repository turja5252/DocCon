# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json
from pathlib import Path

from doccon.kinds import BOTH, CLIENT, FIELD, SHOP
from doccon.match import LocatedPdf
from doccon.pack_state import (
    PACK_SCHEMA,
    ClientPack,
    cover_recipients,
    load_client_pack,
    pack_cover_initialized,
    pack_cover_is_saved,
    pack_recipients_saved,
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
        client="Gibson",
        location="Hardisty",
        tag="TK12",
        po="4500123",
        wo="WO-14",
        moc="MOC-9",
        pep_fields_saved=True,
        selected_keys=("P2024-15578",),
        located_pdfs={"P2024-15578": LocatedPdf(str(tmp_path / "sheet.pdf"))},
        next_edits={"P2024-15578": {"outgoing_rev": "B", "status": "IFI"}},
    )
    dest = save_client_pack(tmp_path, pack)
    assert dest == pack_path(tmp_path)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded == pack


def test_shop_and_field_folders_travel_with_the_pack(tmp_path: Path) -> None:
    shop = tmp_path / "1.0 Current IFC Drawings" / "2026-Tanzim"
    field = tmp_path / "2026-Tanzim" / "8.0 Field Construction"
    pack = ClientPack(
        job_number="2026-Tanzim",
        shop_folder=str(shop),
        field_folder=str(field),
    )
    save_client_pack(tmp_path, pack)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.shop_folder == str(shop)
    assert loaded.field_folder == str(field)


def test_cover_recipients_stay_per_kind() -> None:
    pack = ClientPack(
        job_number="2026-Tanzim",
        to_line="client@example.com",
        cc_line="pm@x.com",
    )
    shop = with_cover_recipients(pack, SHOP, "", "")
    field = with_cover_recipients(shop, FIELD, "foreman@x.com", "")
    client = with_cover_recipients(field, CLIENT, "new@example.com", "cc@example.com")
    both = with_cover_recipients(client, BOTH, "shop@x.com", "field@x.com")
    assert cover_recipients(client, CLIENT) == ("new@example.com", "cc@example.com")
    assert cover_recipients(client, SHOP) == ("", "")
    assert cover_recipients(client, FIELD) == ("foreman@x.com", "")
    assert both == client


def test_saved_job_fields_count_as_a_saved_cover() -> None:
    assert pack_cover_initialized(ClientPack(job_number="2026-Tanzim", client="Gibson")) is True
    assert pack_cover_initialized(ClientPack(job_number="2026-Tanzim", moc="MOC-9")) is True
    assert pack_cover_initialized(ClientPack(job_number="2026-Tanzim", client="N/A")) is False


def test_saved_cover_skips_the_letter_read(tmp_path: Path) -> None:
    assert pack_cover_is_saved(None) is False
    assert pack_cover_is_saved(ClientPack(job_number="2026-Tanzim")) is False
    assert pack_cover_is_saved(ClientPack(job_number="2026-Tanzim", to_line="a@b.com")) is True
    blank = ClientPack(job_number="2026-Tanzim", cover_captured=True)
    assert pack_cover_is_saved(blank) is True
    save_client_pack(tmp_path, blank)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.cover_captured is True
    assert pack_cover_is_saved(loaded) is True
    assert pack_recipients_saved(None) is False
    assert pack_recipients_saved(blank) is False
    assert pack_recipients_saved(ClientPack(job_number="2026-Tanzim", to_line="a@b.com")) is True


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


def test_located_pdfs_keep_email_dropped_metadata(tmp_path: Path) -> None:
    dropped = tmp_path / "3.0 Doc Con" / "DocCon" / "dropped" / "sheet.pdf"
    dropped.parent.mkdir(parents=True)
    dropped.write_bytes(b"%PDF")
    pack = ClientPack(
        job_number="2026-Tanzim",
        located_pdfs={"P2024-15578": LocatedPdf(str(dropped), email_dropped=True)},
    )
    dest = save_client_pack(tmp_path, pack)
    raw = dest.read_text(encoding="utf-8")
    assert '"email_dropped": true' in raw
    assert "token" not in raw.casefold()
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    rec = loaded.located_pdfs["P2024-15578"]
    assert rec.path == str(dropped)
    assert rec.email_dropped is True


def test_load_legacy_dropped_path_is_email_dropped(tmp_path: Path) -> None:
    dest = pack_path(tmp_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dropped = tmp_path / "3.0 Doc Con" / "DocCon" / "dropped" / "sheet.pdf"
    dest.write_text(
        json.dumps({"job_number": "2026-Tanzim", "located_pdfs": {"P2024-1": str(dropped)}}) + "\n",
        encoding="utf-8",
    )
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    rec = loaded.located_pdfs["P2024-1"]
    assert rec.email_dropped is True
    assert rec.path == str(dropped)


def test_round_trip_jira_id_next(tmp_path: Path) -> None:
    pack = ClientPack(
        job_number="2026-Tanzim",
        selected_keys=("P2024-15578",),
        issued="2026-09-11",
        expected="2026-09-22",
        next_edits={"P2024-15578": {"drawing_id": "2026-Tanzim-1-STWD", "title": "SPIRAL STAIRWAY"}},
    )
    save_client_pack(tmp_path, pack)
    loaded = load_client_pack(tmp_path, "2026-Tanzim")
    assert loaded is not None
    assert loaded.next_edits == {
        "P2024-15578": {"drawing_id": "2026-Tanzim-1-STWD", "title": "SPIRAL STAIRWAY"}
    }


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


def test_editor_keeps_a_saved_to_when_the_cover_box_is_empty() -> None:
    from doccon.pack_state import editor_to_line

    saved = editor_to_line("tanzim@ijij.com", "", current=True)
    assert saved == "tanzim@ijij.com"
    both = editor_to_line("tanzim@ijij.com", "tanzim@ijij.com", current=True)
    assert both == "tanzim@ijij.com"
    other = editor_to_line("shop@eliteintegrityservices.com", "ignored@example.com", current=False)
    assert other == "shop@eliteintegrityservices.com"
