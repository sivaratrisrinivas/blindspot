"""Regression: a datestamp-free invoice must never crash the agent.

Blindspot's reproducer '$500.00' has no date at all, so ISO-only date parsing
raises DateFormatError, which the top-level handler turns into terminal="error".
The agent must instead either complete a booking or issue a clean, explicit
refusal (terminal="refused") -- never terminate with an unhandled error.
"""

from __future__ import annotations

from targets.invoice_agent import run

REPRODUCER = "$500.00"


def test_dateless_invoice_never_errors():
    result = run(REPRODUCER)
    assert result.terminal in ("ok", "refused")
    assert result.terminal != "error"
    assert result.error_type is None


def test_dateless_invoice_refuses_explicitly():
    result = run(REPRODUCER)
    assert result.terminal == "refused"
    assert result.output


def test_metamorphic_date_position_books_same_account():
    """Same vendor/amount, date clause moved -- must still book the same GL account."""
    a = run("Invoice from Acme Corp dated 2026-03-01 for $500.00.")
    b = run("Bill from Acme Corp for $500.00 dated 2026-03-01.")
    assert a.terminal == "ok" and b.terminal == "ok"
    assert a.output is not None and b.output is not None
    assert "GL 1100" in a.output and "GL 1100" in b.output
