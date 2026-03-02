from __future__ import annotations

import pytest

from ease2026.analysis.reviewer_robustness import (
    build_neighborhood_configs,
    multifaceted_reopen_advantage_share,
    ts_sh_is_strongest_pair,
)


def test_build_neighborhood_configs_matches_expected_pairs() -> None:
    configs = build_neighborhood_configs()
    assert len(configs) == 8

    config_tuples = {
        (cfg.top_fraction, cfg.coverage_fraction, cfg.hybrid_quantile) for cfg in configs
    }
    assert (0.20, 0.80, 0.50) in config_tuples
    assert (0.25, 0.75, 0.75) in config_tuples
    assert (0.15, 0.85, 0.50) in config_tuples
    assert (0.30, 0.70, 0.75) in config_tuples


def test_ts_sh_is_strongest_pair_detects_global_max() -> None:
    strong = {
        ("social", "technical"): 0.02,
        ("sociotechnical", "super"): 0.55,
        ("super", "technosocial"): 0.92,
    }
    weak = {
        ("social", "technical"): 0.02,
        ("sociotechnical", "super"): 0.91,
        ("super", "technosocial"): 0.90,
    }

    assert ts_sh_is_strongest_pair(strong) is True
    assert ts_sh_is_strongest_pair(weak) is False


def test_multifaceted_reopen_advantage_share_counts_favorable_cells() -> None:
    reopen_median = {
        ("blocker", "social"): 6.0,
        ("blocker", "sociotechnical"): 4.0,
        ("blocker", "technosocial"): 5.0,
        ("blocker", "super"): 6.0,
        ("critical", "social"): 4.0,
        ("critical", "sociotechnical"): 5.0,  # unfavorable
        ("critical", "technosocial"): 4.0,
        ("critical", "super"): 3.0,
    }

    share, favorable, total = multifaceted_reopen_advantage_share(reopen_median)
    assert favorable == 5
    assert total == 6
    assert share == pytest.approx(5 / 6)
