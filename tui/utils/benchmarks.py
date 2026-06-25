"""Benchmark comparisons for LoL roles.

Sources: Riot API aggregated stats, community benchmarks (emerlad+).
Values represent "good" performance for each role.
"""

from typing import Dict, Any

BENCHMARKS: Dict[str, Dict[str, float]] = {
    "Top": {
        "cs_per_min": 7.5,
        "kda": 3.0,
        "gold_per_min": 420,
        "vision_per_min": 0.5,
        "kill_participation": 55,
    },
    "Jungle": {
        "cs_per_min": 5.5,
        "kda": 3.5,
        "gold_per_min": 380,
        "vision_per_min": 1.2,
        "kill_participation": 65,
    },
    "Mid": {
        "cs_per_min": 8.0,
        "kda": 3.5,
        "gold_per_min": 440,
        "vision_per_min": 0.6,
        "kill_participation": 55,
    },
    "ADC": {
        "cs_per_min": 8.5,
        "kda": 4.0,
        "gold_per_min": 460,
        "vision_per_min": 0.4,
        "kill_participation": 60,
    },
    "Support": {
        "cs_per_min": 1.5,
        "kda": 3.0,
        "gold_per_min": 260,
        "vision_per_min": 2.0,
        "kill_participation": 65,
    },
}


def get_benchmark(role: str) -> Dict[str, float]:
    """Return benchmarks for the given role, defaulting to Mid if unknown."""
    return BENCHMARKS.get(role, BENCHMARKS["Mid"])


def compare_to_benchmark(role: str, metric: str, value: float) -> Dict[str, Any]:
    """Compare a metric against the role benchmark.

    Returns:
        dict with: benchmark, diff, is_above (bool), pct_of_benchmark
    """
    bm = get_benchmark(role).get(metric, 0)
    if bm == 0:
        return {"benchmark": 0, "diff": 0, "is_above": False, "pct_of_benchmark": 0}
    diff = value - bm
    pct = (value / bm) * 100
    return {
        "benchmark": bm,
        "diff": round(diff, 2),
        "is_above": diff >= 0,
        "pct_of_benchmark": round(pct, 1),
    }
