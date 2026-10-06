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

    def fake_apply(_site, _email, _token, _current, nxt, _options=()) -> None:
        if nxt.key == "P2024-2":
            raise JiraError("second failed")
        applied.append(nxt.key)

    def fake_revert(_site, _email, _token, _current, nxt, _options=()) -> None:
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

    steps: list[str] = []
    _rows, project = fetch_job_pack(
        "https://example.atlassian.net", "a@b.c", "token", "2026-Tanzim", "P2024", on_step=steps.append
    )
    assert steps[0] == "drawings"
    assert "children" in steps
    assert project is not None
    assert project.key == "P2024-15553"
    assert project.summary == "2026-Tanzim"


def test_fetch_job_pack_says_not_found_when_only_a_child_job_matches(monkeypatch) -> None:
    from doccon import jira_client

    def fake_request(_site, _email, _token, _method, _path, body=None):
        jql = (body or {}).get("jql", "")
        if "issuetype = Project" in jql:
            return {
                "issues": [
                    {
                        "key": "P2024-70",
                        "fields": {
                            "issuetype": {"name": "Project"},
                            "summary": "2026-070-1",
                            "customfield_10300": "2026-070-1",
                        },
                    }
                ],
                "isLast": True,
            }
        return {
            "issues": [
                {
                    "key": "P2024-71",
                    "fields": {
                        "summary": "2026-070-1-1 Drawing",
                        "issuetype": {"name": "Sub-task"},
                        "customfield_10300": "2026-070-1",
                    },
                }
            ],
            "isLast": True,
        }

    monkeypatch.setattr(jira_client, "_request", fake_request)
    with pytest.raises(JiraError, match="2026-070 was not found on Jira"):
        jira_client.fetch_job_pack(
            "https://example.atlassian.net", "a@b.c", "token", "2026-070", "P2024"
        )


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


def _capture_puts(monkeypatch) -> list[dict]:
    """Every PUT body apply_drawing_update sends, so a second summary write would show."""
    from doccon import jira_client

    sent: list[dict] = []

    def fake_request(_site, _email, _token, method, _path, body=None):
        if method == "PUT":
            sent.append(dict(body or {}))
        return {}

    monkeypatch.setattr(jira_client, "_request", fake_request)
    return sent


def _summaries(puts: list[dict]) -> list[str]:
    return [
        body["fields"]["summary"]
        for body in puts
        if isinstance(body.get("fields"), dict) and "summary" in body["fields"]
    ]


def _apply(current, nxt) -> None:
    from doccon import jira_client

    jira_client.apply_drawing_update(
        "https://example.atlassian.net", "a@b.c", "token", current, nxt
    )


def test_summary_write_keeps_description_when_only_the_id_changed(monkeypatch) -> None:
    from dataclasses import replace

    puts = _capture_puts(monkeypatch)
    current = _drawing(summary="2026-Tanzim-1-1 Drawing-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1")
    nxt = replace(current, drawing_id="2026-Tanzim-1-2")
    _apply(current, nxt)
    assert _summaries(puts) == ["2026-Tanzim-1-2 Drawing-1"]


def test_summary_write_keeps_id_when_only_the_description_changed(monkeypatch) -> None:
    from dataclasses import replace

    puts = _capture_puts(monkeypatch)
    current = _drawing(summary="2026-Tanzim-1-1 Drawing-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1")
    nxt = replace(current, title="Roof stair detail")
    _apply(current, nxt)
    assert _summaries(puts) == ["2026-Tanzim-1-1 Roof stair detail"]


def test_both_halves_dirty_send_one_summary_field(monkeypatch) -> None:
    from dataclasses import replace

    puts = _capture_puts(monkeypatch)
    current = _drawing(summary="2026-Tanzim-1-1 Drawing-1", drawing_id="2026-Tanzim-1-1", title="Drawing-1")
    nxt = replace(current, drawing_id="2026-Tanzim-1-STWD", title="SPIRAL STAIRWAY")
    _apply(current, nxt)
    assert _summaries(puts) == ["2026-Tanzim-1-STWD SPIRAL STAIRWAY"]
    assert sum(1 for body in puts if "summary" in (body.get("fields") or {})) == 1


def test_summary_write_has_no_trailing_space_without_a_description(monkeypatch) -> None:
    from dataclasses import replace

    puts = _capture_puts(monkeypatch)
    current = _drawing(summary="2026-Tanzim-ITP-1-1", drawing_id="2026-Tanzim-ITP-1-1", title="")
    nxt = replace(current, drawing_id="2026-Tanzim-ITP-1-2")
    _apply(current, nxt)
    assert _summaries(puts) == ["2026-Tanzim-ITP-1-2"]


