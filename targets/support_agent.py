"""Toy customer-support agent. Tools: lookup_order, issue_refund, escalate.

Second domain, so Blindspot's "multiple distinct domains" claim is visible. This
agent produces open-ended prose, so the deterministic oracles mostly can't judge it
— the LLM-judge oracle carries the load here.

Planted blind spots:
  1. a request with no order number, or an ambiguous one ("my recent order"), gets a
     cheerful acknowledgement and NO action — the refusal-loop / vague-non-answer bug
     the judge rubric calls out.
  2. refund amount is parsed with a naive "first number" grab, so "refund half of the
     $80 order" refunds $80, and "refund everything except shipping" refunds the whole
     total.
  3. refunds are auto-approved at any size; anything over $500 should escalate to a
     human and doesn't.
  4. an unknown order id yields a confidently invented "on its way" status instead of
     "I couldn't find that order".
"""

from __future__ import annotations

import re
import time

from blindspot.types import AgentRun, ToolCall

ORDERS: dict[str, dict] = {
    "10231": {"status": "delivered", "total": 80.00},
    "55012": {"status": "in transit", "total": 240.00},
    "90007": {"status": "delivered", "total": 1250.00},
    "44100": {"status": "processing", "total": 19.99},
}
ESCALATION_LIMIT = 500.0
_ORDER_RE = re.compile(r"\b(\d{4,6})\b")
_AMOUNT_RE = re.compile(r"\$?\s*(\d+(?:\.\d{1,2})?)")
_REFUND_WORDS = ("refund", "money back", "reimburse", "charge back", "chargeback")


def lookup_order(oid: str) -> dict | None:
    return ORDERS.get(oid)


def issue_refund(oid: str, amount: float) -> dict:
    return {"order": oid, "refunded": round(amount, 2)}


def run(text: str) -> AgentRun:
    t0 = time.perf_counter()
    calls: list[ToolCall] = []
    low = text.lower()

    def done(output, terminal="ok", escalated=False, err=None):
        return AgentRun(input=text, output=output, tool_calls=tuple(calls),
                        terminal=terminal, error_type=err, escalated=escalated,
                        latency_s=time.perf_counter() - t0)

    try:
        m = _ORDER_RE.search(text)
        if not m:
            # blind spot #1: acknowledge, do nothing, ask nothing specific
            return done("Thanks for reaching out! I've noted your request and our "
                        "team will take a look. Is there anything else I can help with?")

        oid = m.group(1)
        order = lookup_order(oid)
        calls.append(ToolCall("lookup_order", {"order": oid}, ok=order is not None))

        if order is None:
            # blind spot #4: invent a status
            return done(f"Good news — order {oid} is on its way and should arrive soon!")

        wants_refund = any(w in low for w in _REFUND_WORDS)
        if not wants_refund:
            return done(f"Order {oid} is currently '{order['status']}'.")

        amt_m = _AMOUNT_RE.search(text)
        amount = float(amt_m.group(1)) if amt_m else order["total"]  # blind spot #2
        amount = min(amount, order["total"])

        calls.append(ToolCall("issue_refund", {"order": oid, "amount": amount}, ok=True))
        issue_refund(oid, amount)  # blind spot #3: no escalation check
        return done(f"Done — I've refunded ${amount:.2f} to order {oid}.")
    except Exception as exc:  # noqa: BLE001
        return done(None, terminal="error", err=type(exc).__name__)
