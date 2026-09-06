"""Regression: Blindspot found that the invoice agent raised DateFormatError on
an invoice with no readable date (reproducer '$1,240.00'). The agent must never
surface an unhandled exception — it either books or refuses cleanly.
"""

from targets.invoice_agent import run
from targets.specs import _invoice_answer

REPRO = "$1,240.00"
# metamorphic sibling: currency reformat, same (missing-date) invoice
REFORMATTED = "USD 1240.00"


def test_repro_is_a_clean_refusal_not_a_crash():
    r = run(REPRO)
    assert r.terminal == "refused"
    assert r.error_type is None
    assert r.output and "date" in r.output.lower()


def test_metamorphic_pair_reaches_the_same_booking_decision():
    a, b = run(REPRO), run(REFORMATTED)
    # neither crashes
    assert a.terminal != "error" and b.terminal != "error"
    # equivalent inputs -> identical terminal and identical GL decision
    assert a.terminal == b.terminal
    assert _invoice_answer(a) == _invoice_answer(b)


def test_dated_invoice_still_books():
    r = run("Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for office chairs.")
    assert r.terminal == "ok"
    assert _invoice_answer(r) == "1100"
