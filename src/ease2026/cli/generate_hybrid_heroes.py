"""Generate hybrid hero sets (ST1..ST6, TS1..TS6, SH1..SH6)."""

from __future__ import annotations

import argparse

from ease2026.core.constants import (
    DEFAULT_HERO_COVERAGE_FRACTION,
    DEFAULT_TOP_CONTRIBUTOR_FRACTION,
)
from ease2026.core.logging import setup_logging
from ease2026.hero.generate import build_hero_flags_and_members
from ease2026.hero.hybrid import (
    SOCIOTECHNICAL_SPECS,
    SUPER_SPECS,
    TECHNOSOCIAL_SPECS,
    generate_sociotechnical,
    generate_super,
    generate_technosocial,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate hybrid hero CSVs for ST1..ST6, TS1..TS6, SH1..SH6.",
    )
    parser.add_argument(
        "--top-fraction",
        type=float,
        default=DEFAULT_TOP_CONTRIBUTOR_FRACTION,
        help="Top contributor fraction used for base hero selection (e.g., 0.2).",
    )
    parser.add_argument(
        "--coverage-fraction",
        type=float,
        default=DEFAULT_HERO_COVERAGE_FRACTION,
        help="Coverage fraction used for base hero project classification (e.g., 0.8).",
    )
    parser.add_argument(
        "--hybrid-quantile",
        type=float,
        default=0.5,
        help="Project-level quantile for hybrid filtering (e.g., 0.5 or 0.75).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    if not 0 < args.top_fraction <= 1:
        parser.error("--top-fraction must be in the range (0, 1].")
    if not 0 < args.coverage_fraction <= 1:
        parser.error("--coverage-fraction must be in the range (0, 1].")
    if not 0 <= args.hybrid_quantile <= 1:
        parser.error("--hybrid-quantile must be in the range [0, 1].")

    return args


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    contribution_map_by_code = {
        "T1": compute_commit_count_contributions(),
        "T2": compute_file_touch_contributions(),
        "T3": compute_loc_churn_contributions(),
        "S1": compute_comment_count_contributions(),
        "S2": compute_issue_participation_contributions(),
    }

    hero_members_by_code: dict[str, dict[str, dict[object, int]]] = {}
    for code, contribution_map in contribution_map_by_code.items():
        _, hero_members = build_hero_flags_and_members(
            contribution_map=contribution_map,
            top_fraction=args.top_fraction,
            coverage_fraction=args.coverage_fraction,
        )
        hero_members_by_code[code] = hero_members

    generated: list[tuple[str, str, int]] = []

    for spec in SOCIOTECHNICAL_SPECS:
        code, output_path, rows = generate_sociotechnical(
            spec=spec,
            hero_members_by_code=hero_members_by_code,
            contribution_map_by_code=contribution_map_by_code,
            quantile=args.hybrid_quantile,
        )
        generated.append((code, str(output_path), len(rows)))

    for spec in TECHNOSOCIAL_SPECS:
        code, output_path, rows = generate_technosocial(
            spec=spec,
            hero_members_by_code=hero_members_by_code,
            contribution_map_by_code=contribution_map_by_code,
            quantile=args.hybrid_quantile,
        )
        generated.append((code, str(output_path), len(rows)))

    for spec in SUPER_SPECS:
        code, output_path, rows = generate_super(
            spec=spec,
            hero_members_by_code=hero_members_by_code,
        )
        generated.append((code, str(output_path), len(rows)))

    print("Generated hybrid hero CSVs:")
    for code, output_path, row_count in generated:
        print(f"- {code}: {output_path} (rows={row_count})")


if __name__ == "__main__":
    main()

