"""Compute RQ3 issue outcomes for hero categories."""

from __future__ import annotations

import argparse

from ease2026.core.logging import setup_logging
from ease2026.outcomes.definitions import FixerAttributionPolicy
from ease2026.outcomes.issue_outcomes import IssueOutcomesComputer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute RQ3 outcomes by project, hero code, and severity.",
    )
    parser.add_argument(
        "--fixer",
        choices=(
            FixerAttributionPolicy.ASSIGNEE.value,
            FixerAttributionPolicy.ASSIGNEE_AT_FIX_TIME.value,
            FixerAttributionPolicy.COMMIT_AUTHOR.value,
            "both",
        ),
        default="both",
        help="Fixer attribution policy (default: both).",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Refresh reverse-identity cache from Mongo before computing outcomes.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def _selected_fixer_policies(raw: str) -> tuple[FixerAttributionPolicy, ...]:
    if raw == "both":
        return (
            FixerAttributionPolicy.ASSIGNEE,
            FixerAttributionPolicy.ASSIGNEE_AT_FIX_TIME,
            FixerAttributionPolicy.COMMIT_AUTHOR,
        )
    return (FixerAttributionPolicy(raw),)


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    computer = IssueOutcomesComputer(refresh_identity_cache=args.refresh_identity_cache)
    output_paths: dict[str, str] = {}
    for fixer_policy in _selected_fixer_policies(args.fixer):
        paths = computer.compute_and_write(fixer_policy=fixer_policy)
        for severity, output_path in sorted(paths.items()):
            output_paths[f"{fixer_policy.value}_{severity}"] = str(output_path)

    print("Generated RQ3 outcome CSVs:")
    for key, output_path in sorted(output_paths.items()):
        print(f"- {key}: {output_path}")


if __name__ == "__main__":
    main()
