"""Core datatypes. No logic lives here — every field is data the pipeline reads."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol

# ---------------------------------------------------------------------------
# The one contract between a target agent and everything downstream.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict            # actual values; metamorphic answer-extraction reads these
    ok: bool


Terminal = Literal["ok", "error", "timeout", "refused", "max_steps"]


@dataclass(frozen=True)
class AgentRun:
    input: str
    output: str | None
    tool_calls: tuple[ToolCall, ...]
    terminal: Terminal
    error_type: str | None = None      # exception class name when terminal == "error"
    retries: int = 0
    escalated: bool = False
    latency_s: float = 0.0
    cost_usd: float = 0.0


TargetAgent = Callable[[str], AgentRun]


# ---------------------------------------------------------------------------
# Mutation. answer_preserving is the one non-obvious coupling: it gates the
# metamorphic oracle, and it is a visible field rather than hidden control flow.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Mutant:
    text: str
    lineage: tuple[str, ...]      # op names applied, in order
    answer_preserving: bool       # AND over every op's preserving flag


# ---------------------------------------------------------------------------
# Behaviour signature granularity — a live CLI knob.
# ---------------------------------------------------------------------------


class Granularity(Enum):
    COARSE = "coarse"
    MEDIUM = "medium"
    FINE = "fine"


# ---------------------------------------------------------------------------
# Oracle output.
# ---------------------------------------------------------------------------

Severity = Literal["crash", "contract", "semantic", "quality"]


@dataclass(frozen=True)
class Finding:
    oracle: str
    input: str                   # reproducing input (mutant text, pre-minimise)
    summary: str
    severity: Severity
    evidence: dict               # {"baseline": ..., "mutant": ..., "transform": ...}
    confidence: float = 1.0      # 1.0 deterministic; <1.0 judge
    signature: str = ""          # oracle + normalised evidence shape -> clustering key


# ---------------------------------------------------------------------------
# Per-agent integration point. Adding a target agent is one of these.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSpec:
    name: str
    entrypoint: TargetAgent
    seeds: list[str]
    contract: Callable[[str | None], bool] | None = None          # SchemaOracle
    extract_answer: Callable[[AgentRun], Hashable] | None = None  # MetamorphicOracle
    judge_rubric: str | None = None                               # JudgeOracle


# ---------------------------------------------------------------------------
# Run configuration and results.
# ---------------------------------------------------------------------------


@dataclass
class FuzzConfig:
    iterations: int
    granularity: Granularity = Granularity.MEDIUM
    seed: int = 0
    judge_budget: int = 40
    time_budget_s: float | None = None
    guided: bool = True
    provider: str = "groq"


@dataclass
class RunStats:
    iterations: int = 0
    unique_behaviours: int = 0
    findings_total: int = 0
    per_oracle: dict[str, int] = field(default_factory=dict)
    llm_calls: int = 0
    cost_usd: float = 0.0
    cost_known: bool = True   # False once a call ran on a model with no published price
    wall_s: float = 0.0

    @property
    def bugs_per_min(self) -> float:
        return 0.0 if self.wall_s == 0 else self.findings_total / (self.wall_s / 60)


@dataclass
class FuzzResult:
    findings: list[Finding]
    corpus: list[str]
    signatures_seen: set[str]
    stats: RunStats


# ---------------------------------------------------------------------------
# Clustering output.
# ---------------------------------------------------------------------------


@dataclass
class FailureClass:
    id: str
    oracle: str
    label: str
    severity: Severity
    members: list[Finding]
    minimal_repro: Finding        # smallest member; mutated in place by minimise_class
    rank_score: float = 0.0


@dataclass(frozen=True)
class MinimiseResult:
    minimal: str
    original_len: int
    minimal_len: int
    reduction_ratio: float
    rounds: int


# ---------------------------------------------------------------------------
# Oracle protocol + context. The load-bearing shape.
# ---------------------------------------------------------------------------


@dataclass
class Budget:
    """Mutable remaining-call counter for the judge oracle. Deterministic oracles ignore it."""

    remaining: int

    def take(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


@dataclass(frozen=True)
class OracleContext:
    seed: str
    seed_run: AgentRun | None     # populated iff any active oracle.needs_baseline
    mutant: Mutant
    mutant_run: AgentRun
    agent: TargetAgent
    spec: AgentSpec
    budget: Budget


class Oracle(Protocol):
    name: str
    deterministic: bool           # False only for JudgeOracle
    needs_baseline: bool

    def check(self, ctx: OracleContext) -> list[Finding]: ...
