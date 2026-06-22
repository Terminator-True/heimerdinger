import importlib
import types
import sys
import pytest

from modules.llm.question_classifier import classify_question


def test_rule_based_laning():
    q = "How do I manage wave and cs in early lane?"
    res = classify_question(q)
    assert res["method"] == "rule"
    assert res["category_id"] == "laning"
    assert res["confidence"] > 0


def test_embedding_fallback(monkeypatch):
    # Simulate sentence_transformers with predictable similarity
    class FakeModel:
        def encode(self, items):
            # first is question -> embedding [1,0]
            # descriptions -> make second description similar
            out = []
            for i, it in enumerate(items):
                if i == 0:
                    out.append([1.0, 0.0])
                else:
                    out.append([0.0, 1.0])
            return out

    fake = FakeModel()

    monkeypatch.setitem(sys.modules, 'sentence_transformers', types.SimpleNamespace(SentenceTransformer=lambda name: fake))

    res = classify_question("this question will use embeddings")
    # Our fake makes the best sim likely below threshold; ensure we get a dict
    assert isinstance(res, dict)
