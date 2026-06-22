"""Player comparison utilities.

Provides deterministic, pure functions to compare a player's metrics to a
reference (pro) metrics or list of pro metrics. Designed to be side-effect
free and easy to unit test.
"""
from typing import Any, Dict, List, Mapping, Optional, Union


def _percentile_from_list(value: float, reference_list: List[float]) -> Optional[float]:
    """Estimate the percentile of ``value`` within ``reference_list``.

    Uses a deterministic linear-interpolation estimator over the sorted
    reference values. Returns a float in the range [0.0, 100.0].

    Behavior:
    - Empty reference_list -> returns None
    - Single-element list -> returns 0.0 if value < ref, 100.0 if value >= ref
    - Multiple elements -> linear interpolation between neighboring sorted
      reference points. Values below the minimum map to 0.0, values above the
      maximum map to 100.0.

    The interpolation places each reference value at an evenly spaced rank
    between 0 and 100 (i.e. rank = i / (n-1) for index i).
    """
    if not reference_list:
        return None

    try:
        s = sorted(float(x) for x in reference_list)
    except (TypeError, ValueError):
        return None

    n = len(s)
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None

    if n == 1:
        # Single reference point: treat as 0/100 boundary
        return 100.0 if v >= s[0] else 0.0

    # Below min (strictly less)
    if v < s[0]:
        return 0.0
    # Above or equal to max
    if v >= s[-1]:
        return 100.0

    # Find interval [s[i], s[i+1]] that contains v
    for i in range(n - 1):
        lo = s[i]
        hi = s[i + 1]
        if lo <= v <= hi:
            # If two reference points are equal, avoid division by zero. In
            # that degenerate case place the value at the lower end.
            if hi == lo:
                t = 0.0
            else:
                t = (v - lo) / (hi - lo)
            # fractional rank between 0 .. (n-1)
            rank = i + t
            # Map rank to percentile as count_le / n * 100 with interpolation.
            # This makes a value equal to the k-th sorted ref (1-based) map to
            # percentile = k / n * 100 (e.g., middle of 3 -> 2/3 -> 66.6%).
            percentile = ((rank + 1) / n) * 100.0
            return percentile

    # Fallback (shouldn't happen) — return None to indicate unknown
    return None


def compare_player_to_reference(player_metrics: Mapping[str, Any], ref_metrics: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Compare a player's metrics to a reference (single or list of pros).

    Args:
        player_metrics: mapping containing the player's metric values. May
            include an identifier under keys like 'player', 'player_id' or
            'id' which, if present, will be copied into the result under
            the 'player' key.
        ref_metrics: either a single pro metrics dict or a list of pro metric
            dicts. Each metrics dict may contain the keys:
                - 'cs_per_min'
                - 'kda'
                - 'dpm' (damage per minute)
                - 'vision_score_per_min'
                - 'gold_per_min'

    Returns:
        A dict with the structure:

        {
            'deltas': {metric: player_value - reference_mean},
            'percentiles': {metric: percentile_or_None},
            'player': identifier_or_None
        }

    The function accepts a single reference dict (treated as a list of one),
    or a list of dicts. Percentiles are computed using the raw list of
    reference values when available; if the reference list is empty the
    percentile value will be None.
    """
    metrics = [
        "cs_per_min",
        "kda",
        "dpm",
        "vision_score_per_min",
        "gold_per_min",
    ]

    # Helper to safely extract a float value
    def _safe(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    # Extract player values
    player_vals: Dict[str, float] = {m: _safe(player_metrics.get(m, 0.0)) for m in metrics}

    # Determine player identifier if present
    player_id = None
    for key in ("player", "player_id", "id", "name", "summoner_name"):
        if key in player_metrics:
            player_id = player_metrics.get(key)
            break

    # Normalize reference metrics into per-metric lists
    ref_lists: Dict[str, List[float]] = {m: [] for m in metrics}

    if isinstance(ref_metrics, list):
        for r in ref_metrics:
            if not isinstance(r, dict):
                continue
            for m in metrics:
                ref_lists[m].append(_safe(r.get(m, 0.0)))
    elif isinstance(ref_metrics, dict):
        # If dict contains lists for metrics (e.g. {'cs_per_min': [..]}), use
        # them. Otherwise treat as a single reference point.
        if any(isinstance(v, list) for v in ref_metrics.values()):
            for m in metrics:
                vals = ref_metrics.get(m, [])
                if isinstance(vals, list):
                    ref_lists[m] = [ _safe(x) for x in vals ]
        else:
            for m in metrics:
                # if ref_metrics provided a scalar, wrap it as a single-element list
                ref_lists[m] = [ _safe(ref_metrics.get(m, 0.0)) ]
    else:
        # Unknown form — leave ref_lists empty
        pass

    # Compute means for deltas (use 0.0 when no reference values exist)
    ref_means: Dict[str, float] = {}
    for m in metrics:
        vals = ref_lists.get(m) or []
        if vals:
            ref_means[m] = sum(vals) / len(vals)
        else:
            ref_means[m] = 0.0

    deltas = {m: player_vals[m] - ref_means[m] for m in metrics}

    # Compute percentiles (None when reference list empty)
    percentiles: Dict[str, Optional[float]] = {}
    for m in metrics:
        vals = ref_lists.get(m) or []
        if len(vals) == 0:
            percentiles[m] = None
        elif len(vals) == 1:
            # Single value -> 0 or 100
            try:
                percentiles[m] = 100.0 if player_vals[m] >= float(vals[0]) else 0.0
            except (TypeError, ValueError):
                percentiles[m] = None
        else:
            percentiles[m] = _percentile_from_list(player_vals[m], vals)

    result: Dict[str, Any] = {
        "deltas": deltas,
        "percentiles": percentiles,
        "player": player_id,
    }

    return result
