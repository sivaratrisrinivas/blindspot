"""Neatlogs observability, opt-in. A no-op when NEATLOGS_API_KEY is unset, so the
fuzz loop never depends on it."""

from __future__ import annotations

import functools
import os

_ENABLED = False

try:  # pragma: no cover - import guard
    import neatlogs as _nl
except Exception:  # noqa: BLE001
    _nl = None


def init() -> bool:
    """Call once at startup. Returns True if traces will actually be shipped."""
    global _ENABLED
    if _nl is None or not os.environ.get("NEATLOGS_API_KEY"):
        return False
    _nl.init(workflow_name="blindspot", tags=["blindspot", "fuzz"])
    _ENABLED = True
    return True


def flush() -> None:
    if _ENABLED and _nl is not None:
        try:
            _nl.flush()
        except Exception:  # noqa: BLE001
            pass


# neatlogs accepts only these OpenInference span kinds.
_KINDS = {"WORKFLOW", "AGENT", "CHAIN", "TOOL", "RETRIEVER", "EMBEDDING",
          "EVALUATOR", "GUARDRAIL", "MCP_TOOL", "MEMORY"}


def span(kind: str, name: str | None = None, **kw):
    """@obs.span("CHAIN", "groq.complete") — real neatlogs span when enabled, else
    identity. A tracing failure (bad kind, exporter error) must never break the
    wrapped function, so it degrades to a plain call."""
    kind = kind if kind in _KINDS else "CHAIN"

    def deco(fn):
        state: dict = {"real": None, "tried": False}

        @functools.wraps(fn)
        def wrapper(*a, **k):
            if not (_ENABLED and _nl is not None):
                return fn(*a, **k)
            if not state["tried"]:
                state["tried"] = True
                try:
                    state["real"] = _nl.span(kind, name or fn.__name__, **kw)(fn)
                except Exception:  # noqa: BLE001 — a bad span kind must not break fn
                    state["real"] = None
            return (state["real"] or fn)(*a, **k)

        return wrapper

    return deco
