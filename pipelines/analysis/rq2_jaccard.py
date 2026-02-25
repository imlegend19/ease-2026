"""RQ2 analysis: Jaccard similarity matrices and plots across hero categories."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_catalog import RQ2_CLUSTERS, RQ2_HERO_ORDER
from pipelines.analysis.hero_membership import HeroMembershipPipeline

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Rq2JaccardOutputPaths:
    matrix_csv_path: Path
    sorted_pairs_csv_path: Path
    cluster_matrix_csv_path: Path
    t_cluster_plot_path: Path
    s_cluster_plot_path: Path
    cluster_heatmap_png_path: Path
    cluster_heatmap_pdf_path: Path


class Rq2JaccardPipeline:
    @property
    def output_csv_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq2"

    @property
    def output_plot_dir(self) -> Path:
        return settings.outputs_plots_dir / "rq2"

    def run(self) -> Rq2JaccardOutputPaths:
        hero_membership = HeroMembershipPipeline().load_or_build()
        matrix_df = self._compute_jaccard_matrix(hero_membership)
        pairs_df = self._build_sorted_pair_rows(matrix_df)
        cluster_matrix_df = self._compute_cluster_level_matrix(matrix_df)

        ensure_directory(self.output_csv_dir)
        matrix_csv_path = self.output_csv_dir / "final_mean_jaccard_matrix.csv"
        pairs_csv_path = self.output_csv_dir / "jaccard_pairs_sorted.csv"
        cluster_matrix_csv_path = self.output_csv_dir / "cluster_level_mean_jaccard_matrix.csv"
        matrix_df.to_csv(matrix_csv_path, float_format="%.6f")
        pairs_df.to_csv(pairs_csv_path, index=False, float_format="%.6f")
        cluster_matrix_df.to_csv(cluster_matrix_csv_path, float_format="%.6f")

        ensure_directory(self.output_plot_dir)
        t_cluster_plot_path = self.output_plot_dir / "jaccard_lower_triangle_t_cluster.png"
        s_cluster_plot_path = self.output_plot_dir / "jaccard_lower_triangle_s_cluster.png"
        cluster_heatmap_png_path = self.output_plot_dir / "cluster_level_mean_jaccard_heatmap.png"
        cluster_heatmap_pdf_path = self.output_plot_dir / "cluster_level_mean_jaccard_heatmap.pdf"

        self._plot_cluster_submatrix(matrix_df, cluster_name="T", output_path=t_cluster_plot_path)
        self._plot_cluster_submatrix(matrix_df, cluster_name="S", output_path=s_cluster_plot_path)
        self._plot_cluster_heatmap(
            cluster_matrix_df=cluster_matrix_df,
            png_path=cluster_heatmap_png_path,
            pdf_path=cluster_heatmap_pdf_path,
        )

        logger.info(
            "Generated RQ2 Jaccard artifacts",
            output_matrix=str(matrix_csv_path),
            output_pairs=str(pairs_csv_path),
            output_cluster_matrix=str(cluster_matrix_csv_path),
        )

        return Rq2JaccardOutputPaths(
            matrix_csv_path=matrix_csv_path,
            sorted_pairs_csv_path=pairs_csv_path,
            cluster_matrix_csv_path=cluster_matrix_csv_path,
            t_cluster_plot_path=t_cluster_plot_path,
            s_cluster_plot_path=s_cluster_plot_path,
            cluster_heatmap_png_path=cluster_heatmap_png_path,
            cluster_heatmap_pdf_path=cluster_heatmap_pdf_path,
        )

    @staticmethod
    def _compute_jaccard_matrix(hero_membership: dict[str, dict[str, set[str]]]) -> pd.DataFrame:
        matrix = pd.DataFrame(index=RQ2_HERO_ORDER, columns=RQ2_HERO_ORDER, dtype=float)

        for hero_a in RQ2_HERO_ORDER:
            for hero_b in RQ2_HERO_ORDER:
                if hero_a == hero_b:
                    matrix.loc[hero_a, hero_b] = 1.0
                    continue

                project_authors_a = hero_membership.get(hero_a, {})
                project_authors_b = hero_membership.get(hero_b, {})
                candidate_projects = set(project_authors_a).intersection(project_authors_b)
                if not candidate_projects:
                    matrix.loc[hero_a, hero_b] = 0.0
                    continue

                scores: list[float] = []
                for project_name in candidate_projects:
                    authors_a = project_authors_a.get(project_name, set())
                    authors_b = project_authors_b.get(project_name, set())
                    union_size = len(authors_a.union(authors_b))
                    if union_size == 0:
                        continue
                    scores.append(len(authors_a.intersection(authors_b)) / union_size)

                matrix.loc[hero_a, hero_b] = float(np.mean(scores)) if scores else 0.0

        return matrix.astype(float)

    @staticmethod
    def _build_sorted_pair_rows(matrix_df: pd.DataFrame) -> pd.DataFrame:
        pair_rows: list[dict[str, float | str]] = []
        for hero_a, hero_b in itertools.combinations(matrix_df.columns, 2):
            pair_rows.append(
                {
                    "pair": f"{hero_a} - {hero_b}",
                    "mean_jaccard": float(matrix_df.loc[hero_a, hero_b]),
                },
            )

        pairs_df = pd.DataFrame(pair_rows)
        return pairs_df.sort_values(by="mean_jaccard", ascending=False).reset_index(drop=True)

    @staticmethod
    def _compute_cluster_level_matrix(matrix_df: pd.DataFrame) -> pd.DataFrame:
        cluster_names = list(RQ2_CLUSTERS.keys())
        cluster_matrix = pd.DataFrame(index=cluster_names, columns=cluster_names, dtype=float)

        for cluster_a in cluster_names:
            for cluster_b in cluster_names:
                labels_a = list(RQ2_CLUSTERS[cluster_a])
                labels_b = list(RQ2_CLUSTERS[cluster_b])
                submatrix = matrix_df.loc[labels_a, labels_b]

                if cluster_a == cluster_b:
                    diagonal_mask = np.eye(submatrix.shape[0], dtype=bool)
                    values = submatrix.values[~diagonal_mask]
                else:
                    values = submatrix.values.flatten()

                cluster_matrix.loc[cluster_a, cluster_b] = float(np.mean(values)) if values.size > 0 else 0.0

        return cluster_matrix.astype(float)

    @staticmethod
    def _plot_cluster_submatrix(matrix_df: pd.DataFrame, cluster_name: str, output_path: Path) -> None:
        labels = list(RQ2_CLUSTERS[cluster_name])
        submatrix = matrix_df.loc[labels, labels].astype(float)
        mask = np.triu(np.ones_like(submatrix, dtype=bool), k=1)

        vmin = float(matrix_df.values.min())
        vmax = float(matrix_df.values.max())
        if np.isclose(vmin, vmax):
            vmin = 0.0
            vmax = max(vmax, 1.0)

        plt.figure(figsize=(6, 6))
        axis = sns.heatmap(
            submatrix,
            mask=mask,
            cmap="coolwarm",
            vmin=vmin,
            vmax=vmax,
            annot=True,
            fmt=".3f",
            annot_kws={"size": 12, "weight": "bold"},
            square=True,
            cbar=False,
            linewidths=0.0,
        )
        axis.xaxis.tick_bottom()
        axis.yaxis.tick_left()
        axis.tick_params(axis="x", rotation=0, labelsize=12)
        axis.tick_params(axis="y", rotation=0, labelsize=12)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

    @staticmethod
    def _plot_cluster_heatmap(cluster_matrix_df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
        cluster_matrix = cluster_matrix_df.astype(float)
        mask = np.triu(np.ones_like(cluster_matrix, dtype=bool), k=1)
        vmin = float(cluster_matrix.values.min())
        vmax = float(cluster_matrix.values.max())
        if np.isclose(vmin, vmax):
            vmin = 0.0
            vmax = max(vmax, 1.0)

        plt.figure(figsize=(6, 3))
        axis = sns.heatmap(
            cluster_matrix,
            mask=mask,
            annot=True,
            fmt=".3f",
            cmap="coolwarm",
            vmin=vmin,
            vmax=vmax,
            square=False,
            cbar_kws={"shrink": 1.0, "aspect": 10, "pad": 0.02},
            linewidths=0.3,
            linecolor="white",
            annot_kws={"size": 7, "weight": "bold"},
        )
        axis.set_aspect(0.5)
        axis.set_xticklabels(axis.get_xticklabels(), fontweight="bold", fontsize=7)
        axis.set_yticklabels(axis.get_yticklabels(), fontweight="bold", fontsize=7)
        plt.tight_layout()
        plt.savefig(png_path, dpi=300, bbox_inches="tight")
        plt.savefig(pdf_path, dpi=300, bbox_inches="tight")
        plt.close()

