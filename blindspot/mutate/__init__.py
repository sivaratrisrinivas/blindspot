"""Mutator protocol + composite. Two implementations: deterministic (metamorphic +
structural, each op tagged answer_preserving) and semantic (Groq, never preserving)."""

from __future__ import annotations

from collections.abc import Iterator
from random import Random
from typing import Protocol

from blindspot.types import Mutant


class Mutator(Protocol):
    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]: ...


class CompositeMutator:
    """Alternates deterministic and semantic mutants by a fixed ratio (default 4:1)."""

    def __init__(self, det: Mutator, sem: Mutator | None, *, det_ratio: int = 4) -> None:
        raise NotImplementedError

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        raise NotImplementedError
