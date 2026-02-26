"""CLI entrypoint for RQ1 prevalence and distribution plots."""

import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.rq1_prevalence import Rq1PrevalencePipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RQ1 prevalence CSVs and Figure 1/2/3 plot artifacts.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    output_paths = Rq1PrevalencePipeline().run()
    print("Generated RQ1 artifacts:")
    print(f"- prevalence CSV: {output_paths.prevalence_csv_path}")
    print(
        f"- sociotechnical/technosocial CSV: "
        f"{output_paths.sociotechnical_technosocial_csv_path}"
    )
    print(f"- superhero CSV: {output_paths.superhero_csv_path}")
    print(f"- Figure 1 PNG: {output_paths.prevalence_plot_png_path}")
    print(f"- Figure 1 PDF: {output_paths.prevalence_plot_pdf_path}")
    print(f"- Figure 2 PNG: {output_paths.combined_distribution_png_path}")
    print(f"- Figure 2 PDF: {output_paths.combined_distribution_pdf_path}")
    print(f"- Figure 3 PNG: {output_paths.superhero_distribution_png_path}")
    print(f"- Figure 3 PDF: {output_paths.superhero_distribution_pdf_path}")


if __name__ == "__main__":
    main()
