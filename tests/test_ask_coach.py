"""Tests for the reordered retrieval flow in scripts/ask_coach.py.

Only the last_match=False (aggregate report) branch changes: semantic query
always runs first, retrieve_for_category always also runs, both merged into
`passages` for PromptEngineer.build_prompt. last_match=True is unaffected.
"""
import sys
import types
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest


class FakeDB:
    def get_collection(self, name):
        raise RuntimeError("not used in these tests")


@pytest.fixture
def patched_ask_coach(monkeypatch):
    """Import ask_coach with all external side effects mocked."""
    import scripts.ask_coach as ask_coach_mod

    monkeypatch.setattr(ask_coach_mod, "get_db", lambda: FakeDB())

    class FakeOllama:
        def generate(self, prompt, model):
            return {"response": "ok"}

    monkeypatch.setattr(ask_coach_mod, "OllamaClient", FakeOllama)

    class FakePromptEngineer:
        def __init__(self):
            self.last_passages = None

        def build_prompt(self, **kwargs):
            self.last_passages = kwargs.get("passages")
            return "prompt"

    fake_pe = FakePromptEngineer()
    monkeypatch.setattr(ask_coach_mod, "PromptEngineer", lambda: fake_pe)

    monkeypatch.setattr(
        ask_coach_mod, "classify_question",
        lambda q: {"category_id": "laning", "category_label": "laning", "method": "rule", "confidence": 0.9},
    )
    monkeypatch.setattr(ask_coach_mod, "_build_aggregate_report", lambda db, role: {})

    # avoid writing response files during tests
    monkeypatch.setattr(ask_coach_mod.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(ask_coach_mod.json, "dump", lambda *a, **k: None)

    real_open = open

    def _guarded_open(path, *a, **k):
        if "ollama_responses" in str(path):
            raise OSError("no io in tests")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", _guarded_open)

    return ask_coach_mod, fake_pe


def test_last_match_false_merges_semantic_and_structured(monkeypatch, patched_ask_coach):
    ask_coach_mod, fake_pe = patched_ask_coach

    monkeypatch.setattr(ask_coach_mod, "retrieve_for_category", lambda *a, **k: ["structured: cs=5.2"])

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1, 0.2]]

    class FakeStore:
        def query(self, emb, top_k=5):
            return [{"document": "semantic: role benchmark", "metadata": {}, "distance": 0.2}]

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    ask_coach_mod.ask_coach(question="how is my laning", role="Jungle", last_match=False)

    assert fake_pe.last_passages == ["semantic: role benchmark", "structured: cs=5.2"]


def test_last_match_false_empty_store_falls_back_to_structured_only(monkeypatch, patched_ask_coach):
    ask_coach_mod, fake_pe = patched_ask_coach

    monkeypatch.setattr(ask_coach_mod, "retrieve_for_category", lambda *a, **k: ["structured: cs=5.2"])

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1, 0.2]]

    class FakeStore:
        def query(self, emb, top_k=5):
            return []

        def search_keywords(self, keywords, top_k=5, where=None):
            return []

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    ask_coach_mod.ask_coach(question="how is my laning", role="Jungle", last_match=False)

    assert fake_pe.last_passages == ["structured: cs=5.2"]


def test_last_match_false_missing_vector_store_does_not_raise(monkeypatch, patched_ask_coach):
    ask_coach_mod, fake_pe = patched_ask_coach

    monkeypatch.setattr(ask_coach_mod, "retrieve_for_category", lambda *a, **k: ["structured only"])

    def _raise_import(*a, **k):
        raise ImportError("chromadb is required for the vector store")

    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = _raise_import
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    ask_coach_mod.ask_coach(question="how is my laning", role="Jungle", last_match=False)

    assert fake_pe.last_passages == ["structured only"]


