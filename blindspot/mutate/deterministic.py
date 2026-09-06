"""Deterministic mutation ops. Each op declares whether it preserves the answer.
The preserving ops ARE the metamorphic relations the metamorphic oracle checks."""

from __future__ import annotations

import re
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


HOMOGLYPHS = {"A": "Α", "E": "Ε", "O": "Ο", "a": "а", "e": "е", "o": "о", "c": "с", "p": "р"}
_CAP_WORD = re.compile(r"\b([A-Z][a-z]{2,})\b")
_MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_SYNONYMS = [
    (r"\bInvoice from\b", "Bill from"),
    (r"\bBill from\b", "Invoice from"),
    (r"\bBilled by\b", "Invoice from"),
    (r"\bamount\b", "total"),
    (r"\bfor\b", "covering"),
    (r"\bdated\b", "on"),
]


@_op("homoglyph_entity", preserving=True)
def homoglyph_entity(text: str, rng: Random) -> str:
    """Swap one Latin letter in a Capitalised word for a Unicode look-alike.
    Same entity to a human; a different byte string to an exact-match lookup."""
    words = _CAP_WORD.findall(text)
    if not words:
        return text
    target = rng.choice(words)
    for i, ch in enumerate(target):
        if ch in HOMOGLYPHS:
            swapped = target[:i] + HOMOGLYPHS[ch] + target[i + 1:]
            return text.replace(target, swapped, 1)
    return text


@_op("reorder_lines", preserving=True)
def reorder_lines(text: str, rng: Random) -> str:
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    shuffled = lines[:]
    rng.shuffle(shuffled)
    return "\n".join(shuffled) if shuffled != lines else text


@_op("reformat_currency", preserving=True)
def reformat_currency(text: str, rng: Random) -> str:
    """'$1,240.00' <-> 'USD 1240.00'. Identical monetary value."""
    def repl(m: re.Match) -> str:
        return "USD " + m.group(1).replace(",", "")

    return _MONEY.sub(repl, text, count=1)


@_op("reformat_date", preserving=True)
def reformat_date(text: str, rng: Random) -> str:
    """ISO '2026-03-01' -> '1 March 2026'. Same calendar day."""
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]

    def repl(m: re.Match) -> str:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return m.group(0)
        return f"{d} {months[mo - 1]} {y}"

    return _ISO_DATE.sub(repl, text, count=1)


@_op("inject_whitespace", preserving=True)
def inject_whitespace(text: str, rng: Random) -> str:
    spots = [i for i, ch in enumerate(text) if ch == " "]
    if not spots:
        return text
    i = rng.choice(spots)
    return text[:i] + "  " + text[i + 1:]


@_op("synonym_swap", preserving=True)
def synonym_swap(text: str, rng: Random) -> str:
    pat, sub = rng.choice(_SYNONYMS)
    new = re.sub(pat, sub, text, count=1)
    return new


@_op("pad_context", preserving=True)
def pad_context(text: str, rng: Random) -> str:
    pads = [
        " Please file under Q1 procurement.",
        " Thanks in advance for processing this promptly.",
        " Note: this supersedes any earlier draft.",
        " CC: accounts payable.",
    ]
    return text + rng.choice(pads)


@_op("bitflip_digit", preserving=False)
def bitflip_digit(text: str, rng: Random) -> str:
    digits = [i for i, ch in enumerate(text) if ch.isdigit()]
    if not digits:
        return text
    i = rng.choice(digits)
    new_d = str((int(text[i]) + rng.randint(1, 8)) % 10)
    return text[:i] + new_d + text[i + 1:]


@_op("truncate", preserving=False)
def truncate(text: str, rng: Random) -> str:
    words = text.split()
    if len(words) < 4:
        return text
    keep = rng.randint(2, max(2, len(words) - 2))
    return " ".join(words[:keep])


class DeterministicMutator:
    """Applies 1-3 random ops per mutant; answer_preserving is the AND of the
    applied ops' flags. Ops that no-op on a given seed are dropped from the lineage."""

    def __init__(self, max_ops: int = 3) -> None:
        self.max_ops = max_ops

    def mutate(self, seed: str, *, rng: Random) -> Iterator[Mutant]:
        names = list(OPS)
        while True:
            k = rng.randint(1, self.max_ops)
            chosen = rng.sample(names, k=min(k, len(names)))
            text = seed
            applied: list[str] = []
            preserving = True
            for name in chosen:
                fn, keep = OPS[name]
                nxt = fn(text, rng)
                if nxt == text:
                    continue
                text = nxt
                applied.append(name)
                preserving = preserving and keep
            if not applied or text == seed:
                continue
            yield Mutant(text=text, lineage=tuple(applied), answer_preserving=preserving)


# --- deterministic single-site application, used by the minimiser -----------------
# ddmin needs to re-apply "the same transform" to a shrinking input without an rng.
# Each entry applies its op at the first applicable site, or returns text unchanged.

def _det_homoglyph(text: str) -> str:
    for m in _CAP_WORD.finditer(text):
        w = m.group(1)
        for i, ch in enumerate(w):
            if ch in HOMOGLYPHS:
                sw = w[:i] + HOMOGLYPHS[ch] + w[i + 1:]
                return text[:m.start(1)] + sw + text[m.end(1):]
    return text


def _det_whitespace(text: str) -> str:
    i = text.find(" ")
    return text if i < 0 else text[:i] + "  " + text[i + 1:]


def _det_currency(text: str) -> str:
    return _MONEY.sub(lambda m: "USD " + m.group(1).replace(",", ""), text, count=1)


def _det_reorder(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(reversed(lines)) if len(lines) > 1 else text


def _det_date(text: str) -> str:
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]

    def repl(m: re.Match) -> str:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{d} {months[mo - 1]} {y}" if 1 <= mo <= 12 else m.group(0)

    return _ISO_DATE.sub(repl, text, count=1)


def _det_synonym(text: str) -> str:
    for pat, sub in _SYNONYMS:
        new = re.sub(pat, sub, text, count=1)
        if new != text:
            return new
    return text


_DETERMINISTIC_OPS = {
    "homoglyph_entity": _det_homoglyph,
    "inject_whitespace": _det_whitespace,
    "reformat_currency": _det_currency,
    "reorder_lines": _det_reorder,
    "reformat_date": _det_date,
    "synonym_swap": _det_synonym,
    "pad_context": lambda t: t + " Please file under Q1 procurement.",
}


def apply_deterministic(op_name: str, text: str) -> str:
    """Apply one answer-preserving op at its first applicable site, no rng."""
    fn = _DETERMINISTIC_OPS.get(op_name)
    return fn(text) if fn else text
