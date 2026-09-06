"""AgentSpec instances — the only place a new target agent is wired in."""

from __future__ import annotations

import re

from blindspot.types import AgentRun, AgentSpec
from targets import invoice_agent, support_agent


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
        "where is my order?? number 55012",
        "cancel everything and give me my money back, order 90007",
    ],
    contract=None,
    extract_answer=None,
    judge_rubric=(
        "The agent must either resolve the request with a concrete action "
        "(refund issued, order status given, escalation opened) or ask one specific "
        "clarifying question. Vague non-answers and refusal loops are bugs."
    ),
)

ALL = [INVOICE, SUPPORT]
