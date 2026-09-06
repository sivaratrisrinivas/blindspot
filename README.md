# Blindspot

A coverage-aware fuzzer for AI agents. Point it at an agent. About ninety seconds
later it hands you the failure classes the author never thought to test, a minimal
input that reproduces each one, and a pytest file full of regression tests nobody
wrote.

Built for the Syndicate by Maximor hackathon, Track 1.

```
blindspot invoice
```

## The problem

Your agent passes every eval you wrote. That tells you nothing about the failures
you didn't imagine, because an eval set is a portrait of its author's assumptions.
Prompt optimisation is the well-trodden half of "improve an agent and analyse where
it fails." Failure discovery is the other half, and it is mostly unsolved.

The lock analogy: you tested your lock with your own key and it opened. You have
learned nothing about whether a burglar can open it, because you are not a burglar.

## How it works

```
seed inputs
   -> mutate (deterministic metamorphic + structural ops; optional Groq semantic)
   -> run the agent, record a behaviour signature (a hash, no model)
   -> new signature? keep the input and mutate from it
   -> oracles: crash | schema | metamorphic | judge (last resort)
   -> delta-debug each failure to a minimal reproducer
   -> cluster into failure classes, rank
   -> emit a pytest file
   -> optional: one Agent Orchestrator worker per class opens a fix PR
```

### The metamorphic oracle does the real work

Most oracles need a correct answer to compare against. This one doesn't. It applies
a transform that must not change the answer, then checks whether the answer changed.
Rename a company from "Acme Corp" to "Åcme Corp" with a Unicode look-alike. Reorder
the line items. Reformat "$1,240.00" as "USD 1240.00". If the booked GL account
moves, that is a proven bug, and no ground truth was needed to prove it.

The bathroom-scale analogy: you don't need to know someone's weight to know the
scale is broken if it reads differently when they face north versus south.

Detection is a string comparison, so this is not a model grading a model.

### Where a model is allowed to run

Two places, both optional and both off the critical path:

- semantic mutation, to generate hostile-but-plausible inputs a random mutator
  can't reach (opt in with `--semantic`; the provider throttles a burst, so a
  semantic run is minutes not seconds)
- the judge oracle, last resort only, for open-ended prose output where no
  deterministic check applies (budgeted, confidence reported)

The behaviour signature, the crash / schema / metamorphic oracles, the minimiser,
the clustering and the emitter make zero model calls.

Both places go through one provider table in `blindspot/llm.py`. Providers are
OpenAI-compatible, so a provider is a row (base URL, key env var, the two models,
published prices) rather than a branch, and `--provider` picks one. Groq is the
default. TensorMux is the second row and serves the same two roles:

```bash
blindspot support --provider tensormux --judge-budget 5
blindspot invoice --provider tensormux --semantic --no-judge
```

TensorMux publishes no per-token price for the model it serves, so a run through
it reports its call count and prints `cost unpublished` instead of a dollar figure
nobody measured.

### The minimiser keeps reproducers honest

Delta debugging shrinks a failing input while the failure survives. For a
metamorphic failure it shrinks the baseline while re-applying the transform at a
site that still flips the answer, so it can never delete the renamed vendor and
leave a reproducer that "works" for the wrong reason. A 70-character invoice
collapses to `Acme Corp $12,500.00 2026-04-01`, and the transform that breaks it
is one Unicode character.

### Agent Orchestrator is the fix loop, not a checkbox

`blindspot invoice --fix` spawns one AO worker per ranked failure class. Each gets
the minimal reproducer and the exact invariant it violates, fixes the target agent,
adds a regression test, and opens a PR. The mandatory-AO requirement became the
architecture: a run with seven failure classes is seven worker sessions on the
Kanban board.

## Results

Two toy target agents, in two domains, each with planted blind spots:

- `targets/invoice_agent.py` — invoice reconciliation. Six blind spots: vendor
  lookup with no Unicode or whitespace folding, first-name-span-wins vendor
  selection, a capex threshold that misreads comma-separated thousands, a
  US-only amount parser, an ISO-only date parser, a hard reject for closed periods.
- `targets/support_agent.py` — customer support. Four blind spots: a cheerful
  non-answer when the order number is missing, an invented status for unknown
  orders, a naive refund-amount parse, no escalation above $500.

`scripts/metrics.py` fuzzes each buggy agent and its repaired twin under identical
settings and scores both against one eval set. Invoice, 600 iterations per run,
three RNG seeds, deterministic mutations:

