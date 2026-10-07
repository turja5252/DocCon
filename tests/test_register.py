# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from doccon.register import (
    JobProject,
    adopted_summary,
    drawing_fields_payload,
    drawing_from_issue,
    drawing_id_error,
    drawings_jql,
    jira_project_label,
    job_project_from_issues,
    new_issue_id_error,
    parse_summary,
    summary_from_parts,
)


def test_summary_from_parts_joins_id_and_description() -> None:
    assert summary_from_parts("2026-075-1-STWD", "SPIRAL STAIRWAY") == "2026-075-1-STWD SPIRAL STAIRWAY"
    assert summary_from_parts("2026-075-ITP-1-1", "") == "2026-075-ITP-1-1"
    assert summary_from_parts("2026-075-ITP-1-1", "   ") == "2026-075-ITP-1-1"
    assert not summary_from_parts("2026-075-ITP-1-1", "").endswith(" ")


def test_drawing_id_error_only_rejects_blank_and_inner_space() -> None:
    assert drawing_id_error("P2024-1", "2026-075-1-STWD") == ""
    assert drawing_id_error("P2024-1", "2026-075-ITP-1-1") == ""
    assert drawing_id_error("P2024-1", "2026-Tanzim-1-1") == ""
    assert drawing_id_error("P2024-1", "  2026-Tanzim-1-1  ") == ""
    assert drawing_id_error("P2024-1", "EIS-1") == ""
    assert drawing_id_error("P2024-1", "whatever-shape_1.2") == ""
    blank = drawing_id_error("P2024-1", "   ")
    assert "P2024-1" in blank and "blank" in blank
    assert "P2024-1" in drawing_id_error("P2024-1", "")
    spaced = drawing_id_error("P2024-9", "2026-075-1-1 Drawing")
    assert "P2024-9" in spaced and "space" in spaced
    assert drawing_id_error("P2024-9", "2026-075\t1")


def test_new_issue_id_error_blank_and_space() -> None:
    assert new_issue_id_error("2026-Tanzim-1-3") == ""
    assert "blank" in new_issue_id_error("  ")
    assert "space" in new_issue_id_error("2026-Tanzim 1")


def test_new_issue_preflight_and_payload() -> None:
    from doccon.register import (
        EDDI_FIELD,
        JOB_NUMBER_FIELD,
        PROJECT_LEAD_FIELD,
        SUBTASK_ISSUE_TYPE_ID,
        FieldOption,
        create_eddi_choices,
        create_subtask_payload,
        new_issue_preflight_error,
        people_account_ids,
        summary_from_parts,
    )

    fab = FieldOption(label="1 - Fabrication Drawings - EDDI", option_id="10166")
    generic = FieldOption(label="0 - Generic Task", option_id="10231")
    choices = create_eddi_choices((generic, fab))
    assert [item.option_id for item in choices] == ["10166"]
    assert "blank" in new_issue_preflight_error(
        drawing_id="",
        parent_key="P2024-15577",
        eddi_label=fab.label,
        job_number="2026-Tanzim",
        eddi_options=choices,
    )
    assert "Parent" in new_issue_preflight_error(
        drawing_id="2026-Tanzim-1-3",
        parent_key="",
        eddi_label=fab.label,
        job_number="2026-Tanzim",
        eddi_options=choices,
    )
    assert "Job Number" in new_issue_preflight_error(
        drawing_id="2026-Tanzim-1-3",
        parent_key="P2024-15577",
        eddi_label=fab.label,
        job_number="",
        eddi_options=choices,
    )
    assert "1–9" in new_issue_preflight_error(
        drawing_id="2026-Tanzim-1-3",
        parent_key="P2024-15577",
        eddi_label=generic.label,
        job_number="2026-Tanzim",
        eddi_options=choices,
    )
    assert new_issue_preflight_error(
        drawing_id="2026-Tanzim-1-3",
        parent_key="P2024-15577",
        eddi_label=fab.label,
        job_number="2026-Tanzim",
        eddi_options=choices,
    ) == ""
    assert people_account_ids({"accountId": "abc"}) == ("abc",)
    assert people_account_ids([{"accountId": "a"}, {"accountId": "a"}, {"accountId": "b"}]) == ("a", "b")
    payload = create_subtask_payload(
        jira_project="P2024",
        parent_key="P2024-15577",
        summary=summary_from_parts("2026-Tanzim-1-3", "ROOF PLAN"),
        job_number="2026-Tanzim",
        eddi=fab,
        lead_account_ids=("lead-1",),
    )
    fields = payload["fields"]
    assert fields["issuetype"] == {"id": SUBTASK_ISSUE_TYPE_ID}
    assert fields["parent"] == {"key": "P2024-15577"}
    assert fields["summary"] == "2026-Tanzim-1-3 ROOF PLAN"
    assert fields[JOB_NUMBER_FIELD] == "2026-Tanzim"
    assert fields[EDDI_FIELD] == [{"id": "10166"}]
    assert fields[PROJECT_LEAD_FIELD] == [{"accountId": "lead-1"}]
    assert "reporter" not in fields
    bare = create_subtask_payload(
        jira_project="P2024",
        parent_key="P2024-15577",
        summary="2026-Tanzim-1-3",
        job_number="2026-Tanzim",
        eddi=fab,
    )
    assert PROJECT_LEAD_FIELD not in bare["fields"]


