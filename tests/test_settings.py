# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json

from doccon.settings import (
    BOARD_LAYOUT_REV,
    AppSettings,
    append_email,
    load_settings,
    locate_start_dir,
    merge_saved_emails,
    normalize_saved_emails,
    remember_board_col_px,
    remember_job_folder,
    remember_locate_dir,
    remembered_job_folder,
    save_settings,
)


def test_settings_roundtrip_does_not_store_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    save_settings(AppSettings(site="https://eliteintegrityservices.atlassian.net", email="sarah@example.com"))
    saved = json.loads((tmp_path / "EliteIntegrity" / "DocCon" / "settings.json").read_text(encoding="utf-8"))
    assert "token" not in saved
    assert "password" not in saved
    assert saved["email"] == "sarah@example.com"
    loaded = load_settings()
    assert loaded.email == "sarah@example.com"


def test_load_settings_strips_token_if_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "EliteIntegrity" / "DocCon" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"site": "https://example.atlassian.net", "email": "a@b.c", "token": "SECRET"}),
        encoding="utf-8",
    )
    loaded = load_settings()
    assert loaded.email == "a@b.c"
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert "token" not in rewritten


def test_saved_emails_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    save_settings(
        AppSettings(
            email="sarah@example.com",
            saved_emails=("Shop@eliteintegrityservices.com", "shop@eliteintegrityservices.com", "not-an-email"),
        )
    )
    loaded = load_settings()
    assert loaded.saved_emails == ("Shop@eliteintegrityservices.com",)
    saved = json.loads((tmp_path / "EliteIntegrity" / "DocCon" / "settings.json").read_text(encoding="utf-8"))
    assert saved["saved_emails"] == ["Shop@eliteintegrityservices.com"]
    assert "token" not in saved


def test_normalize_and_append_emails() -> None:
    assert normalize_saved_emails("Ada <ada@elite.com>; bob@elite.com") == ("ada@elite.com", "bob@elite.com")
    assert normalize_saved_emails(["ada@elite.com", "Ada@elite.com"]) == ("ada@elite.com",)
    assert append_email("ada@elite.com", "bob@elite.com") == "ada@elite.com; bob@elite.com"
    assert append_email("ada@elite.com", "ADA@elite.com") == "ada@elite.com"


def test_merge_saved_emails_keeps_existing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    save_settings(AppSettings(email="sarah@example.com", saved_emails=("ada@elite.com",)))
    current = load_settings()
    merged = merge_saved_emails(
        current.saved_emails,
        ["ADA@elite.com", "bob@client.test", "not-an-email", "Shop Lead"],
    )
    save_settings(AppSettings(email=current.email, saved_emails=merged))
    loaded = load_settings()
    assert loaded.saved_emails == ("ada@elite.com", "bob@client.test")
    saved = json.loads((tmp_path / "EliteIntegrity" / "DocCon" / "settings.json").read_text(encoding="utf-8"))
    assert saved["saved_emails"] == ["ada@elite.com", "bob@client.test"]
    assert "token" not in saved


def test_last_locate_dir_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    folder = tmp_path / "pdfs"
    folder.mkdir()
    pdf = folder / "EIS-1 (Rev 4).pdf"
    pdf.write_bytes(b"%PDF")
    remember_locate_dir(pdf)
    loaded = load_settings()
    assert loaded.last_locate_dir == str(folder)
    assert locate_start_dir("fallback") == str(folder)
    gone = tmp_path / "gone"
    save_settings(AppSettings(last_locate_dir=str(gone)))
    assert locate_start_dir("fallback") == "fallback"


def test_job_folder_mapping_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    folder = tmp_path / "2.1 Current Jobs" / "2026-049"
    folder.mkdir(parents=True)
    remember_job_folder("2026-049-1", folder)
    loaded = load_settings()
    assert loaded.job_folders["2026-049-1"] == str(folder.resolve())
    assert remembered_job_folder("2026-049-1") == folder.resolve()
    saved = json.loads((tmp_path / "EliteIntegrity" / "DocCon" / "settings.json").read_text(encoding="utf-8"))
    assert "token" not in saved
    assert saved["job_folders"]["2026-049-1"] == str(folder.resolve())


def test_board_col_px_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    remember_board_col_px([80, 90, 100])
    loaded = load_settings()
    assert loaded.board_col_px == (80, 90, 100)
    assert loaded.board_layout_rev == BOARD_LAYOUT_REV
    saved = json.loads((tmp_path / "EliteIntegrity" / "DocCon" / "settings.json").read_text(encoding="utf-8"))
    assert saved["board_col_px"] == [80, 90, 100]
    assert saved["board_layout_rev"] == BOARD_LAYOUT_REV
    assert "token" not in saved


def test_missing_layout_rev_is_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "EliteIntegrity" / "DocCon" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"email": "sarah@example.com", "board_col_px": [94, 180, 564]}),
        encoding="utf-8",
    )
    loaded = load_settings()
    assert loaded.board_col_px == (94, 180, 564)
    assert loaded.board_layout_rev == 0
    from doccon.drawing_board import DESC_COL_INDEX, DESC_COL_PX, merge_col_px

    assert merge_col_px(loaded.board_col_px, loaded.board_layout_rev)[DESC_COL_INDEX] == DESC_COL_PX

