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


def _drawing(**kwargs):
    from doccon.register import DrawingRow

    values = {
        "key": "P2024-1",
        "summary": "2026-Tanzim-1-1 Drawing-1",
        "drawing_id": "2026-Tanzim-1-1",
        "title": "Drawing-1",
        "status": "To Do",
        "job_number": "2026-Tanzim",
        "outgoing_rev": "A",
        "purpose": "Approval",
        "parent_summary": "Drawing Package",
    }
    values.update(kwargs)
    return DrawingRow(**values)


def test_preflight_rejects_bad_date() -> None:
    from dataclasses import replace

    from doccon.jira_client import preflight_drawing_update

    current = _drawing()
    nxt = replace(current, due_date="soon")
    with pytest.raises(JiraError, match="YYYY-MM-DD"):
        preflight_drawing_update("https://example.atlassian.net", "a@b.c", "token", current, nxt)


def test_preflight_rejects_blocked_status(monkeypatch) -> None:
    from dataclasses import replace

    from doccon import jira_client

    current = _drawing(status="To Do")
    nxt = replace(current, status="IFC")
    monkeypatch.setattr(
        jira_client,
        "list_transitions",
        lambda *_args, **_kwargs: [
            {"id": "6", "name": "In Progress", "to": "In Progress"},
            {"id": "41", "name": "Done", "to": "Done"},
        ],
    )
    with pytest.raises(JiraError, match="Cannot move"):
        jira_client.preflight_drawing_update(
            "https://example.atlassian.net", "a@b.c", "token", current, nxt
        )


def test_apply_jira_updates_rolls_back_on_later_failure(monkeypatch) -> None:
    from dataclasses import replace

    from doccon import jira_client

    applied: list[str] = []
    reverted: list[str] = []

    def fake_apply(_site, _email, _token, _current, nxt) -> None:
        if nxt.key == "P2024-2":
            raise JiraError("second failed")
        applied.append(nxt.key)

    def fake_revert(_site, _email, _token, _current, nxt) -> None:
        reverted.append(nxt.key)

    monkeypatch.setattr(jira_client, "apply_drawing_update", fake_apply)
    monkeypatch.setattr(jira_client, "revert_drawing_update", fake_revert)
    first = _drawing(key="P2024-1")
    second = _drawing(key="P2024-2")
    with pytest.raises(JiraError, match="second failed"):
        jira_client.apply_jira_updates(
            "https://example.atlassian.net",
            "a@b.c",
            "token",
            [
                (first, replace(first, outgoing_rev="B")),
                (second, replace(second, outgoing_rev="B")),
            ],
        )
    assert applied == ["P2024-1"]
    assert reverted == ["P2024-1"]


def test_fetch_drawings_includes_job_tree(monkeypatch) -> None:
    from doccon import jira_client

    def fake_request(_site, _email, _token, _method, _path, body=None):
        jql = (body or {}).get("jql", "")
        if "issuetype = Project" in jql:
            return {
                "issues": [
                    {
                        "key": "P2024-15553",
                        "fields": {"issuetype": {"name": "Project"}, "summary": "2026-Tanzim"},
                    }
                ],
                "isLast": True,
            }
        if "parent in (P2024-15553)" in jql:
            return {
                "issues": [
                    {
                        "key": "P2024-QC",
                        "fields": {
                            "summary": "ITP package",
                            "issuetype": {"name": "Task"},
                            "customfield_10289": [
                                {"value": "5 - QC - WO, ITP, NDE Records, Procedures - EDDI"}
                            ],
                        },
                    }
                ],
                "isLast": True,
            }
        if "parent in (P2024-QC)" in jql:
            return {
                "issues": [
                    {
                        "key": "P2024-ITP1",
                        "fields": {
                            "summary": "2026-Tanzim-ITP ITP-1",
                            "issuetype": {"name": "Sub-task"},
                            "customfield_10289": [
                                {"value": "5 - QC - WO, ITP, NDE Records, Procedures - EDDI"}
                            ],
                        },
                    }
                ],
                "isLast": True,
            }
        return {
            "issues": [
                {
                    "key": "P2024-15578",
                    "fields": {
                        "summary": "2026-Tanzim-1-1 Drawing-1",
                        "issuetype": {"name": "Sub-task"},
                        "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
                    },
                }
            ],
            "isLast": True,
        }

    monkeypatch.setattr(jira_client, "_request", fake_request)
    rows = fetch_drawings("https://example.atlassian.net", "a@b.c", "token", "2026-Tanzim", "P2024")
    assert [row.key for row in rows] == ["P2024-15578", "P2024-ITP1", "P2024-QC"]
    from doccon.jira_client import fetch_job_pack

    _rows, project = fetch_job_pack("https://example.atlassian.net", "a@b.c", "token", "2026-Tanzim", "P2024")
    assert project is not None
    assert project.key == "P2024-15553"
    assert project.summary == "2026-Tanzim"


