"""Tests for LLM response parsing in LLMAdvisor."""
import json
import sys
import types

import pytest

from modules.llm.llm_advisor import LLMAdvisor
from modules.llm.prompt_engineer import PromptEngineer


class FakeClient:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_prompt = None
        self.last_model = None

    def generate(self, prompt: str, model: str = None):
        self.last_prompt = prompt
        self.last_model = model
        # mimic Ollama minimal shape
        return {"output": self.response_text}


@pytest.fixture
def hermetic_embeddings(monkeypatch):
    """LLMAdvisor loads the embedding model in its constructor; keep it fake
    so unit tests never download/load the real (multilingual) model."""
    class FakeEmbedder:
        def embed_texts(self, texts):
            return [[0.1, 0.2]]

    class FakeStore:
        def query(self, emb, top_k=5):
            return []

    fake_embeddings_mod = types.ModuleType("modules.embeddings.embedder")
    fake_embeddings_mod.Embedder = FakeEmbedder
    fake_store_mod = types.ModuleType("modules.embeddings.store")
    fake_store_mod.VectorStore = FakeStore
    monkeypatch.setitem(sys.modules, "modules.embeddings.embedder", fake_embeddings_mod)
    monkeypatch.setitem(sys.modules, "modules.embeddings.store", fake_store_mod)


def test_advise_parses_json_block_and_composes_advice(hermetic_embeddings):
    # noisy text surrounding a JSON block
    llm_output = (
        "Here is my analysis.\n\n" 
        "```json\n"
        "{\n"
        "  \"areas_of_improvement\": [\"positioning\", \"map awareness\"],\n"
        "  \"exercises\": [\"ward 5 times per game\", \"practice last-hitting under pressure\"],\n"
        "  \"strengths\": [\"mechanics\", \"lane trading\"],\n"
        "  \"summary\": \"Focus on vision and positioning to convert advantages.\"\n"
        "}\n````\n"
        "Good luck!"
    )

    fake = FakeClient(llm_output)
    advisor = LLMAdvisor(client=fake, engineer=PromptEngineer())

    player_report = {"name": "Eve", "notes": "often caught out"}
    result = advisor.advise(player_report)

    assert result["parsed"] is not None
    assert isinstance(result["parsed"], dict)
    assert "areas_of_improvement" in result["parsed"]
    assert "positioning" in result["parsed"]["areas_of_improvement"]
    # advice_text should be assembled from parsed
    assert "Areas of improvement" in result["advice_text"]


def test_advise_falls_back_on_malformed_json(hermetic_embeddings):
    # missing closing brace -> malformed
    llm_output = "Results: ```{ \"areas_of_improvement\": [\"patience\"]``` some trailing text"
    fake = FakeClient(llm_output)
    advisor = LLMAdvisor(client=fake, engineer=PromptEngineer())

    player_report = {"name": "Sam", "notes": "rushed engages"}
    result = advisor.advise(player_report)

    # parsed should be None due to malformed JSON
    assert result["parsed"] is None
    # advice_text should equal the raw_advice_text fallback
    assert isinstance(result["advice_text"], str)
