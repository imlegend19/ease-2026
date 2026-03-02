"""Policy definitions for issue-outcome computation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class BugFilterPolicy(StrEnum):
    BUG_ONLY = "bug_only"


class SeverityPolicy(StrEnum):
    PRIORITY = "priority"


class FixerAttributionPolicy(StrEnum):
    ASSIGNEE = "assignee"
    ASSIGNEE_AT_FIX_TIME = "assignee_at_fix_time"
    COMMIT_AUTHOR = "commit_author"
    COMBINED = "combined"


class ReopenCountingPolicy(StrEnum):
    BINARY_REOPENED = "binary_reopened"


VALID_PRIORITIES: tuple[str, ...] = ("blocker", "critical", "major", "minor", "trivial")
VALID_PRIORITY_SET = frozenset(VALID_PRIORITIES)


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def is_bug_issue(
    issue_type: Any,
    issue_type_verified: Any,
    policy: BugFilterPolicy = BugFilterPolicy.BUG_ONLY,
) -> bool:
    if policy is not BugFilterPolicy.BUG_ONLY:
        raise ValueError(f"Unsupported bug filter policy: {policy}")

    verified = normalize_text(issue_type_verified)
    issue_kind = verified if verified is not None else normalize_text(issue_type)
    return issue_kind == "bug"


def normalize_priority(
    priority: Any,
    policy: SeverityPolicy = SeverityPolicy.PRIORITY,
) -> str | None:
    if policy is not SeverityPolicy.PRIORITY:
        raise ValueError(f"Unsupported severity policy: {policy}")

    normalized = normalize_text(priority)
    if normalized in VALID_PRIORITY_SET:
        return normalized
    return None
