from ease2026.hero.hybrid import (
    project_quantile_threshold,
    sociotechnical_heroes,
    superheroes,
    technosocial_heroes,
)


def test_project_quantile_threshold_q_05_matches_legacy_median_intent() -> None:
    odd_counts = {"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}
    even_counts = {"a": 10, "b": 8, "c": 6, "d": 4}

    assert project_quantile_threshold(odd_counts, 0.5) == 6
    assert project_quantile_threshold(even_counts, 0.5) == 6


def test_project_quantile_threshold_q_075_is_stricter_than_q_05() -> None:
    counts = {"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}

    assert project_quantile_threshold(counts, 0.5) == 6
    assert project_quantile_threshold(counts, 0.75) == 8


def test_sociotechnical_quantile_uses_full_project_distribution() -> None:
    social_heroes = {"p": {"c": 30, "d": 20, "e": 10}}
    technical_contributions = {"p": {"a": 10, "b": 8, "c": 6, "d": 4, "e": 2}}

    selected = sociotechnical_heroes(
        social_heroes=social_heroes,
        technical_contributions=technical_contributions,
        quantile=0.75,
    )

    assert selected == {}


def test_technosocial_quantile_uses_full_project_distribution() -> None:
    technical_heroes = {"p": {"c": 30, "d": 20, "e": 10}}
    social_contributions = {"p": {"a": 100, "b": 80, "c": 60, "d": 40, "e": 20}}

    selected = technosocial_heroes(
        technical_heroes=technical_heroes,
        social_contributions=social_contributions,
        quantile=0.75,
    )

    assert selected == {}


def test_superheroes_are_strict_intersection() -> None:
    technical_heroes = {"p": {"a": 10, "b": 9}, "q": {"x": 5}}
    social_heroes = {"p": {"b": 20, "c": 15}, "q": {}}

    selected = superheroes(technical_heroes=technical_heroes, social_heroes=social_heroes)

    assert selected == {"p": {"b": 9}}


def test_hybrid_handles_empty_projects_defensively() -> None:
    social_heroes = {"p": {"a": 10}}
    technical_contributions = {}

    assert project_quantile_threshold({}, 0.5) is None
    assert sociotechnical_heroes(social_heroes, technical_contributions, quantile=0.5) == {}
