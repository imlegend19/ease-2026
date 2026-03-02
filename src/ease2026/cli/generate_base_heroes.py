"""Generate the five base hero sets (T1/T2/T3/S1/S2)."""


import argparse
from collections.abc import Callable

from ease2026.core.constants import (
    DEFAULT_HERO_COVERAGE_FRACTION,
    DEFAULT_TOP_CONTRIBUTOR_FRACTION,
)
from ease2026.core.logging import setup_logging
from ease2026.identity.canonical import load_identity_context
from ease2026.hero.generate import (
    HeroGenerationResult,
    ProjectContributionMap,
    generate_hero_outputs,
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
from ease2026.identity.reverse_identity import ReverseIdentityMap, ReverseIdentityResolver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate base hero CSVs for T1/T2/T3/S1/S2 metrics.",
    )
    parser.add_argument(
        "--top-fraction",
        type=float,
        default=DEFAULT_TOP_CONTRIBUTOR_FRACTION,
        help="Top contributor fraction used for hero candidate selection (e.g., 0.2).",
    )
    parser.add_argument(
        "--coverage-fraction",
        type=float,
        default=DEFAULT_HERO_COVERAGE_FRACTION,
        help="Coverage fraction required to classify a project as hero (e.g., 0.8).",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Refresh reverse-identity cache from Mongo before generating metrics.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    if not 0 < args.top_fraction <= 1:
        parser.error("--top-fraction must be in the range (0, 1].")
    if not 0 < args.coverage_fraction <= 1:
        parser.error("--coverage-fraction must be in the range (0, 1].")

    return args


def _base_metric_extractors(
    reverse_identity_map: ReverseIdentityMap,
    reverse_identity_resolver: ReverseIdentityResolver,
) -> list[tuple[str, Callable[[], ProjectContributionMap]]]:
    return [
        (
            "T1",
            lambda: compute_commit_count_contributions(
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            ),
        ),
        (
            "T2",
            lambda: compute_file_touch_contributions(
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            ),
        ),
        (
            "T3",
            lambda: compute_loc_churn_contributions(
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            ),
        ),
        (
            "S1",
            lambda: compute_comment_count_contributions(
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            ),
        ),
        (
            "S2",
            lambda: compute_issue_participation_contributions(
                reverse_identity_map=reverse_identity_map,
                reverse_identity_resolver=reverse_identity_resolver,
            ),
        ),
    ]


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    reverse_identity_map, reverse_identity_resolver = load_identity_context(
        refresh_cache=args.refresh_identity_cache
    )

    results: list[HeroGenerationResult] = []
    for metric_name, extractor in _base_metric_extractors(
        reverse_identity_map=reverse_identity_map,
        reverse_identity_resolver=reverse_identity_resolver,
    ):
        contribution_map = extractor()
        result = generate_hero_outputs(
            contribution_map=contribution_map,
            metric_name=metric_name,
            top_fraction=args.top_fraction,
            coverage_fraction=args.coverage_fraction,
        )
        results.append(result)

    print("Generated base hero CSVs:")
    for result in results:
        hero_projects = sum(1 for is_hero in result.hero_project_flags.values() if is_hero)
        hero_members = sum(len(author_counts) for author_counts in result.hero_members.values())
        print(
            f"- {result.metric_name}: {result.csv_path} "
            f"(hero_projects={hero_projects}, hero_members={hero_members})"
        )


if __name__ == "__main__":
    main()
