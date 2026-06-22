import sys
import types

import pytest


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
