"""Groq client factory (openai SDK pointed at Groq's base_url) + retry + cost tally.
The only module the fuzz loop is allowed to import a model through."""

from __future__ import annotations

import os
import time

from openai import OpenAI

from blindspot import obs

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
FUZZ_MODEL = "openai/gpt-oss-20b"       # ~0.53s round trip, does tool calls
JUDGE_MODEL = "openai/gpt-oss-120b"     # slower, used sparingly by the judge oracle

# Rough Groq list pricing ($/1M tokens); only used for a relative cost story, not billing.
_PRICE = {
    "openai/gpt-oss-20b": (0.10, 0.50),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "qwen/qwen3-32b": (0.29, 0.59),
}


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, model: str = FUZZ_MODEL, *, api_key: str | None = None, timeout: float = 30.0) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY not set")
        self.model = model
        self._client = OpenAI(base_url=GROQ_BASE_URL, api_key=key, timeout=timeout)
        self.calls = 0
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @obs.span("LLM", "groq.complete")
    def complete(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
        max_retries: int = 4,
    ) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        delay = 0.6
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = self._client.chat.completions.create(**kwargs)
                self._tally(resp)
                content = resp.choices[0].message.content
                return content or ""
            except Exception as exc:  # noqa: BLE001 — retry on any transient API failure
                last_exc = exc
                if attempt == max_retries - 1:
                    break
                time.sleep(delay)
                delay *= 2
        raise LLMError(f"{self.model} failed after {max_retries} attempts: {last_exc}")

    def _tally(self, resp) -> None:
        self.calls += 1
        usage = getattr(resp, "usage", None)
        if not usage:
            return
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0
        self.prompt_tokens += pt
        self.completion_tokens += ct
        pin, pout = _PRICE.get(self.model, (0.0, 0.0))
        self.cost_usd += pt / 1_000_000 * pin + ct / 1_000_000 * pout
