import sys
import types

import pytest


def _fake_chromadb_module(persistent_client_cls):
    fake = types.ModuleType("chromadb")
    fake.PersistentClient = persistent_client_cls
    return fake


def test_embedder_with_fake_sentence_transformers(monkeypatch):
    # Create a fake sentence_transformers module with SentenceTransformer class
    fake_module = types.SimpleNamespace()

    class FakeModel:
        def __init__(self, name):
            self.name = name

        def encode(self, texts, show_progress_bar=False, convert_to_numpy=True):
            # return a list of lists (or numpy-like objects)
            return [[float(len(t)), float(len(t) * 2)] for t in texts]

    fake_module.SentenceTransformer = FakeModel

    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    # import the embedder after patching
    from modules.embeddings.embedder import Embedder

    emb = Embedder(model_name="fake-model")
    vecs = emb.embed_texts(["a", "ab", "abc"])

    assert isinstance(vecs, list)
    assert len(vecs) == 3
    assert all(isinstance(v, list) for v in vecs)
    assert vecs[0][0] == 1.0


def test_embedder_empty_input(monkeypatch):
    # even if sentence-transformers present, empty input returns empty list
    fake_module = types.SimpleNamespace()

    class FakeModel:
        def __init__(self, name):
            pass

        def encode(self, texts, show_progress_bar=False, convert_to_numpy=True):
            return []

    fake_module.SentenceTransformer = FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    from modules.embeddings.embedder import Embedder

    emb = Embedder()
    assert emb.embed_texts([]) == []


def test_vector_store_persistent_client(monkeypatch):
    """VectorStore must init chromadb via PersistentClient(path=...)."""
    calls = []

    class FakeCollection:
        def upsert(self, **kwargs):
            pass

        def query(self, **kwargs):
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    class FakeClient:
        def __init__(self, path):
            calls.append(path)

        def get_or_create_collection(self, name):
            return FakeCollection()

    fake_chromadb = _fake_chromadb_module(FakeClient)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    # ensure a fresh import picks up the fake module
    sys.modules.pop("modules.embeddings.store", None)
    from modules.embeddings.store import VectorStore

    store = VectorStore(persist_directory="/tmp/some_chroma_dir")

    assert calls == ["/tmp/some_chroma_dir"]
    assert isinstance(store.client, FakeClient)


def test_ingest_roundtrip(monkeypatch, tmp_path):
    """Ingesting a fake report doc should be retrievable via a fake VectorStore."""
    from modules.embeddings.ingest import render_report_text, ingest_reports

    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[float(len(t))] for t in texts]

    class FakeCollection:
        def __init__(self):
            self.docs = {}

        def upsert(self, ids, documents, embeddings, metadatas):
            for i, doc, emb, meta in zip(ids, documents, embeddings, metadatas):
                self.docs[i] = {"document": doc, "embedding": emb, "metadata": meta}

    class FakeStore:
        def __init__(self):
            self.collection = FakeCollection()

        def upsert_docs(self, ids, texts, embeddings, metadatas=None):
            self.collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas or [{}] * len(ids))

    class FakeCol:
        def __init__(self, docs):
            self._docs = docs

        def find(self, *_args, **_kwargs):
            return list(self._docs)

    class FakeDB:
        def __init__(self, reports):
            self._reports = reports

        def get_collection(self, name):
            if name == "reports":
                return FakeCol(self._reports)
            return FakeCol([])

    report_doc = {
        "_id": "r1",
        "player": "puuid-123",
        "role": "Jungle",
        "games_analyzed": 12,
        "metrics": {"cs_per_min": 5.2, "vision_score": 22},
    }

    db = FakeDB([report_doc])
    store = FakeStore()
    embedder = FakeEmbedder()

    count = ingest_reports(db, store, embedder)

    assert count == 1
    expected_id = "report:r1"
    assert expected_id in store.collection.docs
    stored = store.collection.docs[expected_id]
    assert stored["metadata"] == {
        "puuid": "puuid-123",
        "role": "Jungle",
        "report_id": "r1",
        "games_analyzed": 12,
        "source_type": "report",
    }
    assert render_report_text(report_doc) == stored["document"]

    # idempotent re-run: same ID overwrites, no duplicate
    count2 = ingest_reports(db, store, embedder)
    assert count2 == 1
    assert len(store.collection.docs) == 1
