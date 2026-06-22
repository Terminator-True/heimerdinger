"""LLMAdvisor ties the OllamaClient and PromptEngineer to produce advice.

The LLMAdvisor is written to be testable by injecting a fake OllamaClient
that implements `generate(prompt: str, model: str = None) -> dict`.
"""
from typing import Dict, Any, Optional
import json
import re
import os
from datetime import datetime

from .ollama_client import OllamaClient
from .prompt_engineer import PromptEngineer
from modules.logger import get_logger

logger = get_logger()


class LLMAdvisor:
    """Produce coaching advice using an LLM backend and a prompt engineer."""

    def __init__(self, client: OllamaClient = None, engineer: PromptEngineer = None):
        self.client = client or OllamaClient()
        self.engineer = engineer or PromptEngineer()

    def advise(self, player_report: Dict[str, Any], model: str = "llama3.1:8b") -> Dict[str, Any]:
        """Generate advice for a player report.

        Returns a dict with keys:
          - raw_response: the raw dict returned by the Ollama client
          - advice_text: the main assistant text (extracted when possible)
          - summary: a short summary (first 200 chars)

        The method is intentionally forgiving about the structure of the
        raw_response so tests can mock minimal payloads.
        """
        # allow role to be passed inside player_report or default to coach
        role = player_report.get("role", "coach") if isinstance(player_report, dict) else "coach"
        meta = player_report.get("meta") if isinstance(player_report, dict) else None
        prompt = self.engineer.build_prompt(player_report, role=role, meta=meta)

        # Log and persist the prompt we send to the model to help iterative prompt tuning.
        try:
            puuid = None
            if isinstance(player_report, dict):
                puuid = player_report.get("puuid") or (player_report.get("meta") or {}).get("puuid")
            # Log a truncated prompt to the main logger for quick inspection
            logger.info("Ollama prompt for %s (first 400 chars): %s", puuid or "<unknown>", (prompt[:400] + "...") if len(prompt) > 400 else prompt)
        except Exception:
            puuid = None

        raw = self.client.generate(prompt=prompt, model=model)

        # Persist raw Ollama response and the exact prompt for debugging if we can identify the player
        try:
            if puuid:
                out_dir = os.path.join("reports", "ollama_responses")
                os.makedirs(out_dir, exist_ok=True)
                ts = datetime.utcnow().isoformat() + "Z"
                fname = os.path.join(out_dir, f"{puuid}.txt")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"# captured_at: {ts}\n# model: {model}\n# prompt:\n")
                    f.write(prompt + "\n\n# raw_response:\n")
                    try:
                        f.write(json.dumps(raw, ensure_ascii=False, indent=2))
                    except Exception:
                        f.write(str(raw))
        except Exception as e:
            # Never fail the advice flow due to logging to disk
            logger.warning("Failed to save raw Ollama response for %s: %s", puuid if puuid else '<unknown>', e)

        # extract assistant text in a few common shapes
        advice_text: Optional[str] = None
        if isinstance(raw, dict):
            # common Ollama shape might include 'output' or 'choices'
            if "output" in raw and isinstance(raw["output"], str):
                advice_text = raw["output"]
            elif "choices" in raw and isinstance(raw["choices"], list) and raw["choices"]:
                first = raw["choices"][0]
                if isinstance(first, dict) and "text" in first:
                    advice_text = first["text"]
                elif isinstance(first, str):
                    advice_text = first

        # fallback: stringify raw
        if not advice_text:
            advice_text = str(raw)

        # Try to extract JSON payload enclosed in triple backticks ``` ... ```
        parsed = None
        json_block = None
        try:
            # find the first triple-backtick block
            m = re.search(r"```(.*?)```", advice_text, re.DOTALL)
            if m:
                json_block = m.group(1).strip()
                # Some models may include language hints like ```json
                if json_block.lower().startswith("json\n"):
                    json_block = json_block.split("\n", 1)[1]
                parsed = json.loads(json_block)
            else:
                # attempt to find a JSON object anywhere in the text
                m2 = re.search(r"(\{\s*\"areas_of_improvement\"[\s\S]*\})", advice_text)
                if m2:
                    json_block = m2.group(1)
                    parsed = json.loads(json_block)
        except Exception:
            # parsing failed; leave parsed as None and continue
            parsed = None

        advice_human = None
        if parsed and isinstance(parsed, dict):
            # assemble a human-readable advice text from parsed fields
            parts = []
            aos = parsed.get("areas_of_improvement") or parsed.get("areas") or []
            ex = parsed.get("exercises") or []
            strengths = parsed.get("strengths") or []
            summ = parsed.get("summary") or ""

            if aos:
                parts.append("Areas of improvement: " + ", ".join(aos))
            if ex:
                parts.append("Exercises: " + ", ".join(ex))
            if strengths:
                parts.append("Strengths: " + ", ".join(strengths))
            if summ:
                parts.append("Summary: " + summ)

            advice_human = "\n\n".join(parts) if parts else None
        else:
            advice_human = advice_text

        summary = (advice_text or "")[:200]

        return {
            "prompt_used": prompt,
            "raw_response": raw,
            "parsed": parsed,
            "advice_text": advice_human,
            "raw_advice_text": advice_text,
        }
