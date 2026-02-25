"""Build project->hero-author membership maps from generated hero CSV files."""

import csv
import pickle
from pathlib import Path

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_catalog import HERO_TYPE_SPECS

logger = get_logger(__name__)

ProjectHeroAuthorMap = dict[str, set[str]]
HeroMembershipByCode = dict[str, ProjectHeroAuthorMap]


class HeroMembershipPipeline:
    @property
    def interim_dir(self) -> Path:
        return settings.interim_dir / "analysis" / "hero_membership"

    @property
    def combined_pickle_path(self) -> Path:
        return self.interim_dir / "hero_membership_by_code.pkl"

    def run(self, write_interim: bool = True) -> HeroMembershipByCode:
        membership_by_code: HeroMembershipByCode = {}

        for spec in HERO_TYPE_SPECS:
            membership_by_code[spec.code] = self._read_membership_from_csv(
                csv_path=spec.csv_path,
                project_column=spec.project_column,
                author_column=spec.author_column,
            )

        if write_interim:
            self._write_pickles(membership_by_code)

        logger.info(
            "Built hero membership index",
            hero_type_count=len(membership_by_code),
            project_membership_count=sum(len(projects) for projects in membership_by_code.values()),
            output_pickle=str(self.combined_pickle_path),
        )
        return membership_by_code

    def load_or_build(self) -> HeroMembershipByCode:
        if self.combined_pickle_path.exists():
            with self.combined_pickle_path.open("rb") as file:
                return pickle.load(file)
        return self.run(write_interim=True)

    @staticmethod
    def _read_membership_from_csv(
        csv_path: Path,
        project_column: str,
        author_column: str,
    ) -> ProjectHeroAuthorMap:
        membership: ProjectHeroAuthorMap = {}

        if not csv_path.exists():
            logger.warning("Hero CSV missing; using empty membership", csv_path=str(csv_path))
            return membership

        with csv_path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                project_name = row.get(project_column)
                author_id = row.get(author_column)
                if not project_name or not author_id:
                    continue

                membership.setdefault(project_name, set()).add(str(author_id))

        return membership

    def _write_pickles(self, membership_by_code: HeroMembershipByCode) -> None:
        ensure_directory(self.interim_dir)

        with self.combined_pickle_path.open("wb") as file:
            pickle.dump(membership_by_code, file)

        for hero_code, project_map in membership_by_code.items():
            output_path = self.interim_dir / f"{hero_code.lower()}_project_author_set.pkl"
            with output_path.open("wb") as file:
                pickle.dump(project_map, file)
