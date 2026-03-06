from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import ease2026.analysis.reviewer_robustness as robustness_module
from ease2026.analysis.reviewer_robustness import (
    COVERAGE_FRACTIONS,
    HYBRID_QUANTILES,
    TOP_FRACTIONS,
    NeighborhoodConfig,
    ReviewerRobustnessGenerator,
    RunObservation,
    build_neighborhood_configs,
    multifaceted_reopen_advantage_share,
    ts_sh_is_strongest_pair,
)


def test_build_neighborhood_configs_matches_expected_pairs() -> None:
    configs = build_neighborhood_configs()
    assert len(configs) == 24

    config_tuples = {
        (cfg.top_fraction, cfg.coverage_fraction, cfg.hybrid_quantile) for cfg in configs
    }
    assert (0.20, 0.80, 0.50) in config_tuples
    assert (0.15, 0.70, 0.50) in config_tuples
    assert (0.25, 0.85, 0.75) in config_tuples
    assert (0.30, 0.80, 0.75) in config_tuples
    assert (0.25, 0.75, 0.75) not in config_tuples


def test_ts_sh_is_strongest_pair_detects_global_max() -> None:
    strong = {
        ("social", "technical"): 0.02,
        ("sociotechnical", "super"): 0.55,
        ("super", "technosocial"): 0.92,
    }
    weak = {
        ("social", "technical"): 0.02,
        ("sociotechnical", "super"): 0.91,
        ("super", "technosocial"): 0.90,
    }

    assert ts_sh_is_strongest_pair(strong) is True
    assert ts_sh_is_strongest_pair(weak) is False


def test_multifaceted_reopen_advantage_share_counts_favorable_cells() -> None:
    reopen_median = {
        ("blocker", "social"): 6.0,
        ("blocker", "sociotechnical"): 4.0,
        ("blocker", "technosocial"): 5.0,
        ("blocker", "super"): 6.0,
        ("critical", "social"): 4.0,
        ("critical", "sociotechnical"): 5.0,  # unfavorable
        ("critical", "technosocial"): 4.0,
        ("critical", "super"): 3.0,
    }

    share, favorable, total = multifaceted_reopen_advantage_share(reopen_median)
    assert favorable == 5
    assert total == 6
    assert share == pytest.approx(5 / 6)


def test_write_q_sensitivity_match_summary_writes_global_totals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        robustness_module,
        "settings",
        SimpleNamespace(
            outputs_csv_dir=tmp_path,
            outputs_plots_dir=tmp_path / "plots",
            artifacts_dir=tmp_path / "artifacts",
        ),
    )

    observations: list[RunObservation] = []
    for top_fraction in TOP_FRACTIONS:
        for coverage_fraction in COVERAGE_FRACTIONS:
            for hybrid_quantile in HYBRID_QUANTILES:
                prevalence = {
                    "technical": 90.0,
                    "social": 80.0,
                    "sociotechnical": 60.0,
                    "technosocial": 70.0,
                    "super": 50.0,
                }
                references = {
                    ("blocker", "technical", "fix_rate"): "T1",
                    ("critical", "social", "reopen_rate"): "S1",
                }
                if top_fraction == 0.30 and coverage_fraction == 0.85 and hybrid_quantile == 0.75:
                    prevalence["social"] = 81.0
                    references[("critical", "social", "reopen_rate")] = "S2"

                member_rows = {
                    "technical": 300,
                    "social": 400,
                    "sociotechnical": 70 if hybrid_quantile == 0.75 else 100,
                    "technosocial": 190 if hybrid_quantile == 0.75 else 200,
                    "super": 120,
                }
                observations.append(
                    RunObservation(
                        config=NeighborhoodConfig(
                            top_fraction=top_fraction,
                            coverage_fraction=coverage_fraction,
                            hybrid_quantile=hybrid_quantile,
                        ),
                        prevalence_by_type=prevalence,
                        hero_member_rows_by_type=member_rows,
                        assignee_reference_codes=references,
                        type_pair_jaccard={("super", "technosocial"): 0.90},
                        assignee_reopen_median={("blocker", "social"): 5.0},
                    )
                )

    output_path = ReviewerRobustnessGenerator()._write_q_sensitivity_match_summary(  # noqa: SLF001
        observations
    )
    assert output_path.exists()

    with output_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 13
    global_row = rows[-1]
    assert global_row["top_fraction"] == "ALL"
    assert global_row["coverage_fraction"] == "ALL"
    assert int(global_row["prevalence_match_count"]) == 59
    assert int(global_row["prevalence_total_count"]) == 60
    assert int(global_row["top_code_match_count"]) == 23
    assert int(global_row["top_code_total_count"]) == 24
    assert float(global_row["st_member_row_reduction_pct"]) == pytest.approx(30.0)
    assert float(global_row["ts_member_row_reduction_pct"]) == pytest.approx(5.0)
