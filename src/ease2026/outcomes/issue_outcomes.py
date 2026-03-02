"""Compute RQ3 outcome metrics by project, hero code, and severity."""


import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ease2026.core.logging import get_logger
from ease2026.core.mongo import get_mongo_collection
from ease2026.core.settings import settings
from ease2026.identity.canonical import (
    load_identity_context,
    resolve_canonical_person_id,
)
from ease2026.identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver
from ease2026.outcomes.definitions import (
    BugFilterPolicy,
    FixerAttributionPolicy,
    ReopenCountingPolicy,
    SeverityPolicy,
    VALID_PRIORITIES,
    is_bug_issue,
    normalize_priority,
    normalize_text,
)

logger = get_logger(__name__)

HeroMembershipByCode = dict[str, dict[str, set[str]]]


@dataclass(frozen=True, slots=True)
class IssueRecord:
    issue_id: str
    project_name: str
    severity: str
    assignee_ids: frozenset[str]
    issue_resolution_fixed: bool


@dataclass(frozen=True, slots=True)
class IssueEvent:
    issue_id: str
    timestamp: datetime | None
    status: str
    new_value: str


@dataclass(frozen=True, slots=True)
class IssueOutcome:
    is_fixed: bool
    is_reopened_after_fixed: bool


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    project_name: str
    hero_code: str
    severity: str
    n_assigned: int
    n_fixed: int
    n_reopened: int
    fix_rate: float
    reopen_rate: float


@dataclass(frozen=True, slots=True)
class HeroCsvSpec:
    code: str
    csv_path: Path


def _default_hero_csv_specs() -> tuple[HeroCsvSpec, ...]:
    root = settings.outputs_csv_dir / "heroes"
    return (
        HeroCsvSpec("S1", root / "S1" / "heroes.csv"),
        HeroCsvSpec("S2", root / "S2" / "heroes.csv"),
        HeroCsvSpec("T1", root / "T1" / "heroes.csv"),
        HeroCsvSpec("T2", root / "T2" / "heroes.csv"),
        HeroCsvSpec("T3", root / "T3" / "heroes.csv"),
        HeroCsvSpec("ST1", root / "hybrid" / "sociotechnical" / "ST1.csv"),
        HeroCsvSpec("ST2", root / "hybrid" / "sociotechnical" / "ST2.csv"),
        HeroCsvSpec("ST3", root / "hybrid" / "sociotechnical" / "ST3.csv"),
        HeroCsvSpec("ST4", root / "hybrid" / "sociotechnical" / "ST4.csv"),
        HeroCsvSpec("ST5", root / "hybrid" / "sociotechnical" / "ST5.csv"),
        HeroCsvSpec("ST6", root / "hybrid" / "sociotechnical" / "ST6.csv"),
        HeroCsvSpec("TS1", root / "hybrid" / "technosocial" / "TS1.csv"),
        HeroCsvSpec("TS2", root / "hybrid" / "technosocial" / "TS2.csv"),
        HeroCsvSpec("TS3", root / "hybrid" / "technosocial" / "TS3.csv"),
        HeroCsvSpec("TS4", root / "hybrid" / "technosocial" / "TS4.csv"),
        HeroCsvSpec("TS5", root / "hybrid" / "technosocial" / "TS5.csv"),
        HeroCsvSpec("TS6", root / "hybrid" / "technosocial" / "TS6.csv"),
        HeroCsvSpec("SH1", root / "hybrid" / "super" / "SH1.csv"),
        HeroCsvSpec("SH2", root / "hybrid" / "super" / "SH2.csv"),
        HeroCsvSpec("SH3", root / "hybrid" / "super" / "SH3.csv"),
        HeroCsvSpec("SH4", root / "hybrid" / "super" / "SH4.csv"),
        HeroCsvSpec("SH5", root / "hybrid" / "super" / "SH5.csv"),
        HeroCsvSpec("SH6", root / "hybrid" / "super" / "SH6.csv"),
    )


