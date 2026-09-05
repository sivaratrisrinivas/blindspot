# Blindspot — design sketch

Coverage-guided fuzzer for AI agents. Point it at an agent; ~90s later it returns
the failure classes the author never imagined, a minimal reproducer for each, and a
pytest regression file.

Scope cut for the 22h solo build: **two** target agents (support, invoice), **four**
oracles (crash, schema, metamorphic, judge). Differential oracle dropped — it doubles
inference cost for an ambiguous signal (handoff §14).

## Caller's usage (written first)

```python
from blindspot import run_fuzz, FuzzConfig, cluster, rank, minimise_class, emit_pytest
from blindspot.ao import AOClient, dispatch_fixes
from targets.specs import INVOICE

result = run_fuzz(INVOICE, FuzzConfig(iterations=800, parallelism=8, seed=0))
classes = rank(cluster(result.findings))
for fc in classes:
    minimise_class(fc, INVOICE)          # shrinks fc.minimal_repro in place
emit_pytest(classes, INVOICE, Path("run/latest/test_blindspot_invoice.py"))

ao = AOClient()
session_ids = dispatch_fixes(classes, INVOICE, ao)   # one worker per class
```

Pipeline, not a framework. One public entrypoint (`run_fuzz`), then free functions
over plain dataclasses. All per-agent variation funnels into one `AgentSpec`.

## The one contract everything shares: `AgentRun`

The target agent is a plain `Callable[[str], AgentRun]`. We write the toy agents, so
we own this contract. Everything downstream — signature, every oracle, the minimiser's
re-run — reads `AgentRun` and nothing else about the agent.

```python
@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict            # actual values (metamorphic answer-extraction reads these)
    ok: bool

@dataclass(frozen=True)
class AgentRun:
    input: str
    output: str | None
    tool_calls: tuple[ToolCall, ...]
    terminal: Literal["ok", "error", "timeout", "refused", "max_steps"]
    error_type: str | None      # exception class name when terminal == "error"
    retries: int
    escalated: bool
    latency_s: float
    cost_usd: float
    raw: dict                   # spillover for the judge oracle
```

## Behaviour signature — pure hash, no model (handoff §5.1)

```python
class Granularity(Enum):
    COARSE = "coarse"; MEDIUM = "medium"; FINE = "fine"

def behaviour_signature(run: AgentRun, *, granularity: Granularity) -> str:
    """SHA1 of a tuple: ordered tool names + arg *shapes* (keys/types, not values),
    terminal class, error class, retry bucket, escalation flag.
    New hash => agent reached new behaviour => keep the input, mutate from it."""
```

`granularity` is a live CLI flag: coarse collides everything, fine makes every run
look novel. Arg *shape* only — value comparison is the metamorphic oracle's job, not
the signature's.

## The oracle interface — the load-bearing shape

An oracle sees one fuzz iteration and returns 0+ findings. Some need a baseline run
(the agent on the un-mutated seed); the runner computes that once, only if some
oracle asks for it.

```python
@dataclass(frozen=True)
class OracleContext:
    seed: str
    seed_run: AgentRun | None    # baseline; populated iff any active oracle.needs_baseline
    mutant: Mutant
    mutant_run: AgentRun
    agent: TargetAgent           # for oracles that re-run (judge self-consistency)
    spec: AgentSpec              # per-agent hooks (contract, extract_answer, rubric)
    budget: Budget               # remaining judge LLM calls; deterministic oracles ignore

class Oracle(Protocol):
    name: str
    deterministic: bool          # False only for JudgeOracle
    needs_baseline: bool
    def check(self, ctx: OracleContext) -> list[Finding]: ...

@dataclass(frozen=True)
class Finding:
    oracle: str
    input: str                   # reproducing input (mutant text, pre-minimise)
    summary: str                 # "answer changed under entity rename: 1100 -> Office Supplies"
    severity: Literal["crash", "contract", "semantic", "quality"]
    evidence: dict               # {"baseline": ..., "mutant": ..., "transform": ...}
    confidence: float            # 1.0 deterministic; <1.0 judge
    signature: str               # oracle + normalised evidence shape -> clustering key
```

### Concrete oracles

| Oracle | deterministic | needs_baseline | fires when |
|---|---|---|---|
| `CrashOracle` | yes | no | `terminal in {error, timeout}`, or retries/steps over a loop threshold |
| `SchemaOracle` | yes | no | `spec.contract(mutant_run.output)` is False |
| `MetamorphicOracle` | yes | yes | `mutant.answer_preserving` **and** `spec.extract_answer(seed_run) != spec.extract_answer(mutant_run)` |
| `JudgeOracle` | **no** | no | open-ended output, no deterministic check applies; budgeted; confidence surfaced |

`MetamorphicOracle` is the heart. `spec.extract_answer` pulls the decision that must
be invariant — for the invoice agent, the GL account code from the booking tool call.
A changed answer under an answer-preserving transform is a proven bug with zero ground
truth (the bathroom-scale argument).

### The mutator ↔ metamorphic coupling (the one non-obvious link, made explicit)

```python
@dataclass(frozen=True)
class Mutant:
    text: str
    lineage: tuple[str, ...]     # op names applied
    answer_preserving: bool      # AND over all ops' preserving flag
```

`DeterministicMutator` ops are each tagged: entity rename via homoglyph (Acme->Åcme),
line-item reorder, currency/date reformat, whitespace inject, synonym swap => all
`answer_preserving=True`. `SemanticMutator` (Groq) generates new hostile inputs =>
`answer_preserving=False`; those feed crash/schema/judge, never metamorphic.

