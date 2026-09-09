# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from doccon.register import adopted_summary, drawing_fields_payload, drawing_from_issue, drawings_jql, parse_summary


def test_parse_summary_live_shape() -> None:
    drawing_id, title = parse_summary("2026-075-1-STWD SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL")
    assert drawing_id == "2026-075-1-STWD"
    assert title.startswith("SPIRAL STAIRWAY")


def test_parse_summary_dummy() -> None:
    drawing_id, title = parse_summary("2026-Tanzim-1-1 Drawing-1")
    assert drawing_id == "2026-Tanzim-1-1"
    assert title == "Drawing-1"


def test_drawings_jql_contains_job() -> None:
    jql = drawings_jql("2026-Tanzim")
    assert "2026-Tanzim" in jql
    assert "Drafting" in jql
    assert "Sub-task" in jql


def test_drawing_from_issue_maps_custom_fields() -> None:
    issue = {
        "key": "P2024-15578",
        "fields": {
            "summary": "2026-Tanzim-1-1 Drawing-1",
            "status": {"name": "To Do"},
            "customfield_10300": "2026-Tanzim",
            "customfield_10280": {"value": "A"},
            "customfield_10281": {"value": "Info"},
            "customfield_10283": {"value": "0"},
            "customfield_10284": {"value": "Approved"},
            "customfield_10285": {"value": "0"},
            "customfield_10287": {"value": "0"},
            "customfield_10279": "CNRL-T-101",
            "parent": {"fields": {"summary": "2026-Tanzim Drawing Package"}},
        },
    }
    row = drawing_from_issue(issue)
    assert row.key == "P2024-15578"
    assert row.drawing_id == "2026-Tanzim-1-1"
    assert row.job_number == "2026-Tanzim"
    assert row.outgoing_rev == "A"
    assert row.purpose == "Info"
    assert row.incoming_rev == "0"
    assert row.approval == "Approved"
    assert row.shop_ifc_rev == "0"
    assert row.field_ifc_rev == "0"
    assert row.client_document_number == "CNRL-T-101"
    assert row.parent_summary == "2026-Tanzim Drawing Package"


def test_drawing_fields_payload_skips_blanks() -> None:
    from doccon.register import CLIENT_DOC_FIELD, PURPOSE_FIELD

    row = drawing_from_issue(
        {
            "key": "P2024-1",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "customfield_10280": {"value": "A"},
                "customfield_10281": {"value": "Approval"},
                "customfield_10279": "  CNRL-T-101  ",
            },
        }
    )
    payload = drawing_fields_payload(row)
    assert payload[PURPOSE_FIELD] == {"value": "Approval"}
    assert payload[CLIENT_DOC_FIELD] == "CNRL-T-101"
    assert "customfield_10283" not in payload


def test_adopted_summary_keeps_title() -> None:
    assert adopted_summary("2026-096-1-1 Drawing-1", "2026-096-1-SK1") == "2026-096-1-SK1 Drawing-1"
