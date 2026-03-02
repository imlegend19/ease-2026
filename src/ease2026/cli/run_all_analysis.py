"""Run final-table analyses for RQ1/RQ2/RQ3."""

from __future__ import annotations

import argparse

from ease2026.analysis.rq1 import Rq1Analyzer
from ease2026.analysis.rq2 import Rq2Analyzer
from ease2026.analysis.rq3 import Rq3Analyzer
from ease2026.analysis.rq3_inferential import Rq3InferentialAnalyzer
from ease2026.core.logging import setup_logging
from ease2026.outcomes.definitions import FixerAttributionPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate final analysis tables for RQ1/RQ2/RQ3. "
            "Assumes hero CSVs and RQ3 outcome CSVs already exist."
        ),
    )
    parser.add_argument(
        "--skip-inferential",
        action="store_true",
        help="Skip RQ3 inferential outputs (Kendall tau and Scott-Knott ESD).",
    )
    parser.add_argument(
        "--inferential-fixer",
        choices=(
            FixerAttributionPolicy.ASSIGNEE.value,
            FixerAttributionPolicy.COMMIT_AUTHOR.value,
            "both",
        ),
        default="both",
        help="Fixer attribution mode for inferential outputs (default: both).",
    )
    parser.add_argument(
        "--docker-image",
        default="rocker/r2u:24.04",
        help="Docker image used for Scott-Knott ESD (default: rocker/r2u:24.04).",
    )
    parser.add_argument(
        "--skip-sk-esd",
        action="store_true",
        help="Skip Docker-based Scott-Knott ESD generation.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def _selected_fixer_policies(raw: str) -> tuple[FixerAttributionPolicy, ...]:
    if raw == "both":
        return (
            FixerAttributionPolicy.ASSIGNEE,
            FixerAttributionPolicy.COMMIT_AUTHOR,
        )
    return (FixerAttributionPolicy(raw),)


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    output_paths: dict[str, str] = {}
    output_paths.update({key: str(path) for key, path in Rq1Analyzer().run().items()})
    output_paths.update({key: str(path) for key, path in Rq2Analyzer().run().items()})
    output_paths.update({key: str(path) for key, path in Rq3Analyzer().run().items()})
    if not args.skip_inferential:
        inferential = Rq3InferentialAnalyzer()
        for fixer_policy in _selected_fixer_policies(args.inferential_fixer):
            paths = inferential.run(
                fixer_policy=fixer_policy,
                docker_image=args.docker_image,
                run_sk_esd=not args.skip_sk_esd,
            )
            output_paths.update(
                {
                    f"rq3_inferential_{fixer_policy.value}_{key}": str(path)
                    for key, path in paths.items()
                }
            )

    print("Generated final analysis tables:")
    for key, path in sorted(output_paths.items()):
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