def test_fetch_drawings_drops_generic(monkeypatch) -> None:
    from doccon import jira_client

    def fake_request(_site, _email, _token, _method, _path, body=None):
        jql = (body or {}).get("jql", "")
        if "issuetype = Project" in jql:
            return {"issues": [], "isLast": True}
        return {
            "issues": [
                {
                    "key": "P2024-G",
                    "fields": {
                        "summary": "Generic task",
                        "issuetype": {"name": "Task"},
                        "customfield_10289": [{"value": "0 - Generic Task"}],
                    },
                },
                {
                    "key": "P2024-1",
                    "fields": {
                        "summary": "2026-Tanzim-1-1 Drawing-1",
                        "issuetype": {"name": "Sub-task"},
                        "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
                    },
                },
            ],
            "isLast": True,
        }

    monkeypatch.setattr(jira_client, "_request", fake_request)
    rows = fetch_drawings("https://example.atlassian.net", "a@b.c", "token", "2026-Tanzim", "P2024")
    assert [row.key for row in rows] == ["P2024-1"]


def test_field_update_does_not_silence_watchers(monkeypatch) -> None:
    from doccon import jira_client

    seen: list[str] = []

    def fake_request(_site, _email, _token, method, path, body=None):
        seen.append(f"{method} {path}")
        return {}

    monkeypatch.setattr(jira_client, "_request", fake_request)
    jira_client.update_drawing_fields(
        "https://example.atlassian.net", "a@b.c", "token", _drawing()
    )
    assert seen
    assert "notifyUsers=false" not in seen[0]


def test_parse_rev_option_lists_uses_allowed_values() -> None:
    from doccon.jira_client import parse_rev_option_lists

    meta = {
        "fields": {
            "customfield_10280": {
                "schema": {
                    "type": "option",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:select",
                },
                "allowedValues": [{"value": "0"}, {"value": "A"}, {"value": "B"}, {"value": "0"}],
            },
            "customfield_10283": {
                "schema": {
                    "type": "string",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textfield",
                },
            },
            "customfield_10285": {
                "schema": {"type": "option"},
                "allowedValues": [{"value": "IFC-1"}],
            },
        }
    }
    lists = parse_rev_option_lists(meta)
    assert lists["outgoing_rev"] == ("", "0", "A", "B")
    assert "incoming_rev" not in lists
    assert lists["shop_ifc_rev"] == ("", "IFC-1")
    assert "field_ifc_rev" not in lists


def test_fetch_rev_option_lists_stubs_editmeta(monkeypatch) -> None:
    from doccon import jira_client

    def fake_request(_site, _email, _token, method, path, body=None):
        assert method == "GET"
        assert path.endswith("/editmeta")
        return {
            "fields": {
                "customfield_10280": {
                    "schema": {"type": "option"},
                    "allowedValues": [{"value": "0"}, {"value": "A"}],
                }
            }
        }

    monkeypatch.setattr(jira_client, "_request", fake_request)
    lists = jira_client.fetch_rev_option_lists(
        "https://example.atlassian.net", "a@b.c", "token", "P2024-1"
    )
    assert lists["outgoing_rev"] == ("", "0", "A")
    assert jira_client.fetch_rev_option_lists(
        "https://example.atlassian.net", "a@b.c", "token", ""
    ) == {}
