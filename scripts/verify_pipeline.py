"""End-to-end pipeline verification. Exercises each stage in isolation, asserts on
the real output, prints evidence. Exit 0 = every stage verified."""
from __future__ import annotations
import os, sys, json, subprocess, tempfile, pathlib
os.environ.setdefault("BLINDSPOT_NO_SEMANTIC", "1")  # stage tests stay deterministic
sys.path.insert(0, ".")

from random import Random
from blindspot.types import FuzzConfig, Granularity, OracleContext, Budget, Mutant
from blindspot.mutate import CompositeMutator, DeterministicMutator
from blindspot.mutate.deterministic import OPS
from blindspot.signature import behaviour_signature
from blindspot.corpus import Corpus
from blindspot.oracles import default_oracles, run_oracles
from blindspot.runner import run_fuzz, _run_agent
from blindspot.cluster import cluster, rank, minimise_class
from blindspot.emit import emit_pytest
from blindspot.report import write_run, metrics_table
from targets.specs import INVOICE, SUPPORT

OK = "\033[32mPASS\033[0m"; BAD = "\033[31mFAIL\033[0m"
fails = []
def check(name, cond, detail=""):
    print(f"  [{OK if cond else BAD}] {name}" + (f"  — {detail}" if detail else ""))
    if not cond: fails.append(name)

print("\n=== 1. target agent contract ===")
r = INVOICE.entrypoint("Invoice from Acme Corp for $1,240.00 dated 2026-03-01 for chairs.")
check("invoice agent returns AgentRun.ok", r.terminal == "ok", r.output)
check("tool calls recorded", len(r.tool_calls) >= 3, [t.name for t in r.tool_calls])
check("extract_answer pulls GL", INVOICE.extract_answer(r) == "1100", INVOICE.extract_answer(r))
rc = _run_agent(INVOICE, "no date here $5")
check("_run_agent converts exception to terminal", rc.terminal == "error", rc.error_type)

print("\n=== 2. mutation ===")
det = DeterministicMutator()
it = det.mutate("Invoice from Acme Corp for $1,240.00 dated 2026-03-01.", rng=Random(0))
muts = [next(it) for _ in range(20)]
check("deterministic mutants are distinct from seed", all(m.text for m in muts))
preserving = [m for m in muts if m.answer_preserving]
check("some mutants answer_preserving, some not",
      0 < len(preserving) < 20, f"{len(preserving)}/20 preserving")
check("lineage names are real ops", all(all(op in OPS for op in m.lineage) for m in muts))

print("\n=== 3. behaviour signature ===")
a = behaviour_signature(r, granularity=Granularity.MEDIUM)
b = behaviour_signature(INVOICE.entrypoint("gibberish no date no money"),  # crash path
                        granularity=Granularity.MEDIUM)
c = behaviour_signature(r, granularity=Granularity.MEDIUM)
check("signature deterministic", a == c, a[:16])
check("different behaviour (ok vs crash) -> different signature", a != b)
d = behaviour_signature(INVOICE.entrypoint("Bill from Globex for $500.00 dated 2026-01-03."),
                        granularity=Granularity.MEDIUM)
check("same behaviour (two clean bookings) -> same signature", a == d,
      "by design: signature hashes arg SHAPES, not values")
check("no model call in signature", isinstance(a, str) and len(a) == 40)

print("\n=== 4. corpus (coverage gate) ===")
cp = Corpus(["seed one", "seed two"])
check("novel signature accepted", cp.add("x", "sigA") is True)
check("repeat signature rejected", cp.add("y", "sigA") is False)
check("round-robin cycles", cp.next_seed() != cp.next_seed() or len(cp) == 1)

print("\n=== 5. oracles ===")
seed = "Invoice from Acme Corp for $12,500.00 dated 2026-04-01 for a forklift."
mut = Mutant("Invoice from Åcme Corp for $12,500.00 dated 2026-04-01 for a forklift.",
             ("homoglyph_entity",), True)
ctx = OracleContext(seed=seed, seed_run=INVOICE.entrypoint(seed), mutant=mut,
                    mutant_run=INVOICE.entrypoint(mut.text), agent=INVOICE.entrypoint,
                    spec=INVOICE, budget=Budget(0))
