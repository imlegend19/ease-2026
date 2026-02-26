"""CLI entrypoint for socio-technical heroes (social-first median filter)."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.socio_technical.median_based import SocioTechnicalMedianPipeline
from pipelines.social.comment_based import SocialCommentHeroPipeline
from pipelines.social.issue_based import SocialIssueHeroPipeline
from pipelines.technical.commit_based import TechnicalCommitHeroPipeline
from pipelines.technical.file_based import TechnicalFileHeroPipeline
from pipelines.technical.loc_based import TechnicalLocHeroPipeline
from scripts.heroes.prerequisites import (
    SOCIAL_COMMENT,
    SOCIAL_ISSUE,
    TECHNICAL_COMMIT,
    TECHNICAL_FILE,
    TECHNICAL_LOC,
    ensure_prerequisites,
)

SOCIO_TECHNICAL_PREREQUISITES = (
    SOCIAL_COMMENT,
    SOCIAL_ISSUE,
    TECHNICAL_COMMIT,
    TECHNICAL_FILE,
    TECHNICAL_LOC,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate socio-technical hero CSVs across all six combinations.",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild identity cache from MongoDB before running.",
    )
    parser.add_argument(
        "--include-prerequisites",
        action="store_true",
        help=(
            "Also run social/technical prerequisite pipelines before socio-technical heroes. "
            "By default this script only computes socio-technical heroes from existing artifacts."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    if args.include_prerequisites:
        SocialCommentHeroPipeline().run(
            refresh_identity_cache=args.refresh_identity_cache,
            write_interim=True,
        )
        SocialIssueHeroPipeline().run(write_interim=True)
        TechnicalCommitHeroPipeline().run(write_interim=True)
        TechnicalLocHeroPipeline().run(write_interim=True)
        TechnicalFileHeroPipeline().run(write_interim=True)
    else:
        ensure_prerequisites(
            SOCIO_TECHNICAL_PREREQUISITES,
            pipeline_name="socio-technical heroes",
        )

    output_paths = SocioTechnicalMedianPipeline().run_all()
    print("Generated CSV files:")
    for output_path in output_paths:
        print(f"- {output_path}")


if __name__ == "__main__":
    main()
