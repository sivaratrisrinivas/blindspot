"""Regression: a dateless invoice string must not crash the invoice agent.

Blindspot class: "agent terminated with error (DateFormatError)".
Reproducer input: '$500.00' — no vendor, no date. The agent used to let
DateFormatError escape _parse_date and land in the generic handler as
terminal="error"; it must instead refuse cleanly.
"""

from __future__ import annotations

from targets.invoice_agent import run
from targets.specs import _invoice_answer

REPRODUCER = "$500.00"


def test_reproducer_refuses_instead_of_erroring():
    r = run(REPRODUCER)
    assert r.terminal == "refused"
    assert r.error_type is None
    # nothing was booked, and the refusal explains why
    assert _invoice_answer(r) is None
    assert r.output and "date" in r.output.lower()


def test_metamorphic_currency_reformat_books_same_account():
    """A cosmetic currency reformat is answer-preserving: both inputs must
    reach the same booked GL account (here: None, since both refuse)."""
    base = _invoice_answer(run(REPRODUCER))
    variant = _invoice_answer(run("USD 500.00"))
    assert base == variant


def test_valid_invoice_still_books():
    """The fix is scoped to the missing-date path — a well-formed invoice is
    unaffected."""
    r = run("Bill from Globex for $500.00 dated 2026-01-03 for consulting.")
    assert r.terminal == "ok"
    assert _invoice_answer(r) == "1200"
