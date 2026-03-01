"""Run final-table analyses for RQ1/RQ2/RQ3."""

from __future__ import annotations

import argparse

from ease2026.analysis.rq1 import Rq1Analyzer
from ease2026.analysis.rq2 import Rq2Analyzer
from ease2026.analysis.rq3 import Rq3Analyzer
from ease2026.core.logging import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate final analysis tables for RQ1/RQ2/RQ3. "
            "Assumes hero CSVs and RQ3 outcome CSVs already exist."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    output_paths: dict[str, str] = {}
    output_paths.update({key: str(path) for key, path in Rq1Analyzer().run().items()})
    output_paths.update({key: str(path) for key, path in Rq2Analyzer().run().items()})
    output_paths.update({key: str(path) for key, path in Rq3Analyzer().run().items()})

    print("Generated final analysis tables:")
    for key, path in sorted(output_paths.items()):
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
