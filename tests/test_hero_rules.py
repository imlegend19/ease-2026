from ease2026.hero.rules import hero_project_and_heroes, is_hero_project, select_top_contributors


def test_single_contributor_selects_one() -> None:
    counts = {"alice": 7}

    selected = select_top_contributors(counts, top_fraction=0.2)

    assert len(selected) == 1
    assert selected == {"alice": 7}


def test_80_20_distribution_passes() -> None:
    counts = {"a": 80, "b": 10, "c": 5, "d": 3, "e": 2}

    assert is_hero_project(counts, top_fraction=0.2, coverage_fraction=0.8)


def test_80_20_distribution_fails() -> None:
    counts = {"a": 79, "b": 10, "c": 5, "d": 3, "e": 3}

    assert not is_hero_project(counts, top_fraction=0.2, coverage_fraction=0.8)


def test_hero_selection_stable_when_top_fraction_changes() -> None:
    counts = {"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}

    small = select_top_contributors(counts, top_fraction=0.2)
    large = select_top_contributors(counts, top_fraction=0.4)

    assert set(small).issubset(set(large))
    assert list(small.items()) == [("a", 10)]
    assert list(large.items()) == [("a", 10), ("b", 8)]

    is_hero_small, heroes_small = hero_project_and_heroes(
        counts,
        top_fraction=0.2,
        coverage_fraction=0.6,
    )
    is_hero_large, heroes_large = hero_project_and_heroes(
        counts,
        top_fraction=0.4,
        coverage_fraction=0.6,
    )

    assert not is_hero_small
    assert is_hero_large
    assert heroes_small == small
    assert heroes_large == large
