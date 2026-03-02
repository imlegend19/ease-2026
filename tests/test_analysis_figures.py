from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import ease2026.analysis.figures as figures_module
from ease2026.analysis.figures import (
    FinalFigureGenerator,
    build_rq3_effect_grids,
    build_type_overlap_matrix,
    summarize_rq1_conditional_prevalence,
)


def test_build_type_overlap_matrix_populates_symmetric_values() -> None:
    rows = [
        {"group_a": "technical", "group_b": "social", "pair_jaccard": "0.25"},
        {"group_a": "super", "group_b": "technical", "pair_jaccard": "0.75"},
    ]
    matrix = build_type_overlap_matrix(rows)

    technical = 0
    social = 1
    super_index = 4

    assert matrix.shape == (5, 5)
    assert matrix[technical, technical] == pytest.approx(1.0)
    assert matrix[technical, social] == pytest.approx(0.25)
    assert matrix[social, technical] == pytest.approx(0.25)
    assert matrix[technical, super_index] == pytest.approx(0.75)
    assert matrix[super_index, technical] == pytest.approx(0.75)


def test_build_rq3_effect_grids_deltas_are_vs_technical() -> None:
    rows = [
        {
            "fixer": "assignee",
            "severity": "major",
            "hero_type": "technical",
            "fix_rate_median": "80",
            "fix_rate_iqr": "5",
            "reopen_rate_median": "10",
            "reopen_rate_iqr": "2",
            "n_projects_with_assigned": "10",
        },
        {
            "fixer": "assignee",
            "severity": "major",
            "hero_type": "social",
            "fix_rate_median": "90",
            "fix_rate_iqr": "7",
            "reopen_rate_median": "6",
            "reopen_rate_iqr": "3",
            "n_projects_with_assigned": "12",
        },
    ]

    fix_delta, reopen_delta, fix_annotations, reopen_annotations = build_rq3_effect_grids(rows)

    technical_index = 0
    social_index = 1
    major_index = 2

    assert fix_delta[technical_index, major_index] == pytest.approx(0.0)
    assert fix_delta[social_index, major_index] == pytest.approx(10.0)
    assert reopen_delta[technical_index, major_index] == pytest.approx(0.0)
    assert reopen_delta[social_index, major_index] == pytest.approx(-4.0)
    assert "IQR 7.0" in fix_annotations[social_index][major_index]
    assert "n=12" in reopen_annotations[social_index][major_index]
    assert np.isnan(fix_delta[social_index, 0])


def test_summarize_rq1_conditional_prevalence_counts_non_zero_projects() -> None:
    rows = [
        {"condition_id": "st_over_s", "percentage": 0.0},
        {"condition_id": "st_over_s", "percentage": 20.0},
        {"condition_id": "ts_over_t", "percentage": 5.0},
        {"condition_id": "ts_over_t", "percentage": 0.0},
        {"condition_id": "sh_over_s_union_t", "percentage": 0.0},
    ]

    summary = summarize_rq1_conditional_prevalence(rows)

    assert summary["st_over_s"].n_projects == 2
    assert summary["st_over_s"].non_zero_projects == 1
    assert summary["st_over_s"].median == pytest.approx(10.0)
    assert summary["ts_over_t"].n_projects == 2
    assert summary["ts_over_t"].non_zero_projects == 1
    assert summary["sh_over_s_union_t"].n_projects == 1
    assert summary["sh_over_s_union_t"].non_zero_projects == 0


def test_resolve_run_dir_prefers_experiment_root_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment_root = tmp_path / "ease-2026"
    dataset_name = "smartshark_2_2"
    runs_dir = experiment_root / "artifacts" / dataset_name / "runs"
    target_run_dir = runs_dir / "top0.20_cov0.80_q0.50"
    target_run_dir.mkdir(parents=True)

    monkeypatch.setattr(
        figures_module,
        "settings",
        SimpleNamespace(
            experiment_root=experiment_root,
            artifacts_dir=experiment_root / "artifacts" / dataset_name,
        ),
    )

    generator = FinalFigureGenerator()
    resolved = generator._resolve_run_dir(
        f"artifacts/{dataset_name}/runs/top0.20_cov0.80_q0.50"
    )

    assert resolved == target_run_dir


