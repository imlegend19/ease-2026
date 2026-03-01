"""Hero selection helpers."""

from ease2026.hero.generate import (
    HeroGenerationResult,
    build_hero_flags_and_members,
    generate_hero_outputs,
    write_hero_members_csv,
)
from ease2026.hero.rules import (
    hero_project_and_heroes,
    is_hero_project,
    select_top_contributors,
)
from ease2026.hero.social import (
    compute_comment_count_contributions,
    compute_issue_participation_contributions,
)
from ease2026.hero.technical import (
    compute_commit_count_contributions,
    compute_file_touch_contributions,
    compute_loc_churn_contributions,
)

__all__ = [
    "select_top_contributors",
    "is_hero_project",
    "hero_project_and_heroes",
    "compute_commit_count_contributions",
    "compute_file_touch_contributions",
    "compute_loc_churn_contributions",
    "compute_comment_count_contributions",
    "compute_issue_participation_contributions",
    "HeroGenerationResult",
    "build_hero_flags_and_members",
    "write_hero_members_csv",
    "generate_hero_outputs",
]
