"""Groq client factory (openai SDK pointed at Groq's base_url) + retry + cost tally.
The only module the fuzz loop is allowed to import a model through."""

from __future__ import annotations

import os

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
FUZZ_MODEL = "openai/gpt-oss-20b"       # 0.53s round trip, does tool calls
JUDGE_MODEL = "openai/gpt-oss-120b"


class LLM:
    def __init__(self, model: str, *, api_key: str | None = None) -> None:
        raise NotImplementedError

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        """Retry on 429/5xx with backoff. Accumulates .calls and .cost_usd."""
        raise NotImplementedError
