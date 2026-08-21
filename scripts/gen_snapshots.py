"""Generate equivalence snapshots for the Hito 0 harness.

Runs ReportBuilder and CoachingPromptBuilder over an anonymized fixture-fed
dict-backed DB and a fixed fake LLM, dumping key-sorted JSON and text outputs
into tests/snapshots/. No live Riot / Ollama / Data Dragon calls.

The same ``build_snapshot_outputs()`` function is imported by
tests/test_equivalence.py, so snapshots and the gate can never drift apart.

Usage:
    python scripts/gen_snapshots.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.coaching.prompt_builder import CoachingPromptBuilder
from modules.data.report_builder import ReportBuilder, render_match_snapshot
from modules.riot_items.models import Item, ItemGold

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "riot"
SNAPSHOT_DIR = ROOT / "tests" / "snapshots"

FOCUS_PUUID = "synthetic-puuid-0001"
FOCUS_ROLE = "Top"
MATCH_ID = "ANON-MATCH-0001"

# Deterministic, offline item names for the focus player's slots.
FAKE_ITEMS = {
    3866: Item(name="Guantes de Bruja", gold=ItemGold(total=1100)),
    2524: Item(name="Filo del Infinito", gold=ItemGold(total=3400)),
    3009: Item(name="Botas de Mercurio", gold=ItemGold(total=1300)),
    3067: Item(name="Corazón de Hielo", gold=ItemGold(total=2900)),
    1028: Item(name="Libro de Hechicero", gold=ItemGold(total=900)),
    3364: Item(name="Centinela de paja", gold=ItemGold(total=0)),
}


class FakeCol(dict):
    """Dict-backed collection matching ReportBuilder's pymongo duck-typing."""

    def find(self, q):
        for v in self.values():
            if v.get("player_puuid") == q.get("player_puuid"):
                yield v

    def update_one(self, filter_q, update_q, upsert=False):
        if "matchId" in filter_q:
            key = f"{filter_q.get('player')}_{filter_q.get('matchId')}"
        else:
            key = filter_q.get("player")
        self[key] = update_q["$set"]


class FakeDB(dict):
    def get_collection(self, name):
        return self.setdefault(name, FakeCol())


class FakeLLM:
    """Fixed LLM client returning a deterministic dict (no network)."""

    def generate(self, prompt, model=None):
        return {
            "model": model or "fake-llm",
            "response": (
                "```json\n"
                '{"areas_of_improvement": ["control de oleadas", "trades cortos", "visión"],'
                ' "exercises": ["practicar freeze", "revisar trades", "wardear río"],'
                ' "strengths": ["buen CS"],'
                ' "summary": "Mejora tu control de oleadas."}\n'
                "```"
            ),
            "done": True,
        }


class FakeDragonClient:
    """Offline Data Dragon stand-in returning fixed item names."""

    version = "14.20.1"

    def __init__(self, items):
        self._items = items

    def resolve_version(self, game_version):
        return self.version

    def get_items_by_ids(self, ids, version=None):
        return {item_id: self._items.get(item_id) for item_id in ids}


def load_match_doc():
    """Load the anonymized match fixture used as snapshot input."""
    return json.loads((FIXTURE_DIR / f"match_{MATCH_ID}.json").read_text(encoding="utf-8"))


def build_fake_db():
    """Deterministic player_matches entries for the focus player."""
    db = FakeDB()
    pm = db.get_collection("player_matches")
    entries = [
        {
            "player_puuid": FOCUS_PUUID,
            "matchId": "ANON-MATCH-0001",
            "championName": "Yone",
            "champion": "Yone",
            "role": "Top",
            "parsed_metrics": {
                "cs_per_min": 6.0,
                "kda": 3.0,
                "goldEarned": 14500,
                "totalDamageDealtToChampions": 28500,
                "visionScore": 25,
                "ch_goldPerMinute": 426.0,
                "ch_killParticipation": 0.18,
            },
        },
        {
            "player_puuid": FOCUS_PUUID,
            "matchId": "ANON-MATCH-0002",
            "championName": "Yone",
            "champion": "Yone",
            "role": "Top",
            "parsed_metrics": {
                "cs_per_min": 6.4,
                "kda": 3.2,
                "goldEarned": 15200,
                "totalDamageDealtToChampions": 30100,
                "visionScore": 22,
                "ch_goldPerMinute": 450.0,
                "ch_killParticipation": 0.21,
            },
        },
        {
            "player_puuid": FOCUS_PUUID,
            "matchId": "ANON-MATCH-0003",
            "championName": "Zed",
            "champion": "Zed",
            "role": "Top",
            "parsed_metrics": {
                "cs_per_min": 6.2,
                "kda": 3.1,
                "goldEarned": 14800,
                "totalDamageDealtToChampions": 29200,
                "visionScore": 24,
                "ch_goldPerMinute": 438.0,
                "ch_killParticipation": 0.19,
            },
        },
    ]
    for e in entries:
        pm[e["matchId"]] = e
    return db


def build_snapshot_outputs():
    """Produce the four equivalence outputs from fixture data (no network)."""
    match_doc = load_match_doc()
    db = build_fake_db()

    with tempfile.TemporaryDirectory() as tmp:
        rb = ReportBuilder(output_dir=tmp)
        player_report = rb.build_player_report(FOCUS_PUUID, db)
        match_report = rb.build_match_report(db["player_matches"][MATCH_ID], db)

    match_snapshot = render_match_snapshot(match_doc)

    coach_builder = CoachingPromptBuilder(ddragon_client=FakeDragonClient(FAKE_ITEMS))
    coach_prompt = coach_builder.build_prompt(
        match_doc,
        puuid=FOCUS_PUUID,
        role=FOCUS_ROLE,
        match_snapshot=match_snapshot,
    )

    return {
        "player_report": player_report,
        "match_report": match_report,
        "match_snapshot": match_snapshot,
        "coach_prompt": coach_prompt,
    }


def dump_snapshots(outputs, snap_dir=None):
    """Write key-sorted JSON + text snapshots to disk."""
    snap_dir = Path(snap_dir or SNAPSHOT_DIR)
    snap_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(name, data):
        (snap_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _write_json("player_report.json", outputs["player_report"])
    _write_json("match_report.json", outputs["match_report"])
    (snap_dir / "match_snapshot.txt").write_text(
        outputs["match_snapshot"] + "\n", encoding="utf-8"
    )
    (snap_dir / "coach_prompt.txt").write_text(
        outputs["coach_prompt"] + "\n", encoding="utf-8"
    )


def main():
    dump_snapshots(build_snapshot_outputs())
    print(f"Snapshots written to {SNAPSHOT_DIR}")


if __name__ == "__main__":
    main()
