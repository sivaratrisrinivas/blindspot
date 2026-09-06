"""Validation gate two (handoff §10): does coverage guidance earn its place?

Run the guided search (novel behaviour signatures re-enter the corpus and get
mutated from) against a fixed random-fuzz baseline (always mutate from the original
seeds) for equal iterations AND equal wall-clock. Compare unique failure classes
(distinct finding signatures) found.

This is the project's central technical claim. Measure it or the pitch is a bluff.
If guided and random come out even, say so in the writeup rather than draw a diagram.

Run:  python scripts/gate2_coverage.py
"""

from __future__ import annotations

import statistics
import sys
import time

sys.path.insert(0, ".")

from blindspot.oracles import default_oracles  # noqa: E402
from blindspot.runner import run_fuzz  # noqa: E402
from blindspot.types import FuzzConfig  # noqa: E402
from targets.specs import INVOICE  # noqa: E402

RNG_SEEDS = [0, 1, 2, 3, 4, 5, 6, 7]
ITERS = 60          # deliberately short: the question is early-discovery efficiency
DET_ORACLES = [o for o in default_oracles() if o.name != "judge"]


def _classes(guided: bool, seed: int) -> tuple[int, float]:
    cfg = FuzzConfig(iterations=ITERS, seed=seed, guided=guided)
    t0 = time.perf_counter()
    r = run_fuzz(INVOICE, cfg, oracles=DET_ORACLES)
    wall = time.perf_counter() - t0
    return len({f.signature for f in r.findings}), wall


def main() -> int:
    import os
    os.environ["BLINDSPOT_NO_SEMANTIC"] = "1"

    rows = []
    for s in RNG_SEEDS:
        g, gw = _classes(True, s)
        r, rw = _classes(False, s)
        rows.append((s, g, r, gw, rw))
        print(f"  seed {s}:  guided {g:2d} classes ({gw*1000:5.0f} ms)   "
              f"random {r:2d} classes ({rw*1000:5.0f} ms)")

    gmean = statistics.mean(x[1] for x in rows)
    rmean = statistics.mean(x[2] for x in rows)
    print("\n" + "=" * 66)
    print(f"  {ITERS} iterations/run, {len(RNG_SEEDS)} RNG seeds, deterministic oracles")
    print(f"  guided : mean {gmean:.2f} unique failure classes/run")
    print(f"  random : mean {rmean:.2f} unique failure classes/run")
    delta = gmean - rmean
    pct = (delta / rmean * 100) if rmean else 0.0
    verdict = (
        "guided clearly ahead — coverage guidance earns its place"
        if delta >= 1.0 else
        "roughly even — SAY SO in the writeup; do not oversell the coverage idea"
        if abs(delta) < 1.0 else
        "random ahead — investigate the signature granularity"
    )
    print(f"  delta  : {delta:+.2f} classes/run ({pct:+.0f}%)  ->  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
