from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from ease2026.analysis.rq3_inferential import (
    InputMatrix,
    Rq3InferentialAnalyzer,
    build_input_matrix,
    compute_kendall_tables,
    compute_mean_ranking,
    compute_rank1_jaccard_rows,
    compute_rbo_tables,
    compute_spearman_tables,
)
from ease2026.outcomes.definitions import FixerAttributionPolicy


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


def test_compute_spearman_tables_matches_expected_values() -> None:
    ranking_order_by_severity = {
        "blocker": ["A", "B", "C"],
        "critical": ["A", "B", "C"],
        "major": ["C", "B", "A"],
        "minor": ["A", "C", "B"],
        "trivial": [],
    }

    rho_table, p_value_table, formatted_table = compute_spearman_tables(
        ranking_order_by_severity=ranking_order_by_severity,
        severity_order=("blocker", "critical", "major", "minor", "trivial"),
    )

    assert rho_table["blocker"]["critical"] == pytest.approx(1.0)
    assert p_value_table["blocker"]["critical"] == pytest.approx(0.0)
    assert rho_table["blocker"]["major"] == pytest.approx(-1.0)
    assert p_value_table["blocker"]["major"] == pytest.approx(0.0)
    assert rho_table["blocker"]["minor"] == pytest.approx(0.5)
    assert p_value_table["blocker"]["minor"] == pytest.approx(2.0 / 3.0)
    assert math.isnan(rho_table["blocker"]["trivial"])
    assert rho_table["trivial"]["trivial"] == pytest.approx(1.0)
    assert formatted_table["blocker"]["major"].startswith("-1.000")


def test_compute_rbo_tables_matches_expected_values() -> None:
    ranking_order_by_severity = {
        "blocker": ["A", "B", "C"],
        "critical": ["A", "B", "C"],
        "major": ["C", "B", "A"],
        "minor": ["A", "C", "B"],
        "trivial": [],
    }

    rbo_table, p_value_table, formatted_table = compute_rbo_tables(
        ranking_order_by_severity=ranking_order_by_severity,
        severity_order=("blocker", "critical", "major", "minor", "trivial"),
    )

    assert rbo_table["blocker"]["critical"] == pytest.approx(1.0)
    assert p_value_table["blocker"]["critical"] == pytest.approx(1.0 / 6.0)
    assert rbo_table["blocker"]["major"] == pytest.approx(0.855)
    assert p_value_table["blocker"]["major"] == pytest.approx(1.0)
    assert rbo_table["blocker"]["minor"] == pytest.approx(0.955)
    assert p_value_table["blocker"]["minor"] == pytest.approx(1.0 / 3.0)
    assert math.isnan(rbo_table["blocker"]["trivial"])
    assert math.isnan(p_value_table["blocker"]["trivial"])
    assert rbo_table["trivial"]["trivial"] == pytest.approx(1.0)
    assert p_value_table["trivial"]["trivial"] == pytest.approx(0.0)
    assert formatted_table["blocker"]["major"].startswith("0.855")


def test_compute_rank1_jaccard_rows_uses_pairwise_severity_overlap() -> None:
    rank1_by_severity = {
        "blocker": {"S1", "T1"},
        "critical": {"S1", "S2"},
        "major": set(),
        "minor": {"T1"},
        "trivial": set(),
    }

    rows = compute_rank1_jaccard_rows(
        rank1_by_severity=rank1_by_severity,
        severity_order=("blocker", "critical", "major", "minor", "trivial"),
    )

    assert len(rows) == 10
    row_map = {(row.severity_a, row.severity_b): row for row in rows}

    blocker_critical = row_map[("blocker", "critical")]
    assert blocker_critical.rank1_categories_a == "S1;T1"
    assert blocker_critical.rank1_categories_b == "S1;S2"
    assert blocker_critical.rank1_intersection_categories == "S1"
    assert blocker_critical.intersection_count == 1
    assert blocker_critical.union_count == 3
    assert blocker_critical.jaccard_overlap == pytest.approx(1.0 / 3.0)

    major_trivial = row_map[("major", "trivial")]
    assert major_trivial.rank1_count_a == 0
    assert major_trivial.rank1_count_b == 0
    assert major_trivial.union_count == 0
    assert math.isnan(major_trivial.jaccard_overlap)


def test_write_sk_esd_ranking_table_hides_fallback_cells_and_caps_rank_rows(
    tmp_path: Path,
) -> None:
    analyzer = Rq3InferentialAnalyzer()
    output_dir = tmp_path / "rq3_inferential" / "assignee"
    sk_esd_dir = output_dir / "sk_esd"
    sk_esd_dir.mkdir(parents=True)

    severities = ("trivial", "minor", "major", "critical", "blocker")
    metrics = ("fix_rate", "reopen_rate")

    for severity in severities:
        for metric in metrics:
            rows: list[dict[str, str]] = []
            if severity == "minor" and metric == "reopen_rate":
                rows = [
                    {
                        "metric": metric,
                        "severity": severity,
                        "hero_code": f"X{rank:02d}",
                        "rank": str(rank),
                        "method": "mean_fallback_docker",
                    }
                    for rank in range(1, 24)
                ]
            else:
                rows = [
                    {
                        "metric": metric,
                        "severity": severity,
                        "hero_code": "A",
                        "rank": "1",
                        "method": "sk_esd_docker",
                    },
                    {
                        "metric": metric,
                        "severity": severity,
                        "hero_code": "B",
                        "rank": "2",
                        "method": "sk_esd_docker",
                    },
                    {
                        "metric": metric,
                        "severity": severity,
                        "hero_code": "C",
                        "rank": "3",
                        "method": "sk_esd_docker",
                    },
                ]

            ranking_path = sk_esd_dir / f"sk_esd_ranking_{metric}_{severity}.csv"
            with ranking_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=("metric", "severity", "hero_code", "rank", "method"),
                )
                writer.writeheader()
                writer.writerows(rows)

    table_path = analyzer._write_sk_esd_ranking_table(
        fixer_policy=FixerAttributionPolicy.ASSIGNEE,
        output_dir=output_dir,
        sk_esd_dir=sk_esd_dir,
    )
    tex = table_path.read_text(encoding="utf-8")

    assert "N/A\\textsuperscript{\\dagger}" in tex
    assert "method != sk\\_esd\\_docker" in tex
    assert "X23" not in tex
    assert "\\textit{\\textbf{23}}" not in tex
    assert "\\textit{\\textbf{4}}" not in tex
