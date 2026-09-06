"""The invoice agent with all six planted blind spots repaired. Used by
scripts/metrics.py for an honest before/after comparison that does not depend on
the AO fix PRs landing before the deadline.

Fixes, matched to targets/invoice_agent.py:
  1. vendor names are Unicode-folded, whitespace-collapsed and case-folded before
     the ledger lookup, so "Åcme  Corp" == "Acme Corp".
  2. a known ledger name anywhere in the text wins over a first-span guess, and
     "ship to" / "deliver to" lines are ignored, so a decoy line or a reorder
     cannot change the booked vendor.
  3. capex routing uses the properly parsed amount, not a first-digit-run guess.
  4. the amount parser also accepts the European "1.234,56" format.
  5. the date parser accepts ISO, "1 March 2026", and "01/03/2026".
  6. a closed-period invoice is an explicit refusal (terminal="refused"), never an
     unhandled exception.
"""

from __future__ import annotations

import re
import time
import unicodedata

from blindspot.types import AgentRun, ToolCall
from targets.invoice_agent import (
    CAPEX_GL,
    CAPEX_THRESHOLD,
    DEFAULT_GL,
    LEDGER,
    _MONTHS,
)

_CONFUSABLES = str.maketrans({
    "Α": "A", "Ε": "E", "Ο": "O", "Ι": "I", "Ρ": "P", "Τ": "T", "Η": "H",
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y", "і": "i",
})
_MONEY = re.compile(
    r"(?:USD|US\$|\$|EUR|€)\s*([0-9][0-9.,]*[0-9]|[0-9])"
    r"|([0-9][0-9.,]*[0-9]|[0-9])\s*(?:USD|EUR)", re.I)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b")
_NAME_HINT = re.compile(r"(?:invoice from|billed by|bill from|bill|from|vendor)\s*:?\s*([^\n,.;]+)", re.I)
_SKIP_LINE = re.compile(r"^\s*(ship to|deliver to|remit to|attn|c/o)\b", re.I)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).translate(_CONFUSABLES)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def _parse_amount(text: str) -> float:
    m = _MONEY.search(text)
    if not m:
        raise ValueError(f"no amount in {text!r}")
    raw = (m.group(1) or m.group(2)).strip()
    if "," in raw and "." in raw:                 # 1.234,56  vs  1,234.56
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") \
            else raw.replace(",", "")
    elif raw.count(",") == 1 and len(raw.split(",")[1]) == 2:
        raw = raw.replace(",", ".")               # 1234,56
    else:
        raw = raw.replace(",", "")
    return float(raw)


def _parse_date(text: str) -> tuple[int, int, int]:
    if m := _ISO.search(text):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    elif m := _TEXT_DATE.search(text):
        mo = _MONTHS.get(m[2].lower())
        if not mo:
            raise ValueError(f"unknown month {m[2]!r}")
        d, y = int(m[1]), int(m[3])
    elif m := _DMY.search(text):
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
    else:
        raise ValueError(f"no date in {text!r}")
    return y, mo, d


def _parse_vendor(text: str) -> tuple[str, str, bool]:
    """Return (display_name, gl_account, matched). A known ledger name anywhere in
    the text wins; 'ship to' style lines are ignored for the fallback guess."""
    folded = _fold(text)
    for key, gl in LEDGER.items():
        if key in folded:
            return key.title(), gl, True
    for line in text.splitlines() or [text]:
        if _SKIP_LINE.search(line):
            continue
        if m := _NAME_HINT.search(line):
            span = re.split(r"\s+(?:for|covering|amount|total|dated|on|invoice|#|inv)\b",
                            m.group(1).strip(), maxsplit=1)[0].strip().rstrip(".")
            if span:
                return span, DEFAULT_GL, False
    return "UNKNOWN", DEFAULT_GL, False


def run(text: str) -> AgentRun:
    t0 = time.perf_counter()
    calls: list[ToolCall] = []

    def done(output, terminal, err=None, escalated=False):
        return AgentRun(input=text, output=output, tool_calls=tuple(calls),
                        terminal=terminal, error_type=err, escalated=escalated,
                        latency_s=time.perf_counter() - t0)

    try:
        vendor, vendor_gl, matched = _parse_vendor(text)
        calls.append(ToolCall("parse_vendor", {"vendor": vendor}, ok=matched))

        try:
            y, mo, d = _parse_date(text)
        except ValueError:
            return done("I can't book this without a valid invoice date — please resend "
                        "with the date.", "refused")
        if (y, mo, d) < (2026, 1, 1):
            calls.append(ToolCall("check_period", {"year": y}, ok=False))
            return done(f"Invoice dated {y:04d}-{mo:02d}-{d:02d} falls in a closed "
                        f"period; routing to the prior-period accrual process.", "refused")
        calls.append(ToolCall("check_period", {"year": y, "month": mo}, ok=True))

        amount = _parse_amount(text)
        calls.append(ToolCall("parse_amount", {"amount": amount}, ok=True))

        if amount >= CAPEX_THRESHOLD:
            gl = CAPEX_GL
            calls.append(ToolCall("route_capex", {"gl_account": gl}, ok=True))
        else:
            gl = vendor_gl
            calls.append(ToolCall("lookup_gl", {"vendor": vendor}, ok=matched))
            if not matched:
                calls.append(ToolCall("escalate", {"reason": "unknown vendor"}, ok=True))

        entry = {"vendor": vendor, "amount": round(amount, 2), "gl_account": gl}
        calls.append(ToolCall("book_invoice", entry, ok=True))
        return done(f"Booked {vendor} ${entry['amount']:.2f} to GL {gl}.", "ok",
                    escalated=not matched)
    except Exception as exc:  # noqa: BLE001
        return done(None, "error", err=type(exc).__name__)
