# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import pytest

from doccon.jira_client import (
    JiraError,
    fetch_drawings,
    normalize_site,
    parse_transitions,
    transition_drawing,
    transition_id_for_status,
)


def test_normalize_site_adds_https() -> None:
    assert normalize_site("eliteintegrityservices.atlassian.net") == "https://eliteintegrityservices.atlassian.net"


def test_fetch_drawings_rejects_bad_job() -> None:
    with pytest.raises(JiraError, match="Job Number"):
        fetch_drawings("https://example.atlassian.net", "a@b.c", "token", "2026 Tanzim", "P2024")


def test_parse_transitions_uses_destination_status() -> None:
    rows = parse_transitions(
        {
            "transitions": [
                {"id": "4", "name": "IFC", "to": {"name": "IFC"}, "isAvailable": False},
                {"id": "11", "name": "in progress from IFC", "to": {"name": "In Progress"}},
                {"id": "41", "name": "Done", "to": {"name": "Done"}, "isAvailable": True},
            ]
        }
    )
    assert [item["id"] for item in rows] == ["11", "41"]
    assert transition_id_for_status(rows, "In Progress") == "11"
    assert transition_id_for_status(rows, "IFC") == ""


def test_transition_rejects_blocked_status(monkeypatch) -> None:
    from doccon import jira_client

    monkeypatch.setattr(
        jira_client,
        "list_transitions",
        lambda *_args, **_kwargs: [
            {"id": "6", "name": "In Progress", "to": "In Progress"},
            {"id": "41", "name": "Done", "to": "Done"},
        ],
    )
    with pytest.raises(JiraError, match="From here Jira allows: In Progress, Done"):
        transition_drawing("https://example.atlassian.net", "a@b.c", "token", "P2024-1", "To Do", "IFC")
