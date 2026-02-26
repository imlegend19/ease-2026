"""CLI entrypoint for SANER-style RQ3 compatibility outputs."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.rq3_legacy_exports import Rq3LegacyExportPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate SANER-style RQ3 artifacts (legacy pickle names, Scott-Knott "
            "CSVs, and Kendall Tau CSV aliases) from ease-2026 pipelines."
        ),
    )
    parser.add_argument(
        "--refresh-identity-cache",
        action="store_true",
        help="Rebuild reverse-identity cache before regenerating dependencies.",
    )
    parser.add_argument(
        "--skip-dependencies",
        action="store_true",
        help=(
            "Do not rerun issue-metrics/rankings/SK-ESD pipelines. "
            "Only export legacy-format files from existing artifacts."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    outputs = Rq3LegacyExportPipeline().run_all(
        refresh_identity_cache=args.refresh_identity_cache,
        regenerate_dependencies=not args.skip_dependencies,
    )
    print("Generated legacy RQ3 artifacts:")
    print(f"- mean summary: {outputs.mean_summary_path}")
    print(f"- SK-ESD summary: {outputs.sk_esd_summary_path}")
    print("- Kendall aliases:")
    for filename, path in sorted(outputs.kendall_paths.items()):
        print(f"  - {filename}: {path}")


if __name__ == "__main__":
    main()
