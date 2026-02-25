"""Canonical hero-type metadata used by analysis pipelines."""

from dataclasses import dataclass
from pathlib import Path

from core.settings import settings

PRIORITY_SEVERITIES: tuple[str, ...] = (
    "minor",
    "major",
    "critical",
    "trivial",
    "blocker",
)

ALL_SEVERITIES: tuple[str, ...] = ("all", *PRIORITY_SEVERITIES)


@dataclass(frozen=True, slots=True)
class HeroTypeSpec:
    code: str
    category: str
    name: str
    csv_relative_path: Path
    project_column: str = "project_name"
    author_column: str = "author_id"

    @property
    def csv_path(self) -> Path:
        return settings.outputs_csv_dir / self.csv_relative_path


HERO_TYPE_SPECS: tuple[HeroTypeSpec, ...] = (
    HeroTypeSpec(
        code="S1",
        category="social",
        name="social_heroes_comment_based",
        csv_relative_path=Path("social/social_heroes_comment_based.csv"),
    ),
    HeroTypeSpec(
        code="S2",
        category="social",
        name="social_heroes_issue_based",
        csv_relative_path=Path("social/social_heroes_issue_based.csv"),
    ),
    HeroTypeSpec(
        code="T1",
        category="technical",
        name="technical_heroes_commit_based",
        csv_relative_path=Path("technical/technical_heroes_commit_based.csv"),
    ),
    HeroTypeSpec(
        code="T2",
        category="technical",
        name="technical_heroes_file_based",
        csv_relative_path=Path("technical/technical_heroes_file_based.csv"),
    ),
    HeroTypeSpec(
        code="T3",
        category="technical",
        name="technical_heroes_loc_based",
        csv_relative_path=Path("technical/technical_heroes_loc_based.csv"),
    ),
    HeroTypeSpec(
        code="TS1",
        category="techno_social",
        name="techno_social_heroes_commit_comments",
        csv_relative_path=Path("techno_social/techno_social_heroes_commit_comments.csv"),
    ),
    HeroTypeSpec(
        code="TS2",
        category="techno_social",
        name="techno_social_heroes_commit_issues",
        csv_relative_path=Path("techno_social/techno_social_heroes_commit_issues.csv"),
    ),
    HeroTypeSpec(
        code="TS3",
        category="techno_social",
        name="techno_social_heroes_file_comments",
        csv_relative_path=Path("techno_social/techno_social_heroes_file_comments.csv"),
    ),
    HeroTypeSpec(
        code="TS4",
        category="techno_social",
        name="techno_social_heroes_file_issues",
        csv_relative_path=Path("techno_social/techno_social_heroes_file_issues.csv"),
    ),
    HeroTypeSpec(
        code="TS5",
        category="techno_social",
        name="techno_social_heroes_loc_comments",
        csv_relative_path=Path("techno_social/techno_social_heroes_loc_comments.csv"),
    ),
    HeroTypeSpec(
        code="TS6",
        category="techno_social",
        name="techno_social_heroes_loc_issues",
        csv_relative_path=Path("techno_social/techno_social_heroes_loc_issues.csv"),
    ),
    HeroTypeSpec(
        code="ST1",
        category="socio_technical",
        name="socio_technical_heroes_comments_commits",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_comments_commits.csv"),
    ),
    HeroTypeSpec(
        code="ST2",
        category="socio_technical",
        name="socio_technical_heroes_issues_commits",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_issues_commits.csv"),
    ),
    HeroTypeSpec(
        code="ST3",
        category="socio_technical",
        name="socio_technical_heroes_comments_files",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_comments_files.csv"),
    ),
    HeroTypeSpec(
        code="ST4",
        category="socio_technical",
        name="socio_technical_heroes_issues_files",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_issues_files.csv"),
    ),
    HeroTypeSpec(
        code="ST5",
        category="socio_technical",
        name="socio_technical_heroes_comments_loc",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_comments_loc.csv"),
    ),
    HeroTypeSpec(
        code="ST6",
        category="socio_technical",
        name="socio_technical_heroes_issues_loc",
        csv_relative_path=Path("socio_technical/socio_technical_heroes_issues_loc.csv"),
    ),
    HeroTypeSpec(
        code="SH1",
        category="super",
        name="super_heroes_commit_comments",
        csv_relative_path=Path("super/super_heroes_commit_comments.csv"),
    ),
    HeroTypeSpec(
        code="SH2",
        category="super",
        name="super_heroes_commit_issues",
        csv_relative_path=Path("super/super_heroes_commit_issues.csv"),
    ),
    HeroTypeSpec(
        code="SH3",
        category="super",
        name="super_heroes_file_comments",
        csv_relative_path=Path("super/super_heroes_file_comments.csv"),
    ),
    HeroTypeSpec(
        code="SH4",
        category="super",
        name="super_heroes_file_issues",
        csv_relative_path=Path("super/super_heroes_file_issues.csv"),
    ),
    HeroTypeSpec(
        code="SH5",
        category="super",
        name="super_heroes_loc_comments",
        csv_relative_path=Path("super/super_heroes_loc_comments.csv"),
    ),
    HeroTypeSpec(
        code="SH6",
        category="super",
        name="super_heroes_loc_issues",
        csv_relative_path=Path("super/super_heroes_loc_issues.csv"),
    ),
)

HERO_TYPE_SPECS_BY_CODE: dict[str, HeroTypeSpec] = {spec.code: spec for spec in HERO_TYPE_SPECS}

# Keep this order aligned with RQ2 figures and labels in the paper.
RQ2_HERO_ORDER: tuple[str, ...] = (
    "ST1",
    "ST2",
    "ST3",
    "ST4",
    "ST5",
    "ST6",
    "S1",
    "S2",
    "T1",
    "T2",
    "T3",
    "TS1",
    "TS2",
    "TS3",
    "TS4",
    "TS5",
    "TS6",
    "SH1",
    "SH2",
    "SH3",
    "SH4",
    "SH5",
    "SH6",
)

RQ2_CLUSTERS: dict[str, tuple[str, ...]] = {
    "ST": ("ST1", "ST2", "ST3", "ST4", "ST5", "ST6"),
    "S": ("S1", "S2"),
    "T": ("T1", "T2", "T3"),
    "TS": ("TS1", "TS2", "TS3", "TS4", "TS5", "TS6"),
    "SH": ("SH1", "SH2", "SH3", "SH4", "SH5", "SH6"),
}
