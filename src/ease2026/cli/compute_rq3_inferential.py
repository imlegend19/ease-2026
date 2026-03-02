"""Compute inferential RQ3 outputs (mean rankings, Kendall tau, Scott-Knott ESD)."""

from __future__ import annotations

import argparse

from ease2026.analysis.rq3_inferential import Rq3InferentialAnalyzer
from ease2026.core.logging import setup_logging
from ease2026.outcomes.definitions import FixerAttributionPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate inferential RQ3 artifacts from rq3_outcomes CSVs, including "
            "mean rankings, Kendall tau matrices, and optional Scott-Knott ESD "
            "rankings via Docker+R."
        ),
    )
    parser.add_argument(
        "--fixer",
        choices=(
            FixerAttributionPolicy.ASSIGNEE.value,
            FixerAttributionPolicy.COMMIT_AUTHOR.value,
            "both",
        ),
        default="both",
        help="Fixer attribution mode to process (default: both).",
    )
    parser.add_argument(
        "--docker-image",
        default="rocker/r2u:24.04",
        help="Docker image used for Scott-Knott ESD (default: rocker/r2u:24.04).",
    )
    parser.add_argument(
        "--skip-sk-esd",
        action="store_true",
        help="Skip Docker-based Scott-Knott ESD ranking generation.",
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
    analyzer = Rq3InferentialAnalyzer()

    output_paths: dict[str, str] = {}
    for fixer_policy in _selected_fixer_policies(args.fixer):
        paths = analyzer.run(
            fixer_policy=fixer_policy,
            docker_image=args.docker_image,
            run_sk_esd=not args.skip_sk_esd,
        )
        for key, path in sorted(paths.items()):
            output_paths[f"{fixer_policy.value}_{key}"] = str(path)

    print("Generated RQ3 inferential artifacts:")
    for key, path in sorted(output_paths.items()):
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
