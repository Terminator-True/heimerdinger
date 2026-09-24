"""Tests for the Oracle's Elixir pro-baseline module.

Stdlib + pytest only: the module under test is deliberately dependency-free.
"""
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from modules.data.pro_baseline import (  # noqa: E402
    DEFAULT_SOURCE,
    canonical_position,
    comparison_rows,
    compute_baseline,
    format_comparison,
    iter_metric_rows,
    load_baseline,
    load_pro_reference,
    save_baseline,
)

HEADER = [
    "gameid", "datacompleteness", "league", "year", "position", "playername",
    "result", "gamelength", "kills", "deaths", "assists", "visionscore",
    "vspm", "wardsplaced", "wardskilled", "wpm", "controlwardsbought",
    "cspm", "dpm", "damagetochampions", "totalgold", "earned gpm", "total cs",
]

# Two complete support games + one mid game + one partial support game.
BASE_ROWS = [
    ["g1", "complete", "LCK", "2025", "sup", "A", "1", "1800", "2", "3", "12",
     "40", "2.0", "20", "5", "1.0", "4", "1.5", "300", "15000", "10000",
     "333.3", "45"],
    ["g2", "complete", "LCK", "2025", "sup", "B", "0", "1900", "0", "5", "8",
     "60", "3.0", "30", "7", "1.5", "6", "1.0", "400", "20000", "11000",
     "350.0", "40"],
    ["g3", "complete", "LCK", "2025", "mid", "C", "1", "1800", "9", "1", "3",
     "10", "0.3", "5", "1", "0.2", "0", "8.0", "600", "30000", "15000",
     "500.0", "220"],
    ["g4", "partial", "LCK", "2025", "sup", "D", "1", "1800", "1", "1", "1",
     "1", "0.1", "1", "1", "0.1", "0", "1.0", "100", "1000", "1000",
     "100.0", "10"],
]


