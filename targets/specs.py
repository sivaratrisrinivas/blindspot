"""AgentSpec instances — the only place a new target agent is wired in."""

from __future__ import annotations

from blindspot.types import AgentRun, AgentSpec
from targets import invoice_agent, support_agent


def _invoice_answer(run: AgentRun):
    """The decision that must be invariant: the GL account on the booking tool call."""
    for tc in run.tool_calls:
        if tc.name == "book_invoice":
            return tc.args.get("gl_account")
    return None


def _invoice_contract(output: str | None) -> bool:
    """Output must name a booked GL account code of exactly 4 digits."""
    raise NotImplementedError


INVOICE = AgentSpec(
    name="invoice",
    entrypoint=invoice_agent.run,
    seeds=[
        "Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for office chairs.",
        "Bill: Globex, amount 500 USD, 01/03/2026, consulting.",
        "Initech invoice #4471 — $3,000 — March 2026 — software licenses.",
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