def test_parse_summary_live_shape() -> None:
    drawing_id, title = parse_summary("2026-075-1-STWD SPIRAL STAIRWAY: INSIDE HANDRAIL DETAIL")
    assert drawing_id == "2026-075-1-STWD"
    assert title.startswith("SPIRAL STAIRWAY")


def test_parse_summary_dummy() -> None:
    drawing_id, title = parse_summary("2026-Tanzim-1-1 Drawing-1")
    assert drawing_id == "2026-Tanzim-1-1"
    assert title == "Drawing-1"


def test_parse_summary_id_only_has_no_description() -> None:
    drawing_id, title = parse_summary("2026-075-ITP-1-1")
    assert drawing_id == "2026-075-ITP-1-1"
    assert title == ""


def test_parse_summary_language_after_id() -> None:
    drawing_id, title = parse_summary("2026-075-ITP-1-1 Inspection and Testing Plan for Roof")
    assert drawing_id == "2026-075-ITP-1-1"
    assert title == "Inspection and Testing Plan for Roof"


def test_parse_summary_keeps_code_tokens_then_language() -> None:
    drawing_id, title = parse_summary("2026-075 ITP-1-1 Inspection and Testing Plan")
    assert drawing_id == "2026-075 ITP-1-1"
    assert title == "Inspection and Testing Plan"


def test_parse_summary_size_after_the_id_is_description() -> None:
    drawing_id, title = parse_summary('2026-011-1-6 48" x 36" Sump Replacement Detail')
    assert drawing_id == "2026-011-1-6"
    assert title == '48" x 36" Sump Replacement Detail'
    drawing_id, title = parse_summary('2026-011-1-6 48" x 36"')
    assert drawing_id == "2026-011-1-6"
    assert title == '48" x 36"'


def test_parse_summary_dash_then_language() -> None:
    drawing_id, title = parse_summary("2026-075-ITP-1-1 - Inspection and Testing Plan")
    assert drawing_id == "2026-075-ITP-1-1"
    assert title == "Inspection and Testing Plan"


def test_parse_summary_weld_procedure_wording() -> None:
    from doccon.register import weld_package_description

    drawing_id, title = parse_summary("EIS-1 Welding Procedure Specification")
    assert drawing_id == "EIS-1"
    assert title == "Welding Procedure Specification"
    drawing_id, title = parse_summary("EIS-2-LT Welding Procedure Specification")
    assert drawing_id == "EIS-2-LT"
    assert title == "Welding Procedure Specification"
    drawing_id, title = parse_summary("FM-WPS-01 Welding Procedure Specification")
    assert drawing_id == "FM-WPS-01"
    assert title == "Welding Procedure Specification"
    drawing_id, title = parse_summary("CWB Certificate CWB Certification")
    assert drawing_id == "CWB Certificate"
    assert title == "CWB Certification"
    drawing_id, title = parse_summary("CWB Certificate")
    assert drawing_id == "CWB Certificate"
    assert title == ""
    assert weld_package_description("EIS-12") == "Welding Procedure Specification"
    assert weld_package_description("WS-2026-Tanzim") == "Elite Weld Procedure Summary"
    assert weld_package_description("CWB Certificate") == "CWB Certification"
    assert weld_package_description("2026-Tanzim-1-1") == ""


