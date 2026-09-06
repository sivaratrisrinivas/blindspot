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
    """One deterministic mutant most of the time, one semantic (Groq) mutant every
    `det_ratio`-th call. The counter is shared across every per-seed stream, so the
    ratio holds over the whole run instead of resetting each time the round-robin
    scheduler revisits a seed. Semantic is optional — with no Groq this is just the
    deterministic stream."""

    def __init__(self, det: Mutator, sem: Mutator | None = None, *, det_ratio: int = 4) -> None:
        self._det = det
        self._sem = sem
        self._det_ratio = max(1, det_ratio)
        self._n = 0
        self._sem_streams: dict[int, Iterator[Mutant]] = {}
        self._sem_dead = False

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        det_stream = self._det.mutate(seed, rng=rng)
        key = id(det_stream)
        while True:
            self._n += 1
            if (self._sem is not None and not self._sem_dead
                    and self._n % (self._det_ratio + 1) == 0):
                sem_stream = self._sem_streams.get(key)
                if sem_stream is None:
                    sem_stream = self._sem.mutate(seed, rng=rng)
                    self._sem_streams[key] = sem_stream
                try:
                    yield next(sem_stream)
                    continue
                except StopIteration:
                    self._sem_dead = True
            yield next(det_stream)
