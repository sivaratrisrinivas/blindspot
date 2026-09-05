"""Toy customer-support agent. Tools: lookup_order, issue_refund, escalate.
Blind spots: refund amount parsing, escalation thresholds, polite-refusal loops."""

from __future__ import annotations

from blindspot.types import AgentRun


def run(text: str) -> AgentRun:
    raise NotImplementedError
