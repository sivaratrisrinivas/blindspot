"""The provider table is the boundary where an API becomes configuration.
No network: these assert the wiring, not the vendor."""

from __future__ import annotations

import pytest

from blindspot.llm import DEFAULT_PROVIDER, LLM, LLMError, PROVIDERS, has_key, provider


def test_every_provider_names_both_roles_and_a_key_env():
    for name, p in PROVIDERS.items():
        assert p.name == name
        assert p.base_url.startswith("https://")
        assert p.api_key_env.endswith("_API_KEY")
        assert p.fuzz_model and p.judge_model


def test_unknown_provider_names_the_ones_that_exist():
    with pytest.raises(LLMError, match="unknown provider"):
        provider("nope")


def test_missing_key_names_the_env_var(monkeypatch):
    p = provider("tensormux")
    monkeypatch.delenv(p.api_key_env, raising=False)
    assert has_key(p) is False
    with pytest.raises(LLMError, match=p.api_key_env):
        LLM(p, p.fuzz_model)


def test_priced_model_bills_and_unpriced_one_does_not():
    groq = provider("groq")
    billed = LLM(groq, groq.judge_model, api_key="x")
    assert billed.priced is True

    tmx = provider("tensormux")
    unbilled = LLM(tmx, tmx.judge_model, api_key="x")
    assert unbilled.priced is False, "tensormux publishes no per-token price"
    assert unbilled.cost_usd == 0.0


def test_default_provider_is_a_real_row():
    assert DEFAULT_PROVIDER in PROVIDERS
