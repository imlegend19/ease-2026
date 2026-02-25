"""Generate technical heroes based on unique files touched."""

import csv
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.constants import (
    DEFAULT_HERO_COVERAGE_FRACTION,
    DEFAULT_TOP_CONTRIBUTOR_FRACTION,
    FILE_ACTION_COLLECTION,
)
from core.logging import get_logger
from core.mongo import get_mongo_collection
from core.paths import ensure_directory
from core.settings import settings
from identity.reverse_identity import ReverseIdentityResolver
from pipelines.common.hero_rules import compute_hero_flags, extract_top_authors
from pipelines.technical.shared import build_commit_project_author_index

logger = get_logger(__name__)

ProjectAuthorFileSets = dict[str, dict[Any, set[Any]]]
ProjectAuthorCounts = dict[str, dict[Any, int]]
ProjectHeroFlags = dict[str, bool]


@dataclass(frozen=True, slots=True)
class TechnicalFileHeroRow:
    project_name: str
    author_id: Any
    file_count: int


@dataclass(slots=True)
class TechnicalFileHeroPipeline:
    top_contributor_fraction: float = DEFAULT_TOP_CONTRIBUTOR_FRACTION
    hero_coverage_fraction: float = DEFAULT_HERO_COVERAGE_FRACTION
    reverse_identity_resolver: ReverseIdentityResolver = field(
        default_factory=ReverseIdentityResolver
    )

    @property
    def interim_dir(self) -> Path:
        return settings.interim_dir / "technical" / "file_based"

    @property
    def output_csv_path(self) -> Path:
        return settings.outputs_csv_dir / "technical" / "technical_heroes_file_based.csv"

    def run(self, refresh_identity_cache: bool = False, write_interim: bool = True) -> Path:
        reverse_identity_map = self.reverse_identity_resolver.load_or_build(
            refresh_cache=refresh_identity_cache
        )
        commit_index = build_commit_project_author_index(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=self.reverse_identity_resolver,
        )

        file_actions = get_mongo_collection(FILE_ACTION_COLLECTION).find(
            {},
            {"commit_id": 1, "file_id": 1},
        )
        project_author_files = self._build_project_author_file_sets(file_actions, commit_index)
        project_author_counts = self._build_project_author_counts(project_author_files)
        top_authors = extract_top_authors(project_author_counts, self.top_contributor_fraction)
        hero_flags = compute_hero_flags(
            project_author_counts, top_authors, self.hero_coverage_fraction
        )
        hero_rows = self._build_rows(top_authors, hero_flags)

        if write_interim:
            self._write_interim(
                commit_index, project_author_files, project_author_counts, top_authors, hero_flags
            )

        self._write_csv(hero_rows)
        logger.info(
            "Completed technical file heroes pipeline",
            hero_projects=sum(1 for is_hero in hero_flags.values() if is_hero),
            hero_rows=len(hero_rows),
            output_csv=str(self.output_csv_path),
        )
        return self.output_csv_path

    @staticmethod
    def _build_project_author_file_sets(file_actions, commit_index) -> ProjectAuthorFileSets:
        project_author_files: ProjectAuthorFileSets = {}
        for record in file_actions:
            commit_id = record.get("commit_id")
            file_id = record.get("file_id")
            if file_id is None:
                continue
            if commit_id not in commit_index and str(commit_id) not in commit_index:
                continue

            project_name, author_id = commit_index.get(commit_id, commit_index[str(commit_id)])
            author_files = project_author_files.setdefault(project_name, {}).setdefault(
                author_id, set()
            )
            author_files.add(file_id)

        return project_author_files

    @staticmethod
    def _build_project_author_counts(
        project_author_files: ProjectAuthorFileSets,
    ) -> ProjectAuthorCounts:
        counts: ProjectAuthorCounts = {}
        for project_name, author_files in project_author_files.items():
            sorted_counts = sorted(
                ((author_id, len(file_ids)) for author_id, file_ids in author_files.items()),
                key=lambda item: item[1],
                reverse=True,
            )
            counts[project_name] = {author_id: count for author_id, count in sorted_counts}
        return counts

    @staticmethod
    def _build_rows(
        top_authors: ProjectAuthorCounts, hero_flags: ProjectHeroFlags
    ) -> list[TechnicalFileHeroRow]:
        rows: list[TechnicalFileHeroRow] = []
        for project_name, author_counts in top_authors.items():
            if not hero_flags.get(project_name, False):
                continue
            for author_id, file_count in author_counts.items():
                rows.append(
                    TechnicalFileHeroRow(
                        project_name=project_name,
                        author_id=author_id,
                        file_count=file_count,
                    ),
                )
        return rows

    def _write_csv(self, hero_rows: list[TechnicalFileHeroRow]) -> None:
        ensure_directory(self.output_csv_path.parent)
        with self.output_csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["project_name", "author_id", "file_count"])
            writer.writerows(
                [row.project_name, str(row.author_id), row.file_count] for row in hero_rows
            )

    def _write_interim(
        self,
        commit_index,
        project_author_files: ProjectAuthorFileSets,
        project_author_counts: ProjectAuthorCounts,
        top_authors: ProjectAuthorCounts,
        hero_flags: ProjectHeroFlags,
    ) -> None:
        ensure_directory(self.interim_dir)

        payloads = {
            "commit_project_author_index.pkl": commit_index,
            "project_author_file_sets.pkl": project_author_files,
            "project_author_file_counts.pkl": project_author_counts,
            "project_top_author_files.pkl": top_authors,
            "project_hero_flags.pkl": hero_flags,
        }

        for filename, data in payloads.items():
            file_path = self.interim_dir / filename
            with file_path.open("wb") as file:
                pickle.dump(data, file)