def test_drawings_jql_is_all_job_issues() -> None:
    from doccon.register import children_of_jql, job_project_jql

    jql = drawings_jql("2026-Tanzim")
    assert "2026-Tanzim" in jql
    assert "Job Number" in jql
    assert "Drafting" not in jql
    assert "Sub-task" not in jql
    assert "issuetype != Project" in jql
    assert 'issuetype = Project' in job_project_jql("2026-Tanzim")
    assert "parent in (P2024-15553, P2024-1)" in children_of_jql(["P2024-15553", "P2024-1"])
    from doccon.register import parent_tasks_by_job_jql, parent_tasks_of_jql

    assert "issuetype = Task" in parent_tasks_of_jql("P2024-15553")
    assert "parent = P2024-15553" in parent_tasks_of_jql("P2024-15553")
    assert "Sub-task" not in parent_tasks_of_jql("P2024-15553")
    assert '"Job Number" ~ "2026-Tanzim"' in parent_tasks_by_job_jql("2026-Tanzim")


def test_jira_project_label_from_project_issue() -> None:
    project = job_project_from_issues(
        [
            {
                "key": "P2024-15577",
                "fields": {"issuetype": {"name": "Task"}, "summary": "Drawing Package"},
            },
            {
                "key": "P2024-15553",
                "fields": {"issuetype": {"name": "Project"}, "summary": "2026-Tanzim Test"},
            },
        ]
    )
    assert project == JobProject(key="P2024-15553", summary="2026-Tanzim Test")
    assert jira_project_label(project) == "P2024-15553  2026-Tanzim Test"
    assert jira_project_label(None) == "No Jira Project for this Job Number"


def test_pack_sort_groups_by_eddi() -> None:
    from doccon.register import eddi_group_title, sort_pack_rows

    generic = drawing_from_issue(
        {
            "key": "P2024-2",
            "fields": {
                "summary": "2026-Tanzim-ITP ITP-1",
                "customfield_10289": [{"value": "0 - Generic Task"}],
            },
        }
    )
    fab = drawing_from_issue(
        {
            "key": "P2024-1",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
            },
        }
    )
    blank = drawing_from_issue(
        {
            "key": "P2024-3",
            "fields": {"summary": "2026-Tanzim-ZZ Later"},
        }
    )
    ordered = sort_pack_rows([blank, fab, generic])
    assert [row.key for row in ordered] == ["P2024-2", "P2024-1", "P2024-3"]
    assert eddi_group_title("") == "Ungrouped"
    assert eddi_group_title("4 - Engineering - EDDI") == "4 - Engineering"
    assert eddi_group_title("1 - Fabrication Drawings - EDDI") == "1 - Fabrication Drawings"


def test_visible_pack_skips_generic() -> None:
    from doccon.register import is_generic_eddi, visible_pack_rows

    generic = drawing_from_issue(
        {
            "key": "P2024-2",
            "fields": {
                "summary": "Generic task",
                "customfield_10289": [{"value": "0 - Generic Task"}],
            },
        }
    )
    fab = drawing_from_issue(
        {
            "key": "P2024-1",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
            },
        }
    )
    assert is_generic_eddi(generic.eddi_status)
    assert not is_generic_eddi(fab.eddi_status)
    assert [row.key for row in visible_pack_rows([generic, fab])] == ["P2024-1"]