class IssueOutcomesComputer:
    def __init__(
        self,
        bug_filter_policy: BugFilterPolicy = BugFilterPolicy.BUG_ONLY,
        severity_policy: SeverityPolicy = SeverityPolicy.PRIORITY,
        reopen_counting_policy: ReopenCountingPolicy = ReopenCountingPolicy.BINARY_REOPENED,
        hero_csv_specs: tuple[HeroCsvSpec, ...] | None = None,
        reverse_identity_map: ReverseIdentityMap | None = None,
        reverse_identity_resolver: ReverseIdentityResolver | None = None,
        refresh_identity_cache: bool = False,
    ) -> None:
        self.bug_filter_policy = bug_filter_policy
        self.severity_policy = severity_policy
        self.reopen_counting_policy = reopen_counting_policy
        self.hero_csv_specs = hero_csv_specs or _default_hero_csv_specs()
        self.reverse_identity_map, self.reverse_identity_resolver = load_identity_context(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
            refresh_cache=refresh_identity_cache,
        )

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq3_outcomes"

    def compute_and_write(
        self,
        fixer_policy: FixerAttributionPolicy,
    ) -> dict[str, Path]:
        hero_membership_by_code = self._load_hero_membership_by_code()
        issue_records = self._load_bug_issue_records()
        issue_ids = frozenset(issue_records)
        issue_outcomes = self._load_issue_outcomes(issue_records=issue_records)

        issue_ids_by_project_and_severity = self._index_issue_ids_by_project_and_severity(
            issue_records=issue_records,
        )

        fix_authors_by_issue: dict[str, set[str]] = {}
        if fixer_policy is FixerAttributionPolicy.COMMIT_AUTHOR:
            fix_authors_by_issue = self._load_fix_authors_by_issue(issue_ids=issue_ids)

        rows_by_severity = self._compute_rows_by_severity(
            fixer_policy=fixer_policy,
            hero_membership_by_code=hero_membership_by_code,
            issue_outcomes=issue_outcomes,
            issue_records=issue_records,
            issue_ids_by_project_and_severity=issue_ids_by_project_and_severity,
            fix_authors_by_issue=fix_authors_by_issue,
        )
        output_paths = self._write_rows_by_severity(
            fixer_policy=fixer_policy,
            rows_by_severity=rows_by_severity,
        )

        logger.info(
            "Computed issue outcomes",
            fixer_policy=fixer_policy.value,
            bug_filter_policy=self.bug_filter_policy.value,
            severity_policy=self.severity_policy.value,
            reopen_counting_policy=self.reopen_counting_policy.value,
            hero_code_count=len(hero_membership_by_code),
            issue_count=len(issue_records),
            output_root=str(self.output_root / fixer_policy.value),
        )
        return output_paths

    def _load_hero_membership_by_code(self) -> HeroMembershipByCode:
        membership_by_code: HeroMembershipByCode = {}
        for spec in self.hero_csv_specs:
            membership_by_code[spec.code] = self._read_hero_csv(spec.csv_path)
        return membership_by_code

    def _read_hero_csv(self, csv_path: Path) -> dict[str, set[str]]:
        membership: dict[str, set[str]] = {}
        if not csv_path.exists():
            logger.warning("Hero CSV missing; treating as empty", csv_path=str(csv_path))
            return membership

        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                project_name = row.get("project_name")
                author_id = row.get("author_id")
                if not project_name or not author_id:
                    continue
                canonical_author_id = resolve_canonical_person_id(
                    person_id=author_id,
                    reverse_identity_map=self.reverse_identity_map,
                    reverse_identity_resolver=self.reverse_identity_resolver,
                )
                if canonical_author_id is None:
                    continue
                membership.setdefault(project_name, set()).add(canonical_author_id)

        return membership

    def _load_bug_issue_records(self) -> dict[str, IssueRecord]:
        project_name_by_id = self._load_project_name_by_id()
        project_name_by_issue_system_id = self._load_project_name_by_issue_system_id(
            project_name_by_id=project_name_by_id,
        )

        issue_records: dict[str, IssueRecord] = {}
        projection = {
            "_id": 1,
            "issue_type": 1,
            "issue_type_verified": 1,
            "priority": 1,
            "resolution": 1,
            "assignee_id": 1,
            "assignee_ids": 1,
            "assignee": 1,
            "assignees": 1,
            "assignee_info": 1,
            "project_id": 1,
            "issue_system_id": 1,
            "project_name": 1,
            "project_name_info": 1,
            "issue_info": 1,
        }

        for issue_doc in get_mongo_collection("issue").find({}, projection):
            issue_id = _normalize_identifier(issue_doc.get("_id"))
            if issue_id is None:
                continue

            if not is_bug_issue(
                issue_type=issue_doc.get("issue_type"),
                issue_type_verified=issue_doc.get("issue_type_verified"),
                policy=self.bug_filter_policy,
            ):
                continue

            severity = normalize_priority(issue_doc.get("priority"), policy=self.severity_policy)
            if severity is None:
                continue

            project_name = _extract_project_name(
                issue_doc=issue_doc,
                project_name_by_id=project_name_by_id,
                project_name_by_issue_system_id=project_name_by_issue_system_id,
            )
            if project_name is None:
                continue

            assignee_ids = _extract_assignee_ids(
                issue_doc=issue_doc,
                reverse_identity_map=self.reverse_identity_map,
                reverse_identity_resolver=self.reverse_identity_resolver,
            )
            issue_resolution_fixed = _is_fixed_value(issue_doc.get("resolution"))
            issue_records[issue_id] = IssueRecord(
                issue_id=issue_id,
                project_name=project_name,
                severity=severity,
                assignee_ids=frozenset(assignee_ids),
                issue_resolution_fixed=issue_resolution_fixed,
            )

        return issue_records

    @staticmethod
    def _load_project_name_by_id() -> dict[str, str]:
        mapping: dict[str, str] = {}
        for doc in get_mongo_collection("project").find({}, {"_id": 1, "name": 1}):
            project_id = _normalize_identifier(doc.get("_id"))
            project_name = normalize_text(doc.get("name"))
            if project_id is None or project_name is None:
                continue
            mapping[project_id] = project_name
        return mapping

    @staticmethod
    def _load_project_name_by_issue_system_id(project_name_by_id: dict[str, str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        projection = {"_id": 1, "project_id": 1}
        for doc in get_mongo_collection("issue_system").find({}, projection):
            issue_system_id = _normalize_identifier(doc.get("_id"))
            project_id = _normalize_identifier(doc.get("project_id"))
            if issue_system_id is None or project_id is None:
                continue
            project_name = project_name_by_id.get(project_id)
            if project_name is None:
                continue
            mapping[issue_system_id] = project_name
        return mapping

    def _load_issue_outcomes(
        self, issue_records: dict[str, IssueRecord]
    ) -> dict[str, IssueOutcome]:
        relevant_issue_ids = frozenset(issue_records)
        events_by_issue: dict[str, list[IssueEvent]] = {}
        projection = {"issue_id": 1, "status": 1, "new_value": 1, "created_at": 1}
        for event_doc in get_mongo_collection("event").find({}, projection):
            issue_id = _normalize_identifier(event_doc.get("issue_id"))
            if issue_id is None or issue_id not in relevant_issue_ids:
                continue

            status = normalize_text(event_doc.get("status"))
            new_value = normalize_text(event_doc.get("new_value"))
            if status is None or new_value is None:
                continue
            if not _is_relevant_outcome_event(status=status, new_value=new_value):
                continue

            event = IssueEvent(
                issue_id=issue_id,
                timestamp=_normalize_datetime(event_doc.get("created_at")),
                status=status,
                new_value=new_value,
            )
            events_by_issue.setdefault(issue_id, []).append(event)

        outcomes: dict[str, IssueOutcome] = {}
        for issue_id, record in issue_records.items():
            events = events_by_issue.get(issue_id, [])
            event_fixed, reopened_after_fixed = _event_outcome_flags(events)
            is_fixed = event_fixed or record.issue_resolution_fixed
            if self.reopen_counting_policy is not ReopenCountingPolicy.BINARY_REOPENED:
                raise ValueError(f"Unsupported reopen policy: {self.reopen_counting_policy}")
            outcomes[issue_id] = IssueOutcome(
                is_fixed=is_fixed,
                is_reopened_after_fixed=is_fixed and reopened_after_fixed,
            )

        return outcomes

    @staticmethod
    def _index_issue_ids_by_project_and_severity(
        issue_records: dict[str, IssueRecord],
    ) -> dict[str, dict[str, list[str]]]:
        index: dict[str, dict[str, list[str]]] = {}
        for issue_id, record in issue_records.items():
            project_by_severity = index.setdefault(record.project_name, {})
            issue_ids = project_by_severity.setdefault(record.severity, [])
            issue_ids.append(issue_id)
        return index

    def _load_fix_authors_by_issue(self, issue_ids: frozenset[str]) -> dict[str, set[str]]:
        fix_authors_by_issue: dict[str, set[str]] = {issue_id: set() for issue_id in issue_ids}
        projection = {"author_id": 1, "fixed_issue_ids": 1}
        for commit_doc in get_mongo_collection("commit").find(
            {"fixed_issue_ids.0": {"$exists": True}}, projection
        ):
            author_id = resolve_canonical_person_id(
                person_id=commit_doc.get("author_id"),
                reverse_identity_map=self.reverse_identity_map,
                reverse_identity_resolver=self.reverse_identity_resolver,
            )
            if author_id is None:
                continue

            fixed_issue_ids = commit_doc.get("fixed_issue_ids")
            if not isinstance(fixed_issue_ids, list):
                continue

            for fixed_issue_id in fixed_issue_ids:
                issue_id = _normalize_identifier(fixed_issue_id)
                if issue_id is None or issue_id not in fix_authors_by_issue:
                    continue
                fix_authors_by_issue[issue_id].add(author_id)

        return fix_authors_by_issue

    def _compute_rows_by_severity(
        self,
        fixer_policy: FixerAttributionPolicy,
        hero_membership_by_code: HeroMembershipByCode,
        issue_outcomes: dict[str, IssueOutcome],
        issue_records: dict[str, IssueRecord],
        issue_ids_by_project_and_severity: dict[str, dict[str, list[str]]],
        fix_authors_by_issue: dict[str, set[str]],
    ) -> dict[str, list[OutcomeRow]]:
        rows_by_severity: dict[str, list[OutcomeRow]] = {
            severity: [] for severity in VALID_PRIORITIES
        }

        for spec in self.hero_csv_specs:
            hero_code = spec.code
            project_hero_authors = hero_membership_by_code.get(hero_code, {})
            for project_name, hero_authors in sorted(project_hero_authors.items()):
                if not hero_authors:
                    continue

                issue_ids_by_severity = issue_ids_by_project_and_severity.get(project_name, {})
                for severity in VALID_PRIORITIES:
                    severity_issue_ids = issue_ids_by_severity.get(severity, [])
                    matched_issue_ids = _match_issue_ids_for_heroes(
                        issue_ids=severity_issue_ids,
                        hero_authors=hero_authors,
                        issue_records=issue_records,
                        fixer_policy=fixer_policy,
                        fix_authors_by_issue=fix_authors_by_issue,
                    )
                    row = _build_outcome_row(
                        project_name=project_name,
                        hero_code=hero_code,
                        severity=severity,
                        matched_issue_ids=matched_issue_ids,
                        issue_outcomes=issue_outcomes,
                    )
                    rows_by_severity[severity].append(row)

        return rows_by_severity

    def _write_rows_by_severity(
        self,
        fixer_policy: FixerAttributionPolicy,
        rows_by_severity: dict[str, list[OutcomeRow]],
    ) -> dict[str, Path]:
        output_paths: dict[str, Path] = {}
        target_root = self.output_root / fixer_policy.value
        target_root.mkdir(parents=True, exist_ok=True)

        for severity, rows in rows_by_severity.items():
            output_path = target_root / f"{severity}.csv"
            with output_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "project_name",
                        "hero_code",
                        "severity",
                        "n_assigned",
                        "n_fixed",
                        "n_reopened",
                        "fix_rate",
                        "reopen_rate",
                    ],
                )
                for row in sorted(rows, key=lambda item: (item.hero_code, item.project_name)):
                    writer.writerow(
                        [
                            row.project_name,
                            row.hero_code,
                            row.severity,
                            row.n_assigned,
                            row.n_fixed,
                            row.n_reopened,
                            row.fix_rate,
                            row.reopen_rate,
                        ],
                    )
            output_paths[severity] = output_path

        return output_paths


