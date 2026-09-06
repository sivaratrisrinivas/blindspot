"""The support agent with its four planted blind spots repaired. Used by
scripts/metrics.py for an honest before/after.

Fixes, matched to targets/support_agent.py:
  1. no order number, or an ambiguous reference, gets exactly one specific
     clarifying question — never a cheerful no-op.
  2. refund amount handles "half", "all/everything", "everything except shipping",
     and an explicit "$X"; anything it can't resolve becomes a clarifying question.
  3. any refund over $500 opens a human escalation instead of auto-approving.
  4. an order id that isn't found is reported as not found, not invented.
"""

from __future__ import annotations

import re
import time

from blindspot.types import AgentRun, ToolCall
from targets.support_agent import ESCALATION_LIMIT, ORDERS, _REFUND_WORDS

_ORDER_RE = re.compile(r"\b(\d{4,6})\b")
_MONEY_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
_SHIPPING = 12.00  # flat, for "everything except shipping"


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
            return done("Which order is this about? Please share the order number so "
                        "I can look it up.", "refused")

        oid = m.group(1)
        order = ORDERS.get(oid)
        calls.append(ToolCall("lookup_order", {"order": oid}, ok=order is not None))
        if order is None:
            return done(f"I couldn't find an order with number {oid}. Can you "
                        f"double-check it, or share the email the order was placed with?",
                        "refused")

        if not any(w in low for w in _REFUND_WORDS):
            return done(f"Order {oid} is currently '{order['status']}'.")

        total = order["total"]
        if money := _MONEY_RE.search(text):
            amount = min(float(money.group(1)), total)
        elif "except shipping" in low or "minus shipping" in low:
            amount = max(total - _SHIPPING, 0.0)
        elif re.search(r"\bhalf\b", low):
            amount = round(total / 2, 2)
        elif re.search(r"\b(all|everything|full|entire|whole)\b", low):
            amount = total
        else:
            return done(f"Order {oid} totals ${total:.2f}. How much would you like "
                        f"refunded — the full amount, or a specific figure?", "refused")

        if amount > ESCALATION_LIMIT:
            calls.append(ToolCall("escalate",
                                  {"order": oid, "amount": amount, "reason": "over limit"},
                                  ok=True))
            return done(f"A refund of ${amount:.2f} on order {oid} is above the "
                        f"${ESCALATION_LIMIT:.0f} auto-approval limit, so I've opened a "
                        f"case for a human agent to approve it.", escalated=True)

        calls.append(ToolCall("issue_refund", {"order": oid, "amount": amount}, ok=True))
        return done(f"Done — I've refunded ${amount:.2f} to order {oid}.")
    except Exception as exc:  # noqa: BLE001
        return done(None, terminal="error", err=type(exc).__name__)
