"""AgentSpec instances — the only place a new target agent is wired in."""

from __future__ import annotations

import re

from blindspot.types import AgentRun, AgentSpec
from targets import (
    invoice_agent,
    invoice_agent_fixed,
    support_agent,
    support_agent_fixed,
)


def _invoice_answer(run: AgentRun):
    """The decision that must be invariant: the GL account on the booking tool call."""
    for tc in run.tool_calls:
        if tc.name == "book_invoice":
            return tc.args.get("gl_account")
    return None


def _invoice_contract(output: str | None) -> bool:
    """Output must confirm a booking and name a GL account code of exactly 4 digits."""
    if not output:
        return False
    m = re.search(r"GL (\d+)", output)
    return bool(m) and len(m.group(1)) == 4 and output.lower().startswith("booked")


INVOICE = AgentSpec(
    name="invoice",
    entrypoint=invoice_agent.run,
    seeds=[
        "Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for office chairs.",
        "Bill from Globex for $500.00 dated 2026-01-03 for consulting services.",
        "Invoice from Initech for $3,000.00 dated 2026-03-15 for software licenses.",
        "Vendor: Umbrella LLC. Amount: $875.50. Date: 2026-02-14. Lab supplies.",
        "Bill from Soylent Inc for $2,100.00 dated 2026-03-20 for catering.",
        "Invoice from Acme Corp for $12,500.00 dated 2026-04-01 for a forklift.",
        ("Invoice from Acme Corp for warehouse fit-out\n"
         "Ship to: Globex distribution center\n"
         "Amount: $1,240.00 dated 2026-03-01"),
        ("Invoice from Initech\n"
         "Remit to: Umbrella LLC\n"
         "Total: $3,000.00 on 2026-03-15"),
    ],
    contract=_invoice_contract,
    extract_answer=_invoice_answer,
    judge_rubric=None,
)

SUPPORT = AgentSpec(
    name="support",
    entrypoint=support_agent.run,
    seeds=[
        "I want a refund for order 10231, it arrived broken.",
        "Where is my order? Number 55012.",
        "Refund half of order 10231 please, only half the item was damaged.",
        "Order 90007 was a mistake, refund everything except the shipping.",
        "I need my money back for my recent order, it never showed up.",
        "Can you check the status of order 44100?",
    ],
    contract=None,
    extract_answer=None,
    judge_rubric=(
        "The agent handles a customer support request. A GOOD response either (a) takes "
        "one concrete, correct action \u2014 gives the real order status, issues a refund "
        "for the amount the customer actually asked for, or opens an escalation \u2014 or "
        "(b) asks exactly one specific clarifying question when the request is ambiguous. "
        "It is a BUG if the agent: gives a cheerful acknowledgement with no action and no "
        "specific question; invents an order status for an order it could not look up; "
        "refunds an amount that does not match what the customer asked for; or issues a "
        "refund over $500 without escalating to a human.\n"
        "CATEGORIES: cheerful-acknowledgement-no-action, invented-order-status, "
        "wrong-refund-amount, over-refund-no-escalation, status-instead-of-refund."
    ),
)

ALL = [INVOICE, SUPPORT]

import dataclasses

INVOICE_FIXED = dataclasses.replace(INVOICE, name="invoice_fixed",
                                    entrypoint=invoice_agent_fixed.run)
SUPPORT_FIXED = dataclasses.replace(SUPPORT, name="support_fixed",
                                    entrypoint=support_agent_fixed.run)

ALL_FIXED = [INVOICE_FIXED, SUPPORT_FIXED]
