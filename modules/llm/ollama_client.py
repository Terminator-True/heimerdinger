"""Minimal Ollama REST client using httpx.

This client targets a local Ollama deployment (default http://localhost:11434)
and exposes a tiny wrapper around the generation endpoint.

The implementation is intentionally small and synchronous to keep tests
simple and deterministic.
"""
from typing import Optional, Dict, Any
import time
from json import JSONDecoder

import httpx


class OllamaError(Exception):
    """Base error for Ollama client failures."""


class OllamaClient:
    """Simple client for Ollama REST API.

    Args:
        base_url: Base URL for the Ollama service (default http://localhost:11434)
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def generate(self, prompt: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Generate text from Ollama.

        Posts to the Ollama generation endpoint and returns the parsed JSON.

        Raises OllamaError on network/HTTP errors or when response JSON is invalid.
        """
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt must be a non-empty string")

        payload = {"prompt": prompt}
        if model:
            payload["model"] = model

        try:
            # Ollama's endpoint for simple generation is /api/generate
            resp = self._client.post("/api/generate", json=payload)
        except httpx.RequestError as exc:
            raise OllamaError(f"network error when contacting Ollama: {exc}") from exc

        if resp.status_code >= 400:
            # try to include server message when available
            text = resp.text
            raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {text}")

        # Attempt to parse JSON; if the response indicates it's not done (e.g. done: False)
        # perform polling with exponential backoff until done=True or timeout.
        text = resp.text
        try:
            data = resp.json()
        except ValueError:
            # Best-effort: extract first JSON object from response text
            text_stripped = text.strip()
            start = text_stripped.find("{")
            if start == -1:
                raise OllamaError(f"invalid JSON response from Ollama; no JSON object found. Raw response: {text!r}")
            dec = JSONDecoder()
            try:
                data, _ = dec.raw_decode(text_stripped[start:])
            except Exception as exc2:
                preview = text_stripped[:500] + ("..." if len(text_stripped) > 500 else "")
                raise OllamaError(f"invalid JSON response from Ollama: {exc2}. Response preview: {preview}") from exc2

        # If the service signals the generation is not finished, poll until done or timeout
        done = bool(data.get("done")) if isinstance(data, dict) else True
        accumulated = data.get("response") if isinstance(data, dict) else None
        if not done:
            start_time = time.monotonic()
            delay = 0.5
            while True:
                if time.monotonic() - start_time > self.timeout:
                    preview = (accumulated or text)[:500]
                    raise OllamaError(f"timeout waiting for Ollama generation to complete. Preview: {preview}")
                time.sleep(delay)
                try:
                    resp = self._client.post("/api/generate", json=payload)
                except httpx.RequestError as exc:
                    raise OllamaError(f"network error when polling Ollama: {exc}") from exc

                if resp.status_code >= 400:
                    raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

                # Try to parse response JSON or recover first JSON object
                try:
                    datum = resp.json()
                except ValueError:
                    text2 = resp.text.strip()
                    s = text2.find("{")
                    if s == -1:
                        datum = None
                    else:
                        try:
                            datum, _ = JSONDecoder().raw_decode(text2[s:])
                        except Exception:
                            datum = None

                if isinstance(datum, dict):
                    part = datum.get("response")
                    if part:
                        # replace/append the accumulated text; prefer latest value
                        if accumulated:
                            accumulated = accumulated + part
                        else:
                            accumulated = part
                    if datum.get("done"):
                        data = datum
                        data["response"] = accumulated
                        break

                # backoff for next poll
                delay = min(delay * 2, 2.0)

        return data

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
