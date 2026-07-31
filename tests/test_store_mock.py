import sys
import types
import pytest


def test_vectorstore_requires_chromadb(monkeypatch):
    # Ensure ImportError is raised when chromadb is not available
    monkeypatch.setitem(sys.modules, 'chromadb', None)
    from importlib import reload

    with pytest.raises(ImportError):
        # reload the module to trigger import
        import importlib
        import modules.embeddings.store as store_mod
        reload(store_mod)
        store_mod.VectorStore()


def _install_fake_chromadb(monkeypatch, collection):
    """Swap chromadb for a fake client and return a fresh VectorStore."""
    fake = types.ModuleType("chromadb")

    class FakeClient:
        def __init__(self, path):
            pass

        def get_or_create_collection(self, name):
            return collection

    fake.PersistentClient = FakeClient
    monkeypatch.setitem(sys.modules, "chromadb", fake)
    # ensure a fresh import picks up the fake module
    sys.modules.pop("modules.embeddings.store", None)
    from modules.embeddings.store import VectorStore

    return VectorStore(persist_directory="/tmp/fake_chroma_dir")


def test_query_passes_where_filter(monkeypatch):
    calls = {}

    class FakeCollection:
        def query(self, **kwargs):
            calls["kwargs"] = kwargs
            return {"ids": [["a"]], "documents": [["doc a"]],
                    "metadatas": [[{"role": "Jungle"}]], "distances": [[0.3]]}

    store = _install_fake_chromadb(monkeypatch, FakeCollection())
    where = {"role": {"$in": ["Jungle", "jungle", "JUNGLE"]}}
    out = store.query([0.1, 0.2], top_k=3, where=where)

    assert calls["kwargs"]["where"] == where
    assert calls["kwargs"]["n_results"] == 3
    assert out == [{"id": "a", "document": "doc a", "metadata": {"role": "Jungle"}, "distance": 0.3}]


def test_query_without_where_omits_kwarg(monkeypatch):
    calls = {}

    class FakeCollection:
        def query(self, **kwargs):
            calls["kwargs"] = kwargs
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    store = _install_fake_chromadb(monkeypatch, FakeCollection())
    store.query([0.1])
    assert "where" not in calls["kwargs"]


def test_search_keywords_ranks_by_hit_count(monkeypatch):
    docs = {
        "ids": ["a", "b", "c"],
        "documents": [
            "Reporte del jugador en rol Jungle. Farmeo (cs_per_min): 5.2. Oro (gold): 1200.",
            "Reporte del jugador en rol Top. Farmeo (cs_per_min): 7.1.",
            "Reporte del jugador en rol Support. Visión (vision_score): 40.",
        ],
        "metadatas": [{"role": "Jungle"}, {"role": "Top"}, {"role": "Support"}],
    }

    calls = {}

    class FakeCollection:
        def get(self, include=None, where=None):
            calls["include"] = include
            calls["where"] = where
            return docs

    store = _install_fake_chromadb(monkeypatch, FakeCollection())
    out = store.search_keywords(["cs", "oro"], top_k=2)

    assert len(out) == 2
    assert out[0]["id"] == "a"  # matches 2 keywords, beats b (1)
    assert out[0]["document"] == docs["documents"][0]
    assert out[0]["metadata"] == {"role": "Jungle"}
    assert out[0]["distance"] is None
    assert {h["id"] for h in out} == {"a", "b"}
    # no where filter requested -> col.get called without the where kwarg
    assert calls["include"] == ["documents", "metadatas"]
    assert calls["where"] is None


def test_search_keywords_passes_where_filter(monkeypatch):
    """search_keywords forwards the role `where` filter to col.get."""
    docs = {
        "ids": ["a", "b"],
        "documents": ["Farmeo (cs): 120", "Farmeo (cs): 80"],
        "metadatas": [{"role": "Support"}, {"role": "Top"}],
    }
    calls = {}

    class FakeCollection:
        def get(self, include=None, where=None):
            calls["include"] = include
            calls["where"] = where
            return docs

    store = _install_fake_chromadb(monkeypatch, FakeCollection())
    where = {"role": {"$in": ["Support", "support", "SUPPORT"]}}
    out = store.search_keywords(["cs"], top_k=5, where=where)

    assert calls["where"] == where
    assert calls["include"] == ["documents", "metadatas"]
    assert {h["id"] for h in out} == {"a", "b"}


def test_search_keywords_returns_empty_on_error(monkeypatch):
    class FakeCollection:
        def get(self, include=None, where=None):
            raise RuntimeError("boom")

    store = _install_fake_chromadb(monkeypatch, FakeCollection())
    assert store.search_keywords(["cs"]) == []
