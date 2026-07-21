"""LLM client. Defaults to local Ollama; can use OpenAI/Anthropic if keys set.

Provides plain chat and a `chat_json` helper that reliably coaxes small local
models into returning valid JSON (used for structured evaluation).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Optional


class LLM:
    def __init__(self, model: Optional[str] = None, backend: Optional[str] = None):
        self.backend = backend or os.getenv("INTERVIEWER_BACKEND", "ollama")
        self.model = model or os.getenv(
            "INTERVIEWER_MODEL",
            "llama3.2:latest" if self.backend == "ollama" else "gpt-4o-mini",
        )
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def chat(self, system: str, user: str, temperature: float = 0.7,
             max_tokens: int = 800, force_json: bool = False) -> str:
        if self.backend == "ollama":
            return self._ollama(system, user, temperature, max_tokens, force_json)
        if self.backend == "openai":
            return self._openai(system, user, temperature, max_tokens, force_json)
        raise ValueError(f"unknown backend {self.backend}")

    def chat_json(self, system: str, user: str, temperature: float = 0.3,
                  retries: int = 2) -> dict:
        """Return parsed JSON, retrying with a stricter nudge on failure."""
        sys_json = system + (
            "\n\nRespond with ONLY a single valid JSON object. No markdown, "
            "no code fences, no commentary before or after."
        )
        last = ""
        for attempt in range(retries + 1):
            raw = self.chat(sys_json, user, temperature=temperature,
                            max_tokens=1200, force_json=True)
            last = raw
            parsed = _extract_json(raw)
            if parsed is not None:
                return parsed
            user = (user + "\n\nYour previous reply was not valid JSON. "
                    "Return ONLY the JSON object, keep strings short.")
        # give up gracefully
        return {"_parse_error": True, "_raw": last}

    # --- backends --------------------------------------------------------
    def _ollama(self, system: str, user: str, temperature: float, max_tokens: int,
                force_json: bool = False) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if force_json:
            body["format"] = "json"  # Ollama native constrained JSON decoding
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.ollama_host}/api/chat", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        text = data.get("message", {}).get("content", "")
        return _strip_think(text).strip()

    def _openai(self, system: str, user: str, temperature: float, max_tokens: int,
                force_json: bool = False) -> str:
        from openai import OpenAI

        client = OpenAI()
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature, max_tokens=max_tokens,
        )
        if force_json:
            kwargs["response_format"] = {"type": "json_object"}
        r = client.chat.completions.create(**kwargs)
        return (r.choices[0].message.content or "").strip()


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)


def _extract_json(text: str) -> Optional[dict]:
    text = _strip_think(text).strip()
    # strip code fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    # direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # find the first balanced {...} block
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None
