"""LLM helpers package for heimerdinger.

Expose small helpers for the Ollama integration.
"""

from .ollama_client import OllamaClient
from .prompt_engineer import PromptEngineer
from .llm_advisor import LLMAdvisor

__all__ = ["OllamaClient", "PromptEngineer", "LLMAdvisor"]