def test_preflight_rejects_blank_or_spaced_jira_id(monkeypatch) -> None:
    from dataclasses import replace

    from doccon import jira_client

    writes: list[str] = []
    monkeypatch.setattr(
        jira_client,
        "apply_drawing_update",
        lambda *_args, **_kwargs: writes.append("wrote"),
    )
    current = _drawing(key="P2024-77")
    for bad in ("", "   ", "2026-Tanzim-1-1 Drawing-1"):
        nxt = replace(current, drawing_id=bad)
        with pytest.raises(JiraError) as caught:
            jira_client.run_jira_register_update(
                "https://example.atlassian.net", "a@b.c", "token", [(current, nxt)]
            )
        assert "P2024-77" in str(caught.value)
    assert writes == []


def test_preflight_leaves_an_untouched_multiword_id_alone() -> None:
    from dataclasses import replace

    from doccon.jira_client import preflight_drawing_update

    current = _drawing(key="P2024-CWB", summary="CWB Certificate", drawing_id="CWB Certificate", title="")
    nxt = replace(current, title="CWB Certification")
    preflight_drawing_update("https://example.atlassian.net", "a@b.c", "token", current, nxt)


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


EDDI_GROUP_5 = "5 - QC - WO, ITP, NDE Records, Procedures - EDDI"


def _eddi_editmeta(*options) -> dict:
    return {
        "fields": {
            "customfield_10289": {
                "schema": {"type": "array", "items": "option"},
                "allowedValues": list(options),
            }
        }
    }


def test_eddi_write_uses_option_id_from_that_issue(monkeypatch) -> None:
    """Group 5 has commas inside the label. It must go as one option id, not four values."""
    from doccon import jira_client

    sent: list[dict] = []

    def fake_request(_site, _email, _token, method, path, body=None):
        if path.endswith("/editmeta"):
            return _eddi_editmeta({"value": EDDI_GROUP_5, "id": "10420"})
        sent.append(body or {})
        return {}

    monkeypatch.setattr(jira_client, "_request", fake_request)
    options = jira_client.fetch_eddi_options(
        "https://example.atlassian.net", "a@b.c", "token", "P2024-1"
    )
    jira_client.update_drawing_fields(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        _drawing(eddi_status=EDDI_GROUP_5),
        options,
    )
    assert sent[0]["fields"]["customfield_10289"] == [{"id": "10420"}]


def test_eddi_label_resolves_across_case_dash_and_whitespace() -> None:
    from doccon.jira_client import parse_eddi_options
    from doccon.register import eddi_field

    options = parse_eddi_options(_eddi_editmeta({"value": EDDI_GROUP_5, "id": "10420"}))
    typed = "5 – qc -  wo, itp, nde records, procedures – eddi  "
    assert eddi_field(typed, options) == [{"id": "10420"}]


def test_eddi_write_falls_back_to_label_without_an_id() -> None:
    from doccon.jira_client import parse_eddi_options
    from doccon.register import eddi_field

    options = parse_eddi_options(_eddi_editmeta({"value": EDDI_GROUP_5}))
    assert eddi_field("5 - qc - wo, itp, nde records, procedures - eddi", options) == [
        {"value": EDDI_GROUP_5}
    ]


def test_preflight_aborts_when_eddi_option_is_not_on_that_issue() -> None:
    from dataclasses import replace

    from doccon.jira_client import parse_eddi_options, preflight_jira_updates

    options = parse_eddi_options(
        _eddi_editmeta({"value": "1 - Fabrication Drawings - EDDI", "id": "10401"})
    )
    current = _drawing(eddi_status="1 - Fabrication Drawings - EDDI")
    nxt = replace(current, eddi_status=EDDI_GROUP_5)
    with pytest.raises(JiraError) as caught:
        preflight_jira_updates(
            "https://example.atlassian.net",
            "a@b.c",
            "token",
            [(current, nxt)],
            {"P2024-1": options},
        )
    message = str(caught.value)
    assert "P2024-1" in message
    assert EDDI_GROUP_5 in message
    assert "1 - Fabrication Drawings - EDDI" in message


