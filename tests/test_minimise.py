"""ddmin minimiser: pure delta debugging, never yields a string the predicate rejects."""

from __future__ import annotations

from blindspot.minimise import minimise
from blindspot.types import MinimiseResult


def test_reduces_sentence_to_single_word():
    r = minimise("the quick brown fox jumps", lambda s: "fox" in s)
    assert r.minimal == "fox"
    assert isinstance(r, MinimiseResult)
    assert r.original_len == len("the quick brown fox jumps")
    assert r.minimal_len == 3
    assert r.rounds >= 1


def test_large_string_keeps_exactly_the_two_needed_words_in_order():
    filler = (
        "lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
        "eiusmod tempor incididunt ut labore et dolore magna aliqua"
    ).split()
    words = filler[:8] + ["alpha"] + filler[8:] + ["omega"] + filler * 3
    text = " ".join(words)
    assert len(text) > 400

    def still_fails(s: str) -> bool:
        return "alpha" in s and "omega" in s and s.index("alpha") < s.index("omega")

    r = minimise(text, still_fails)
    assert still_fails(r.minimal)
    assert r.minimal == "alpha omega"
    assert r.reduction_ratio > 0.8


def test_predicate_always_true_reduces_to_empty():
    r = minimise("one two three four five six", lambda s: True)
    assert r.minimal == ""
    assert r.minimal_len == 0
    assert r.reduction_ratio == 1.0


def test_predicate_false_at_entry_returns_unchanged():
    text = "nothing wrong here"
    r = minimise(text, lambda s: "absent" in s)
    assert r.minimal == text
    assert r.original_len == len(text)
    assert r.minimal_len == len(text)
    assert r.reduction_ratio == 0.0
    assert r.rounds == 0


def test_idempotence():
    pred = lambda s: "fox" in s  # noqa: E731
    once = minimise("the quick brown fox jumps over", pred)
    twice = minimise(once.minimal, pred)
    assert twice.minimal == once.minimal
    assert twice.reduction_ratio == 0.0


def test_char_unit():
    r = minimise("abcXdef", lambda s: "X" in s, unit="char")
    assert r.minimal == "X"
    assert r.minimal_len == 1


def test_line_unit():
    text = "keep\ndrop this\nND\nalso drop"
    r = minimise(text, lambda s: "ND" in s, unit="line")
    assert r.minimal == "ND"


def test_never_returns_a_rejected_string_random_ish():
    text = "a b c d e f g h i j k l m n o p"

    def still_fails(s: str) -> bool:
        toks = s.split()
        return "d" in toks and "k" in toks

    r = minimise(text, still_fails)
    assert still_fails(r.minimal)
    assert r.minimal == "d k"
