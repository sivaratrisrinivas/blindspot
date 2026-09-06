"""Behaviour-space corpus. add() is the coverage gate; next_seed() is round-robin
(handoff: no clever scheduler)."""

from __future__ import annotations

from collections import deque


class Corpus:
    def __init__(self, seeds: list[str]) -> None:
        if not seeds:
            raise ValueError("corpus needs at least one seed")
        self._entries: list[str] = list(dict.fromkeys(seeds))  # dedupe, keep order
        self._signatures: set[str] = set()
        self._queue: deque[str] = deque(self._entries)

    def add(self, text: str, sig: str) -> bool:
        """Return True iff sig was previously unseen; if so, keep text for mutation."""
        if sig in self._signatures:
            return False
        self._signatures.add(sig)
        if text not in self._entries:
            self._entries.append(text)
            self._queue.append(text)
        return True

    def next_seed(self) -> str:
        seed = self._queue.popleft()
        self._queue.append(seed)
        return seed

    def seen(self, sig: str) -> bool:
        return sig in self._signatures

    @property
    def signatures(self) -> set[str]:
        return set(self._signatures)

    def entries(self) -> list[str]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
