from datetime import datetime

from ease2026.outcomes.definitions import (
    BugFilterPolicy,
    FixerAttributionPolicy,
    normalize_priority,
)
from ease2026.outcomes.issue_outcomes import (
    IssueOutcome,
    IssueEvent,
    IssueRecord,
    _build_outcome_row,
    _event_outcome_flags,
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
        fix_authors_by_issue={},
    )

    assert matched == ["i1"]


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
