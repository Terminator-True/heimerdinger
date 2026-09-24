"""Pro-player role baselines from Oracle's Elixir match CSVs.

This module turns the public Oracle's Elixir dataset into per-role metric
baselines (mean/median/p25/p75) that our coaching reports can compare a
player against. It is intentionally stdlib-only (csv, json, statistics,
datetime) so it can run on a bare interpreter without the project's
third-party stack.

Usage:
    from modules.data.pro_baseline import (
        iter_metric_rows, compute_baseline, comparison_rows,
        format_comparison, save_baseline, load_pro_reference,
    )
    rows = iter_metric_rows("2025_LoL_esports_match_data.csv", position="sup")
    baseline = compute_baseline(rows, role="Support")
"""
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, Iterator, List, Optional

# ------------------------------------------------------------------
#  Oracle's Elixir -> our canonical metric keys
# ------------------------------------------------------------------

# OE `position` values are lowercase; our reports use canonical role names.
POSITION_ALIASES: Dict[str, str] = {
    "top": "Top",
    "jng": "Jungle",
    "jungle": "Jungle",
    "mid": "Mid",
    "middle": "Mid",
    "bot": "Bot",
    "adc": "Bot",
    "sup": "Support",
    "support": "Support",
    "utility": "Support",
}

# OE column (normalized: strip().lower(), internal spaces kept) -> canonical
# metric key. Canonical names mirror the field names already used by our
# reports (see report_builder.extract_rich_participant and match_parser).
OE_METRIC_MAP: Dict[str, str] = {
    "kills": "kills",
    "deaths": "deaths",
    "assists": "assists",
    "visionscore": "visionScore",
    "vspm": "visionScorePerMinute",
    "wardsplaced": "wardsPlaced",
    "wardskilled": "wardsKilled",
    "wpm": "wardsPerMinute",
    "controlwardsbought": "controlWardsPlaced",
    "cspm": "cs_per_min",
    "dpm": "damagePerMinute",
    "damagetochampions": "damageDealtToChampions",
    "totalgold": "goldEarned",
    "earned gpm": "goldPerMinute",
    "gamelength": "gameDuration",
}

# canonical baseline metric -> possible keys in our reports (first match wins).
# Our reports disagree on key spelling depending on the source: match_parser /
# build_player_report use bare names, while extract_rich_participant uses the
# Riot raw names and `ch_`-prefixed challenge fields. This table lets the
# comparison resolve either variant without changing the reports themselves.
METRIC_KEY_ALIASES: Dict[str, tuple] = {
    "kills": ("kills",),
    "deaths": ("deaths",),
    "assists": ("assists",),
    "kda": ("kda",),
    "win": ("win",),
    "cs_per_min": ("cs_per_min", "cspm"),
    "visionScore": ("visionScore",),
    "visionScorePerMinute": ("visionScorePerMinute", "ch_visionScorePerMinute", "vspm"),
    "wardsPlaced": ("wardsPlaced",),
    "wardsKilled": ("wardsKilled",),
    "controlWardsPlaced": ("controlWardsPlaced", "ch_controlWardsPlaced", "controlwardsbought"),
    "damageDealtToChampions": ("damageDealtToChampions", "totalDamageDealtToChampions"),
    "damagePerMinute": ("damagePerMinute", "ch_damagePerMinute", "dpm"),
    "goldPerMinute": ("goldPerMinute", "ch_goldPerMinute", "earned gpm"),
    "goldEarned": ("goldEarned",),
    "gameDuration": ("gameDuration", "gameDurationSeconds"),
    "wardsPerMinute": ("wardsPerMinute", "wpm"),
}

COLLECTION = "pro_baselines"
DEFAULT_JSON_PATH = Path("config") / "pro_baseline.json"
DEFAULT_SOURCE = "oracles_elixir"


def canonical_position(raw: Optional[str]) -> Optional[str]:
    """Map an OE/role position string to its canonical role name, or None."""
    if raw is None:
        return None
    return POSITION_ALIASES.get(str(raw).strip().lower())