def _build_outcome_row(
    project_name: str,
    hero_code: str,
    severity: str,
    matched_issue_ids: list[str],
    issue_outcomes: dict[str, IssueOutcome],
) -> OutcomeRow:
    n_assigned = len(matched_issue_ids)
    n_fixed = 0
    n_reopened = 0
    for issue_id in matched_issue_ids:
        outcome = issue_outcomes[issue_id]
        if outcome.is_fixed:
            n_fixed += 1
            if outcome.is_reopened_after_fixed:
                n_reopened += 1

    fix_rate = float("nan") if n_assigned == 0 else (n_fixed / n_assigned) * 100
    reopen_rate = float("nan") if n_fixed == 0 else (n_reopened / n_fixed) * 100
    return OutcomeRow(
        project_name=project_name,
        hero_code=hero_code,
        severity=severity,
        n_assigned=n_assigned,
        n_fixed=n_fixed,
        n_reopened=n_reopened,
        fix_rate=fix_rate,
        reopen_rate=reopen_rate,
    )


def _match_issue_ids_for_heroes(
    issue_ids: list[str],
    hero_authors: set[str],
    issue_records: dict[str, IssueRecord],
    fixer_policy: FixerAttributionPolicy,
    fix_authors_by_issue: dict[str, set[str]],
) -> list[str]:
    matched: list[str] = []
    if fixer_policy is FixerAttributionPolicy.ASSIGNEE:
        for issue_id in issue_ids:
            assignee_ids = issue_records[issue_id].assignee_ids
            if assignee_ids.intersection(hero_authors):
                matched.append(issue_id)
        return matched

    if fixer_policy is FixerAttributionPolicy.COMMIT_AUTHOR:
        for issue_id in issue_ids:
            fix_authors = fix_authors_by_issue.get(issue_id, set())
            if fix_authors.intersection(hero_authors):
                matched.append(issue_id)
        return matched

    raise ValueError(f"Unsupported fixer attribution policy: {fixer_policy}")


