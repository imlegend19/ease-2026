"""RQ1 analysis: prevalence and cross-dimensional hero distributions."""

from dataclasses import dataclass
from pathlib import Path

import matplotlib
import pandas as pd
import seaborn as sns

from core.logging import get_logger
from core.paths import ensure_directory
from core.settings import settings
from pipelines.analysis.hero_membership import HeroMembershipByCode, HeroMembershipPipeline

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logger = get_logger(__name__)

BASE_HERO_ORDER: tuple[str, ...] = ("T1", "T2", "T3", "S1", "S2")
ST_ORDER: tuple[str, ...] = ("ST1", "ST2", "ST3", "ST4", "ST5", "ST6")
TS_ORDER: tuple[str, ...] = ("TS1", "TS2", "TS3", "TS4", "TS5", "TS6")
SH_ORDER: tuple[str, ...] = ("SH1", "SH2", "SH3", "SH4", "SH5", "SH6")

ST_DENOMINATORS: dict[str, str] = {
    "ST1": "S1",
    "ST2": "S2",
    "ST3": "S1",
    "ST4": "S2",
    "ST5": "S1",
    "ST6": "S2",
}

TS_DENOMINATORS: dict[str, str] = {
    "TS1": "T1",
    "TS2": "T1",
    "TS3": "T2",
    "TS4": "T2",
    "TS5": "T3",
    "TS6": "T3",
}

SH_TECHNICAL_DENOMINATORS: dict[str, str] = {
    "SH1": "T1",
    "SH2": "T1",
    "SH3": "T2",
    "SH4": "T2",
    "SH5": "T3",
    "SH6": "T3",
}

SH_SOCIAL_DENOMINATORS: dict[str, str] = {
    "SH1": "S1",
    "SH2": "S2",
    "SH3": "S1",
    "SH4": "S2",
    "SH5": "S1",
    "SH6": "S2",
}


@dataclass(frozen=True, slots=True)
class Rq1PrevalenceOutputPaths:
    prevalence_csv_path: Path
    sociotechnical_technosocial_csv_path: Path
    superhero_csv_path: Path
    prevalence_plot_png_path: Path
    prevalence_plot_pdf_path: Path
    combined_distribution_png_path: Path
    combined_distribution_pdf_path: Path
    superhero_distribution_png_path: Path
    superhero_distribution_pdf_path: Path


