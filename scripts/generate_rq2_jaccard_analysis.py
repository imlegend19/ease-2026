"""CLI entrypoint for RQ2 Jaccard matrices and plots."""


import argparse

from core.logging import setup_logging
from core.paths import ensure_artifact_directories
from pipelines.analysis.rq2_jaccard import Rq2JaccardPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RQ2 Jaccard matrix CSVs and plot artifacts.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)
    ensure_artifact_directories()

    output_paths = Rq2JaccardPipeline().run()
    print("Generated RQ2 artifacts:")
    print(f"- matrix: {output_paths.matrix_csv_path}")
    print(f"- pairs: {output_paths.sorted_pairs_csv_path}")
    print(f"- cluster matrix: {output_paths.cluster_matrix_csv_path}")
    print(f"- T plot: {output_paths.t_cluster_plot_path}")
    print(f"- S plot: {output_paths.s_cluster_plot_path}")
    print(f"- cluster heatmap PNG: {output_paths.cluster_heatmap_png_path}")
    print(f"- cluster heatmap PDF: {output_paths.cluster_heatmap_pdf_path}")


if __name__ == "__main__":
    main()