def test_last_match_true_path_unaffected(monkeypatch, patched_ask_coach):
    """last_match=True must still use CoachingPromptBuilder with no passages, untouched."""
    ask_coach_mod, fake_pe = patched_ask_coach

    # This path can hit the inline embedding fallback; keep the embedding
    # stack hermetic so the real (multilingual) model is never loaded.
    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1, 0.2]]

    class FakeStore:
        def query(self, emb, top_k=5, where=None):
            return []

        def search_keywords(self, keywords, top_k=5, where=None):
            return []

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    calls = {}

    class FakeCoachingPromptBuilder:
        def build_prompt(self, match_doc, puuid, role, match_snapshot=None, history=None):
            calls["called"] = True
            calls["kwargs"] = {"match_doc": match_doc, "puuid": puuid, "role": role,
                               "match_snapshot": match_snapshot, "history": history}
            return "schema-driven prompt"

    monkeypatch.setattr(ask_coach_mod, "CoachingPromptBuilder", FakeCoachingPromptBuilder)
    monkeypatch.setattr(
        ask_coach_mod, "_build_last_match_report",
        lambda db, role, puuid=None: {"report": {}, "full_match": {"info": {}}, "puuid": "p1"},
    )

    # retrieve_for_category / semantic retrieval should not matter for this path,
    # but ensure they're not required to be called
    monkeypatch.setattr(ask_coach_mod, "retrieve_for_category", lambda *a, **k: [])

    ask_coach_mod.ask_coach(
        question="analyze my last game", role="Mid", last_match=True,
        history=[{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola"}],
    )

    assert calls.get("called") is True
    assert fake_pe.last_passages is None
    # snapshot ("" for a doc with no participants) and history flow into the builder
    assert calls["kwargs"]["match_snapshot"] == ""
    assert calls["kwargs"]["history"] == [
        {"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola"},
    ]


def test_semantic_passages_applies_role_where_filter(monkeypatch, patched_ask_coach):
    """A role mentioned in the question narrows the vector query via where=."""
    ask_coach_mod, _ = patched_ask_coach
    calls = {}

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1]]

    class FakeStore:
        def query(self, emb, top_k=5, where=None):
            calls["where"] = where
            calls["top_k"] = top_k
            return [{"document": "doc jungle", "metadata": {"role": "Jungle"}, "distance": 0.2}]

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    out = ask_coach_mod._semantic_passages(
        "cómo viene el farm del jungler", role="Top", threshold=1.0
    )

    assert calls["where"] == {"role": {"$in": ["Jungle", "jungle", "JUNGLE"]}}
    assert calls["top_k"] == 5
    assert out == ["doc jungle"]


def test_semantic_passages_keyword_fallback_when_threshold_misses(monkeypatch, patched_ask_coach):
    """When no semantic hit beats the threshold, keyword search takes over."""
    ask_coach_mod, _ = patched_ask_coach
    calls = {}

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1]]

    class FakeStore:
        def query(self, emb, top_k=5, where=None):
            # semantic hit is too far from the question
            return [{"document": "far away", "metadata": {}, "distance": 1.8}]

        def search_keywords(self, keywords, top_k=5, where=None):
            calls["keywords"] = keywords
            calls["kw_where"] = where
            return [{"document": "keyword hit", "metadata": {}, "distance": None}]

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    out = ask_coach_mod._semantic_passages(
        "cómo viene el farm del jungler", role=None, threshold=1.0
    )

    assert out == ["keyword hit"]
    assert "cs" in calls["keywords"]  # farm -> cs synonym expansion
    # the role where filter survives into the keyword fallback
    assert calls["kw_where"] == {"role": {"$in": ["Jungle", "jungle", "JUNGLE"]}}


def test_semantic_passages_role_where_uses_canonical_names(monkeypatch, patched_ask_coach):
    """A question mentioning "support" (canonical) yields a where filter the
    normalized ingest metadata can actually match."""
    ask_coach_mod, _ = patched_ask_coach
    calls = {}

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1]]

    class FakeStore:
        def query(self, emb, top_k=5, where=None):
            calls["where"] = where
            return [{"document": "doc support", "metadata": {"role": "Support"}, "distance": 0.2}]

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)

    out = ask_coach_mod._semantic_passages(
        "necesito consejos de support", role="Top", threshold=1.0
    )

    assert calls["where"] == {"role": {"$in": ["Support", "support", "SUPPORT"]}}
    assert out == ["doc support"]
