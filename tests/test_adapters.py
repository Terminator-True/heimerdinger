"""Offline tests for the additive port adapters (Work Unit 2)."""

import json

from modules.adapters.file_output import LocalFileOutput
from modules.adapters.json_config import JsonConfigSource
from modules.adapters.report_repository import ReportRepository
from modules.ports import (
    FileOutputPort,
    RateLimiterPort,
    ReportRepositoryPort,
)


class FakeCol(dict):
    def find(self, q):
        for v in self.values():
            if all(v.get(k) == val for k, val in q.items()):
                yield v

    def update_one(self, filter_q, update_q, upsert=False):
        key = filter_q.get("player")
        if filter_q.get("matchId"):
            key = f"{filter_q.get('player')}_{filter_q.get('matchId')}"
        self[key] = update_q["$set"]


class FakeDB(dict):
    def get_collection(self, name):
        return self.setdefault(name, FakeCol())


def test_ports_are_satisfied_by_adapters():
    assert isinstance(LocalFileOutput(), FileOutputPort)
    assert isinstance(ReportRepository(FakeDB()), ReportRepositoryPort)
    # TokenBucketLimiter.acquire returns bool -> structurally satisfies the port.
    from modules.riot_api.rate_limiter import TokenBucketLimiter

    assert isinstance(TokenBucketLimiter(rate=20), RateLimiterPort)


def test_local_file_output_write_report_is_byte_identical(tmp_path):
    report = {"player": "p1", "metrics": {"kda": 3.2}, "role": "MID"}
    LocalFileOutput(output_dir=str(tmp_path)).write_report(report, "p1.json")
    expected = json.dumps(report, ensure_ascii=False, indent=2)
    assert (tmp_path / "p1.json").read_text(encoding="utf-8") == expected


def test_local_file_output_write_ollama_response_format(tmp_path):
    out = LocalFileOutput(output_dir=str(tmp_path))
    out.write_ollama_response("puuid-1", "PROMPT TEXT", {"response": "hi"}, "llama3.1")
    text = (tmp_path / "ollama_responses" / "puuid-1.txt").read_text(encoding="utf-8")
    assert text.startswith("# captured_at: ")
    assert "# model: llama3.1\n# prompt:\n" in text
    assert "PROMPT TEXT\n\n# raw_response:\n" in text
    assert '"response": "hi"' in text


def test_local_file_output_write_coach_exchange(tmp_path):
    payload = {"question": "q?", "response": {"response": "a"}}
    LocalFileOutput(output_dir=str(tmp_path)).write_coach_exchange(payload, "2026-08-21T00-00-00")
    path = tmp_path / "ollama_responses" / "ask_coach_2026-08-21T00-00-00.json"
    assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_report_repository_upsert_and_find_by_role():
    db = FakeDB()
    repo = ReportRepository(db)
    repo.upsert_report({"player": "p1", "role": "MID", "games_analyzed": 5})
    repo.upsert_report({"player": "p2", "role": "TOP", "games_analyzed": 3})
    # upsert same player again -> no duplicate
    repo.upsert_report({"player": "p1", "role": "MID", "games_analyzed": 9})

    mids = repo.find_reports_by_role("MID", limit=10)
    assert len(mids) == 1
    assert mids[0]["games_analyzed"] == 9


def test_json_config_source_delegates(tmp_path):
    src = JsonConfigSource()
    cfg = src.get_embeddings_config()
    assert cfg["collection_name"] == "heimerdinger"
    ddragon = src.get_ddragon_config()
    assert "language" in ddragon