## Per-agent integration point: `AgentSpec`

Adding a target agent is one dataclass with four optional hooks.

```python
@dataclass(frozen=True)
class AgentSpec:
    name: str
    entrypoint: TargetAgent
    seeds: list[str]
    contract: Callable[[str], bool] | None          # SchemaOracle
    extract_answer: Callable[[AgentRun], Hashable] | None  # MetamorphicOracle
    judge_rubric: str | None                        # JudgeOracle
```

## Runner

```python
@dataclass
class FuzzConfig:
    iterations: int
    parallelism: int = 8
    granularity: Granularity = Granularity.MEDIUM
    seed: int = 0
    judge_budget: int = 40
    time_budget_s: float | None = None

@dataclass
class FuzzResult:
    findings: list[Finding]          # raw, pre-minimise
    corpus: list[str]
    signatures_seen: set[str]
    stats: RunStats                  # iterations, unique behaviours, bugs/min, per-oracle counts, cost

def run_fuzz(spec: AgentSpec, cfg: FuzzConfig) -> FuzzResult: ...
```

Loop: round-robin a seed from the corpus (handoff: no clever scheduler) -> mutate ->
run agent (thread pool, `parallelism` wide) -> signature -> `corpus.add` returns True
if novel -> run active oracles -> collect findings. Baseline run computed once per
seed and cached when any oracle `needs_baseline`.

## Minimiser — delta debugging (the one place TDD applies)

```python
def minimise(text: str, still_fails: Callable[[str], bool], *, max_rounds: int = 20) -> MinimiseResult

@dataclass(frozen=True)
class MinimiseResult:
    minimal: str
    original_len: int
    minimal_len: int
    reduction_ratio: float
    rounds: int
```

`still_fails` is a per-finding closure: re-run agent on the candidate, re-run the same
oracle, assert a finding with the same `signature` returns. Word-granularity ddmin.

## Cluster + rank + emit

```python
def cluster(findings: list[Finding]) -> list[FailureClass]     # group by (oracle, signature)
def rank(classes: list[FailureClass]) -> list[FailureClass]    # severity weight * distinct sigs * 1/len
def emit_pytest(classes: list[FailureClass], spec: AgentSpec, path: Path) -> None

@dataclass
class FailureClass:
    id: str
    oracle: str
    label: str
    severity: str
    members: list[Finding]
    minimal_repro: Finding       # smallest member; mutated in place by minimise_class
    rank_score: float
```

## AO client — thin adapter, one file (handoff §6)

```python
class AOClient:
    def __init__(self, base_url="http://localhost:3011", project="."): ...
    def spawn_worker(self, name: str, prompt: str, *, model: str = "sonnet") -> str   # POST /api/v1/sessions
    def send(self, sid: str, msg: str) -> None                                        # POST .../{id}/send
    def get(self, sid: str) -> dict                                                   # GET .../{id}
    def list(self) -> list[dict]                                                      # GET /api/v1/sessions

def dispatch_fixes(classes, spec, ao) -> list[str]:
    """One worker session per class. Prompt = minimal repro + emitted failing test +
    'make it pass without regressing the corpus'. Returns session ids to poll."""
```

## Module map

```
blindspot/
  types.py         AgentRun, ToolCall, Mutant, Finding, FailureClass, AgentSpec, configs — no logic
  signature.py     behaviour_signature(), Granularity
  corpus.py        Corpus (add-if-novel, round-robin next_seed)
  llm.py           Groq client factory (openai SDK + base_url), retry, cost tally
  mutate/
    __init__.py    Mutator protocol, CompositeMutator
    deterministic.py  metamorphic + structural ops, each tagged answer_preserving
    semantic.py    SemanticMutator (Groq)
  oracles/
    __init__.py    Oracle protocol, OracleContext, run_oracles(), DEFAULT_ORACLES
    crash.py  schema.py  metamorphic.py  judge.py
  runner.py        run_fuzz(), thread-pool executor, baseline cache
  minimise.py      ddmin  (TDD'd)
  cluster.py       cluster() + rank() + minimise_class()
  emit.py          emit_pytest()
  ao.py            AOClient, dispatch_fixes()
  report.py        metrics table across agents; JSONL read/write
  cli.py           `blindspot targets/specs.py:INVOICE` — rich live counters
targets/
  support_agent.py  invoice_agent.py  specs.py
run/                per-run dirs: findings.jsonl, corpus.jsonl, stats.json, emitted tests
```

## Where a model is allowed to touch anything (handoff §5.4)

Two places only. `SemanticMutator` (hostile input generation) and `JudgeOracle`
(last-resort grading, budgeted, confidence surfaced). If a deterministic check can
prove it, a model must not opine. Signature, crash/schema/metamorphic oracles,
minimiser, clustering, ranking, emit — zero model calls.

## Interface-depth check

Public surface: `run_fuzz(spec, cfg) -> FuzzResult`, then `cluster/rank/minimise_class/
emit_pytest/dispatch_fixes` as a linear pipeline over dataclasses. Every per-agent
knob is one `AgentSpec` with 4 optional fields. Every oracle is one file implementing
one method. The only subtle coupling — `Mutant.answer_preserving` gating the
metamorphic oracle — is a visible field on a frozen dataclass, not hidden control flow.

## Deviations from handoff, surfaced

1. Differential oracle cut (time + §14 rationale). Judge stays as last-resort #4.
2. Two target agents, not three. Invoice is the demo star; SQL agent dropped.
3. Demo recording moves to ~hour 12 per the re-cut in handoff §1.
