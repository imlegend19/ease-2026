"""Compute RQ3 issue outcomes for hero categories."""


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
        choices=(FixerAttributionPolicy.ASSIGNEE.value, FixerAttributionPolicy.COMMIT_AUTHOR.value),
        required=True,
        help="Fixer attribution policy.",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Refresh reverse-identity cache from Mongo before computing outcomes.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    fixer_policy = FixerAttributionPolicy(args.fixer)
    output_paths = IssueOutcomesComputer(
        refresh_identity_cache=args.refresh_identity_cache
    ).compute_and_write(fixer_policy=fixer_policy)

    print("Generated RQ3 outcome CSVs:")
    for severity, output_path in sorted(output_paths.items()):
        print(f"- {severity}: {output_path}")


if __name__ == "__main__":
    main()
