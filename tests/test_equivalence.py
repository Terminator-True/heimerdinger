"""Equivalence gate: current output must match the Hito 0 snapshots exactly.

Imports the same ``build_snapshot_outputs()`` used by scripts/gen_snapshots.py,
so the gate compares live ReportBuilder / CoachingPromptBuilder output to the
snapshots with no drift. Run with ``--snapshot-update`` to regenerate the
snapshots from current output.
"""
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gen_snapshots  # noqa: E402

SNAPSHOT_DIR = gen_snapshots.SNAPSHOT_DIR

JSON_SNAPSHOTS = ["player_report.json", "match_report.json"]
TEXT_SNAPSHOTS = ["match_snapshot.txt", "coach_prompt.txt"]


@pytest.fixture(scope="module")
def outputs():
    return gen_snapshots.build_snapshot_outputs()


def _load_json(name):
    path = SNAPSHOT_DIR / name
    assert path.exists(), (
        f"Missing snapshot {path} — run `python scripts/gen_snapshots.py` first."
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(name):
    path = SNAPSHOT_DIR / name
    assert path.exists(), (
        f"Missing snapshot {path} — run `python scripts/gen_snapshots.py` first."
    )
    return path.read_text(encoding="utf-8").rstrip("\n")


def _key(name):
    return name.replace(".json", "").replace(".txt", "")


@pytest.mark.parametrize("name", JSON_SNAPSHOTS)
def test_json_snapshot_matches(outputs, snapshot_update, name):
    if snapshot_update:
        gen_snapshots.dump_snapshots(outputs)
        pytest.skip("--snapshot-update: snapshots regenerated")
    assert outputs[_key(name)] == _load_json(name)


@pytest.mark.parametrize("name", TEXT_SNAPSHOTS)
def test_text_snapshot_matches(outputs, snapshot_update, name):
    if snapshot_update:
        gen_snapshots.dump_snapshots(outputs)
        pytest.skip("--snapshot-update: snapshots regenerated")
    assert outputs[_key(name)] == _load_text(name)