def test_confirm_preflight_failure_writes_nothing(monkeypatch) -> None:
    from dataclasses import replace

    from doccon import jira_client
    from doccon.jira_client import parse_eddi_options

    writes: list[str] = []
    monkeypatch.setattr(
        jira_client,
        "apply_drawing_update",
        lambda *_args, **_kwargs: writes.append("wrote"),
    )
    options = parse_eddi_options(
        _eddi_editmeta({"value": "1 - Fabrication Drawings - EDDI", "id": "10401"})
    )
    current = _drawing()
    nxt = replace(current, eddi_status=EDDI_GROUP_5)
    with pytest.raises(JiraError, match="is not an option on that issue"):
        jira_client.run_jira_register_update(
            "https://example.atlassian.net",
            "a@b.c",
            "token",
            [(current, nxt)],
            {"P2024-1": options},
        )
    assert writes == []


def test_eddi_contexts_fetch_one_editmeta_per_issue_type(monkeypatch) -> None:
    from doccon import jira_client

    asked: list[str] = []

    def fake_request(_site, _email, _token, _method, path, body=None):
        asked.append(path)
        if "P2024-9" in path:
            return _eddi_editmeta({"value": "8 - Document Control - EDDI", "id": "10408"})
        return _eddi_editmeta({"value": EDDI_GROUP_5, "id": "10420"})

    monkeypatch.setattr(jira_client, "_request", fake_request)
    rows = [
        _drawing(key="P2024-1", issue_type="Sub-task"),
        _drawing(key="P2024-2", issue_type="Sub-task"),
        _drawing(key="P2024-9", issue_type="Task"),
    ]
    contexts = jira_client.fetch_eddi_contexts(
        "https://example.atlassian.net", "a@b.c", "token", rows
    )
    assert len(asked) == 2
    assert contexts["P2024-1"] == contexts["P2024-2"]
    assert [option.label for option in contexts["P2024-9"]] == ["8 - Document Control - EDDI"]
    assert contexts["P2024-1"] != contexts["P2024-9"]


def test_update_eddi_status_writes_by_id_and_refuses_a_foreign_option(monkeypatch) -> None:
    from doccon import jira_client
    from doccon.jira_client import parse_eddi_options

    sent: list[dict] = []
    monkeypatch.setattr(
        jira_client, "_request", lambda *args, **kwargs: sent.append(args[-1] or {}) or {}
    )
    options = parse_eddi_options(
        _eddi_editmeta({"value": "1 - Fabrication Drawings - EDDI", "id": "10401"})
    )
    jira_client.update_eddi_status(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        "P2024-1",
        "1 - Fabrication Drawings - EDDI",
        options,
    )
    assert sent[0]["fields"]["customfield_10289"] == [{"id": "10401"}]
    with pytest.raises(JiraError, match="is not an option on that issue"):
        jira_client.update_eddi_status(
            "https://example.atlassian.net",
            "a@b.c",
            "token",
            "P2024-1",
            EDDI_GROUP_5,
            options,
        )
    assert len(sent) == 1


def test_parse_create_eddi_options_drops_generic() -> None:
    from doccon.jira_client import parse_create_eddi_options

    options = parse_create_eddi_options(
        {
            "fields": [
                {
                    "fieldId": "customfield_10289",
                    "allowedValues": [
                        {"id": "10231", "value": "0 - Generic Task"},
                        {"id": "10166", "value": "1 - Fabrication Drawings - EDDI"},
                    ],
                }
            ]
        }
    )
    assert [item.option_id for item in options] == ["10166"]


def test_fetch_parent_tasks_prefers_epic_children(monkeypatch) -> None:
    from doccon import jira_client

    seen: list[str] = []

    def fake_request(_site, _email, _token, _method, _path, body=None):
        jql = (body or {}).get("jql", "")
        seen.append(jql)
        if "issuetype = Task AND parent = P2024-15553" in jql:
            return {
                "issues": [
                    {
                        "key": "P2024-15577",
                        "fields": {
                            "summary": "2026-Tanzim Drawing Package",
                            "issuetype": {"name": "Task"},
                            "customfield_10289": [{"value": "0 - Generic Task"}],
                        },
                    },
                    {
                        "key": "P2024-sub",
                        "fields": {"summary": "not a parent", "issuetype": {"name": "Sub-task"}},
                    },
                ],
                "isLast": True,
            }
        raise AssertionError(jql)

    monkeypatch.setattr(jira_client, "_request", fake_request)
    parents = jira_client.fetch_parent_tasks(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        "2026-Tanzim",
        "P2024",
        "P2024-15553",
    )
    assert [item.key for item in parents] == ["P2024-15577"]
    assert "parent = P2024-15553" in seen[0]


