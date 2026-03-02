
import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import ease2026.analysis.rq2 as rq2_module
from ease2026.analysis.rq2 import MembershipSet, Rq2Analyzer, _summarize_per_project_jaccard


def _membership(authors_by_project: dict[str, set[str]]) -> MembershipSet:
    project_author_pairs = frozenset(
        (project_name, author_id)
        for project_name, authors in authors_by_project.items()
        for author_id in authors
    )
    return MembershipSet(
        project_author_pairs=project_author_pairs,
        projects=frozenset(authors_by_project),
        authors_by_project={
            project_name: frozenset(authors)
            for project_name, authors in authors_by_project.items()
        },
    )


def test_summarize_per_project_jaccard_skips_projects_without_both_groups() -> None:
    summary = _summarize_per_project_jaccard(
        {
            "p1": frozenset({"a1", "a2"}),
            "p2": frozenset({"a1"}),
            "p3": frozenset(),
        },
        {
            "p1": frozenset({"a2", "a3"}),
            "p2": frozenset(),
            "p3": frozenset({"a3"}),
        },
    )

    assert summary.n_projects == 1
    assert summary.mean_jaccard == pytest.approx(1 / 3)
    assert summary.median_jaccard == pytest.approx(1 / 3)
    assert summary.std_jaccard == pytest.approx(0.0)
    assert summary.iqr_jaccard == pytest.approx(0.0)


def test_write_pairwise_overlap_table_includes_per_project_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rq2_module,
        "settings",
        SimpleNamespace(outputs_csv_dir=tmp_path),
    )
    (tmp_path / "analysis" / "final_tables").mkdir(parents=True, exist_ok=True)

    analyzer = Rq2Analyzer()
    output_path = analyzer._write_pairwise_overlap_table(
        output_name="rq2_overlap_technical_per_project.csv",
        groups={
            "T1": _membership({"p1": {"a1", "a2"}, "p2": {"a1"}}),
            "T2": _membership({"p1": {"a2", "a3"}, "p2": {"a1"}}),
        },
        include_per_project=True,
    )

    with output_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert len(rows) == 1
    row = rows[0]

    assert row["group_a"] == "T1"
    assert row["group_b"] == "T2"
    assert int(row["pair_intersection"]) == 2
    assert int(row["pair_union"]) == 4
    assert float(row["pair_jaccard"]) == pytest.approx(0.5)
    assert int(row["per_project_n"]) == 2
    assert float(row["per_project_mean_jaccard"]) == pytest.approx(2 / 3)
    assert float(row["per_project_median_jaccard"]) == pytest.approx(2 / 3)
    assert float(row["per_project_std_jaccard"]) == pytest.approx(1 / 3)
    assert float(row["per_project_iqr_jaccard"]) == pytest.approx(1 / 3)
