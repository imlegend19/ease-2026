from __future__ import annotations

import math

import pytest

from ease2026.analysis.rq3_inferential import (
    InputMatrix,
    build_input_matrix,
    compute_kendall_tables,
    compute_mean_ranking,
)


def test_build_input_matrix_uses_common_project_intersection() -> None:
    metric_by_hero = {
        "T1": {"p1": 10.0, "p2": 20.0, "p3": 30.0},
        "T2": {"p2": 5.0, "p3": 15.0},
        "S1": {"p2": 2.0, "p3": 4.0},
    }

    matrix = build_input_matrix(metric_by_hero)

    assert matrix.hero_codes == ("S1", "T1", "T2")
    assert matrix.project_names == ("p2", "p3")
    assert matrix.rows == ((2.0, 20.0, 5.0), (4.0, 30.0, 15.0))


@pytest.mark.parametrize(
    ("metric_name", "expected_order"),
    [
        ("fix_rate", ("C", "B", "A")),
        ("reopen_rate", ("A", "B", "C")),
    ],
)
def test_compute_mean_ranking_respects_metric_direction(
    metric_name: str,
    expected_order: tuple[str, ...],
) -> None:
    matrix = InputMatrix(
        hero_codes=("A", "B", "C"),
        project_names=("p1", "p2"),
        rows=((10.0, 20.0, 30.0), (10.0, 20.0, 30.0)),
    )

    ranking = compute_mean_ranking(matrix, metric_name=metric_name)

    assert tuple(hero_code for _, hero_code, _ in ranking) == expected_order
    assert tuple(rank for rank, _, _ in ranking) == (1, 2, 3)


def test_compute_kendall_tables_matches_expected_values() -> None:
    ranking_order_by_severity = {
        "blocker": ["A", "B", "C"],
        "critical": ["A", "B", "C"],
        "major": ["C", "B", "A"],
        "minor": ["A", "C", "B"],
        "trivial": [],
    }

    tau_table, p_value_table, formatted_table = compute_kendall_tables(
        ranking_order_by_severity=ranking_order_by_severity,
        severity_order=("blocker", "critical", "major", "minor", "trivial"),
    )

    assert tau_table["blocker"]["critical"] == pytest.approx(1.0)
    assert p_value_table["blocker"]["critical"] == pytest.approx(1.0 / 3.0)
    assert tau_table["blocker"]["major"] == pytest.approx(-1.0)
    assert tau_table["blocker"]["minor"] == pytest.approx(1.0 / 3.0, rel=1e-3)
    assert math.isnan(tau_table["blocker"]["trivial"])
    assert tau_table["trivial"]["trivial"] == pytest.approx(1.0)
    assert formatted_table["blocker"]["major"].startswith("-1.000")
