"""Regression test for the DateFormatError crash class in targets/invoice_agent.py.

Reproducer: '$500.00' has no date at all. The agent must never let DateFormatError
(or any exception) escape as terminal='error' — it must either complete a booking
or cleanly refuse (terminal='refused').
"""

from targets.invoice_agent import run

DATELESS_INPUT = "$500.00"


def test_dateless_invoice_never_crashes():
    result = run(DATELESS_INPUT)
    assert result.terminal in ("ok", "refused"), (
        f"expected a booking or a clean refusal, got terminal={result.terminal!r} "
        f"error_type={result.error_type!r}"
    )
    assert result.error_type is None


def test_dateless_invoice_metamorphic_same_account_when_booked():
    """If a missing date is later supplied, the vendor/account must not change —
    two invoices differing only in date-presence should agree on where they book."""
    dateless = run("Acme Corp $500.00")
    dated = run("Acme Corp $500.00 2026-03-01")

    assert dateless.terminal in ("ok", "refused")
    assert dated.terminal == "ok"

    if dateless.terminal == "ok":
        dateless_gl = next(
            (c.args.get("gl_account") for c in dateless.tool_calls if c.name == "book_invoice"),
            None,
        )
        dated_gl = next(
            (c.args.get("gl_account") for c in dated.tool_calls if c.name == "book_invoice"),
            None,
        )
        assert dateless_gl == dated_gl == "1100"
