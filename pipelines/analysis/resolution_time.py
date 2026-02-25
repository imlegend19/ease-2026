"""Compute severity-wise resolution-time metrics for hero categories."""


import csv
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from identity.reverse_identity import ReverseIdentityResolver
from pipelines.analysis.hero_catalog import HERO_TYPE_SPECS, PRIORITY_SEVERITIES
from pipelines.analysis.hero_membership import HeroMembershipByCode, HeroMembershipPipeline
from pipelines.analysis.issue_data import IssueMetadata, build_issue_metadata, build_relevant_issue_events, extract_first_fixed_timestamp

logger = get_logger(__name__)

ProjectAssigneeAverages = dict[str, dict[str, float]]
SeverityAssigneeAverages = dict[str, ProjectAssigneeAverages]
HeroProjectAverages = dict[str, dict[str, dict[str, float]]]


@dataclass(frozen=True, slots=True)
class ResolutionTimeOutputPaths:
    assignee_pickle_paths: dict[str, Path]
    hero_pickle_paths: dict[str, Path]
    hero_csv_paths: dict[str, Path]


class ResolutionTimePipeline:
    @property
    def interim_root(self) -> Path:
        return settings.interim_dir / "analysis" / "resolution_time"

    @property
    def assignee_pickle_root(self) -> Path:
        return self.interim_root / "assignee_avg_seconds"

    @property
    def hero_pickle_root(self) -> Path:
        return self.interim_root / "hero_avg_hours"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "resolution_time"

    def run(
        self,
        refresh_identity_cache: bool = False,
        write_interim: bool = True,
        write_csv: bool = True,
    ) -> ResolutionTimeOutputPaths:
        hero_membership = HeroMembershipPipeline().load_or_build()
        reverse_identity_resolver = ReverseIdentityResolver()
        reverse_identity_map = reverse_identity_resolver.load_or_build(refresh_cache=refresh_identity_cache)

        issue_metadata = build_issue_metadata(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        )
        events_by_issue = build_relevant_issue_events()

        assignee_avg_seconds = self._compute_assignee_avg_seconds_by_severity(
            issue_metadata=issue_metadata,
            events_by_issue=events_by_issue,
        )
        hero_avg_hours = self._compute_hero_avg_hours_by_severity(
            hero_membership=hero_membership,
            assignee_avg_seconds=assignee_avg_seconds,
        )

        assignee_pickle_paths: dict[str, Path] = {}
        hero_pickle_paths: dict[str, Path] = {}
        hero_csv_paths: dict[str, Path] = {}

        if write_interim:
            assignee_pickle_paths = self._write_assignee_pickles(assignee_avg_seconds)
            hero_pickle_paths = self._write_hero_pickles(hero_avg_hours)

        if write_csv:
            hero_csv_paths = self._write_hero_csv(hero_avg_hours)

        logger.info(
            "Computed resolution-time metrics",
            severities=len(PRIORITY_SEVERITIES),
            hero_type_count=len(HERO_TYPE_SPECS),
        )

        return ResolutionTimeOutputPaths(
            assignee_pickle_paths=assignee_pickle_paths,
            hero_pickle_paths=hero_pickle_paths,
            hero_csv_paths=hero_csv_paths,
        )

    @staticmethod
    def _compute_assignee_avg_seconds_by_severity(
        issue_metadata: dict[str, IssueMetadata],
        events_by_issue: dict[str, list],
    ) -> SeverityAssigneeAverages:
        raw_totals: dict[str, dict[str, dict[str, tuple[float, int]]]] = {
            severity: {}
            for severity in PRIORITY_SEVERITIES
        }

        for issue_id, metadata in issue_metadata.items():
            severity = metadata.priority
            if severity not in PRIORITY_SEVERITIES:
                continue
            if not metadata.project_name or not metadata.assignee_ids:
                continue
            if metadata.created_at is None:
                continue

            fixed_timestamp = extract_first_fixed_timestamp(events_by_issue.get(issue_id, []))
            if fixed_timestamp is None:
                continue

            created_ts = _datetime_to_utc_timestamp(metadata.created_at)
            fixed_ts = _datetime_to_utc_timestamp(fixed_timestamp)
            if created_ts is None or fixed_ts is None:
                continue

            duration_seconds = fixed_ts - created_ts
            if duration_seconds <= 0:
                continue

            project_totals = raw_totals[severity].setdefault(metadata.project_name, {})
            for assignee_id in metadata.assignee_ids:
                current_total, current_count = project_totals.get(assignee_id, (0.0, 0))
                project_totals[assignee_id] = (current_total + duration_seconds, current_count + 1)

        output: SeverityAssigneeAverages = {severity: {} for severity in PRIORITY_SEVERITIES}
        for severity, project_totals in raw_totals.items():
            for project_name, assignee_totals in project_totals.items():
                output[severity][project_name] = {}
                for assignee_id, (total_seconds, count) in assignee_totals.items():
                    if count == 0:
                        continue
                    output[severity][project_name][assignee_id] = total_seconds / count

        return output

    @staticmethod
    def _compute_hero_avg_hours_by_severity(
        hero_membership: HeroMembershipByCode,
        assignee_avg_seconds: SeverityAssigneeAverages,
    ) -> HeroProjectAverages:
        hero_avg_hours: HeroProjectAverages = {
            severity: {spec.code: {} for spec in HERO_TYPE_SPECS}
            for severity in PRIORITY_SEVERITIES
        }

        for severity in PRIORITY_SEVERITIES:
            project_assignee_avgs = assignee_avg_seconds.get(severity, {})
            for hero_spec in HERO_TYPE_SPECS:
                hero_code = hero_spec.code
                project_hero_authors = hero_membership.get(hero_code, {})

                for project_name, hero_author_ids in project_hero_authors.items():
                    assignee_seconds = project_assignee_avgs.get(project_name)
                    if not assignee_seconds:
                        continue

                    total_hours = 0.0
                    total_counter = 0
                    for author_id in hero_author_ids:
                        if author_id in assignee_seconds:
                            total_hours += assignee_seconds[author_id] / 3600.0
                        total_counter += 1

                    if total_counter > 0:
                        hero_avg_hours[severity][hero_code][project_name] = total_hours / total_counter

        return hero_avg_hours

    def _write_assignee_pickles(self, assignee_avg_seconds: SeverityAssigneeAverages) -> dict[str, Path]:
        ensure_directory(self.assignee_pickle_root)
        output_paths: dict[str, Path] = {}

        for severity in PRIORITY_SEVERITIES:
            output_path = self.assignee_pickle_root / f"{severity}_project_assignee_avg_seconds.pkl"
            with output_path.open("wb") as file:
                pickle.dump(assignee_avg_seconds.get(severity, {}), file)
            output_paths[severity] = output_path

        return output_paths

    def _write_hero_pickles(self, hero_avg_hours: HeroProjectAverages) -> dict[str, Path]:
        ensure_directory(self.hero_pickle_root)
        output_paths: dict[str, Path] = {}

        for severity in PRIORITY_SEVERITIES:
            output_path = self.hero_pickle_root / f"{severity}_avg_resolution_hours_by_hero.pkl"
            with output_path.open("wb") as file:
                pickle.dump(hero_avg_hours.get(severity, {}), file)
            output_paths[severity] = output_path

        return output_paths

    def _write_hero_csv(self, hero_avg_hours: HeroProjectAverages) -> dict[str, Path]:
        ensure_directory(self.output_root)
        output_paths: dict[str, Path] = {}

        for severity in PRIORITY_SEVERITIES:
            output_path = self.output_root / f"avg_resolution_time_hours_{severity}.csv"
            with output_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "severity",
                        "hero_code",
                        "project_name",
                        "avg_resolution_time_hours",
                    ],
                )
                severity_data = hero_avg_hours.get(severity, {})
                for hero_spec in HERO_TYPE_SPECS:
                    hero_code = hero_spec.code
                    for project_name, avg_hours in sorted(severity_data.get(hero_code, {}).items()):
                        writer.writerow([severity, hero_code, project_name, avg_hours])
            output_paths[severity] = output_path

        return output_paths


def _datetime_to_utc_timestamp(value: datetime) -> float | None:
    if value.tzinfo is None:
        normalized_value = value.replace(tzinfo=UTC)
    else:
        normalized_value = value.astimezone(UTC)
    return normalized_value.timestamp()

