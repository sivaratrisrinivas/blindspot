"""Regression test for the PeriodClosedError crash Blindspot found on '2020-03-15'.

Before the fix, any date before 2026-01-01 raised PeriodClosedError and the agent's
top-level try/except turned it into terminal='error' — an unhandled failure class
rather than a clean business decision. The fix makes a closed-period invoice an
explicit refusal instead.
"""

from __future__ import annotations

from targets.invoice_agent import run


def test_closed_period_reproducer_never_crashes():
    r = run("2020-03-15")
    assert r.terminal != "error"
    assert r.error_type is None


def test_closed_period_full_invoice_refuses_cleanly():
    r = run("Invoice from Acme Corp dated 2020-03-15 for $500.00")
    assert r.terminal == "refused"
    assert r.error_type is None
    assert r.output  # a human-readable refusal, not a silent None


def test_metamorphic_open_period_booking_is_stable_across_formatting():
    """Two surface-different but semantically identical open-period invoices for
    the same vendor and amount must book to the same GL account."""
    a = run("Invoice from Acme Corp dated 2026-03-15 for $500.00")
    b = run("Invoice from   Acme Corp  dated 2026-03-15 for $500.00")

    assert a.terminal == "ok"
    assert b.terminal == "ok"
    assert a.tool_calls[-1].args["gl_account"] == b.tool_calls[-1].args["gl_account"]
    assert a.tool_calls[-1].args["gl_account"] == "1100"
