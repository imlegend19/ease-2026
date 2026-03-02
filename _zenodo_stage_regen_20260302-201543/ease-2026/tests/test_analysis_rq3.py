from __future__ import annotations

import csv
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import ease2026.analysis.rq3 as rq3_module
from ease2026.analysis.rq3 import Rq3Analyzer


def _write_outcome_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "project_name",
                "hero_code",
                "severity",
                "n_assigned",
                "n_fixed",
                "n_reopened",
                "fix_rate",
                "reopen_rate",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def test_rq3_analyzer_writes_combined_type_summary(tmp_path: Path, monkeypatch) -> None:
    outcomes_root = tmp_path / "analysis" / "rq3_outcomes" / "combined"
    _write_outcome_csv(
        outcomes_root / "major.csv",
        [
            {
                "project_name": "proj_a",
                "hero_code": "T1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "8",
                "n_reopened": "1",
                "fix_rate": "80",
                "reopen_rate": "12.5",
            },
            {
                "project_name": "proj_a",
                "hero_code": "S1",
                "severity": "major",
                "n_assigned": "5",
                "n_fixed": "4",
                "n_reopened": "1",
                "fix_rate": "80",
                "reopen_rate": "25",
            },
        ],
    )

    monkeypatch.setattr(
        rq3_module,
        "settings",
        SimpleNamespace(outputs_csv_dir=tmp_path),
    )

    outputs = Rq3Analyzer().run()
    combined_path = outputs["rq3_type_summary_combined"]
    assert combined_path.exists()

    with combined_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert rows
    assert {row["fixer"] for row in rows} == {"combined"}
    assert {row["severity"] for row in rows} == {"major"}


def test_rq3_reopen_social_multifaceted_significance_table(tmp_path: Path, monkeypatch) -> None:
    outcomes_root = tmp_path / "analysis" / "rq3_outcomes" / "assignee"
    _write_outcome_csv(
        outcomes_root / "major.csv",
        [
            {
                "project_name": "proj_a",
                "hero_code": "S1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "8",
                "n_reopened": "4",
                "fix_rate": "80",
                "reopen_rate": "40",
            },
            {
                "project_name": "proj_b",
                "hero_code": "S1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "8",
                "n_reopened": "3",
                "fix_rate": "80",
                "reopen_rate": "30",
            },
            {
                "project_name": "proj_c",
                "hero_code": "S1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "8",
                "n_reopened": "2",
                "fix_rate": "80",
                "reopen_rate": "20",
            },
            {
                "project_name": "proj_a",
                "hero_code": "ST1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "2",
                "fix_rate": "90",
                "reopen_rate": "20",
            },
            {
                "project_name": "proj_b",
                "hero_code": "ST1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "1",
                "fix_rate": "90",
                "reopen_rate": "10",
            },
            {
                "project_name": "proj_c",
                "hero_code": "ST1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "1",
                "fix_rate": "90",
                "reopen_rate": "10",
            },
            {
                "project_name": "proj_a",
                "hero_code": "SH1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "1",
                "fix_rate": "90",
                "reopen_rate": "10",
            },
            {
                "project_name": "proj_b",
                "hero_code": "SH1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "1",
                "fix_rate": "90",
                "reopen_rate": "10",
            },
            {
                "project_name": "proj_c",
                "hero_code": "SH1",
                "severity": "major",
                "n_assigned": "10",
                "n_fixed": "9",
                "n_reopened": "1",
                "fix_rate": "90",
                "reopen_rate": "10",
            },
        ],
    )

    monkeypatch.setattr(
        rq3_module,
        "settings",
        SimpleNamespace(outputs_csv_dir=tmp_path),
    )

    outputs = Rq3Analyzer().run()
    table_path = outputs["rq3_reopen_social_multifaceted_significance"]
    assert table_path.exists()

    with table_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 10  # 5 severities x 2 comparisons

    major_rows = {row["comparison"]: row for row in rows if row["severity"] == "major"}
    st_row = major_rows["social_vs_sociotechnical"]
    sh_row = major_rows["social_vs_super"]

    assert st_row["fixer"] == "assignee"
    assert int(st_row["n_projects_social"]) == 3
    assert int(st_row["n_projects_comparison"]) == 3
    assert float(st_row["cliffs_delta_social_minus_comparison"]) == pytest.approx(8.0 / 9.0)
    assert 0.0 <= float(st_row["mannwhitney_p_value"]) <= 1.0

    assert sh_row["fixer"] == "assignee"
    assert int(sh_row["n_projects_social"]) == 3
    assert int(sh_row["n_projects_comparison"]) == 3
    assert float(sh_row["cliffs_delta_social_minus_comparison"]) == pytest.approx(1.0)
    assert 0.0 <= float(sh_row["mannwhitney_p_value"]) <= 1.0

    blocker_st = next(
        row
        for row in rows
        if row["severity"] == "blocker" and row["comparison"] == "social_vs_sociotechnical"
    )
    assert math.isnan(float(blocker_st["cliffs_delta_social_minus_comparison"]))
    assert math.isnan(float(blocker_st["mannwhitney_p_value"]))