class Rq1PrevalencePipeline:
    @property
    def output_csv_dir(self) -> Path:
        return settings.outputs_csv_dir / "analysis" / "rq1"

    @property
    def output_plot_dir(self) -> Path:
        return settings.outputs_plots_dir / "rq1"

    def run(self) -> Rq1PrevalenceOutputPaths:
        hero_membership = HeroMembershipPipeline().load_or_build()

        prevalence_df = self._build_prevalence_rows(hero_membership)
        st_ts_df = self._build_st_ts_ratio_rows(hero_membership)
        superhero_df = self._build_superhero_ratio_rows(hero_membership)

        ensure_directory(self.output_csv_dir)
        ensure_directory(self.output_plot_dir)

        prevalence_csv_path = self.output_csv_dir / "project_prevalence.csv"
        st_ts_csv_path = self.output_csv_dir / "sociotechnical_technosocial_percentages.csv"
        superhero_csv_path = self.output_csv_dir / "superhero_percentages.csv"

        prevalence_df.to_csv(prevalence_csv_path, index=False, float_format="%.6f")
        st_ts_df.to_csv(st_ts_csv_path, index=False, float_format="%.6f")
        superhero_df.to_csv(superhero_csv_path, index=False, float_format="%.6f")

        prevalence_plot_png_path = self.output_plot_dir / "technical_social_prevalence.png"
        prevalence_plot_pdf_path = self.output_plot_dir / "technical_social_prevalence.pdf"
        combined_distribution_png_path = self.output_plot_dir / "combined_hero_distribution.png"
        combined_distribution_pdf_path = self.output_plot_dir / "combined_hero_distribution.pdf"
        superhero_distribution_png_path = self.output_plot_dir / "superhero_distribution.png"
        superhero_distribution_pdf_path = self.output_plot_dir / "superhero_distribution.pdf"

        self._plot_prevalence(
            prevalence_df=prevalence_df,
            png_path=prevalence_plot_png_path,
            pdf_path=prevalence_plot_pdf_path,
        )
        self._plot_st_ts_distribution(
            ratio_df=st_ts_df,
            png_path=combined_distribution_png_path,
            pdf_path=combined_distribution_pdf_path,
        )
        self._plot_superhero_distribution(
            ratio_df=superhero_df,
            png_path=superhero_distribution_png_path,
            pdf_path=superhero_distribution_pdf_path,
        )

        logger.info(
            "Generated RQ1 prevalence artifacts",
            prevalence_csv=str(prevalence_csv_path),
            st_ts_csv=str(st_ts_csv_path),
            superhero_csv=str(superhero_csv_path),
            prevalence_plot=str(prevalence_plot_png_path),
            combined_plot=str(combined_distribution_png_path),
            superhero_plot=str(superhero_distribution_png_path),
        )

        return Rq1PrevalenceOutputPaths(
            prevalence_csv_path=prevalence_csv_path,
            sociotechnical_technosocial_csv_path=st_ts_csv_path,
            superhero_csv_path=superhero_csv_path,
            prevalence_plot_png_path=prevalence_plot_png_path,
            prevalence_plot_pdf_path=prevalence_plot_pdf_path,
            combined_distribution_png_path=combined_distribution_png_path,
            combined_distribution_pdf_path=combined_distribution_pdf_path,
            superhero_distribution_png_path=superhero_distribution_png_path,
            superhero_distribution_pdf_path=superhero_distribution_pdf_path,
        )

    @staticmethod
    def _all_projects(hero_membership: HeroMembershipByCode) -> set[str]:
        all_projects: set[str] = set()
        for project_map in hero_membership.values():
            all_projects.update(project_map.keys())
        return all_projects

    def _build_prevalence_rows(self, hero_membership: HeroMembershipByCode) -> pd.DataFrame:
        total_projects = len(self._all_projects(hero_membership))
        label_by_code = {
            "T1": "Commits (T1)",
            "T2": "Files (T2)",
            "T3": "LOC (T3)",
            "S1": "Comments (S1)",
            "S2": "Issues (S2)",
        }
        rows: list[dict[str, str | int | float]] = []

        for hero_code in BASE_HERO_ORDER:
            hero_projects = len(hero_membership.get(hero_code, {}))
            percentage = (hero_projects / total_projects * 100) if total_projects else 0.0
            category = "technical" if hero_code.startswith("T") else "social"
            rows.append(
                {
                    "hero_code": hero_code,
                    "metric_label": label_by_code[hero_code],
                    "category": category,
                    "hero_project_count": hero_projects,
                    "total_project_count": total_projects,
                    "project_percentage": percentage,
                }
            )

        return pd.DataFrame(rows)

    def _build_st_ts_ratio_rows(self, hero_membership: HeroMembershipByCode) -> pd.DataFrame:
        rows: list[dict[str, str | float]] = []

        for hero_code in ST_ORDER:
            denominator_code = ST_DENOMINATORS[hero_code]
            rows.extend(
                self._build_ratio_rows(
                    hero_membership=hero_membership,
                    numerator_code=hero_code,
                    denominator_code=denominator_code,
                    group="sociotechnical",
                )
            )

        for hero_code in TS_ORDER:
            denominator_code = TS_DENOMINATORS[hero_code]
            rows.extend(
                self._build_ratio_rows(
                    hero_membership=hero_membership,
                    numerator_code=hero_code,
                    denominator_code=denominator_code,
                    group="technosocial",
                )
            )

        return pd.DataFrame(rows)

    def _build_superhero_ratio_rows(self, hero_membership: HeroMembershipByCode) -> pd.DataFrame:
        rows: list[dict[str, str | float]] = []

        for hero_code in SH_ORDER:
            rows.extend(
                self._build_ratio_rows(
                    hero_membership=hero_membership,
                    numerator_code=hero_code,
                    denominator_code=SH_TECHNICAL_DENOMINATORS[hero_code],
                    group="technical_base",
                )
            )
            rows.extend(
                self._build_ratio_rows(
                    hero_membership=hero_membership,
                    numerator_code=hero_code,
                    denominator_code=SH_SOCIAL_DENOMINATORS[hero_code],
                    group="social_base",
                )
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _build_ratio_rows(
        hero_membership: HeroMembershipByCode,
        numerator_code: str,
        denominator_code: str,
        group: str,
    ) -> list[dict[str, str | float]]:
        rows: list[dict[str, str | float]] = []
        numerator_map = hero_membership.get(numerator_code, {})
        denominator_map = hero_membership.get(denominator_code, {})

        for project_name, denominator_authors in denominator_map.items():
            denominator_size = len(denominator_authors)
            if denominator_size == 0:
                continue

            numerator_size = len(numerator_map.get(project_name, set()))
            ratio = (numerator_size / denominator_size) * 100
            rows.append(
                {
                    "project_name": project_name,
                    "hero_code": numerator_code,
                    "denominator_code": denominator_code,
                    "group": group,
                    "ratio_percent": ratio,
                }
            )

        return rows

    @staticmethod
    def _plot_prevalence(prevalence_df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
        order = list(BASE_HERO_ORDER)
        category_palette = {"technical": "#4C72B0", "social": "#55A868"}

        plt.figure(figsize=(8, 4.5))
        axis = sns.barplot(
            data=prevalence_df,
            x="hero_code",
            y="project_percentage",
            hue="category",
            order=order,
            dodge=False,
            palette=category_palette,
        )
        axis.set_ylim(0, 100)
        axis.set_xlabel("Hero Definition")
        axis.set_ylabel("Hero Projects (%)")
        axis.set_title("RQ1 Figure 1: Project Prevalence by Social and Technical Metrics")
        axis.legend(title="Category", loc="upper right")

        for patch in axis.patches:
            height = patch.get_height()
            axis.annotate(
                f"{height:.1f}%",
                (patch.get_x() + patch.get_width() / 2, height),
                ha="center",
                va="bottom",
                fontsize=8,
                xytext=(0, 2),
                textcoords="offset points",
            )

        plt.tight_layout()
        plt.savefig(png_path, dpi=300, bbox_inches="tight")
        plt.savefig(pdf_path, dpi=300, bbox_inches="tight")
        plt.close()

    @staticmethod
    def _plot_st_ts_distribution(ratio_df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), sharey=True)
        sns.boxplot(
            data=ratio_df[ratio_df["group"] == "sociotechnical"],
            x="hero_code",
            y="ratio_percent",
            order=list(ST_ORDER),
            color="#55A868",
            ax=axes[0],
        )
        axes[0].set_title("Social Heroes -> Sociotechnical (%)")
        axes[0].set_xlabel("Sociotechnical Hero Type")
        axes[0].set_ylabel("Percentage")
        axes[0].set_ylim(0, 100)

        sns.boxplot(
            data=ratio_df[ratio_df["group"] == "technosocial"],
            x="hero_code",
            y="ratio_percent",
            order=list(TS_ORDER),
            color="#4C72B0",
            ax=axes[1],
        )
        axes[1].set_title("Technical Heroes -> Technosocial (%)")
        axes[1].set_xlabel("Technosocial Hero Type")
        axes[1].set_ylabel("")
        axes[1].set_ylim(0, 100)

        fig.suptitle("RQ1 Figure 2: Cross-Dimensional Hero Distributions", y=1.03)
        fig.tight_layout()
        fig.savefig(png_path, dpi=300, bbox_inches="tight")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _plot_superhero_distribution(ratio_df: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
        fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), sharey=True)
        sns.boxplot(
            data=ratio_df[ratio_df["group"] == "technical_base"],
            x="hero_code",
            y="ratio_percent",
            order=list(SH_ORDER),
            color="#C44E52",
            ax=axes[0],
        )
        axes[0].set_title("Technical Heroes -> Superheroes (%)")
        axes[0].set_xlabel("Superhero Type")
        axes[0].set_ylabel("Percentage")
        axes[0].set_ylim(0, 100)

        sns.boxplot(
            data=ratio_df[ratio_df["group"] == "social_base"],
            x="hero_code",
            y="ratio_percent",
            order=list(SH_ORDER),
            color="#8172B3",
            ax=axes[1],
        )
        axes[1].set_title("Social Heroes -> Superheroes (%)")
        axes[1].set_xlabel("Superhero Type")
        axes[1].set_ylabel("")
        axes[1].set_ylim(0, 100)

        fig.suptitle("RQ1 Figure 3: Superhero Distributions", y=1.03)
        fig.tight_layout()
        fig.savefig(png_path, dpi=300, bbox_inches="tight")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
