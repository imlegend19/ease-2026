from __future__ import annotations

import numpy as np
import pytest

from ease2026.analysis.figures import (
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
