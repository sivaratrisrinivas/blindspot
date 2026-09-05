"""Deterministic mutation ops. Each op declares whether it preserves the answer.
answer_preserving ops are exactly the metamorphic relations."""

from __future__ import annotations

from collections.abc import Iterator
from random import Random

from blindspot.types import Mutant

# name -> (fn(text, rng) -> str, answer_preserving)
OPS: dict[str, tuple[object, bool]] = {}


def _op(name: str, preserving: bool):
    def deco(fn):
        OPS[name] = (fn, preserving)
        return fn

    return deco


@_op("homoglyph_entity", preserving=True)
def homoglyph_entity(text: str, rng: Random) -> str:
    """Acme -> Åcme. Routing must not change under a cosmetic rename."""
    raise NotImplementedError


@_op("reorder_lines", preserving=True)
def reorder_lines(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("reformat_currency", preserving=True)
def reformat_currency(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("reformat_date", preserving=True)
def reformat_date(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("inject_whitespace", preserving=True)
def inject_whitespace(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("synonym_swap", preserving=True)
def synonym_swap(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("pad_context", preserving=True)
def pad_context(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("bitflip_digit", preserving=False)
def bitflip_digit(text: str, rng: Random) -> str:
    raise NotImplementedError


@_op("truncate", preserving=False)
def truncate(text: str, rng: Random) -> str:
    raise NotImplementedError


class DeterministicMutator:
    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        """Apply 1-3 random ops; answer_preserving = AND of the chosen ops' flags."""
        raise NotImplementedError
