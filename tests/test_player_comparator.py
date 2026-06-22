from modules.data.player_comparator import compare_player_to_reference


def test_compare_single_reference_higher_and_lower():
    player = {"cs_per_min": 5.0, "kda": 3.0}
    pro = {"cs_per_min": 4.0, "kda": 4.0}

    res = compare_player_to_reference(player, pro)
    assert "deltas" in res and "percentiles" in res
    # deltas: player - pro
    assert abs(res["deltas"]["cs_per_min"] - 1.0) < 1e-6
    assert abs(res["deltas"]["kda"] - (-1.0)) < 1e-6
    # percentiles: cs >= pro -> 100, kda < pro -> 0
    assert res["percentiles"]["cs_per_min"] == 100.0
    assert res["percentiles"]["kda"] == 0.0


def test_compare_against_list_percentile():
    player = {"cs_per_min": 4.5, "kda": 2.0}
    pros = [
        {"cs_per_min": 3.0, "kda": 1.0},
        {"cs_per_min": 4.5, "kda": 2.0},
        {"cs_per_min": 5.0, "kda": 3.0},
    ]

    res = compare_player_to_reference(player, pros)
    # For cs_per_min: two refs <= 4.5 (3.0 and 4.5) out of 3 -> 66.666...
    assert abs(res["percentiles"]["cs_per_min"] - (2 / 3 * 100.0)) < 1e-6
    # For kda: two refs <= 2.0 (1.0 and 2.0) out of 3 -> same
    assert abs(res["percentiles"]["kda"] - (2 / 3 * 100.0)) < 1e-6
