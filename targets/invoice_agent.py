"""Toy invoice-reconciliation agent. Real tool calls, deliberate blind spots.
The demo star: rename a customer to Åcme and it books to the wrong GL account."""

from __future__ import annotations

from blindspot.types import AgentRun

# customer -> GL account. Keyed on exact ASCII name (the planted blind spot).
LEDGER = {
    "Acme Corp": "1100",
    "Globex": "1200",
    "Initech": "1300",
}


def book_invoice(vendor: str, amount: float, date: str) -> AgentRun:
    """Parse a free-text invoice, look up the GL account, 'book' it."""
    raise NotImplementedError


def run(text: str) -> AgentRun:
    """Entrypoint used by AgentSpec. Free-text invoice in, AgentRun out."""
    raise NotImplementedError
