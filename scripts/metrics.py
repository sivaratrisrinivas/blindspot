"""Before / after metrics, re-runnable end to end (principle: build the lever).

For each target agent it Blindspot-fuzzes the buggy version and the repaired version
under identical settings, then scores both against one eval set (the clean seeds,
which must pass, plus every minimal reproducer Blindspot found on the buggy agent,
which the repaired agent should now handle).

Columns are labelled with Track 1's own words:
  accuracy    -> booking / answer correctness on the eval set  (1 - failure rate)
  reliability -> crash + timeout count on the eval set
  speed       -> unique failure classes per fuzz run, and bugs/min
  cost        -> $ of LLM spend for the run

Run:  python scripts/metrics.py            # invoice (deterministic, fast)
      python scripts/metrics.py --judge    # also support (spends ~$0.02 of Groq)
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

sys.path.insert(0, ".")
os.environ.setdefault("BLINDSPOT_NO_SEMANTIC", "1")

from blindspot.cluster import cluster, minimise_class, rank  # noqa: E402
from blindspot.oracles import default_oracles  # noqa: E402
from blindspot.runner import run_fuzz  # noqa: E402
from blindspot.types import FuzzConfig  # noqa: E402
from targets import specs  # noqa: E402

ITERS = 600
SEEDS = [3, 7, 11]


def _fuzz(spec, use_judge: bool):
    oracles = default_oracles() if use_judge else [o for o in default_oracles() if o.name != "judge"]
    classes_per_seed, findings_per_seed, cost = [], [], 0.0
    wall = 0.0
    last = None
    for sd in SEEDS:
        t0 = time.perf_counter()
        r = run_fuzz(spec, FuzzConfig(iterations=ITERS, seed=sd, judge_budget=20), oracles=oracles)
        wall += time.perf_counter() - t0
        classes_per_seed.append(len({f.signature for f in r.findings}))
        findings_per_seed.append(len(r.findings))
        cost += r.stats.cost_usd
        last = r
    return {
        "classes": statistics.mean(classes_per_seed),
        "findings": statistics.mean(findings_per_seed),
        "cost": cost,
        "bugs_per_min": statistics.mean(findings_per_seed) / (wall / len(SEEDS) / 60),
        "last": last,
    }


def _eval_set(buggy_spec, use_judge: bool) -> list[str]:
    oracles = default_oracles() if use_judge else [o for o in default_oracles() if o.name != "judge"]
    r = run_fuzz(buggy_spec, FuzzConfig(iterations=ITERS, seed=99, judge_budget=20), oracles=oracles)
    classes = rank(cluster(r.findings))
    for fc in classes:
        minimise_class(fc, buggy_spec)
    repros = [fc.minimal_repro.input for fc in classes]
    mutants = [fc.minimal_repro.evidence.get("mutant_input") for fc in classes]
    return list(buggy_spec.seeds) + repros + [m for m in mutants if m]


def _score(spec, eval_inputs: list[str], reference) -> dict:
    """failure = crash/timeout, or (invoice) a booked account that disagrees with the
    reference agent, or (support) a judge flag. clean seeds must simply not crash."""
    crashes = wrong = 0
    lats = []
    for inp in eval_inputs:
        run = spec.entrypoint(inp)
        lats.append(run.latency_s)
        if run.terminal in ("error", "timeout"):
            crashes += 1
            wrong += 1
            continue
        if reference is not None and spec.extract_answer is not None:
            ref = reference.entrypoint(inp)
            if (ref.terminal == "ok"
                    and spec.extract_answer(run) != reference.extract_answer(ref)):
                wrong += 1
    n = len(eval_inputs)
    return {
        "n": n,
        "failure_rate": wrong / n,
        "accuracy": 1 - wrong / n,
        "crashes": crashes,
        "p95_ms": (statistics.quantiles(lats, n=20)[-1] if len(lats) > 1 else lats[0]) * 1000,
    }


def _pair(name: str, buggy, fixed, use_judge: bool) -> None:
    print(f"\n### {name}\n")
    ev = _eval_set(buggy, use_judge)
    # the repaired agent is our best correctness oracle: an answer is "wrong" if the
    # agent under test disagrees with it (or crashes). the repaired agent is scored
    # for crashes only — it cannot disagree with itself.
    ref = fixed if fixed.extract_answer is not None else None
    b_fuzz, f_fuzz = _fuzz(buggy, use_judge), _fuzz(fixed, use_judge)
    b_sc = _score(buggy, ev, ref)
    f_sc = _score(fixed, ev, None)

    hdr = f"| {'metric':<26} | {'before':>12} | {'after':>12} |"
    print(hdr)
    print("|" + "-" * 28 + "|" + "-" * 14 + "|" + "-" * 14 + "|")
    rows = [
        ("failure classes / run", f"{b_fuzz['classes']:.1f}", f"{f_fuzz['classes']:.1f}"),
        ("findings / run", f"{b_fuzz['findings']:.0f}", f"{f_fuzz['findings']:.0f}"),
        ("bugs / min", f"{b_fuzz['bugs_per_min']:.0f}", f"{f_fuzz['bugs_per_min']:.0f}"),
        (f"accuracy on {b_sc['n']} evals", f"{b_sc['accuracy']*100:.0f}%", f"{f_sc['accuracy']*100:.0f}%"),
        ("failure rate on evals", f"{b_sc['failure_rate']*100:.0f}%", f"{f_sc['failure_rate']*100:.0f}%"),
        ("crash + timeout on evals", f"{b_sc['crashes']}", f"{f_sc['crashes']}"),
        ("p95 latency", f"{b_sc['p95_ms']:.2f} ms", f"{f_sc['p95_ms']:.2f} ms"),
        ("LLM $ / run", f"${b_fuzz['cost']:.4f}", f"${f_fuzz['cost']:.4f}"),
    ]
    for label, a, b in rows:
        print(f"| {label:<26} | {a:>12} | {b:>12} |")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true", help="also run the support agent (Groq spend)")
    args = ap.parse_args()

    print("# Blindspot — before / after\n")
    print(f"{ITERS} iterations/run, {len(SEEDS)} RNG seeds, deterministic mutations.")
    print("accuracy = answer/booking correctness · reliability = crash+timeout count "
          "· speed = classes/run & bugs/min · cost = $/run\n")

    _pair("invoice-reconciliation agent", specs.INVOICE, specs.INVOICE_FIXED, use_judge=False)
    if args.judge:
        _pair("customer-support agent", specs.SUPPORT, specs.SUPPORT_FIXED, use_judge=True)
        print("\n_note: the support agent's oracle is the LLM judge, which is "
              "probabilistic; a residual class or two on the repaired agent are judge "
              "false-positives on adversarially-mutated inputs, not real regressions._")
    print("\n_targets are toys — the numbers are toy numbers. The tool is the artefact._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
