"""Behaviour-space corpus. add() is the coverage gate; next_seed() is round-robin
(handoff: no clever scheduler)."""

from __future__ import annotations


class Corpus:
    def __init__(self, seeds: list[str]) -> None:
        raise NotImplementedError

    def add(self, text: str, sig: str) -> bool:
        """Return True iff sig was previously unseen (input then kept for mutation)."""
        raise NotImplementedError

    def next_seed(self) -> str:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
