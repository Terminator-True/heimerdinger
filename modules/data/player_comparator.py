"""Player comparison utilities.

Provides deterministic, pure functions to compare a player's metrics to a
reference (pro) metrics or list of pro metrics. Designed to be side-effect
free and easy to unit test.
"""
from typing import Any, Dict, List, Mapping


def _percentile_from_list(value: float, reference_list: List[float]) -> float:
    """Estimate the percentile of `value` within `reference_list`.

    Simple deterministic estimator: percentile = (count of refs <= value) / len
    Returns value in [0.0, 100.0]. If reference_list is empty, returns 0.0.
    """
    if not reference_list:
        return 0.0
    try:
        sorted_refs = sorted(float(x) for x in reference_list)
    except (TypeError, ValueError):
        return 0.0
    count = 0
    for r in sorted_refs:
        if r <= value:
            count += 1
    return (count / len(sorted_refs)) * 100.0


def _percentile_single(value: float, ref_value: float) -> float:
    """Return percentile comparing value to a single reference value.

    If value >= ref_value -> 100.0 else 0.0. Deterministic for single point.
    """
    try:
        v = float(value)
        r = float(ref_value)
    except (TypeError, ValueError):
        return 0.0
    return 100.0 if v >= r else 0.0


def compare_player_to_reference(player_metrics: Mapping[str, Any], ref_metrics: Any) -> Dict[str, Any]:
    """Compare player_metrics to a reference.

    Args:
        player_metrics: mapping with at least 'cs_per_min' and 'kda' numeric fields
        ref_metrics: either a mapping (single reference) or a list of mappings or
            a mapping of lists for each metric. Acceptable forms:
               - dict: {'cs_per_min': float, 'kda': float}
               - list[dict]: list of pro player metric dicts
               - dict of lists: {'cs_per_min': [..], 'kda': [..]}

    Returns:
        dict with keys 'deltas' and 'percentiles', each mapping metric->value
    """
    # Extract player values
    player_cs = float(player_metrics.get("cs_per_min", 0.0) or 0.0)
    player_kda = float(player_metrics.get("kda", 0.0) or 0.0)

    # Normalize reference into lists for each metric
    cs_refs: List[float] = []
    kda_refs: List[float] = []

    # If ref_metrics is a list of dicts
    if isinstance(ref_metrics, list):
        for r in ref_metrics:
            cs_refs.append(float(r.get("cs_per_min", 0.0) or 0.0))
            kda_refs.append(float(r.get("kda", 0.0) or 0.0))
    elif isinstance(ref_metrics, dict):
        # Could be dict of lists or single dict
        if all(isinstance(v, list) for v in ref_metrics.values()):
            cs_refs = [float(x or 0.0) for x in ref_metrics.get("cs_per_min", [])]
            kda_refs = [float(x or 0.0) for x in ref_metrics.get("kda", [])]
        else:
            # Single reference point
            cs_val = float(ref_metrics.get("cs_per_min", 0.0) or 0.0)
            kda_val = float(ref_metrics.get("kda", 0.0) or 0.0)
            cs_refs = [cs_val]
            kda_refs = [kda_val]
    else:
        # Unknown type -> empty refs
        cs_refs = []
        kda_refs = []

    deltas = {
        "cs_per_min": player_cs - (cs_refs[0] if cs_refs else 0.0),
        "kda": player_kda - (kda_refs[0] if kda_refs else 0.0),
    }

    # Percentiles
    if len(cs_refs) == 1:
        cs_percent = _percentile_single(player_cs, cs_refs[0])
    else:
        cs_percent = _percentile_from_list(player_cs, cs_refs)

    if len(kda_refs) == 1:
        kda_percent = _percentile_single(player_kda, kda_refs[0])
    else:
        kda_percent = _percentile_from_list(player_kda, kda_refs)

    percentiles = {
        "cs_per_min": cs_percent,
        "kda": kda_percent,
    }

    return {"deltas": deltas, "percentiles": percentiles}
