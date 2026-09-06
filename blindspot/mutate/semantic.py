"""Semantic mutation via Groq: plausible but hostile inputs a random mutator can't
reach. Never answer_preserving — these are new inputs, not transformations, so they
feed crash / schema / judge, never the metamorphic oracle."""

from __future__ import annotations

from collections.abc import Iterator
from random import Random

import sys

from blindspot.llm import LLM, FUZZ_MODEL, LLMError
from blindspot.types import Mutant

SYSTEM = (
    "You generate adversarial test inputs for an AI agent. Given one example input, "
    "produce ONE realistic variant a real user might actually send that is more "
    "likely to trip the agent up: edge-case values, ambiguous phrasing, conflicting "
    "constraints, unusual-but-valid formats, missing fields, extra noise. Keep the "
    "same task and domain. Output ONLY the variant text, nothing else."
)


class SemanticMutator:
    def __init__(self, llm: LLM | None = None, *, temperature: float = 1.0) -> None:
        self._llm = llm or LLM(FUZZ_MODEL)
        self._temperature = temperature

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        while True:
            try:
                text = self._llm.complete(
                    SYSTEM, f"EXAMPLE INPUT:\n{seed}", temperature=self._temperature
                ).strip()
            except LLMError as exc:  # a dead / throttled model must not stop the loop
                print(f"[blindspot] semantic mutation disabled: {exc}", file=sys.stderr)
                return
            text = text.strip().strip('"')
            if not text or text == seed:
                continue
            yield Mutant(text=text, lineage=("semantic",), answer_preserving=False)
