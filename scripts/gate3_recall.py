"""Validation gate three (handoff §10): recall on planted bugs.

The invoice agent has six deliberately planted blind spots, each mapped to the
failure-class signature Blindspot should rediscover. Run the fuzzer over several
RNG seeds and measure how many of the six it catches each time.

Run:  python scripts/gate3_recall.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, ".")
os.environ["BLINDSPOT_NO_SEMANTIC"] = "1"

from blindspot.oracles import default_oracles  # noqa: E402
from blindspot.runner import run_fuzz  # noqa: E402
from blindspot.types import FuzzConfig  # noqa: E402
from targets.specs import INVOICE  # noqa: E402

# planted blind spot -> the signature Blindspot should produce
PLANTED = {
    "vendor lookup: no unicode folding": "metamorphic:homoglyph_entity",
    "vendor lookup: no whitespace collapse": "metamorphic:inject_whitespace",
    "vendor: first-span-wins / decoy line": "metamorphic:reorder_lines",
    "capex threshold: sloppy first-digit parse": "metamorphic:reformat_currency",
    "date parser: ISO only": "crash:DateFormatError",
    "closed-period hard reject": "crash:PeriodClosedError",
}
SEEDS = [0, 1, 2, 3, 4, 5, 6, 7]
DET = [o for o in default_oracles() if o.name != "judge"]


def main() -> int:
    caught_counts = []
    never_caught = set(PLANTED)
    for sd in SEEDS:
        r = run_fuzz(INVOICE, FuzzConfig(iterations=600, seed=sd), oracles=DET)
        sigs = {f.signature for f in r.findings}
        caught = {name for name, sig in PLANTED.items() if sig in sigs}
        never_caught -= caught
        caught_counts.append(len(caught))
        print(f"  seed {sd}: {len(caught)}/6  " + ("" if len(caught) == 6 else
              "MISSED " + ", ".join(sorted(set(PLANTED) - caught))))

    lo, hi = min(caught_counts), max(caught_counts)
    mean = sum(caught_counts) / len(caught_counts)
    print("\n" + "=" * 60)
    print(f"  recall over {len(SEEDS)} seeds: min {lo}/6, max {hi}/6, mean {mean:.2f}/6")
    if never_caught:
        print(f"  NEVER caught by any seed: {', '.join(sorted(never_caught))}")
    else:
        print("  every planted blind spot caught by every seed")
    return 0 if not never_caught else 1


if __name__ == "__main__":
    raise SystemExit(main())