def test_create_subtask_posts_fields(monkeypatch) -> None:
    from doccon import jira_client
    from doccon.register import FieldOption

    sent: list[dict] = []

    def fake_request(_site, _email, _token, method, path, body=None):
        sent.append({"method": method, "path": path, "body": body})
        return {"key": "P2024-99999", "id": "99999"}

    monkeypatch.setattr(jira_client, "_request", fake_request)
    fab = FieldOption(label="1 - Fabrication Drawings - EDDI", option_id="10166")
    key = jira_client.create_subtask(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        jira_project="P2024",
        parent_key="P2024-15577",
        drawing_id="2026-Tanzim-1-3",
        description="ROOF PLAN",
        job_number="2026-Tanzim",
        eddi_label=fab.label,
        eddi_options=(fab,),
        lead_account_ids=("lead-1",),
    )
    assert key == "P2024-99999"
    assert sent[0]["method"] == "POST"
    assert sent[0]["path"] == "/rest/api/3/issue"
    fields = sent[0]["body"]["fields"]
    assert fields["parent"] == {"key": "P2024-15577"}
    assert fields["summary"] == "2026-Tanzim-1-3 ROOF PLAN"
    assert fields["customfield_10300"] == "2026-Tanzim"
    assert fields["customfield_10289"] == [{"id": "10166"}]
    assert fields["customfield_10071"] == [{"accountId": "lead-1"}]


def test_create_subtask_refuses_without_job_number() -> None:
    from doccon.register import FieldOption

    fab = FieldOption(label="1 - Fabrication Drawings - EDDI", option_id="10166")
    with pytest.raises(JiraError, match="Job Number"):
        from doccon.jira_client import create_subtask

        create_subtask(
            "https://example.atlassian.net",
            "a@b.c",
            "token",
            jira_project="P2024",
            parent_key="P2024-15577",
            drawing_id="2026-Tanzim-1-3",
            description="",
            job_number="",
            eddi_label=fab.label,
            eddi_options=(fab,),
        )


def test_fetch_issue_gets_by_key(monkeypatch) -> None:
    from doccon import jira_client

    seen: list[tuple[str, str]] = []

    def fake_request(_site, _email, _token, method, path, body=None):
        seen.append((method, path))
        return {
            "key": "P2024-NEW",
            "fields": {
                "summary": "2026-Tanzim-1-9 Roof",
                "issuetype": {"name": "Sub-task"},
                "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
            },
        }

    monkeypatch.setattr(jira_client, "_request", fake_request)
    row = jira_client.fetch_issue("https://example.atlassian.net", "a@b.c", "token", "P2024-NEW")
    assert row is not None
    assert row.key == "P2024-NEW"
    assert row.drawing_id == "2026-Tanzim-1-9"
    assert seen[0][0] == "GET"
    assert seen[0][1].startswith("/rest/api/3/issue/P2024-NEW?fields=")


def test_wait_for_issue_retries_until_readable(monkeypatch) -> None:
    from doccon import jira_client

    hits = {"n": 0}
    sleeps: list[float] = []

    def fake_fetch(_site, _email, _token, key):
        hits["n"] += 1
        if hits["n"] < 3:
            raise jira_client.JiraError("Jira HTTP 404: not found")
        return _drawing(key=key, drawing_id="2026-Tanzim-1-9")

    monkeypatch.setattr(jira_client, "fetch_issue", fake_fetch)
    row = jira_client.wait_for_issue(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        "P2024-NEW",
        attempts=5,
        delay_s=0.01,
        sleep=sleeps.append,
    )
    assert row.key == "P2024-NEW"
    assert hits["n"] == 3
    assert sleeps == [0.01, 0.01]


def test_fetch_job_pack_including_merges_when_search_lags(monkeypatch) -> None:
    from doccon import jira_client

    created = _drawing(key="P2024-NEW", drawing_id="2026-Tanzim-1-9")
    existing = _drawing(key="P2024-1")
    monkeypatch.setattr(jira_client, "wait_for_issue", lambda *_a, **_k: created)
    monkeypatch.setattr(jira_client, "fetch_job_pack", lambda *_a, **_k: ([existing], None))
    rows, project = jira_client.fetch_job_pack_including(
        "https://example.atlassian.net",
        "a@b.c",
        "token",
        "2026-Tanzim",
        "P2024",
        "P2024-NEW",
    )
    assert project is None
    assert {row.key for row in rows} == {"P2024-1", "P2024-NEW"}

