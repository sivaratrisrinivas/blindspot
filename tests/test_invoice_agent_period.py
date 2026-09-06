"""Regression: a closed accounting period must be a clean refusal, never a crash.

Blindspot failure class: agent terminated with error (PeriodClosedError) on the
reproducer input '2022-03-01'.
"""

import pytest

from targets.invoice_agent import run

REPRO = "2022-03-01"


def test_closed_period_repro_does_not_crash():
    r = run(REPRO)
    assert r.terminal not in ("error", "timeout"), r.error_type
    assert r.terminal == "refused"
    assert r.error_type is None
    assert r.output and "closed period" in r.output.lower()


@pytest.mark.parametrize(
    "text",
    [
        "Invoice from Acme Corp for $1,240.00 dated 2022-03-01 for office chairs.",
        "Vendor: Globex. Amount: $500.00. Date: 2025-12-31.",
        "2022-03-01",
    ],
)
def test_closed_period_always_refuses(text):
    r = run(text)
    assert r.terminal == "refused"
    assert r.error_type is None


def test_same_invoice_books_when_period_is_open():
    closed = "Invoice from Acme Corp for $1,240.00 dated 2022-03-01 for office chairs."
    open_ = "Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for office chairs."
    assert run(closed).terminal == "refused"
    assert run(open_).terminal == "ok"
