from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

import ease2026.analysis.rq2 as rq2_module
from ease2026.analysis.rq2 import MembershipSet, Rq2Analyzer


def _membership(project_authors: dict[str, set[str]]) -> MembershipSet:
    project_author_pairs: set[tuple[str, str]] = set()
    projects: set[str] = set()
    normalized_project_authors: dict[str, frozenset[str]] = {}
    for project_name, author_ids in project_authors.items():
        normalized_authors = frozenset(author_ids)
        if not normalized_authors:
            continue
        projects.add(project_name)
        normalized_project_authors[project_name] = normalized_authors
        for author_id in normalized_authors:
            project_author_pairs.add((project_name, author_id))
    return MembershipSet(
        project_author_pairs=frozenset(project_author_pairs),
        projects=frozenset(projects),
        project_authors=normalized_project_authors,
    )


def test_write_pairwise_overlap_table_includes_per_project_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rq2_module,
        "settings",
        SimpleNamespace(outputs_csv_dir=tmp_path),
    )

    analyzer = Rq2Analyzer()
    output_path = analyzer._write_pairwise_overlap_table(  # noqa: SLF001
        output_name="rq2_overlap_test_per_project.csv",
        groups={
            "A": _membership(
                {
                    "p1": {"u1", "u2"},
                    "p2": {"u1"},
                    "p3": {"u9"},
                }
            ),
            "B": _membership(
                {
                    "p1": {"u2", "u3"},
                    "p2": {"u1", "u4"},
                    "p4": {"u1"},
                }
            ),
        },
        include_per_project_summary=True,
    )

    with output_path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    row = rows[0]
    assert float(row["pair_jaccard"]) == pytest.approx(2.0 / 7.0)
    assert float(row["project_jaccard"]) == pytest.approx(0.5)
    assert int(row["per_project_n"]) == 2
    assert float(row["per_project_mean_jaccard"]) == pytest.approx(5.0 / 12.0)
    assert float(row["per_project_median_jaccard"]) == pytest.approx(5.0 / 12.0)
    assert float(row["per_project_std_jaccard"]) == pytest.approx(1.0 / 12.0)
    assert float(row["per_project_iqr_jaccard"]) == pytest.approx(1.0 / 12.0)


def test_rq2_run_writes_new_per_project_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rq2_module,
        "settings",
        SimpleNamespace(outputs_csv_dir=tmp_path),
    )
    monkeypatch.setattr(
        rq2_module,
        "HERO_CODE_ORDER",
        ("T1", "T2", "T3", "S1", "S2", "ST1", "TS1", "SH1"),
    )

    memberships = {
        "T1": _membership({"p1": {"a", "b"}, "p2": {"c"}}),
        "T2": _membership({"p1": {"b"}, "p2": {"c", "d"}}),
        "T3": _membership({"p1": {"a"}, "p2": {"d"}}),
        "S1": _membership({"p1": {"x"}}),
        "S2": _membership({"p1": {"x", "y"}}),
        "ST1": _membership({"p1": {"a", "x"}}),
        "TS1": _membership({"p1": {"b", "y"}}),
        "SH1": _membership({"p1": {"a", "b"}}),
    }

    def fake_load_membership_set(hero_code: str) -> MembershipSet:
        return memberships[hero_code]

    monkeypatch.setattr(rq2_module, "_load_membership_set", fake_load_membership_set)

    output_paths = Rq2Analyzer().run()

    expected_keys = {
        "rq2_overlap_technical",
        "rq2_overlap_technical_per_project",
        "rq2_overlap_social",
        "rq2_overlap_social_per_project",
        "rq2_overlap_type_groups",
        "rq2_overlap_type_groups_per_project",
    }
    assert expected_keys == set(output_paths)
    for output_path in output_paths.values():
        assert output_path.exists()
