from datetime import datetime

from ease2026.outcomes.definitions import (
    BugFilterPolicy,
    FixerAttributionPolicy,
    normalize_priority,
)
from ease2026.outcomes.issue_outcomes import (
    AssigneeChangeEvent,
    IssueOutcome,
    IssueEvent,
    IssueRecord,
    _assignee_id_at_timestamp,
    _build_outcome_row,
    _extract_assignee_ids,
    _extract_current_assignee_id,
    _event_outcome_flags,
    _first_fixed_timestamp,
    _match_issue_ids_for_heroes,
)


def test_event_outcome_flags_detects_reopen_after_first_fixed() -> None:
    events = [
        IssueEvent(
            issue_id="i1",
            timestamp=datetime(2021, 1, 1),
            status="status",
            new_value="reopened",
        ),
        IssueEvent(
            issue_id="i1",
            timestamp=datetime(2021, 1, 2),
            status="resolution",
            new_value="fixed",
        ),
        IssueEvent(
            issue_id="i1",
            timestamp=datetime(2021, 1, 3),
            status="status",
            new_value="reopened",
        ),
    ]

    is_fixed, reopened = _event_outcome_flags(events)  # noqa: SLF001
    assert is_fixed is True
    assert reopened is True


def test_build_outcome_row_reopen_rate_is_conditional_on_n_fixed() -> None:
    issue_outcomes = {
        "i1": IssueOutcome(is_fixed=False, is_reopened_after_fixed=False),
        "i2": IssueOutcome(is_fixed=False, is_reopened_after_fixed=False),
    }
    row = _build_outcome_row(  # noqa: SLF001
        project_name="p",
        hero_code="S1",
        severity="major",
        matched_issue_ids=["i1", "i2"],
        issue_outcomes=issue_outcomes,
    )

    assert row.n_assigned == 2
    assert row.n_fixed == 0
    assert row.n_reopened == 0
    assert row.fix_rate == 0.0
    assert str(row.reopen_rate) == "nan"


def test_match_issue_ids_for_heroes_assignee() -> None:
    issue_records = {
        "i1": IssueRecord("i1", "p", "major", frozenset({"h1"}), False),
        "i2": IssueRecord("i2", "p", "major", frozenset({"u1"}), False),
    }

    matched = _match_issue_ids_for_heroes(  # noqa: SLF001
        issue_ids=["i1", "i2"],
        hero_authors={"h1"},
        issue_records=issue_records,
        fixer_policy=FixerAttributionPolicy.ASSIGNEE,
        fix_time_assignee_by_issue={},
        fix_authors_by_issue={},
    )

    assert matched == ["i1"]


def test_match_issue_ids_for_heroes_assignee_at_fix_time() -> None:
    issue_records = {
        "i1": IssueRecord("i1", "p", "major", frozenset({"fallback_1"}), False),
        "i2": IssueRecord("i2", "p", "major", frozenset({"fallback_2"}), False),
    }

    matched = _match_issue_ids_for_heroes(  # noqa: SLF001
        issue_ids=["i1", "i2"],
        hero_authors={"h1"},
        issue_records=issue_records,
        fixer_policy=FixerAttributionPolicy.ASSIGNEE_AT_FIX_TIME,
        fix_time_assignee_by_issue={"i1": "h1", "i2": "h2"},
        fix_authors_by_issue={},
    )

    assert matched == ["i1"]


def test_match_issue_ids_for_heroes_combined_uses_assignee_or_fix_author() -> None:
    issue_records = {
        "i1": IssueRecord("i1", "p", "major", frozenset({"fallback_1"}), False),
        "i2": IssueRecord("i2", "p", "major", frozenset({"fallback_2"}), False),
        "i3": IssueRecord("i3", "p", "major", frozenset({"fallback_3"}), False),
    }

    matched = _match_issue_ids_for_heroes(  # noqa: SLF001
        issue_ids=["i1", "i2", "i3"],
        hero_authors={"h1"},
        issue_records=issue_records,
        fixer_policy=FixerAttributionPolicy.COMBINED,
        fix_time_assignee_by_issue={"i1": "h1", "i2": "u2", "i3": "h1"},
        fix_authors_by_issue={"i2": {"h1"}, "i3": {"h1"}},
    )

    assert matched == ["i1", "i2", "i3"]


def test_bug_filter_prefers_verified_issue_type() -> None:
    from ease2026.outcomes.definitions import is_bug_issue

    assert (
        is_bug_issue(
            issue_type="bug",
            issue_type_verified="improvement",
            policy=BugFilterPolicy.BUG_ONLY,
        )
        is False
    )
    assert (
        is_bug_issue(
            issue_type="improvement",
            issue_type_verified="bug",
            policy=BugFilterPolicy.BUG_ONLY,
        )
        is True
    )


def test_priority_normalization_accepts_defined_values_only() -> None:
    assert normalize_priority("Critical") == "critical"
    assert normalize_priority("unknown") is None


def test_extract_assignee_ids_resolves_canonical_identity() -> None:
    class DummyResolver:
        @staticmethod
        def resolve_person_id(person_id, reverse_identity_map):  # noqa: ANN001,ANN002
            return reverse_identity_map.get(person_id, person_id)

    issue_doc = {
        "assignee_id": "raw_1",
        "assignee_ids": ["raw_2"],
        "assignee_info": {"person_id": "raw_3"},
    }

    assignee_ids = _extract_assignee_ids(  # noqa: SLF001
        issue_doc=issue_doc,
        reverse_identity_map={"raw_1": "canon_1", "raw_3": "canon_3"},
        reverse_identity_resolver=DummyResolver(),
    )

    assert assignee_ids == {"canon_1", "raw_2", "canon_3"}


def test_extract_current_assignee_id_prefers_primary_assignee_field() -> None:
    class DummyResolver:
        @staticmethod
        def resolve_person_id(person_id, reverse_identity_map):  # noqa: ANN001,ANN002
            return reverse_identity_map.get(person_id, person_id)

    issue_doc = {
        "assignee_id": "raw_primary",
        "assignees": ["raw_secondary"],
    }

    assignee_id = _extract_current_assignee_id(  # noqa: SLF001
        issue_doc=issue_doc,
        reverse_identity_map={"raw_primary": "canon_primary"},
        reverse_identity_resolver=DummyResolver(),
    )

    assert assignee_id == "canon_primary"


def test_first_fixed_timestamp_uses_first_resolution_fixed_event() -> None:
    events = [
        IssueEvent("i1", datetime(2021, 1, 3), "resolution", "fixed"),
        IssueEvent("i1", datetime(2021, 1, 2), "resolution", "fixed"),
        IssueEvent("i1", datetime(2021, 1, 1), "status", "reopened"),
    ]

    assert _first_fixed_timestamp(events) == datetime(2021, 1, 2)  # noqa: SLF001


def test_assignee_id_at_timestamp_replays_events_up_to_cutoff() -> None:
    assignee_events = [
        AssigneeChangeEvent("i1", datetime(2021, 1, 1), "u1"),
        AssigneeChangeEvent("i1", datetime(2021, 1, 2), "u2"),
        AssigneeChangeEvent("i1", datetime(2021, 1, 4), "u3"),
    ]

    assignee_id = _assignee_id_at_timestamp(  # noqa: SLF001
        assignee_events=assignee_events,
        cutoff_timestamp=datetime(2021, 1, 3),
    )
    assert assignee_id == "u2"