| metric                     |       before |        after |
|----------------------------|-------------:|-------------:|
| failure classes / run      |          6.0 |          0.0 |
| findings / run             |          327 |            0 |
| bugs / min                 |     ~150,000 |            0 |
| accuracy on 18 evals       |          56% |         100% |
| failure rate on evals      |          44% |           0% |
| crash + timeout on evals   |            2 |            0 |
| p95 latency                |      0.09 ms |      0.27 ms |

Columns map onto Track 1's own words: accuracy is booking correctness, reliability
is the crash and timeout count, speed is classes per run and bugs per minute, cost
is LLM spend (zero for the deterministic invoice run).

The targets are toys, so the numbers are toy numbers. The tool is the artefact.

### Validation gates

Three checks, each with a kill criterion, run before trusting the pipeline:

- **Gate 1, metamorphic precision** (`scripts/gate1_metamorphic.py`). Six
  hand-written cosmetic relations over the invoice agent: 42 trials, 11 flagged
  violations, all 11 genuine, zero false positives. Threshold was six genuine.
- **Gate 2, coverage guidance** (`scripts/gate2_coverage.py`). Covered below.
- **Gate 3, recall on planted bugs** (`scripts/gate3_recall.py`). The invoice
  agent has six planted blind spots. Across eight RNG seeds the fuzzer catches
  6/6 every time.

### What we measured that didn't work

The corpus is coverage-aware: it fingerprints each run's behaviour, dedupes
findings by that fingerprint, and re-seeds from inputs that reached a new
behaviour. AFL does the same thing for code coverage. We toggled it
(`--guided` / `--no-guided`) and measured it in `scripts/gate2_coverage.py`.

At this scale it does not beat a random baseline. Over eight to ten RNG seeds,
guided found about 3.8 unique failure classes per short run and random found about
4.4. The invoice agent only ever reaches five distinct behaviour signatures, so
there is almost nothing for coverage guidance to exploit, and finer signature
granularity changes nothing. On agents with deeper reachable state it may pay off.
We haven't tested that, so we're not claiming it. The value here is the oracle
stack, the coupled minimiser, and the AO loop.

Reporting this straight is on-thesis. The whole project is an argument that an
unmeasured claim is worthless.

## Honest weaknesses

- Metamorphic relations are hand-written. A sloppy relation produces a flood of
  false alarms, which is worse than no tool.
- The judge oracle is probabilistic. On the support agent it leaves a residual
  class or two on the repaired agent that are false positives on adversarially
  mutated inputs, not real regressions.
- Without the metamorphic oracle, what's left is a crash fuzzer, which is 1998
  technology with a model attached.
- The target agents are toys. A real agent would give real improvement numbers.

## Running it

```bash
uv sync
export GROQ_API_KEY=...            # semantic mutation and the judge oracle
export TENSORMUX_API_KEY=...       # optional, for --provider tensormux

blindspot invoice                  # fast: deterministic mutations, live counters, emits a pytest file
blindspot invoice --semantic       # add semantic mutations (slower, more coverage)
blindspot support --judge-budget 20                    # the judge-oracle showcase
blindspot support --provider tensormux --judge-budget 5  # same, through TensorMux
blindspot invoice --fix --fix-limit 3                  # dispatch AO fix workers

python scripts/gate1_metamorphic.py   # metamorphic precision check
python scripts/gate2_coverage.py      # guided vs random
python scripts/gate3_recall.py        # recall on the planted bugs
python scripts/metrics.py             # the before/after table
python scripts/verify_pipeline.py     # all 10 stages, including the CLI
python -m pytest -q                   # 30 tests
```

The AO daemon must be running for `--fix` (`AO_PORT=3011 ao daemon`).

## Layout

```
blindspot/
  types.py        the datatypes; no logic
  signature.py    behaviour signature (a hash)
  corpus.py       behaviour-space corpus, round-robin scheduler
  mutate/         deterministic ops (each tagged answer-preserving) + Groq semantic
  oracles/        crash, schema, metamorphic, judge; one check() each
  runner.py       run_fuzz(spec, cfg) -> FuzzResult
  minimise.py     delta debugging (test-first)
  cluster.py      cluster / rank / minimise_class
  emit.py         the regression pytest file
  llm.py          the provider table (Groq, TensorMux) + one OpenAI-compatible client
  ao.py           AO daemon client + dispatch_fixes
  report.py       JSONL persistence
  cli.py          blindspot <spec>
targets/          two buggy agents + their repaired twins
scripts/          the three validation gates and the metrics table
```

Adding a target agent is one `AgentSpec`: an entrypoint, some seeds, and up to
three optional hooks (an output contract, an answer extractor for the metamorphic
oracle, a judge rubric).

## AO usage

Every module except the design sketch was built through AO worker sessions. See
`docs/AO_USAGE.md` for the session count and what each session produced.