def write_csv(path: Path, rows, header=HEADER, encoding: str = "utf-8-sig") -> Path:
    with path.open("w", encoding=encoding, newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def fixture(tmp_path: Path, rows=BASE_ROWS, encoding: str = "utf-8-sig") -> Path:
    return write_csv(tmp_path / "oe.csv", rows, encoding=encoding)


# ------------------------------------------------------------------
#  position canonicalization
# ------------------------------------------------------------------

def test_canonical_position_aliases():
    assert canonical_position("sup") == "Support"
    assert canonical_position("support") == "Support"
    assert canonical_position("utility") == "Support"
    assert canonical_position("bot") == "Bot"
    assert canonical_position("adc") == "Bot"
    assert canonical_position("jng") == "Jungle"
    assert canonical_position("jungle") == "Jungle"
    assert canonical_position("MID") == "Mid"
    assert canonical_position("middle") == "Mid"
    assert canonical_position("top") == "Top"
    assert canonical_position(None) is None
    assert canonical_position("unknown") is None


# ------------------------------------------------------------------
#  row streaming / filtering
# ------------------------------------------------------------------

def test_position_filter_keeps_support_only(tmp_path):
    rows = list(iter_metric_rows(fixture(tmp_path), position="sup"))
    assert len(rows) == 2
    # the mid game has 9 kills and the partial game 1 kill — neither leaks in
    assert [r["kills"] for r in rows] == [2.0, 0.0]


def test_header_normalization_preserves_internal_spaces(tmp_path):
    row = next(iter_metric_rows(fixture(tmp_path), position="sup"))
    # "earned gpm" -> goldPerMinute
    assert row["goldPerMinute"] == 333.3
    # "total cs" is intentionally unmapped — no fabricated mapping
    assert "total cs" not in row
    assert "total cs" not in row.values()


def test_bom_tolerance(tmp_path):
    # Written with a UTF-8 BOM; utf-8-sig decoding is required to read gameid.
    rows = list(iter_metric_rows(fixture(tmp_path, encoding="utf-8-sig"), position="sup"))
    assert len(rows) == 2
    assert rows[0]["gameDuration"] == 1800.0


def test_non_complete_rows_skipped(tmp_path):
    rows = list(iter_metric_rows(fixture(tmp_path), position="sup"))
    # g4 is partial (deaths=1); g1/g2 have deaths 3 and 5
    assert sorted(r["deaths"] for r in rows) == [3.0, 5.0]


def test_year_and_league_filters(tmp_path):
    extra = BASE_ROWS + [
        ["g5", "complete", "LPL", "2024", "sup", "E", "1", "1700", "1", "2", "9",
         "30", "1.5", "15", "4", "0.8", "3", "1.2", "250", "12000", "9000",
         "300.0", "35"],
    ]
    path = fixture(tmp_path, rows=extra)

    only_2025 = list(iter_metric_rows(path, position="sup", years=[2025]))
    assert len(only_2025) == 2

    only_lpl = list(iter_metric_rows(path, position="sup", leagues=["lpl"]))
    assert len(only_lpl) == 1
    assert only_lpl[0]["kills"] == 1.0

    both = list(iter_metric_rows(path, position="sup", years=[2024], leagues=["LPL"]))
    assert len(both) == 1
    assert both[0]["goldPerMinute"] == 300.0


def test_derived_kda_and_win(tmp_path):
    rows = list(iter_metric_rows(fixture(tmp_path), position="sup"))
    assert rows[0]["win"] == 1.0
    assert rows[1]["win"] == 0.0
    assert rows[0]["kda"] == (2 + 12) / 3
    assert rows[1]["kda"] == (0 + 8) / 5


def test_deaths_zero_kda_uses_max_one(tmp_path):
    rows = [
        ["g0", "complete", "LCK", "2025", "sup", "Z", "1", "1800", "5", "0", "10",
         "20", "1.0", "10", "2", "0.5", "1", "1.0", "200", "10000", "8000",
         "260.0", "30"],
    ]
    row = next(iter_metric_rows(fixture(tmp_path, rows=rows), position="sup"))
    assert row["kda"] == 15.0  # (5 + 10) / max(1, 0)


# ------------------------------------------------------------------
#  baseline aggregation
# ------------------------------------------------------------------

def test_compute_baseline_mean_and_percentiles(tmp_path):
    rows = list(iter_metric_rows(fixture(tmp_path), position="sup"))
    baseline = compute_baseline(rows, role="Support")

    assert baseline["games"] == 2
    assert baseline["role"] == "Support"
    assert baseline["source"] == DEFAULT_SOURCE
    assert isinstance(baseline["generated_at"], str) and baseline["generated_at"]

    assert baseline["metrics"]["kills"] == {
        "mean": 1.0, "median": 1.0, "p25": 0.0, "p75": 2.0, "n": 2,
    }
    assert baseline["metrics"]["deaths"]["mean"] == 4.0
    assert baseline["metrics"]["assists"]["mean"] == 10.0
    assert baseline["metrics"]["kda"]["mean"] == 3.133
    assert baseline["metrics"]["win"]["mean"] == 0.5
    assert baseline["metrics"]["visionScore"]["mean"] == 50.0
    assert baseline["metrics"]["visionScorePerMinute"]["mean"] == 2.5
    assert baseline["metrics"]["goldPerMinute"]["mean"] == 341.65
    assert baseline["metrics"]["gameDuration"]["mean"] == 1850.0


def test_compute_baseline_empty_rows():
    baseline = compute_baseline([], role="Support")
    assert baseline["games"] == 0
    assert baseline["metrics"] == {}


# ------------------------------------------------------------------
#  comparison
# ------------------------------------------------------------------

def test_comparison_rows_pct_math_and_ordering():
    metrics = {"kills": 2.0, "visionScore": 40.0, "kda": 4.0}
    reference = {"kills": 1.0, "visionScore": 50.0, "kda": 3.133}

    rows = comparison_rows(metrics, reference)

    assert [r["metric"] for r in rows] == ["kills", "kda", "visionScore"]
    assert rows[0]["pct"] == 100.0
    assert rows[0]["delta"] == 1.0
    assert rows[1]["pct"] == 27.7
    assert rows[2]["pct"] == -20.0
    assert rows[2]["delta"] == -10.0


def test_comparison_rows_only_both_sides():
    rows = comparison_rows({"kills": 2.0, "unmapped": 9.0}, {"kills": 1.0, "other": 5.0})
    assert [r["metric"] for r in rows] == ["kills"]


def test_comparison_rows_resolves_report_key_aliases():
    # Report-side spellings: bare damage key + ch_-prefixed challenge key.
    metrics = {"damageDealtToChampions": 15000.0, "ch_visionScorePerMinute": 3.0}
    reference = {"damageDealtToChampions": 20000.0, "visionScorePerMinute": 2.5}

    rows = comparison_rows(metrics, reference)

    assert [r["metric"] for r in rows] == [
        "damageDealtToChampions", "visionScorePerMinute"]
    assert rows[0]["player"] == 15000.0
    assert rows[0]["pro"] == 20000.0
    assert rows[0]["pct"] == -25.0
    assert rows[1]["player"] == 3.0
    assert rows[1]["pro"] == 2.5
    assert rows[1]["pct"] == 20.0


def test_comparison_rows_skips_reference_only_metric():
    # wardsKilled is on the reference only — no player counterpart, so skipped.
    rows = comparison_rows({"kills": 2.0}, {"kills": 1.0, "wardsKilled": 5.0})
    assert [r["metric"] for r in rows] == ["kills"]


def test_comparison_rows_zero_pro_pct_is_none():
    rows = comparison_rows({"kills": 5.0}, {"kills": 0})
    assert rows[0]["pct"] is None
    # rows without pct sort last
    both = comparison_rows({"kills": 5.0, "deaths": 2.0}, {"kills": 0, "deaths": 1.0})
    assert both[0]["metric"] == "deaths"
    assert both[1]["metric"] == "kills"


def test_comparison_rows_limit():
    metrics = {f"m{i}": float(i + 1) for i in range(10)}
    reference = {f"m{i}": 1.0 for i in range(10)}
    rows = comparison_rows(metrics, reference, limit=3)
    assert len(rows) == 3


def test_format_comparison_output():
    rows = [
        {"metric": "kills", "player": 2.0, "pro": 1.0, "delta": 1.0, "pct": 100.0},
        {"metric": "visionScore", "player": 40.0, "pro": 50.0, "delta": -10.0, "pct": -20.0},
        {"metric": "kda", "player": 4.0, "pro": 0.0, "delta": 4.0, "pct": None},
    ]
    text = format_comparison(rows, limit=2)
    assert text == (
        "- kills: 2.00 vs 1.00 pro (+100.0%)\n"
        "- visionScore: 40.00 vs 50.00 pro (-20.0%)"
    )
    assert "n/a" in format_comparison(rows)


# ------------------------------------------------------------------
#  persistence
# ------------------------------------------------------------------

def test_save_and_load_roundtrip_dict_db():
    db = {}
    baseline = {"role": "Support", "source": DEFAULT_SOURCE, "games": 1,
                "generated_at": "2026-01-01T00:00:00+00:00",
                "metrics": {"kills": {"mean": 3.0, "n": 1}}}
    assert save_baseline(db, baseline) is True
    assert load_pro_reference(db, "Support") == {"kills": 3.0}


def test_load_pro_reference_json_fallback(tmp_path):
    path = tmp_path / "pro_baseline.json"
    path.write_text(json.dumps({
        "role": "Support",
        "metrics": {"kills": {"mean": 2.5}, "goldPerMinute": {"mean": 340.0}},
    }), encoding="utf-8")

    ref = load_pro_reference({}, "Support", json_path=path)
    assert ref == {"kills": 2.5, "goldPerMinute": 340.0}


def test_load_pro_reference_missing_returns_empty(tmp_path):
    assert load_pro_reference({}, "Support", json_path=tmp_path / "nope.json") == {}


# ------------------------------------------------------------------
#  load_baseline
# ------------------------------------------------------------------

class _FakeCol:
    def __init__(self, doc, default=None):
        self._doc = doc

    def find_one(self, filt):
        if self._doc is not None and self._doc.get("role") == filt.get("role"):
            return self._doc
        return None


class _FakeDB:
    def __init__(self, doc):
        self._doc = doc

    def get_collection(self, name):
        return _FakeCol(self._doc)


def test_load_baseline_from_collection():
    doc = {"role": "Support", "source": DEFAULT_SOURCE, "games": 3,
           "metrics": {"kills": {"mean": 1.0, "n": 3}}}
    db = _FakeDB(doc)
    assert load_baseline(db, "Support") == doc
    assert load_baseline(db, "Top") is None


def test_load_baseline_roundtrip_dict_db():
    db = {}
    baseline = {"role": "Support", "source": DEFAULT_SOURCE, "games": 1,
                "metrics": {"kills": {"mean": 3.0, "n": 1}}}
    assert save_baseline(db, baseline) is True
    # load_baseline returns the FULL doc, not just the {metric: mean} view
    assert load_baseline(db, "Support") == baseline


def test_load_baseline_json_dict(tmp_path):
    path = tmp_path / "pro_baseline.json"
    doc = {"role": "Support", "metrics": {"kills": {"mean": 2.5, "n": 1}}}
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load_baseline({}, "Support", json_path=path) == doc


def test_load_baseline_json_list_keyed_by_role(tmp_path):
    path = tmp_path / "pro_baseline.json"
    support = {"role": "Support", "metrics": {"kills": {"mean": 2.5, "n": 1}}}
    mid = {"role": "Mid", "metrics": {"kills": {"mean": 5.0, "n": 2}}}
    path.write_text(json.dumps([support, mid]), encoding="utf-8")
    assert load_baseline({}, "Mid", json_path=path) == mid
    assert load_baseline({}, "Top", json_path=path) is None


def test_load_baseline_missing_returns_none(tmp_path):
    assert load_baseline({}, "Support", json_path=tmp_path / "nope.json") is None
