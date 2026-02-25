"""Shared Mongo extractors for issue-based analysis pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.mongo import get_mongo_collection
from identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver
from pipelines.analysis.hero_catalog import PRIORITY_SEVERITIES

logger = get_logger(__name__)

SEVERITY_SET = set(PRIORITY_SEVERITIES)


@dataclass(frozen=True, slots=True)
class IssueMetadata:
    issue_id: str
    project_name: str | None
    priority: str | None
    assignee_ids: frozenset[str]
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class IssueEvent:
    issue_id: str
    timestamp: datetime | None
    status: str
    new_value: str


def build_issue_metadata(
    reverse_identity_map: ReverseIdentityMap,
    reverse_identity_resolver: ReverseIdentityResolver,
) -> dict[str, IssueMetadata]:
    metadata_by_issue: dict[str, IssueMetadata] = {}
    project_name_by_id = _load_project_name_index()

    issue_collection = get_mongo_collection("issue")
    for issue_doc in issue_collection.find({}):
        issue_id = _normalize_identifier(issue_doc.get("_id"))
        if issue_id is None:
            continue

        project_name = _extract_project_name(issue_doc, project_name_by_id)
        priority = _normalize_priority(issue_doc.get("priority"))
        created_at = _normalize_datetime(issue_doc.get("created_at"))

        raw_assignee_ids = _extract_assignee_identifiers(issue_doc)
        merged_assignee_ids: set[str] = set()
        for raw_assignee_id in raw_assignee_ids:
            resolved_person_id = reverse_identity_resolver.resolve_person_id(raw_assignee_id, reverse_identity_map)
            normalized_person_id = _normalize_identifier(resolved_person_id)
            if normalized_person_id is not None:
                merged_assignee_ids.add(normalized_person_id)

        metadata_by_issue[issue_id] = IssueMetadata(
            issue_id=issue_id,
            project_name=project_name,
            priority=priority,
            assignee_ids=frozenset(merged_assignee_ids),
            created_at=created_at,
        )

    logger.info("Loaded issue metadata", issue_count=len(metadata_by_issue))
    return metadata_by_issue


def build_relevant_issue_events() -> dict[str, list[IssueEvent]]:
    events_by_issue: dict[str, list[IssueEvent]] = {}
    event_collection = get_mongo_collection("event")

    for event_doc in event_collection.find({}):
        issue_id = _normalize_identifier(event_doc.get("issue_id"))
        if issue_id is None:
            continue

        status = str(event_doc.get("status", "")).strip().lower()
        new_value = str(event_doc.get("new_value", "")).strip().lower()
        if not _is_relevant_event(status=status, new_value=new_value):
            continue

        event = IssueEvent(
            issue_id=issue_id,
            timestamp=_normalize_datetime(event_doc.get("created_at")),
            status=status,
            new_value=new_value,
        )
        events_by_issue.setdefault(issue_id, []).append(event)

    for issue_id, events in events_by_issue.items():
        events.sort(key=issue_event_sort_key)
        events_by_issue[issue_id] = events

    logger.info("Loaded relevant issue events", issue_count=len(events_by_issue))
    return events_by_issue


def issue_event_sort_key(event: IssueEvent) -> float:
    if event.timestamp is None:
        return float("-inf")

    normalized_timestamp = event.timestamp
    if normalized_timestamp.tzinfo is None:
        normalized_timestamp = normalized_timestamp.replace(tzinfo=UTC)
    return normalized_timestamp.timestamp()


def extract_first_fixed_timestamp(events: list[IssueEvent]) -> datetime | None:
    for event in events:
        if event.status == "resolution" and event.new_value == "fixed":
            return event.timestamp
    return None


def _load_project_name_index() -> dict[str, str]:
    project_name_by_id: dict[str, str] = {}
    project_collection = get_mongo_collection("project")

    for project_doc in project_collection.find({}, {"_id": 1, "name": 1}):
        project_id = _normalize_identifier(project_doc.get("_id"))
        project_name = project_doc.get("name")
        if project_id is None or not project_name:
            continue
        project_name_by_id[project_id] = str(project_name)

    return project_name_by_id


def _extract_project_name(issue_doc: dict[str, Any], project_name_by_id: dict[str, str]) -> str | None:
    if "project_name" in issue_doc and issue_doc["project_name"]:
        return str(issue_doc["project_name"])

    project_name_info = issue_doc.get("project_name_info")
    if isinstance(project_name_info, dict) and project_name_info.get("name"):
        return str(project_name_info["name"])

    issue_info = issue_doc.get("issue_info")
    if isinstance(issue_info, dict):
        nested_project_info = issue_info.get("project_name_info")
        if isinstance(nested_project_info, dict) and nested_project_info.get("name"):
            return str(nested_project_info["name"])

    project_id = _normalize_identifier(issue_doc.get("project_id"))
    if project_id is not None:
        return project_name_by_id.get(project_id)

    return None


def _normalize_priority(priority: Any) -> str | None:
    if priority is None:
        return None

    normalized_priority = str(priority).strip().lower()
    return normalized_priority if normalized_priority in SEVERITY_SET else None


def _normalize_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            # Accept RFC3339 "Z" timezone suffix.
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_identifier(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _extract_assignee_identifiers(issue_doc: dict[str, Any]) -> set[Any]:
    assignee_ids: set[Any] = set()
    assignee_keys = (
        "assignee_id",
        "assignee_ids",
        "assignee",
        "assignees",
        "assignee_info",
    )
    for key in assignee_keys:
        assignee_ids.update(_extract_identifier_values(issue_doc.get(key)))
    return assignee_ids


def _extract_identifier_values(value: Any) -> set[Any]:
    if value is None:
        return set()
    if isinstance(value, (str, int, float)):
        return {value}
    if isinstance(value, (list, tuple, set, frozenset)):
        extracted: set[Any] = set()
        for item in value:
            extracted.update(_extract_identifier_values(item))
        return extracted
    if isinstance(value, dict):
        extracted = set()
        for key in ("_id", "id", "person_id", "assignee_id"):
            if key in value:
                extracted.update(_extract_identifier_values(value.get(key)))
        return extracted
    try:
        return {value}
    except TypeError:
        return set()


def _is_relevant_event(status: str, new_value: str) -> bool:
    return (status == "resolution" and new_value == "fixed") or (status == "status" and new_value == "reopened")