def test_load_rq1_conditional_rows_computes_superhero_over_social_and_technical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heroes_root = tmp_path / "heroes"
    (heroes_root / "T1").mkdir(parents=True)
    (heroes_root / "S1").mkdir(parents=True)
    (heroes_root / "hybrid" / "super").mkdir(parents=True)

    (heroes_root / "T1" / "heroes.csv").write_text(
        "project_name,author_id\nproj,a\nproj,b\nproj,c\n",
        encoding="utf-8",
    )
    (heroes_root / "S1" / "heroes.csv").write_text(
        "project_name,author_id\nproj,b\nproj,c\nproj,d\n",
        encoding="utf-8",
    )
    # Include an extra superhero not in social/technical sets to verify intersection logic.
    (heroes_root / "hybrid" / "super" / "SH1.csv").write_text(
        "project_name,author_id\nproj,b\nproj,c\nproj,e\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        figures_module,
        "settings",
        SimpleNamespace(
            outputs_csv_dir=tmp_path,
            outputs_dir=tmp_path / "outputs",
            artifacts_dir=tmp_path / "artifacts",
        ),
    )

    generator = FinalFigureGenerator()
    rows = generator._load_rq1_conditional_rows(include_superhero_denominator_conditions=True)
    by_condition = {
        str(row["condition_id"]): row
        for row in rows
        if str(row["project_name"]) == "proj"
        and str(row["condition_id"]) in {"sh_over_t", "sh_over_s"}
    }

    assert int(by_condition["sh_over_t"]["numerator_count"]) == 2
    assert int(by_condition["sh_over_t"]["denominator_count"]) == 3
    assert float(by_condition["sh_over_t"]["percentage"]) == pytest.approx(66.6666666667)

    assert int(by_condition["sh_over_s"]["numerator_count"]) == 2
    assert int(by_condition["sh_over_s"]["denominator_count"]) == 3
    assert float(by_condition["sh_over_s"]["percentage"]) == pytest.approx(66.6666666667)


def test_write_rq1_superhero_conditional_packet_rows_outputs_new_csvs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        figures_module,
        "settings",
        SimpleNamespace(
            outputs_csv_dir=tmp_path / "csv",
            outputs_dir=tmp_path / "outputs",
            artifacts_dir=tmp_path / "artifacts",
        ),
    )

    generator = FinalFigureGenerator()
    output_paths = generator._write_rq1_superhero_conditional_packet_rows(
        [
            {
                "condition_id": "sh_over_t",
                "condition_label": "SH*/T*",
                "project_name": "p2",
                "numerator_count": 0,
                "denominator_count": 1,
                "percentage": 0.0,
            },
            {
                "condition_id": "sh_over_t",
                "condition_label": "SH*/T*",
                "project_name": "p1",
                "numerator_count": 1,
                "denominator_count": 2,
                "percentage": 50.0,
            },
            {
                "condition_id": "sh_over_s",
                "condition_label": "SH*/S*",
                "project_name": "p1",
                "numerator_count": 2,
                "denominator_count": 4,
                "percentage": 50.0,
            },
        ]
    )

    expected_keys = {
        "rq1_coauthor_sh_over_t_project_csv",
        "rq1_coauthor_sh_over_t_summary_csv",
        "rq1_coauthor_sh_over_s_project_csv",
        "rq1_coauthor_sh_over_s_summary_csv",
    }
    assert set(output_paths.keys()) == expected_keys
    for path in output_paths.values():
        assert path.exists()

    sh_over_t_summary_path = output_paths["rq1_coauthor_sh_over_t_summary_csv"]
    with sh_over_t_summary_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["condition_id"] == "sh_over_t"
    assert int(rows[0]["n_projects"]) == 2
    assert int(rows[0]["non_zero_projects"]) == 1
    assert float(rows[0]["median_pct"]) == pytest.approx(25.0)
    assert float(rows[0]["mean_pct"]) == pytest.approx(25.0)