def _extract_project_name(
    issue_doc: dict[str, Any],
    project_name_by_id: dict[str, str],
    project_name_by_issue_system_id: dict[str, str],
) -> str | None:
    project_name = normalize_text(issue_doc.get("project_name"))
    if project_name is not None:
        return project_name

    project_name_info = issue_doc.get("project_name_info")
    if isinstance(project_name_info, dict):
        nested_name = normalize_text(project_name_info.get("name"))
        if nested_name is not None:
            return nested_name

    issue_info = issue_doc.get("issue_info")
    if isinstance(issue_info, dict):
        nested_project_name_info = issue_info.get("project_name_info")
        if isinstance(nested_project_name_info, dict):
            nested_name = normalize_text(nested_project_name_info.get("name"))
            if nested_name is not None:
                return nested_name

    project_id = _normalize_identifier(issue_doc.get("project_id"))
    if project_id is not None:
        project_name = project_name_by_id.get(project_id)
        if project_name is not None:
            return project_name

    issue_system_id = _normalize_identifier(issue_doc.get("issue_system_id"))
    if issue_system_id is not None:
        return project_name_by_issue_system_id.get(issue_system_id)

    return None


def _extract_assignee_ids(
    issue_doc: dict[str, Any],
    reverse_identity_map: ReverseIdentityMap,
    reverse_identity_resolver: ReverseIdentityResolver,
) -> set[str]:
    assignee_ids: set[str] = set()
    for key in ("assignee_id", "assignee_ids", "assignee", "assignees", "assignee_info"):
        for identifier in _extract_identifier_values(issue_doc.get(key)):
            canonical_assignee_id = resolve_canonical_person_id(
                person_id=identifier,
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            )
            if canonical_assignee_id is not None:
                assignee_ids.add(canonical_assignee_id)
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
        extracted: set[Any] = set()
        for key in ("_id", "id", "person_id", "assignee_id"):
            if key in value:
                extracted.update(_extract_identifier_values(value.get(key)))
        return extracted
    try:
        return {value}
    except TypeError:
        return set()


def _normalize_identifier(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_fixed_value(value: Any) -> bool:
    return normalize_text(value) == "fixed"


def _is_relevant_outcome_event(status: str, new_value: str) -> bool:
    return (status == "resolution" and new_value == "fixed") or (
        status == "status" and new_value == "reopened"
    )


def _event_sort_key(event: IssueEvent) -> float:
    if event.timestamp is None:
        return float("-inf")

    timestamp = event.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.timestamp()


def _event_outcome_flags(events: list[IssueEvent]) -> tuple[bool, bool]:
    if not events:
        return False, False

    first_fixed_seen = False
    reopened_after_fixed = False
    for event in sorted(events, key=_event_sort_key):
        if event.status == "resolution" and event.new_value == "fixed":
            first_fixed_seen = True
            continue
        if first_fixed_seen and event.status == "status" and event.new_value == "reopened":
            reopened_after_fixed = True
            break

    return first_fixed_seen, reopened_after_fixed
