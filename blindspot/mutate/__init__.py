"""Mutator protocol + composite. Deterministic (metamorphic + structural, each op
tagged answer_preserving) and semantic (Groq, never preserving)."""

from __future__ import annotations

from collections.abc import Iterator
from random import Random
from typing import Protocol

from blindspot.mutate.deterministic import DeterministicMutator
from blindspot.mutate.semantic import SemanticMutator
from blindspot.types import Mutant

__all__ = ["Mutator", "CompositeMutator", "DeterministicMutator", "SemanticMutator"]


class Mutator(Protocol):
    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]: ...


class CompositeMutator:
    """Round-robins deterministic and semantic mutants at a fixed ratio (default 4:1).
    Semantic is optional — if None (no Groq), this is just the deterministic stream."""

    def __init__(self, det: Mutator, sem: Mutator | None = None, *, det_ratio: int = 4) -> None:
        self._det = det
        self._sem = sem
        self._det_ratio = max(1, det_ratio)

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        det_stream = self._det.mutate(seed, rng=rng)
        sem_stream = self._sem.mutate(seed, rng=rng) if self._sem else None
        while True:
            for _ in range(self._det_ratio):
                yield next(det_stream)
            if sem_stream is not None:
                try:
                    yield next(sem_stream)
                except StopIteration:
                    sem_stream = None
