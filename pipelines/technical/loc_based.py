"""Generate technical heroes based on lines changed (added + deleted)."""

from __future__ import annotations

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

ProjectAuthorCounts = dict[str, dict[Any, int]]
ProjectHeroFlags = dict[str, bool]


@dataclass(frozen=True, slots=True)
class TechnicalLocHeroRow:
    project_name: str
    author_id: Any
    loc_changed: int


@dataclass(slots=True)
class TechnicalLocHeroPipeline:
    top_contributor_fraction: float = DEFAULT_TOP_CONTRIBUTOR_FRACTION
    hero_coverage_fraction: float = DEFAULT_HERO_COVERAGE_FRACTION
    reverse_identity_resolver: ReverseIdentityResolver = field(default_factory=ReverseIdentityResolver)

    @property
    def interim_dir(self) -> Path:
        return settings.interim_dir / "technical" / "loc_based"

    @property
    def output_csv_path(self) -> Path:
        return settings.outputs_csv_dir / "technical" / "technical_heroes_loc_based.csv"

    def run(self, refresh_identity_cache: bool = False, write_interim: bool = True) -> Path:
        reverse_identity_map = self.reverse_identity_resolver.load_or_build(refresh_cache=refresh_identity_cache)
        commit_index = build_commit_project_author_index(
            reverse_identity_map=reverse_identity_map,
            reverse_identity_resolver=self.reverse_identity_resolver,
        )

        file_actions = get_mongo_collection(FILE_ACTION_COLLECTION).find(
            {},
            {"commit_id": 1, "lines_added": 1, "lines_deleted": 1},
        )
        project_author_counts = self._build_project_author_loc_counts(file_actions, commit_index)
        top_authors = extract_top_authors(project_author_counts, self.top_contributor_fraction)
        hero_flags = compute_hero_flags(project_author_counts, top_authors, self.hero_coverage_fraction)
        hero_rows = self._build_rows(top_authors, hero_flags)

        if write_interim:
            self._write_interim(commit_index, project_author_counts, top_authors, hero_flags)

        self._write_csv(hero_rows)
        logger.info(
            "Completed technical LOC heroes pipeline",
            hero_projects=sum(1 for is_hero in hero_flags.values() if is_hero),
            hero_rows=len(hero_rows),
            output_csv=str(self.output_csv_path),
        )
        return self.output_csv_path

    def _build_project_author_loc_counts(self, file_actions, commit_index) -> ProjectAuthorCounts:
        project_author_counts: ProjectAuthorCounts = {}
        for record in file_actions:
            commit_id = record.get("commit_id")
            if commit_id not in commit_index and str(commit_id) not in commit_index:
                continue

            project_name, author_id = commit_index.get(commit_id, commit_index[str(commit_id)])
            lines_added = self._to_int(record.get("lines_added"))
            lines_deleted = self._to_int(record.get("lines_deleted"))
            loc_changed = lines_added + lines_deleted

            author_counts = project_author_counts.setdefault(project_name, {})
            author_counts[author_id] = author_counts.get(author_id, 0) + loc_changed

        for project_name, author_counts in project_author_counts.items():
            project_author_counts[project_name] = dict(
                sorted(author_counts.items(), key=lambda item: item[1], reverse=True),
            )

        return project_author_counts

    @staticmethod
    def _to_int(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _build_rows(top_authors: ProjectAuthorCounts, hero_flags: ProjectHeroFlags) -> list[TechnicalLocHeroRow]:
        rows: list[TechnicalLocHeroRow] = []
        for project_name, author_counts in top_authors.items():
            if not hero_flags.get(project_name, False):
                continue
            for author_id, loc_changed in author_counts.items():
                rows.append(
                    TechnicalLocHeroRow(
                        project_name=project_name,
                        author_id=author_id,
                        loc_changed=loc_changed,
                    ),
                )
        return rows

    def _write_csv(self, hero_rows: list[TechnicalLocHeroRow]) -> None:
        ensure_directory(self.output_csv_path.parent)
        with self.output_csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["project_name", "author_id", "loc_changed"])
            writer.writerows(
                [row.project_name, str(row.author_id), row.loc_changed]
                for row in hero_rows
            )

    def _write_interim(
        self,
        commit_index,
        project_author_counts: ProjectAuthorCounts,
        top_authors: ProjectAuthorCounts,
        hero_flags: ProjectHeroFlags,
    ) -> None:
        ensure_directory(self.interim_dir)

        payloads = {
            "commit_project_author_index.pkl": commit_index,
            "project_author_loc_counts.pkl": project_author_counts,
            "project_top_author_loc.pkl": top_authors,
            "project_hero_flags.pkl": hero_flags,
        }

        for filename, data in payloads.items():
            file_path = self.interim_dir / filename
            with file_path.open("wb") as file:
                pickle.dump(data, file)

