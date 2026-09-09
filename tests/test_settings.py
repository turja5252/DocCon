# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json

from doccon.settings import AppSettings, load_settings, save_settings


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
    path.write_text(json.dumps({"site": "https://example.atlassian.net", "email": "a@b.c", "token": "SECRET"}), encoding="utf-8")
    loaded = load_settings()
    assert loaded.email == "a@b.c"
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert "token" not in rewritten
