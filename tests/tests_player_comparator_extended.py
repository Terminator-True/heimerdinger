import math
from modules.data import player_comparator as pc


def test_percentile_interpolation_odd_even():
    # Odd-length list
    refs = [10, 20, 30]
    # 10 -> 0.0, 20 -> 50.0, 30 -> 100.0
    assert math.isclose(pc._percentile_from_list(10, refs), 0.0, abs_tol=1e-9)
    assert math.isclose(pc._percentile_from_list(20, refs), 50.0, abs_tol=1e-9)
    assert math.isclose(pc._percentile_from_list(30, refs), 100.0, abs_tol=1e-9)

    # Interpolate between 10 and 20 -> should be 25.0 at value 15
    assert math.isclose(pc._percentile_from_list(15, refs), 25.0, abs_tol=1e-9)

    # Even-length list
    refs2 = [0, 100]
    # value 0 -> 0, 100 -> 100, 50 -> 50
    assert math.isclose(pc._percentile_from_list(0, refs2), 0.0, abs_tol=1e-9)
    assert math.isclose(pc._percentile_from_list(100, refs2), 100.0, abs_tol=1e-9)
    assert math.isclose(pc._percentile_from_list(50, refs2), 50.0, abs_tol=1e-9)


def test_percentile_edges_and_single():
    # Empty -> None
    assert pc._percentile_from_list(10, []) is None

    # Single element
    assert pc._percentile_from_list(5, [10]) == 0.0
    assert pc._percentile_from_list(10, [10]) == 100.0
    assert pc._percentile_from_list(15, [10]) == 100.0


def test_multi_metric_comparison():
    player = {
        "player": "testplayer",
        "cs_per_min": 9.0,
        "kda": 3.0,
        "dpm": 400.0,
        "vision_score_per_min": 1.2,
        "gold_per_min": 350.0,
    }

    pros = [
        {"cs_per_min": 8.0, "kda": 2.5, "dpm": 380.0, "vision_score_per_min": 1.0, "gold_per_min": 330.0},
        {"cs_per_min": 10.0, "kda": 3.5, "dpm": 420.0, "vision_score_per_min": 1.4, "gold_per_min": 360.0},
        {"cs_per_min": 9.0, "kda": 3.0, "dpm": 400.0, "vision_score_per_min": 1.3, "gold_per_min": 345.0},
    ]

    res = pc.compare_player_to_reference(player, pros)

    # Deltas: player - mean
    mean_cs = (8.0 + 10.0 + 9.0) / 3.0
    assert math.isclose(res["deltas"]["cs_per_min"], 9.0 - mean_cs, rel_tol=1e-9)

    mean_kda = (2.5 + 3.5 + 3.0) / 3.0
    assert math.isclose(res["deltas"]["kda"], 3.0 - mean_kda, rel_tol=1e-9)

    # Percentiles should be finite numbers between 0 and 100
    cs_pct = res["percentiles"]["cs_per_min"]
    kda_pct = res["percentiles"]["kda"]
    assert isinstance(cs_pct, float) and 0.0 <= cs_pct <= 100.0
    assert isinstance(kda_pct, float) and 0.0 <= kda_pct <= 100.0

    # Check one of the other metrics
    dpm_pct = res["percentiles"]["dpm"]
    assert isinstance(dpm_pct, float) and 0.0 <= dpm_pct <= 100.0


def test_empty_reference_list_percentiles_none():
    player = {"cs_per_min": 7.0, "kda": 1.5}
    res = pc.compare_player_to_reference(player, [])
    # All percentiles should be None when ref list empty
    for v in res["percentiles"].values():
        assert v is None