def _normalize_header(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip and lowercase header names while keeping internal spaces."""
    return {(k or "").strip().lower(): v for k, v in row.items()}


def _percentile(values: List[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile (0..100). Returns None for an empty list."""
    if not values:
        return None
    d = sorted(values)
    n = len(d)
    if n == 1:
        return d[0]
    rank = math.ceil((pct / 100.0) * n)
    idx = min(max(rank - 1, 0), n - 1)
    return d[idx]


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def iter_metric_rows(csv_path, position: str = "sup",
                     years: Optional[Iterable[int]] = None,
                     leagues: Optional[Iterable[str]] = None) -> Iterator[Dict[str, float]]:
    """Stream OE rows as ``{canonical_metric: float}`` dicts.

    Filters (all optional):
      - ``position``: canonicalized before comparing (default ``sup``).
      - ``years``: ints compared against the row's ``year``.
      - ``leagues``: compared case-insensitively (uppercased).

    Rows with ``datacompleteness != 'complete'`` are skipped. Only columns
    present in :data:`OE_METRIC_MAP` and non-empty are emitted; ``kda`` and
    ``win`` are derived from kills/deaths/assists and result.
    """
    want_pos = canonical_position(position) if position else None
    want_years = {int(y) for y in years} if years else None
    want_leagues = {str(l).strip().upper() for l in leagues} if leagues else None

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            row = _normalize_header(raw)

            if (row.get("datacompleteness") or "").strip().lower() != "complete":
                continue
            if want_pos is not None and canonical_position(row.get("position")) != want_pos:
                continue
            if want_years is not None:
                year = _to_float(row.get("year"))
                if year is None or int(year) not in want_years:
                    continue
            if want_leagues is not None:
                if (row.get("league") or "").strip().upper() not in want_leagues:
                    continue

            out: Dict[str, float] = {}
            for col, metric in OE_METRIC_MAP.items():
                value = _to_float(row.get(col))
                if value is not None:
                    out[metric] = value

            kills = _to_float(row.get("kills"))
            deaths = _to_float(row.get("deaths"))
            assists = _to_float(row.get("assists"))
            if kills is not None and deaths is not None and assists is not None:
                out["kda"] = (kills + assists) / max(1.0, deaths)

            win = _to_float(row.get("result"))
            if win is not None:
                out["win"] = win

            yield out


def compute_baseline(rows: Iterable[Dict[str, float]], role: str = "Support",
                     source: str = DEFAULT_SOURCE) -> Dict[str, Any]:
    """Aggregate metric rows into a baseline document.

    Returns::

        {"role", "source", "games", "generated_at",
         "metrics": {metric: {"mean", "median", "p25", "p75", "n"}}}
    """
    acc: Dict[str, List[float]] = {}
    games = 0
    for r in rows:
        games += 1
        for key, value in r.items():
            v = _to_float(value)
            if v is not None:
                acc.setdefault(key, []).append(v)

    metrics: Dict[str, Any] = {}
    for key, values in acc.items():
        metrics[key] = {
            "mean": round(mean(values), 3),
            "median": round(median(values), 3),
            "p25": round(_percentile(values, 25), 3),
            "p75": round(_percentile(values, 75), 3),
            "n": len(values),
        }

    return {
        "role": role,
        "source": source,
        "games": games,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }


# ------------------------------------------------------------------
#  persistence
# ------------------------------------------------------------------

def save_baseline(db, baseline: Dict[str, Any]) -> bool:
    """Upsert a baseline into the ``pro_baselines`` collection by role.

    Works with a pymongo-like Database or a plain dict fallback. Returns
    True on success, False when neither backend accepts the write.
    """
    role = baseline.get("role")
    try:
        col = db.get_collection(COLLECTION)
        col.update_one({"role": role}, {"$set": baseline}, upsert=True)
        return True
    except Exception:
        try:
            col = db.setdefault(COLLECTION, {})
            col[role] = baseline
            return True
        except Exception:
            return False


def _means_from_doc(doc: Any) -> Dict[str, float]:
    """Extract ``{metric: mean}`` from a stored baseline document."""
    if not isinstance(doc, dict):
        return {}
    metrics = doc.get("metrics")
    if isinstance(metrics, dict):
        out: Dict[str, float] = {}
        for key, value in metrics.items():
            if isinstance(value, dict):
                m = _to_float(value.get("mean"))
                if m is not None:
                    out[key] = m
            else:
                v = _to_float(value)
                if v is not None:
                    out[key] = v
        return out
    # flat {metric: number} fallback
    out = {}
    for key, value in doc.items():
        if isinstance(value, bool):
            continue
        v = _to_float(value)
        if v is not None:
            out[key] = v
    return out


def load_baseline(db, role: str,
                  json_path=DEFAULT_JSON_PATH) -> Optional[Dict[str, Any]]:
    """Return the full stored baseline document for *role*, or None.

    Reads the ``pro_baselines`` collection first and falls back to the
    ``config/pro_baseline.json`` file (dict or list of dicts keyed by
    ``role``).
    """
    doc = None
    try:
        col = db.get_collection(COLLECTION)
        doc = col.find_one({"role": role})
    except Exception:
        try:
            col = db.setdefault(COLLECTION, {})
            doc = col.get(role)
        except Exception:
            doc = None

    if doc:
        return doc

    try:
        path = Path(json_path)
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                for d in data:
                    if isinstance(d, dict) and d.get("role") == role:
                        return d
                return None
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


def load_pro_reference(db, role: str,
                       json_path=DEFAULT_JSON_PATH) -> Dict[str, float]:
    """Return ``{metric: mean}`` for *role*, or ``{}`` when absent.

    Reads the ``pro_baselines`` collection first and falls back to the
    ``config/pro_baseline.json`` file. The result is ready to pass to
    ``ReportBuilder.build_player_report(..., pro_reference=...)``.
    """
    return _means_from_doc(load_baseline(db, role, json_path=json_path))


# ------------------------------------------------------------------
#  comparison
# ------------------------------------------------------------------

def _player_value(metrics: Dict[str, Any],
                  canonical_key: str) -> Optional[float]:
    """Resolve *canonical_key* against player *metrics* via alias fallbacks.

    Tries :data:`METRIC_KEY_ALIASES` in order and returns the first numeric
    value found, or None when no alias is present.
    """
    for alias in METRIC_KEY_ALIASES.get(canonical_key, (canonical_key,)):
        value = _to_float((metrics or {}).get(alias))
        if value is not None:
            return value
    return None


def comparison_rows(metrics: Dict[str, Any], reference: Dict[str, Any],
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Compare player metrics against a pro reference.

    Iterates the *reference* (baseline) metrics and resolves each canonical
    key against the player side through :func:`_player_value`, so reports
    using a variant spelling (e.g. ``ch_visionScorePerMinute``) still match a
    baseline keyed ``visionScorePerMinute``. Reference metrics with no numeric
    player counterpart are skipped.

    Rows are ``{"metric", "player", "pro", "delta", "pct"}``. ``pct`` is None
    when the pro value is 0. Rows are sorted by ``abs(pct)`` descending; rows
    without a pct go last.
    """
    rows: List[Dict[str, Any]] = []
    for key, pro_raw in (reference or {}).items():
        pro = _to_float(pro_raw)
        if pro is None:
            continue
        player = _player_value(metrics, key)
        if player is None:
            continue
        pct = round((player - pro) / pro * 100, 1) if pro != 0 else None
        rows.append({
            "metric": key,
            "player": player,
            "pro": pro,
            "delta": round(player - pro, 3),
            "pct": pct,
        })
    rows.sort(key=lambda r: abs(r["pct"]) if r["pct"] is not None else -1.0,
              reverse=True)
    if limit is not None:
        rows = rows[:limit]
    return rows


def format_comparison(rows: List[Dict[str, Any]], limit: int = 8) -> str:
    """Render comparison rows as compact English lines for an LLM prompt."""
    lines: List[str] = []
    for r in (rows or [])[:limit]:
        pct = "n/a" if r.get("pct") is None else f"{r['pct']:+.1f}%"
        lines.append(
            f"- {r['metric']}: {r['player']:.2f} vs {r['pro']:.2f} pro ({pct})"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------
#  self-check  (bare python3, no third-party deps)
# ------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    header = [
        "gameid", "datacompleteness", "league", "year", "position", "playername",
        "result", "gamelength", "kills", "deaths", "assists", "visionscore",
        "vspm", "wardsplaced", "wardskilled", "wpm", "controlwardsbought",
        "cspm", "dpm", "damagetochampions", "totalgold", "earned gpm", "total cs",
    ]
    rows = [
        ["g1", "complete", "LCK", "2025", "sup", "A", "1", "1800", "2", "3", "12",
         "40", "2.0", "20", "5", "1.0", "4", "1.5", "300", "15000", "10000",
         "333.3", "45"],
        ["g2", "complete", "LCK", "2025", "sup", "B", "0", "1900", "0", "5", "8",
         "60", "3.0", "30", "7", "1.5", "6", "1.0", "400", "20000", "11000",
         "350.0", "40"],
        # filtered out: wrong position
        ["g3", "complete", "LCK", "2025", "mid", "C", "1", "1800", "9", "1", "3",
         "10", "0.3", "5", "1", "0.2", "0", "8.0", "600", "30000", "15000",
         "500.0", "220"],
        # filtered out: partial data
        ["g4", "partial", "LCK", "2025", "sup", "D", "1", "1800", "1", "1", "1",
         "1", "0.1", "1", "1", "0.1", "0", "1.0", "100", "1000", "1000",
         "100.0", "10"],
    ]

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "oe.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

        parsed = list(iter_metric_rows(csv_path, position="sup"))
        assert len(parsed) == 2, parsed
        assert parsed[0]["kills"] == 2.0
        assert parsed[0]["goldPerMinute"] == 333.3
        assert parsed[0]["visionScorePerMinute"] == 2.0
        assert "total cs" not in parsed[0]
        assert parsed[0]["win"] == 1.0
        assert parsed[1]["win"] == 0.0
        assert abs(parsed[0]["kda"] - (2 + 12) / 3) < 1e-9
        assert abs(parsed[1]["kda"] - (0 + 8) / 5) < 1e-9

        baseline = compute_baseline(parsed, role="Support")
        assert baseline["games"] == 2
        assert baseline["role"] == "Support"
        assert baseline["source"] == DEFAULT_SOURCE
        assert baseline["metrics"]["kills"] == {
            "mean": 1.0, "median": 1.0, "p25": 0.0, "p75": 2.0, "n": 2,
        }
        assert baseline["metrics"]["kda"]["mean"] == 3.133
        assert baseline["metrics"]["visionScorePerMinute"]["mean"] == 2.5
        assert baseline["metrics"]["goldPerMinute"]["mean"] == 341.65
        assert baseline["metrics"]["win"]["mean"] == 0.5

        reference = {
            "kills": baseline["metrics"]["kills"]["mean"],
            "visionScore": baseline["metrics"]["visionScore"]["mean"],
            "kda": baseline["metrics"]["kda"]["mean"],
        }
        compared = comparison_rows(
            {"kills": 2.0, "visionScore": 40.0, "kda": 4.0}, reference)
        assert [r["metric"] for r in compared] == ["kills", "kda", "visionScore"], compared
        assert compared[0]["pct"] == 100.0
        assert compared[1]["pct"] == 27.7
        assert compared[2]["pct"] == -20.0
        text = format_comparison(compared, limit=2)
        assert text == (
            "- kills: 2.00 vs 1.00 pro (+100.0%)\n"
            "- kda: 4.00 vs 3.13 pro (+27.7%)"
        ), text

        # alias resolution: report variants must match canonical baseline keys
        alias_rows = comparison_rows(
            {"damageDealtToChampions": 15000.0, "ch_visionScorePerMinute": 3.0},
            {"damageDealtToChampions": 20000.0, "visionScorePerMinute": 2.5},
        )
        assert [r["metric"] for r in alias_rows] == [
            "damageDealtToChampions", "visionScorePerMinute"], alias_rows
        assert alias_rows[0]["player"] == 15000.0
        assert alias_rows[1]["player"] == 3.0

        # a reference metric the player side lacks is skipped
        only_ref = comparison_rows(
            {"kills": 1.0},
            {"kills": 1.0, "wardsKilled": 5.0},
        )
        assert [r["metric"] for r in only_ref] == ["kills"], only_ref

    print("pro_baseline self-check: OK")
