"""Toy invoice-reconciliation agent. Real tool calls, deliberate blind spots.

The demo star: rename a customer "Acme Corp" -> "Åcme Corp" and it silently books
to the miscellaneous GL account instead of the customer's real one. Two inputs that
deserve the same answer; they get different ones.

Planted blind spots, each a failure *class* Blindspot should rediscover on its own:
  1. vendor lookup is exact lowercased-ASCII match — no unicode folding, no
     whitespace collapse -> homoglyph or double-space rename falls through to
     DEFAULT_GL ("6000", miscellaneous).           [metamorphic: homoglyph_entity]
  2. vendor is the first name-like span in the text -> a "Ship to:" decoy line and
     a line reorder change the booked vendor.       [metamorphic: reorder_lines]
  3. capital-expenditure routing (>= $10,000 -> "1900") uses a sloppy "first digit
     run" parse, so "$10,000.00" reads as 10 and misses the threshold, while the
     comma-free "USD 10000.00" hits it.             [metamorphic: reformat_currency]
  4. amount parser is US-format only; European "1.234,56" and mangled amounts raise.
                                                     [crash: AmountParseError]
  5. date parser is ISO-only; "1 March 2026" raises. [crash: DateFormatError]
  6. anything dated before 2026-01-01 is a hard reject. [crash: PeriodClosedError]
"""

from __future__ import annotations

import re
import time

from blindspot.types import AgentRun, ToolCall


class AmountParseError(ValueError):
    pass


class DateFormatError(ValueError):
    pass


class PeriodClosedError(RuntimeError):
    pass


# customer -> GL account. Keyed on the exact lowercased ASCII name (blind spot #1).
LEDGER: dict[str, str] = {
    "acme corp": "1100",
    "globex": "1200",
    "initech": "1300",
    "umbrella llc": "1400",
    "soylent inc": "1500",
}
DEFAULT_GL = "6000"    # "miscellaneous expense" — where unknown vendors quietly land
CAPEX_GL = "1900"      # capital expenditure
CAPEX_THRESHOLD = 10_000

_MONEY = re.compile(r"(?:USD|US\$|\$)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)|([0-9][0-9,]*\.[0-9]{2})\s*USD", re.I)
_FIRST_DIGITS = re.compile(r"([0-9]+)")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NAME_HINT = re.compile(r"(?:invoice from|billed by|bill from|bill|from|vendor)\s*:?\s*([^\n,.;]+)", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def _parse_amount(text: str) -> float:
    """US-format only. European '1.234,56' or a bit-flipped amount raises (blind spot #4)."""
    m = _MONEY.search(text)
    if not m:
        raise AmountParseError(f"no US-format amount in {text!r}")
    raw = (m.group(1) or m.group(2)).replace(",", "")
    try:
        return float(raw)
    except ValueError as exc:
        raise AmountParseError(str(exc)) from exc


def _rough_amount(text: str) -> int:
    """Sloppy 'first digit run' used ONLY for capex routing (blind spot #3)."""
    m = _FIRST_DIGITS.search(text.split(".")[0] if "." in text else text)
    return int(m.group(1)) if m else 0


def _parse_date(text: str) -> tuple[int, int, int]:
    """ISO-only (blind spot #5). Then reject closed periods (blind spot #6)."""
    m = _ISO_DATE.search(text)
    if not m:
        raise DateFormatError(f"no ISO (YYYY-MM-DD) date in {text!r}")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if (y, mo, d) < (2026, 1, 1):
        raise PeriodClosedError(f"{y:04d}-{mo:02d}-{d:02d} is in a closed period")
    return y, mo, d


def _parse_vendor(text: str) -> str:
    """Scanned line by line, FIRST hit wins (blind spot #2: a 'Ship to:' decoy or a
    line reorder changes the answer). Within a line, an exact lowercased-ASCII ledger
    name is matched with no unicode folding or whitespace collapse (blind spot #1)."""
    lines = text.splitlines() or [text]
    for line in lines:
        low = line.lower()
        for key in LEDGER:
            if key in low:
                i = low.index(key)
                return line[i:i + len(key)]
        m = _NAME_HINT.search(line)
        if m:
            span = re.split(r"\s+(?:for|covering|amount|total|dated|on|invoice|#|inv)\b",
                            m.group(1).strip(), maxsplit=1)[0]
            cand = span.strip().rstrip(".").strip()
            if cand:
                return cand
    m = re.search(r"\b([A-Z][A-Za-z0-9&'.]+(?: [A-Z][A-Za-z0-9&'.]+)*)", text)
    return m.group(1).strip() if m else "UNKNOWN"


def lookup_gl(vendor: str) -> tuple[str, bool]:
    key = vendor.strip().lower()
    if key in LEDGER:
        return LEDGER[key], True
    return DEFAULT_GL, False


def run(text: str) -> AgentRun:
    """Entrypoint used by AgentSpec. Free-text invoice in, AgentRun out."""
    t0 = time.perf_counter()
    calls: list[ToolCall] = []

    def done(output, terminal, err=None, escalated=False):
        return AgentRun(input=text, output=output, tool_calls=tuple(calls),
                        terminal=terminal, error_type=err, escalated=escalated,
                        latency_s=time.perf_counter() - t0)

    try:
        vendor = _parse_vendor(text)
        calls.append(ToolCall("parse_vendor", {"vendor": vendor}, ok=vendor != "UNKNOWN"))

        try:
            y, mo, d = _parse_date(text)
        except DateFormatError:
            calls.append(ToolCall("check_period", {}, ok=False))
            return done("I can't book this without a valid invoice date — please "
                        "resend with the date.", "refused")
        calls.append(ToolCall("check_period", {"year": y, "month": mo}, ok=True))

        amount = _parse_amount(text)
        calls.append(ToolCall("parse_amount", {"amount": amount}, ok=True))

        if _rough_amount(text) >= CAPEX_THRESHOLD:
            gl, matched = CAPEX_GL, True
            calls.append(ToolCall("route_capex", {"gl_account": gl}, ok=True))
        else:
            gl, matched = lookup_gl(vendor)
            calls.append(ToolCall("lookup_gl", {"vendor": vendor}, ok=matched))
            if not matched:
                calls.append(ToolCall("escalate", {"reason": "unknown vendor"}, ok=True))

        entry = {"vendor": vendor, "amount": round(amount, 2), "gl_account": gl}
        calls.append(ToolCall("book_invoice", entry, ok=True))
        out = f"Booked {vendor} ${entry['amount']:.2f} to GL {gl}."
        return done(out, "ok", escalated=not matched)
    except Exception as exc:  # noqa: BLE001 — the agent must never crash the fuzzer
        return done(None, "error", err=type(exc).__name__)
