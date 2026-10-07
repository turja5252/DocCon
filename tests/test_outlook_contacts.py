# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json

import pytest

from doccon.outlook_contacts import (
    OPEN_OUTLOOK,
    OutlookContactsError,
    _list_script,
    filter_import_addresses,
    import_saved_emails_from_outlook,
    pick_outlook_directory_account,
)
from doccon.pep import DOC_CONTROL_FROM
from doccon.settings import AppSettings, load_settings, save_settings


def test_pick_outlook_directory_account_prefers_elite() -> None:
    assert (
        pick_outlook_directory_account(
            ["sarah.chan@eliteintegrityservices.com", DOC_CONTROL_FROM]
        )
        == DOC_CONTROL_FROM
    )
    assert (
        pick_outlook_directory_account(["chris.samm@eliteintegrityservices.com"])
        == "chris.samm@eliteintegrityservices.com"
    )
    assert pick_outlook_directory_account(["personal@example.com"]) == ""


def test_filter_import_addresses_skips_noreply_and_roles() -> None:
    assert filter_import_addresses(
        [
            "Ada <ada@client.test>",
            "noreply@eliteintegrityservices.com",
            "no-reply@client.test",
            "Shop Lead",
            "not-an-email",
            "bob@client.test",
        ]
    ) == ("ada@client.test", "bob@client.test")


def test_import_outlook_stub_merges_unique(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("doccon.paths.mail_formats_path", lambda: tmp_path / "mail-formats.json")
    save_settings(
        AppSettings(
            email="sarah@example.com",
            saved_emails=("keep@elite.com",),
        )
    )

    def fake_lister() -> list[str]:
        return [
            "keep@elite.com",
            "KEEP@elite.com",
            "Ada <ada@client.test>",
            "noreply@client.test",
            "not-an-email",
            "new@client.test",
        ]

    result = import_saved_emails_from_outlook(lister=fake_lister)
    assert result.added == 2
    assert result.saved_emails == ("keep@elite.com", "ada@client.test", "new@client.test")
    from doccon.pack_mail import load_saved_addresses

    assert load_saved_addresses() == result.saved_emails
    saved = json.loads((tmp_path / "mail-formats.json").read_text(encoding="utf-8"))
    assert saved["saved_addresses"] == ["keep@elite.com", "ada@client.test", "new@client.test"]


def test_import_outlook_failure_leaves_list_unchanged(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("doccon.paths.mail_formats_path", lambda: tmp_path / "mail-formats.json")
    save_settings(AppSettings(email="sarah@example.com", saved_emails=("keep@elite.com",)))

    def boom() -> list[str]:
        raise OutlookContactsError(OPEN_OUTLOOK)

    with pytest.raises(OutlookContactsError, match="Open Outlook") as vis:
        import_saved_emails_from_outlook(lister=boom)
    assert "Traceback" not in str(vis.value)
    assert load_settings().saved_emails == ("keep@elite.com",)


def test_import_outlook_generic_failure_is_short(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("doccon.paths.mail_formats_path", lambda: tmp_path / "mail-formats.json")
    save_settings(AppSettings(email="sarah@example.com", saved_emails=("keep@elite.com",)))

    def boom() -> list[str]:
        raise RuntimeError("COM class not registered")

    with pytest.raises(OutlookContactsError, match="Open Outlook") as vis:
        import_saved_emails_from_outlook(lister=boom)
    assert "COM class" not in str(vis.value)
    assert load_settings().saved_emails == ("keep@elite.com",)


def test_outlook_list_script_reads_gal_and_contacts_without_sending() -> None:
    script = _list_script(r"C:\temp\payload.json")
    assert "GetGlobalAddressList" in script
    assert "GetDefaultFolder" in script
    assert "AddressLists" in script
    assert "CreateItem" not in script
    assert ".Send(" not in script
    assert ".Send $" not in script
    assert "Display()" not in script
