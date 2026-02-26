"""Prerequisite artifact checks for hero-combination scripts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core.settings import settings

INTERIM_ROOT = settings.interim_dir


@dataclass(frozen=True, slots=True)
class Prerequisite:
    name: str
    command: str
    files: tuple[Path, ...]


SOCIAL_COMMENT = Prerequisite(
    name="social comment artifacts",
    command="python -m scripts.heroes.generate_social_comment_heroes",
    files=(
        INTERIM_ROOT / "social" / "comment_based" / "project_author_comment_counts.pkl",
        INTERIM_ROOT / "social" / "comment_based" / "project_top_author_comments.pkl",
        INTERIM_ROOT / "social" / "comment_based" / "project_hero_flags.pkl",
    ),
)

SOCIAL_ISSUE = Prerequisite(
    name="social issue artifacts",
    command="python -m scripts.heroes.generate_social_issue_heroes",
    files=(
        INTERIM_ROOT / "social" / "issue_based" / "project_author_issue_counts.pkl",
        INTERIM_ROOT / "social" / "issue_based" / "project_top_author_issues.pkl",
        INTERIM_ROOT / "social" / "issue_based" / "project_hero_flags.pkl",
    ),
)

TECHNICAL_COMMIT = Prerequisite(
    name="technical commit artifacts",
    command="python -m scripts.heroes.generate_technical_commit_heroes",
    files=(
        INTERIM_ROOT / "technical" / "commit_based" / "project_author_commit_counts.pkl",
        INTERIM_ROOT / "technical" / "commit_based" / "project_top_author_commits.pkl",
        INTERIM_ROOT / "technical" / "commit_based" / "project_hero_flags.pkl",
    ),
)

TECHNICAL_FILE = Prerequisite(
    name="technical file artifacts",
    command="python -m scripts.heroes.generate_technical_file_heroes",
    files=(
        INTERIM_ROOT / "technical" / "file_based" / "project_author_file_counts.pkl",
        INTERIM_ROOT / "technical" / "file_based" / "project_top_author_files.pkl",
        INTERIM_ROOT / "technical" / "file_based" / "project_hero_flags.pkl",
    ),
)

TECHNICAL_LOC = Prerequisite(
    name="technical LOC artifacts",
    command="python -m scripts.heroes.generate_technical_loc_heroes",
    files=(
        INTERIM_ROOT / "technical" / "loc_based" / "project_author_loc_counts.pkl",
        INTERIM_ROOT / "technical" / "loc_based" / "project_top_author_loc.pkl",
        INTERIM_ROOT / "technical" / "loc_based" / "project_hero_flags.pkl",
    ),
)


def ensure_prerequisites(
    prerequisites: Sequence[Prerequisite],
    pipeline_name: str,
) -> None:
    missing: list[tuple[Prerequisite, list[Path]]] = []
    for prerequisite in prerequisites:
        missing_files = [path for path in prerequisite.files if not path.exists()]
        if missing_files:
            missing.append((prerequisite, missing_files))

    if not missing:
        return

    print(f"Missing prerequisite artifacts for {pipeline_name}:")
    for prerequisite, missing_files in missing:
        print(f"- {prerequisite.name}:")
        for path in missing_files:
            print(f"  - {path}")

    print("")
    print("Run the missing prerequisite script(s):")
    ordered_commands: list[str] = []
    for prerequisite, _ in missing:
        if prerequisite.command not in ordered_commands:
            ordered_commands.append(prerequisite.command)
    for command in ordered_commands:
        print(f"  {command}")

    print("")
    print("Or run everything once:")
    print("  python -m scripts.heroes.generate_all_heroes --refresh-identity-cache")
    raise SystemExit(2)
