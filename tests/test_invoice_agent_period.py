"""Regression test for the PeriodClosedError crash class in targets/invoice_agent.py.

Reproducer: '2020-03-15' used to raise PeriodClosedError, surfacing as an unhandled
error (terminal="error") instead of a clean, explicit refusal. The agent must never
crash on this input; it must either book or refuse cleanly.
"""

from targets.invoice_agent import run


def test_closed_period_bare_date_refuses_cleanly():
    r = run("2020-03-15")
    assert r.terminal in ("ok", "refused")
    assert r.terminal != "error"
    # No vendor/amount info in the bare date, so a clean refusal is the right call.
    assert r.terminal == "refused"
    assert r.error_type == "PeriodClosedError"
    assert r.output is not None


def test_closed_period_full_invoice_refuses_without_crashing():
    r = run("Invoice from Acme Corp for USD 500.00 dated 2020-03-15")
    assert r.terminal != "error"
    assert r.terminal == "refused"
    assert r.error_type == "PeriodClosedError"


def test_open_period_same_invoice_still_books_same_account():
    # Metamorphic check: shifting only the date across the period boundary should
    # not change which GL account the same vendor/amount would book to.
    closed = run("Invoice from Acme Corp for USD 500.00 dated 2020-03-15")
    open_ = run("Invoice from Acme Corp for USD 500.00 dated 2026-03-15")

    assert closed.terminal == "refused"
    assert open_.terminal == "ok"
    assert open_.output == "Booked Acme Corp $500.00 to GL 1100."

    # The vendor resolves identically regardless of the (closed) period.
    closed_vendor_call = next(c for c in closed.tool_calls if c.name == "parse_vendor")
    open_vendor_call = next(c for c in open_.tool_calls if c.name == "parse_vendor")
    assert closed_vendor_call.args["vendor"] == open_vendor_call.args["vendor"] == "Acme Corp"
