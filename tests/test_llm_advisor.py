"""Unit tests for the LLMAdvisor using a mocked OllamaClient."""
import pytest

from modules.llm.llm_advisor import LLMAdvisor
from modules.llm.prompt_engineer import PromptEngineer


class FakeClient:
    def __init__(self):
        self.last_prompt = None
        self.last_model = None

    def generate(self, prompt: str, model: str = None):
        self.last_prompt = prompt
        self.last_model = model
        # return a canned Ollama-like response
        return {"output": "Focus on positioning and clear communication."}


def test_llm_advisor_advise_uses_prompt_engineer_and_returns_structure():
    fake = FakeClient()
    pe = PromptEngineer()
    advisor = LLMAdvisor(client=fake, engineer=pe)

    player_report = {"name": "Bob", "notes": "missed two passes due to positioning"}

    result = advisor.advise(player_report, model="llama3.1:8b")

    assert "raw_response" in result
    assert "advice_text" in result
    # maintain backward-compatible keys used by callers
    assert "prompt_used" in result

    # ensure the fake client's generate was called with the prompt from the engineer
    assert fake.last_prompt == result["prompt_used"]
    assert fake.last_model == "llama3.1:8b"

    assert "positioning" in result["advice_text"] or "communication" in result["advice_text"]
