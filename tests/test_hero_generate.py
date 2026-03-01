from pathlib import Path

from ease2026.hero.generate import build_hero_flags_and_members, generate_hero_outputs


def test_build_hero_flags_and_members_filters_non_hero_projects() -> None:
    contribution_map = {
        "p1": {"a": 80, "b": 10, "c": 5, "d": 3, "e": 2},
        "p2": {"a": 30, "b": 25, "c": 20, "d": 15, "e": 10},
    }

    flags, members = build_hero_flags_and_members(
        contribution_map=contribution_map,
        top_fraction=0.2,
        coverage_fraction=0.8,
    )

    assert flags == {"p1": True, "p2": False}
    assert members == {"p1": {"a": 80}}


def test_generate_hero_outputs_writes_expected_csv_schema(tmp_path: Path) -> None:
    contribution_map = {"p1": {"a": 80, "b": 10, "c": 5, "d": 3, "e": 2}}

    result = generate_hero_outputs(
        contribution_map=contribution_map,
        metric_name="T1",
        top_fraction=0.2,
        coverage_fraction=0.8,
        output_root=tmp_path,
    )

    assert result.csv_path == tmp_path / "T1" / "heroes.csv"
    assert result.csv_path.exists()

    csv_text = result.csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert csv_text[0] == "project_name,author_id,metric_value"
    assert csv_text[1] == "p1,a,80"