def test_drawing_from_issue_maps_custom_fields() -> None:
    issue = {
        "key": "P2024-15578",
        "fields": {
            "summary": "2026-Tanzim-1-1 Drawing-1",
            "status": {"name": "To Do"},
            "customfield_10300": "2026-Tanzim",
            "customfield_10280": {"value": "A"},
            "customfield_10281": {"value": "Info"},
            "customfield_10626": {"value": "Construction"},
            "customfield_10625": {"value": "Planned"},
            "customfield_10283": {"value": "0"},
            "customfield_10284": {"value": "Approved"},
            "customfield_10285": {"value": "0"},
            "customfield_10287": {"value": "0"},
            "customfield_10279": "CNRL-T-101",
            "duedate": "2026-09-15",
            "customfield_10301": "2026-09-09",
            "customfield_10046": "2026-09-20",
            "customfield_10066": "2026-09-22",
            "customfield_10286": "2026-09-25",
            "customfield_10288": "2026-09-26",
            "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
            "parent": {"fields": {"summary": "2026-Tanzim Drawing Package"}},
        },
    }
    row = drawing_from_issue(issue)
    assert row.key == "P2024-15578"
    assert row.drawing_id == "2026-Tanzim-1-1"
    assert row.job_number == "2026-Tanzim"
    assert row.outgoing_rev == "A"
    assert row.purpose == "Info"
    assert row.shop_purpose == "Construction"
    assert row.field_purpose == "Planned"
    assert row.incoming_rev == "0"
    assert row.approval == "Approved"
    assert row.shop_ifc_rev == "0"
    assert row.field_ifc_rev == "0"
    assert row.client_document_number == "CNRL-T-101"
    assert row.due_date == "2026-09-15"
    assert row.submission_date == "2026-09-09"
    assert row.return_request_date == "2026-09-20"
    assert row.return_date == "2026-09-22"
    assert row.shop_ifc_date == "2026-09-25"
    assert row.field_ifc_date == "2026-09-26"
    assert row.eddi_status == "1 - Fabrication Drawings - EDDI"
    assert row.parent_summary == "2026-Tanzim Drawing Package"


def test_drawing_fields_payload_skips_blanks() -> None:
    from doccon.register import (
        CLIENT_DOC_FIELD,
        DUE_DATE_FIELD,
        EDDI_FIELD,
        FIELD_PURPOSE_FIELD,
        PURPOSE_FIELD,
        SHOP_PURPOSE_FIELD,
    )

    row = drawing_from_issue(
        {
            "key": "P2024-1",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "customfield_10280": {"value": "A"},
                "customfield_10281": {"value": "Approval"},
                "customfield_10626": {"value": "Info"},
                "customfield_10625": {"value": "Construction"},
                "customfield_10279": "  CNRL-T-101  ",
                "duedate": "2026-09-15",
                "customfield_10289": [{"value": "1 - Fabrication Drawings - EDDI"}],
            },
        }
    )
    payload = drawing_fields_payload(row)
    assert payload[PURPOSE_FIELD] == {"value": "Approval"}
    assert payload[SHOP_PURPOSE_FIELD] == {"value": "Info"}
    assert payload[FIELD_PURPOSE_FIELD] == {"value": "Construction"}
    assert payload[CLIENT_DOC_FIELD] == "CNRL-T-101"
    assert payload[DUE_DATE_FIELD] == "2026-09-15"
    assert payload[EDDI_FIELD] == [{"value": "1 - Fabrication Drawings - EDDI"}]
    assert "customfield_10283" not in payload


def test_no_return_clears_return_request_and_due_date() -> None:
    from dataclasses import replace

    from doccon.register import DUE_DATE_FIELD, RETURN_REQUEST_DATE_FIELD

    row = drawing_from_issue(
        {
            "key": "P2024-1",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "duedate": "2026-09-15",
                "customfield_10046": "2026-09-15",
            },
        }
    )
    row = replace(row, return_request_date="N/A", due_date="N/A")
    payload = drawing_fields_payload(row)
    assert payload[RETURN_REQUEST_DATE_FIELD] is None
    assert payload[DUE_DATE_FIELD] is None


