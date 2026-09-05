"""Toy invoice-reconciliation agent. Real tool calls, deliberate blind spots.

The demo star: rename a customer "Acme Corp" -> "Åcme Corp" and it silently books
to the miscellaneous GL account instead of the customer's real one. Two inputs that
deserve the same answer; they get different ones.

Planted blind spots (each is a failure *class* Blindspot should rediscover):
  1. vendor lookup is exact-match on a lowercased name, no unicode folding, no
     whitespace collapse -> homoglyph / double-space rename falls through to
     DEFAULT_GL ("6000", miscellaneous).
  2. amount parser only understands the US format "$1,234.56" / "1234.56" / "USD 1234";
     the European "1.234,56" parses to a wrong number or raises.
  3. vendor is taken from the *first* line that looks like a name -> reordering the
     lines changes the vendor.
"""

from __future__ import annotations

import re
import time

from blindspot.types import AgentRun, ToolCall

# customer -> GL account. Keyed on the exact lowercased ASCII name (blind spot #1).
LEDGER: dict[str, str] = {
    "acme corp": "1100",
    "globex": "1200",
    "initech": "1300",
    "umbrella llc": "1400",
    "soylent inc": "1500",
}
DEFAULT_GL = "6000"  # "miscellaneous expense" — where unknown vendors quietly land

_AMOUNT_US = re.compile(r"(?:USD|US\$|\$)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:USD)?", re.I)
_NAME_HINT = re.compile(r"(?:from|bill(?:ed by)?|vendor|invoice from)\s*:?\s*([A-Za-z0-9 .&'À-ɏ]+)", re.I)


def _parse_amount(text: str) -> float:
    """US-format only. European '1.234,56' is a blind spot: it either mis-parses or raises."""
    m = _AMOUNT_US.search(text)
    if not m:
        raise ValueError(f"no amount found in {text!r}")
    raw = m.group(1).replace(",", "")
    return float(raw)  # "1.234,56" -> _AMOUNT_US grabs "1.23" -> 1.23 (silently wrong)


def _parse_vendor(text: str) -> str:
    """Known vendor wins if its exact lowercased name appears verbatim (blind spot #1:
    no unicode folding, no whitespace collapse). Otherwise take the first name-like
    span after a lead-in keyword (blind spot #3: first span wins)."""
    haystack = text.lower()
    for key in LEDGER:
        if key in haystack:
            # recover original casing from the source text
            i = haystack.index(key)
            return text[i:i + len(key)]
    for line in text.splitlines():
        m = _NAME_HINT.search(line)
        if m:
            return re.split(r"\s+(?:for|on|dated|amount|invoice|#)\b", m.group(1).strip(), maxsplit=1)[0].strip().rstrip(".")
    m = re.search(r"\b([A-Z][A-Za-z0-9&'.]+(?: [A-Z][A-Za-z0-9&'.]+)*)", text)
    return m.group(1).strip() if m else "UNKNOWN"


def lookup_gl(vendor: str) -> tuple[str, bool]:
    """Return (gl_account, matched). Exact lowercased match only — no folding (blind spot #1)."""
    key = vendor.strip().lower()
    if key in LEDGER:
        return LEDGER[key], True
    return DEFAULT_GL, False


def book_invoice(vendor: str, amount: float, gl_account: str) -> dict:
    """The 'booking' tool. Pure; returns the ledger entry it would write."""
    return {"vendor": vendor, "amount": round(amount, 2), "gl_account": gl_account}


def run(text: str) -> AgentRun:
    """Entrypoint used by AgentSpec. Free-text invoice in, AgentRun out."""
    t0 = time.perf_counter()
    calls: list[ToolCall] = []
    try:
        vendor = _parse_vendor(text)
        calls.append(ToolCall("parse_vendor", {"text_len": len(text)}, ok=True))

        amount = _parse_amount(text)
        calls.append(ToolCall("parse_amount", {"text_len": len(text)}, ok=True))

        gl, matched = lookup_gl(vendor)
        calls.append(ToolCall("lookup_gl", {"vendor": vendor}, ok=matched))

        entry = book_invoice(vendor, amount, gl)
        calls.append(ToolCall("book_invoice", entry, ok=True))

        out = f"Booked {entry['vendor']} ${entry['amount']:.2f} to GL {gl}."
        return AgentRun(
            input=text,
            output=out,
            tool_calls=tuple(calls),
            terminal="ok",
            escalated=not matched,
            latency_s=time.perf_counter() - t0,
        )
    except Exception as exc:  # noqa: BLE001 — the agent must not crash the fuzzer
        return AgentRun(
            input=text,
            output=None,
            tool_calls=tuple(calls),
            terminal="error",
            error_type=type(exc).__name__,
            latency_s=time.perf_counter() - t0,
        )
