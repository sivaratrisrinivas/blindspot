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


def span(kind: str, name: str | None = None, **kw):
    """@obs.span("WORKFLOW", "fuzz") — real neatlogs span when enabled, else identity."""
    def deco(fn):
        real = None

        @functools.wraps(fn)
        def wrapper(*a, **k):
            nonlocal real
            if _ENABLED and _nl is not None:
                if real is None:
                    real = _nl.span(kind, name or fn.__name__, **kw)(fn)
                return real(*a, **k)
            return fn(*a, **k)

        return wrapper

    return deco
