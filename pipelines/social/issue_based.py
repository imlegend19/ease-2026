"""Generate social heroes based on unique issues touched in comments."""


import csv
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.constants import (
    COMMENTS_WITH_ISSUE_COLLECTION,
    DEFAULT_HERO_COVERAGE_FRACTION,
    DEFAULT_TOP_CONTRIBUTOR_FRACTION,
)
from core.logging import get_logger
from core.mongo import get_mongo_collection
from core.paths import ensure_directory
from core.settings import settings
from identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver
from pipelines.common.hero_rules import compute_hero_flags, extract_top_authors

logger = get_logger(__name__)

ProjectAuthorIssues = dict[str, dict[Any, set[Any]]]
ProjectAuthorCounts = dict[str, dict[Any, int]]
ProjectHeroFlags = dict[str, bool]


@dataclass(frozen=True, slots=True)
class SocialIssueHeroRow:
    project_name: str
    author_id: Any
    issue_count: int


@dataclass(slots=True)
class SocialIssueHeroPipeline:
    top_contributor_fraction: float = DEFAULT_TOP_CONTRIBUTOR_FRACTION
    hero_coverage_fraction: float = DEFAULT_HERO_COVERAGE_FRACTION
    reverse_identity_resolver: ReverseIdentityResolver = field(default_factory=ReverseIdentityResolver)

    @property
    def interim_dir(self) -> Path:
        return settings.interim_dir / "social" / "issue_based"

    @property
    def output_csv_path(self) -> Path:
        return settings.outputs_csv_dir / "social" / "social_heroes_issue_based.csv"

    def run(self, refresh_identity_cache: bool = False, write_interim: bool = True) -> Path:
        reverse_identity_map = self.reverse_identity_resolver.load_or_build(refresh_cache=refresh_identity_cache)

        records = get_mongo_collection(COMMENTS_WITH_ISSUE_COLLECTION).find({})
        project_author_issues = self._build_project_author_issues(records, reverse_identity_map)
        project_author_counts = self._build_project_author_counts(project_author_issues)
        top_authors = extract_top_authors(project_author_counts, self.top_contributor_fraction)
        hero_flags = compute_hero_flags(project_author_counts, top_authors, self.hero_coverage_fraction)
        hero_rows = self._build_rows(top_authors, hero_flags)

        if write_interim:
            self._write_interim(project_author_issues, project_author_counts, top_authors, hero_flags)

        self._write_csv(hero_rows)
        logger.info(
            "Completed social issue heroes pipeline",
            hero_projects=sum(1 for is_hero in hero_flags.values() if is_hero),
            hero_rows=len(hero_rows),
            output_csv=str(self.output_csv_path),
        )
        return self.output_csv_path

    def _build_project_author_issues(
        self,
        records,
        reverse_identity_map: ReverseIdentityMap,
    ) -> ProjectAuthorIssues:
        project_author_issues: ProjectAuthorIssues = {}

        for record in records:
            try:
                issue_id = record["issue_id"]
                person_id = record["author_id"]
                project_name = record["issue_info"]["project_name_info"]["name"]
            except KeyError:
                continue

            merged_author_id = self.reverse_identity_resolver.resolve_person_id(person_id, reverse_identity_map)
            author_issues = project_author_issues.setdefault(project_name, {}).setdefault(merged_author_id, set())
            author_issues.add(issue_id)

        return project_author_issues

    @staticmethod
    def _build_project_author_counts(project_author_issues: ProjectAuthorIssues) -> ProjectAuthorCounts:
        counts: ProjectAuthorCounts = {}
        for project_name, author_issues in project_author_issues.items():
            sorted_counts = sorted(
                ((author_id, len(issue_ids)) for author_id, issue_ids in author_issues.items()),
                key=lambda item: item[1],
                reverse=True,
            )
            counts[project_name] = {author_id: count for author_id, count in sorted_counts}
        return counts

    @staticmethod
    def _build_rows(top_authors: ProjectAuthorCounts, hero_flags: ProjectHeroFlags) -> list[SocialIssueHeroRow]:
        rows: list[SocialIssueHeroRow] = []
        for project_name, author_counts in top_authors.items():
            if not hero_flags.get(project_name, False):
                continue
            for author_id, issue_count in author_counts.items():
                rows.append(
                    SocialIssueHeroRow(
                        project_name=project_name,
                        author_id=author_id,
                        issue_count=issue_count,
                    ),
                )
        return rows

    def _write_csv(self, hero_rows: list[SocialIssueHeroRow]) -> None:
        ensure_directory(self.output_csv_path.parent)
        with self.output_csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["project_name", "author_id", "issue_count"])
            writer.writerows(
                [row.project_name, str(row.author_id), row.issue_count]
                for row in hero_rows
            )

    def _write_interim(
        self,
        project_author_issues: ProjectAuthorIssues,
        project_author_counts: ProjectAuthorCounts,
        top_authors: ProjectAuthorCounts,
        hero_flags: ProjectHeroFlags,
    ) -> None:
        ensure_directory(self.interim_dir)

        payloads = {
            "project_author_issues.pkl": project_author_issues,
            "project_author_issue_counts.pkl": project_author_counts,
            "project_top_author_issues.pkl": top_authors,
            "project_hero_flags.pkl": hero_flags,
        }

        for filename, data in payloads.items():
            file_path = self.interim_dir / filename
            with file_path.open("wb") as file:
                pickle.dump(data, file)