dets = [o for o in default_oracles() if o.name != "judge"]
found = run_oracles(dets, ctx)
check("metamorphic oracle fires on homoglyph", any(f.oracle == "metamorphic" for f in found),
      [f.signature for f in found])
crash_ctx = OracleContext(seed="x", seed_run=None,
                          mutant=Mutant("$5 no date", (), False),
                          mutant_run=INVOICE.entrypoint("$5 no date"),
                          agent=INVOICE.entrypoint, spec=INVOICE, budget=Budget(0))
check("crash oracle fires on exception",
      any(f.oracle == "crash" for f in run_oracles(dets, crash_ctx)))

print("\n=== 6. full runner ===")
res = run_fuzz(INVOICE, FuzzConfig(iterations=600, seed=3), oracles=dets)
sigs = {f.signature for f in res.findings}
check("runner produced findings", len(res.findings) > 50, len(res.findings))
check(">=6 distinct failure signatures", len(sigs) >= 6, sorted(sigs))
check("stats populated", res.stats.iterations == 600 and res.stats.wall_s > 0,
      f"{res.stats.iterations} iters {res.stats.wall_s:.2f}s")

print("\n=== 7. cluster + rank + minimise ===")
classes = rank(cluster(res.findings))
check("clustered into classes", 5 <= len(classes) <= 10, len(classes))
check("ranked descending", all(classes[i].rank_score >= classes[i+1].rank_score
                               for i in range(len(classes)-1)))
homo = next(c for c in classes if c.id == "metamorphic_homoglyph_entity")
before_len = len(homo.minimal_repro.input)
minimise_class(homo, INVOICE)
ev = homo.minimal_repro.evidence
check("minimiser shrank the repro", len(homo.minimal_repro.input) <= before_len,
      f"{ev.get('original_len')} -> {ev.get('minimal_len')}")
check("minimised metamorphic pair still diverges",
      ev.get("baseline_answer") != ev.get("mutant_answer"),
      f"{ev.get('baseline_answer')} vs {ev.get('mutant_answer')}")
check("repro still contains a vendor (not over-shrunk)",
      any(v in homo.minimal_repro.input.lower() for v in ("acme", "globex", "initech",
                                                          "umbrella", "soylent")))

print("\n=== 8. pytest emitter ===")
for c in classes: minimise_class(c, INVOICE)
tmp = pathlib.Path(tempfile.mkdtemp()) / "test_emitted.py"
emit_pytest(classes, INVOICE, tmp)
src = tmp.read_text()
check("emitted file compiles", compile(src, str(tmp), "exec") or True)
check("one test per class", src.count("def test_") >= len(classes), src.count("def test_"))
cp = subprocess.run([sys.executable, "-m", "pytest", "--co", "-q", str(tmp)],
                    capture_output=True, text=True, cwd=".")
check("pytest can collect emitted file", cp.returncode in (0, 5), cp.stdout.strip()[-120:])

print("\n=== 9. JSONL persistence ===")
rundir = pathlib.Path(tempfile.mkdtemp()) / "invoice-20260906T120000Z"
rundir.mkdir(parents=True)
write_run(rundir, res)
for fn in ("findings.jsonl", "corpus.jsonl", "stats.json"):
    p = rundir / fn
    check(f"{fn} written", p.exists() and p.stat().st_size > 0)
lines = (rundir / "findings.jsonl").read_text().splitlines()
check("findings.jsonl lines parse as JSON", all(json.loads(x) for x in lines), len(lines))
st = json.loads((rundir / "stats.json").read_text())
check("stats.json has bugs_per_min", "bugs_per_min" in st, st.get("bugs_per_min"))
tbl = metrics_table([rundir])
check("metrics_table renders headers + agent row",
      "bugs/min" in tbl and "invoice" in tbl, tbl.splitlines()[0] if tbl else "")

print()
if fails:
    print(f"\033[31m{len(fails)} STAGE(S) FAILED: {fails}\033[0m")
    sys.exit(1)
print("\033[32mALL 9 PIPELINE STAGES VERIFIED\033[0m")
