"""Delta debugging (ddmin). The one module built test-first."""

from __future__ import annotations

from collections.abc import Callable

from blindspot.types import MinimiseResult


def minimise(
    text: str,
    still_fails: Callable[[str], bool],
    *,
    max_rounds: int = 20,
    unit: str = "word",     # "word" | "line" | "char"
) -> MinimiseResult:
    """Classic ddmin: partition into n chunks, try removing each chunk (and each
    complement); keep any removal where still_fails stays True; increase granularity
    on a stuck round; stop when no removal helps or max_rounds hit."""
    raise NotImplementedError
