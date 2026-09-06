"""Delta debugging (ddmin). The one module built test-first."""

from __future__ import annotations

from collections.abc import Callable

from blindspot.types import MinimiseResult

_SPLIT: dict[str, Callable[[str], list[str]]] = {
    "word": str.split,
    "line": str.splitlines,
    "char": list,
}
_JOINER = {"word": " ", "line": "\n", "char": ""}


def _partition(units: list[str], n: int) -> list[list[str]]:
    n = max(1, min(n, len(units)))
    base, rem = divmod(len(units), n)
    chunks: list[list[str]] = []
    start = 0
    for i in range(n):
        size = base + (1 if i < rem else 0)
        chunks.append(units[start : start + size])
        start += size
    return chunks


def _without(chunks: list[list[str]], i: int) -> list[str]:
    return [u for j, chunk in enumerate(chunks) if j != i for u in chunk]


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
    if unit not in _SPLIT:
        raise ValueError(f"unit must be one of {sorted(_SPLIT)}, got {unit!r}")

    split = _SPLIT[unit]
    join = _JOINER[unit].join
    original_len = len(text)

    def result(minimal: str, rounds: int) -> MinimiseResult:
        minimal_len = len(minimal)
        ratio = 1 - minimal_len / original_len if original_len else 0.0
        return MinimiseResult(minimal, original_len, minimal_len, ratio, rounds)

    if not still_fails(text):
        return result(text, 0)

    units = split(text)
    n = 2
    rounds = 0

    while units and rounds < max_rounds:
        rounds += 1
        n = min(n, len(units))
        chunks = _partition(units, n)

        # Phase 1: drop one chunk at a time, keep the first drop that still fails.
        for i in range(len(chunks)):
            candidate = _without(chunks, i)
            if still_fails(join(candidate)):
                units = candidate
                n = max(n - 1, 2)
                break
        else:
            # Phase 2: complements — reduce to a single chunk; keep the smallest
            # one that still fails.
            best: list[str] | None = None
            for chunk in chunks:
                if len(chunk) < len(units) and still_fails(join(chunk)):
                    if best is None or len(chunk) < len(best):
                        best = chunk
            if best is not None:
                units = best
                n = 2
            elif n >= len(units):
                break
            else:
                n = min(2 * n, len(units))

    return result(join(units), rounds)
