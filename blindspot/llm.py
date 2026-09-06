"""The one place a model is reached. Providers are OpenAI-compatible, so a provider
is a row in a table, not a branch: base URL, key env var, the two models the pipeline
uses, and published prices."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from openai import OpenAI

from blindspot import obs


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: str
    fuzz_model: str                              # semantic mutation: cheap and fast
    judge_model: str                             # judge oracle: stronger, used sparingly
    price: dict[str, tuple[float, float]] | None  # $/1M (in, out); None = unpublished


PROVIDERS: dict[str, Provider] = {
    # Rough list pricing, for a relative cost story rather than billing.
    "groq": Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        fuzz_model="openai/gpt-oss-20b",     # ~0.53s round trip, does tool calls
        judge_model="openai/gpt-oss-120b",
        price={"openai/gpt-oss-20b": (0.10, 0.50), "openai/gpt-oss-120b": (0.15, 0.75)},
    ),
    # TensorMux serves one model on this key and publishes no per-token price, so
    # runs through it report call counts and no dollar figure.
    "tensormux": Provider(
        name="tensormux",
        base_url="https://api.tensormux.com/v1",
        api_key_env="TENSORMUX_API_KEY",
        fuzz_model="glm-4-7-flash",          # ~1.9s round trip, honours json_object
        judge_model="glm-4-7-flash",
        price=None,
    ),
}

DEFAULT_PROVIDER = "groq"


class LLMError(RuntimeError):
    pass


def provider(name: str) -> Provider:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise LLMError(f"unknown provider {name!r}; have {sorted(PROVIDERS)}") from None


def has_key(p: Provider) -> bool:
    return bool(os.environ.get(p.api_key_env))


class LLM:
    def __init__(self, p: Provider, model: str, *, api_key: str | None = None,
                 timeout: float = 30.0) -> None:
        key = api_key or os.environ.get(p.api_key_env)
        if not key:
            raise LLMError(f"{p.api_key_env} not set")
        self.provider = p
        self.model = model
        self.priced = p.price is not None and model in p.price
        self._client = OpenAI(base_url=p.base_url, api_key=key, timeout=timeout)
        self.calls = 0
        self.cost_usd = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @obs.span("CHAIN", "llm.complete")
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
        if self.priced:
            pin, pout = self.provider.price[self.model]
            self.cost_usd += pt / 1_000_000 * pin + ct / 1_000_000 * pout
