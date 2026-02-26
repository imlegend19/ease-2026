"""CLI entrypoint for all migrated post-processing analysis pipelines."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.hero_membership import HeroMembershipPipeline
from pipelines.analysis.issue_metrics import IssueOutcomeMetricsPipeline
from pipelines.analysis.resolution_time import ResolutionTimePipeline
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline
from pipelines.analysis.rq1_prevalence import Rq1PrevalencePipeline
from pipelines.analysis.rq2_jaccard import Rq2JaccardPipeline
from pipelines.analysis.rq3_rankings import Rq3RankingPipeline
from pipelines.analysis.rq3_sk_esd import Rq3ScottKnottEsdPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all migrated SANER analysis pipelines (avg-time, fixed/reopened, RQ2, RQ3).",
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild reverse-identity cache from Mongo before running.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    HeroMembershipPipeline().run(write_interim=True)
    IssueOutcomeMetricsPipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
        write_csv=True,
    )
    ResolutionTimePipeline().run(
        refresh_identity_cache=args.refresh_identity_cache,
        write_interim=True,
        write_csv=True,
    )
    Rq1PrevalencePipeline().run()
    Rq2JaccardPipeline().run()
    Rq3RankingPipeline().run_all()
    Rq3ScottKnottEsdPipeline().run_all()
    Rq3LegacyExportPipeline().run_all(regenerate_dependencies=False)

    print("Generated all analysis artifacts.")


if __name__ == "__main__":
    main()
