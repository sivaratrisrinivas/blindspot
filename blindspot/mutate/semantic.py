"""Semantic mutation via Groq: plausible but hostile inputs a random mutator can't
reach. Never answer_preserving — these are new inputs, not transformations."""

from __future__ import annotations

from collections.abc import Iterator
from random import Random

from blindspot.llm import LLM
from blindspot.types import Mutant

SYSTEM = (
    "You generate adversarial test inputs for an AI agent. Given one example input, "
    "produce ONE realistic variant a real user might send that is more likely to trip "
    "the agent up: edge-case values, ambiguous phrasing, conflicting constraints, "
    "unusual-but-valid formats. Output only the variant text."
)


class SemanticMutator:
    def __init__(self, llm: LLM) -> None:
        raise NotImplementedError

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        raise NotImplementedError
