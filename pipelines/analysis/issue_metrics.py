"""Compute fixed/reopened issue percentages for each hero type and severity."""

from __future__ import annotations

import csv
import pickle
from dataclasses import dataclass
from pathlib import Path

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from identity.reverse_identity import ReverseIdentityResolver
from pipelines.analysis.hero_catalog import ALL_SEVERITIES, HERO_TYPE_SPECS
from pipelines.analysis.hero_membership import HeroMembershipByCode, HeroMembershipPipeline
from pipelines.analysis.issue_data import IssueEvent, IssueMetadata, build_issue_metadata, build_relevant_issue_events

logger = get_logger(__name__)

IssueMetricByProject = dict[str, float]
IssueMetricByHero = dict[str, IssueMetricByProject]
IssueMetricBySeverity = dict[str, IssueMetricByHero]


@dataclass(frozen=True, slots=True)
class IssuePayload:
    project_name: str
    priority: str | None
    assignee_ids: frozenset[str]
    events: tuple[IssueEvent, ...]


@dataclass(frozen=True, slots=True)
class IssueMetricOutputPaths:
    fixed_pickles: dict[str, Path]
    reopened_pickles: dict[str, Path]
    fixed_csv: dict[str, Path]
    reopened_csv: dict[str, Path]


class IssueOutcomeMetricsPipeline:
    @property
    def interim_root(self) -> Path:
        return settings.interim_dir / "analysis" / "issue_metrics"

    @property
    def fixed_pickle_root(self) -> Path:
        return self.interim_root / "fixed"

    @property
    def reopened_pickle_root(self) -> Path:
        return self.interim_root / "reopened"

    @property
    def output_root(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "issue_metrics"

    def run(
        self,
        refresh_identity_cache: bool = False,
        write_interim: bool = True,
        write_csv: bool = True,
    ) -> IssueMetricOutputPaths:
        hero_membership = HeroMembershipPipeline().load_or_build()
        reverse_identity_resolver = ReverseIdentityResolver()
        reverse_identity_map = reverse_identity_resolver.load_or_build(refresh_cache=refresh_identity_cache)

        issue_metadata = build_issue_metadata(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=reverse_identity_resolver,
        )
        events_by_issue = build_relevant_issue_events()
        issue_payload_by_issue, issue_ids_by_project = self._build_issue_payload_index(
            issue_metadata=issue_metadata,
            events_by_issue=events_by_issue,
        )

        fixed_metrics, reopened_metrics = self._compute_metrics(
            hero_membership=hero_membership,
            issue_payload_by_issue=issue_payload_by_issue,
            issue_ids_by_project=issue_ids_by_project,
        )

        fixed_pickle_paths: dict[str, Path] = {}
        reopened_pickle_paths: dict[str, Path] = {}
        fixed_csv_paths: dict[str, Path] = {}
        reopened_csv_paths: dict[str, Path] = {}

        if write_interim:
            fixed_pickle_paths = self._write_metric_pickles(
                metric_by_severity=fixed_metrics,
                output_dir=self.fixed_pickle_root,
                metric_name="fixed",
            )
            reopened_pickle_paths = self._write_metric_pickles(
                metric_by_severity=reopened_metrics,
                output_dir=self.reopened_pickle_root,
                metric_name="reopened",
            )

        if write_csv:
            fixed_csv_paths = self._write_metric_csv(
                metric_by_severity=fixed_metrics,
                metric_name="fixed",
            )
            reopened_csv_paths = self._write_metric_csv(
                metric_by_severity=reopened_metrics,
                metric_name="reopened",
            )

        logger.info(
            "Computed issue outcome metrics",
            issue_count=len(issue_payload_by_issue),
            project_count=len(issue_ids_by_project),
            hero_type_count=len(hero_membership),
        )

        return IssueMetricOutputPaths(
            fixed_pickles=fixed_pickle_paths,
            reopened_pickles=reopened_pickle_paths,
            fixed_csv=fixed_csv_paths,
            reopened_csv=reopened_csv_paths,
        )

    @staticmethod
    def _build_issue_payload_index(
        issue_metadata: dict[str, IssueMetadata],
        events_by_issue: dict[str, list[IssueEvent]],
    ) -> tuple[dict[str, IssuePayload], dict[str, list[str]]]:
        issue_payload_by_issue: dict[str, IssuePayload] = {}
        issue_ids_by_project: dict[str, list[str]] = {}

        for issue_id, events in events_by_issue.items():
            metadata = issue_metadata.get(issue_id)
            if metadata is None:
                continue
            if not metadata.project_name:
                continue
            if not metadata.assignee_ids:
                continue

            payload = IssuePayload(
                project_name=metadata.project_name,
                priority=metadata.priority,
                assignee_ids=metadata.assignee_ids,
                events=tuple(events),
            )
            issue_payload_by_issue[issue_id] = payload
            issue_ids_by_project.setdefault(payload.project_name, []).append(issue_id)

        return issue_payload_by_issue, issue_ids_by_project

    @staticmethod
    def _compute_metrics(
        hero_membership: HeroMembershipByCode,
        issue_payload_by_issue: dict[str, IssuePayload],
        issue_ids_by_project: dict[str, list[str]],
    ) -> tuple[IssueMetricBySeverity, IssueMetricBySeverity]:
        hero_codes = [spec.code for spec in HERO_TYPE_SPECS]

        fixed_metrics: IssueMetricBySeverity = {
            severity: {hero_code: {} for hero_code in hero_codes}
            for severity in ALL_SEVERITIES
        }
        reopened_metrics: IssueMetricBySeverity = {
            severity: {hero_code: {} for hero_code in hero_codes}
            for severity in ALL_SEVERITIES
        }

        for hero_code, project_hero_authors in hero_membership.items():
            for project_name, hero_author_ids in project_hero_authors.items():
                if not hero_author_ids:
                    continue

                project_issue_ids = issue_ids_by_project.get(project_name, [])
                if not project_issue_ids:
                    continue

                relevant_issue_ids = [
                    issue_id
                    for issue_id in project_issue_ids
                    if issue_payload_by_issue[issue_id].assignee_ids.intersection(hero_author_ids)
                ]
                if not relevant_issue_ids:
                    continue

                for severity in ALL_SEVERITIES:
                    severity_issue_ids = [
                        issue_id
                        for issue_id in relevant_issue_ids
                        if severity == "all" or issue_payload_by_issue[issue_id].priority == severity
                    ]
                    if not severity_issue_ids:
                        continue

                    total_issues = len(severity_issue_ids)
                    fixed_issue_events = 0
                    reopened_issues = 0

                    for issue_id in severity_issue_ids:
                        payload = issue_payload_by_issue[issue_id]
                        fixed_seen = False
                        reopened_after_fixed = False

                        for event in payload.events:
                            if event.status == "resolution" and event.new_value == "fixed":
                                fixed_issue_events += 1
                                fixed_seen = True
                            elif fixed_seen and event.status == "status" and event.new_value == "reopened":
                                reopened_after_fixed = True
                                break

                        if reopened_after_fixed:
                            reopened_issues += 1

                    fixed_percentage = (fixed_issue_events / total_issues) * 100
                    reopened_percentage = (reopened_issues / total_issues) * 100

                    fixed_metrics[severity][hero_code][project_name] = fixed_percentage
                    reopened_metrics[severity][hero_code][project_name] = reopened_percentage

        return fixed_metrics, reopened_metrics

    @staticmethod
    def _write_metric_pickles(
        metric_by_severity: IssueMetricBySeverity,
        output_dir: Path,
        metric_name: str,
    ) -> dict[str, Path]:
        ensure_directory(output_dir)
        output_paths: dict[str, Path] = {}

        for severity, metric_by_hero in metric_by_severity.items():
            output_path = output_dir / f"{severity}_{metric_name}_percentage_by_hero.pkl"
            with output_path.open("wb") as file:
                pickle.dump(metric_by_hero, file)
            output_paths[severity] = output_path

        return output_paths

    def _write_metric_csv(
        self,
        metric_by_severity: IssueMetricBySeverity,
        metric_name: str,
    ) -> dict[str, Path]:
        ensure_directory(self.output_root)
        output_paths: dict[str, Path] = {}

        for severity, metric_by_hero in metric_by_severity.items():
            output_path = self.output_root / f"{metric_name}_{severity}_percentages.csv"
            with output_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(
                    [
                        "severity",
                        "hero_code",
                        "project_name",
                        f"{metric_name}_percentage",
                    ],
                )
                for hero_code in (spec.code for spec in HERO_TYPE_SPECS):
                    project_values = metric_by_hero.get(hero_code, {})
                    for project_name, value in sorted(project_values.items()):
                        writer.writerow([severity, hero_code, project_name, value])
            output_paths[severity] = output_path

        return output_paths

    def load_metric_pickle(self, metric_name: str, severity: str) -> IssueMetricByHero:
        if metric_name not in {"fixed", "reopened"}:
            raise ValueError(f"Unsupported metric '{metric_name}'")
        if severity not in ALL_SEVERITIES:
            raise ValueError(f"Unsupported severity '{severity}'")

        metric_root = self.fixed_pickle_root if metric_name == "fixed" else self.reopened_pickle_root
        file_path = metric_root / f"{severity}_{metric_name}_percentage_by_hero.pkl"
        if not file_path.exists():
            return {spec.code: {} for spec in HERO_TYPE_SPECS}

        with file_path.open("rb") as file:
            return pickle.load(file)