def test_eddi_conflicts_from_multi_checkbox() -> None:
    from doccon.register import eddi_conflicts, eddi_fix_options, eddi_options, has_multiple_eddi

    row = drawing_from_issue(
        {
            "key": "P2024-15578",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "customfield_10289": [
                    {"value": "1 - Fabrication Drawings - EDDI"},
                    {"value": "4 - Engineering - EDDI"},
                ],
            },
        }
    )
    assert eddi_options(
        [
            {"value": "1 - Fabrication Drawings - EDDI"},
            {"value": "4 - Engineering - EDDI"},
        ]
    ) == ("1 - Fabrication Drawings - EDDI", "4 - Engineering - EDDI")
    assert has_multiple_eddi(row.eddi_status)
    conflicts = eddi_conflicts([row])
    assert [item.key for item in conflicts] == ["P2024-15578"]
    assert conflicts[0].drawing_id == "2026-Tanzim-1-1"
    assert conflicts[0].options == (
        "1 - Fabrication Drawings - EDDI",
        "4 - Engineering - EDDI",
    )
    assert "0 - Generic Task" not in eddi_fix_options()
    assert all(name.startswith(f"{n} -") for n, name in enumerate(eddi_fix_options(), start=1))


def test_adopted_summary_keeps_title() -> None:
    assert adopted_summary("2026-096-1-1 Drawing-1", "2026-096-1-SK1") == "2026-096-1-SK1 Drawing-1"


def test_eddi_field_never_splits_a_label_on_a_comma() -> None:
    """1.54: group 5 sent four bogus options and Jira rejected 'Procedures - EDDI'."""
    from doccon.register import eddi_field

    label = "5 - QC - WO, ITP, NDE Records, Procedures - EDDI"
    assert eddi_field(label) == [{"value": label}]
    assert eddi_field("1 - Fabrication Drawings - EDDI; 4 - Engineering - EDDI") == [
        {"value": "1 - Fabrication Drawings - EDDI"},
        {"value": "4 - Engineering - EDDI"},
    ]


def test_eddi_helpers_use_that_issues_own_options() -> None:
    from doccon.register import (
        FieldOption,
        drawing_from_issue,
        eddi_conflicts,
        eddi_fix_options,
        eddi_option_labels,
        unknown_eddi_options,
    )

    options = (
        FieldOption(label="0 - Generic Task", option_id="10400"),
        FieldOption(label="1 - Fabrication Drawings - EDDI", option_id="10401"),
        FieldOption(label="8 - Document Control - EDDI", option_id="10408"),
    )
    assert eddi_fix_options(options) == (
        "1 - Fabrication Drawings - EDDI",
        "8 - Document Control - EDDI",
    )
    assert eddi_option_labels(options)[0] == ""
    assert eddi_option_labels(()) == ()
    assert unknown_eddi_options("4 - Engineering - EDDI", options) == ("4 - Engineering - EDDI",)
    assert unknown_eddi_options("1 - fabrication drawings – eddi", options) == ()
    assert unknown_eddi_options("4 - Engineering - EDDI", ()) == ()

    row = drawing_from_issue(
        {
            "key": "P2024-15578",
            "fields": {
                "summary": "2026-Tanzim-1-1 Drawing-1",
                "issuetype": {"name": "Sub-task"},
                "customfield_10289": [
                    {"value": "1 - Fabrication Drawings - EDDI"},
                    {"value": "8 - Document Control - EDDI"},
                ],
            },
        }
    )
    assert row.issue_type == "Sub-task"
    conflicts = eddi_conflicts([row], {"P2024-15578": options})
    assert conflicts[0].allowed == (
        "1 - Fabrication Drawings - EDDI",
        "8 - Document Control - EDDI",
    )


def test_due_date_follows_new_return_request_only() -> None:
    from doccon.register import due_date_from_return_request

    assert due_date_from_return_request("2026-09-01", "", "2026-09-20") == "2026-09-20"
    assert due_date_from_return_request("2026-09-01", "2026-09-10", "2026-09-20") == "2026-09-20"
    assert due_date_from_return_request("2026-09-01", "2026-09-10", "2026-09-10") == "2026-09-01"
    assert due_date_from_return_request("2026-09-01", "2026-09-10", "") == "2026-09-01"
    assert due_date_from_return_request("2026-09-01", "2026-09-10", "N/A") == "N/A"
