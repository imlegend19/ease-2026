"""CLI entrypoint to generate all hero categories end-to-end."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.socio_technical.median_based import SocioTechnicalMedianPipeline
from pipelines.social.comment_based import SocialCommentHeroPipeline
from pipelines.social.issue_based import SocialIssueHeroPipeline
from pipelines.super.intersection_based import SuperIntersectionPipeline
from pipelines.techno_social.median_based import TechnoSocialMedianPipeline
from pipelines.technical.commit_based import TechnicalCommitHeroPipeline
from pipelines.technical.file_based import TechnicalFileHeroPipeline
from pipelines.technical.loc_based import TechnicalLocHeroPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run all hero-generation pipelines once: social, technical, super, "
            "socio-technical, and techno-social."
        ),
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild identity cache from MongoDB before running.",
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

    social_comment_csv = SocialCommentHeroPipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
    )
    social_issue_csv = SocialIssueHeroPipeline().run(write_interim=True)
    technical_commit_csv = TechnicalCommitHeroPipeline().run(write_interim=True)
    technical_loc_csv = TechnicalLocHeroPipeline().run(write_interim=True)
    technical_file_csv = TechnicalFileHeroPipeline().run(write_interim=True)

    super_csv_paths = SuperIntersectionPipeline().run_all()
    socio_csv_paths = SocioTechnicalMedianPipeline().run_all()
    techno_csv_paths = TechnoSocialMedianPipeline().run_all()

    print("Generated hero CSV files:")
    print(f"- {social_comment_csv}")
    print(f"- {social_issue_csv}")
    print(f"- {technical_commit_csv}")
    print(f"- {technical_loc_csv}")
    print(f"- {technical_file_csv}")
    for output_path in super_csv_paths:
        print(f"- {output_path}")
    for output_path in socio_csv_paths:
        print(f"- {output_path}")
    for output_path in techno_csv_paths:
        print(f"- {output_path}")


if __name__ == "__main__":
    main()
