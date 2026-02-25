"""CLI entrypoint for generating hero membership index artifacts."""

from __future__ import annotations

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.hero_membership import HeroMembershipPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build project->author membership pickles for all 23 hero categories.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    membership = HeroMembershipPipeline().run(write_interim=True)
    print("Generated hero membership pickles:")
    print(f"- hero_types={len(membership)}")


if __name__ == "__main__":
    main()

