"""Validation gate one (handoff §10): metamorphic precision.

Six hand-written metamorphic relations — cosmetic transforms a correct invoice agent
MUST answer identically under. Apply each to a spread of seed invoices, run the agent
on original vs transformed, flag every case where the booked GL account changed.

PASS  : >= 6 of the flagged violations are genuine (transform truly answer-preserving,
        answer genuinely changed).
FAIL  : <= 2 genuine -> take fallback 2 (drop metamorphic, reframe as robustness fuzzing).

Run:  python scripts/gate1_metamorphic.py
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

sys.path.insert(0, ".")

from targets.invoice_agent import run as invoice_run  # noqa: E402
from targets.specs import _invoice_answer  # noqa: E402

# --- seed invoices, deliberately varied in phrasing and known vendors -------------
SEEDS = [
    "Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for office chairs.",
    "Bill from Globex for $500.00 on 2026-01-03 for consulting services.",
    "Invoice from Initech for $3,000.00 — March 2026 — software licenses.",
    "Vendor: Umbrella LLC. Amount: $875.50. Date: 2026-02-14. Lab supplies.",
    "Bill from Soylent Inc for $2,100.00 dated 2026-03-20 for catering.",
    "Invoice from Acme Corp for $99.99 on 2026-04-01 for staplers.",
    "Billed by Globex for $12,000.00, 2026-05-05, annual retainer.",
    "Vendor: Initech. Amount: $450.00. Date 2026-06-30. Support renewal.",
]

# --- six metamorphic relations: each MUST NOT change the booked GL account --------

HOMOGLYPH = {"A": "Α", "e": "е", "o": "ο", "c": "с"}  # Greek/Cyrillic look-alikes


def r1_homoglyph_vendor(text: str) -> str:
    """Swap one Latin letter in the vendor name for a look-alike. Cosmetic; same company."""
    def swap(m: re.Match) -> str:
        name = m.group(1)
        for latin, glyph in HOMOGLYPH.items():
            if latin in name:
                return m.group(0).replace(name, name.replace(latin, glyph, 1), 1)
        return m.group(0)

    return re.sub(r"(?:from|Vendor:|by)\s+([A-Z][A-Za-z ]+?)(?=\s+for|\.|,)", swap, text, count=1)


def r2_double_space_vendor(text: str) -> str:
    """Insert a second space inside the vendor name. Whitespace is not semantics."""
    return re.sub(r"([A-Z][a-z]+) ([A-Z][a-z]+)", r"\1  \2", text, count=1)


def r3_currency_reformat(text: str) -> str:
    """'$1,240.00' -> 'USD 1240.00'. Same monetary value."""
    return re.sub(r"\$([0-9,]+\.[0-9]{2})", lambda m: "USD " + m.group(1).replace(",", ""), text, count=1)


def r4_uppercase_vendor(text: str) -> str:
    """Shout the vendor name. Case is not identity."""
    return re.sub(r"([A-Z][a-z]+(?: [A-Z][a-z]+)*)( for| —|\.| on|,)", lambda m: m.group(1).upper() + m.group(2), text, count=1)


def r5_synonym_lead(text: str) -> str:
    """'Invoice from' <-> 'Bill from' — same speech act."""
    if text.startswith("Invoice from"):
        return "Bill from" + text[len("Invoice from"):]
    if text.startswith("Bill from"):
        return "Invoice from" + text[len("Bill from"):]
    if text.startswith("Billed by"):
        return "Invoice from" + text[len("Billed by"):]
    return "Please process: " + text


def r6_trailing_context(text: str) -> str:
    """Append a neutral sentence. Extra context must not move the booking."""
    return text + " Please file under Q1 procurement."


RELATIONS = [
    ("homoglyph_vendor", r1_homoglyph_vendor),
    ("double_space_vendor", r2_double_space_vendor),
    ("currency_reformat", r3_currency_reformat),
    ("uppercase_vendor", r4_uppercase_vendor),
    ("synonym_lead", r5_synonym_lead),
    ("trailing_context", r6_trailing_context),
]


@dataclass
class Flag:
    relation: str
    seed: str
    transformed: str
    answer_before: object
    answer_after: object


def main() -> int:
    flags: list[Flag] = []
    total_trials = 0
    for seed in SEEDS:
        base = _invoice_answer(invoice_run(seed))
        for name, fn in RELATIONS:
            t = fn(seed)
            if t == seed:
                continue  # relation didn't apply to this seed
            total_trials += 1
            after = _invoice_answer(invoice_run(t))
            if after != base:
                flags.append(Flag(name, seed, t, base, after))

    print(f"trials: {total_trials}   flagged violations: {len(flags)}\n")
    for i, f in enumerate(flags, 1):
        print(f"[{i:2}] {f.relation}")
        print(f"     seed : {f.seed}")
        print(f"     xform: {f.transformed}")
        print(f"     GL   : {f.answer_before}  ->  {f.answer_after}")
        print()

    print("=" * 70)
    print(f"Eyeball the {len(flags)} flags above. Count how many are GENUINE")
    print("(transform truly answer-preserving AND the GL account genuinely changed).")
    print("PASS >= 6 genuine   |   FAIL <= 2 genuine -> fallback 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
