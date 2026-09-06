"""The fuzz loop. Public entrypoint: run_fuzz(spec, cfg) -> FuzzResult.

seed (round-robin) -> mutate -> run agent (thread pool) -> behaviour signature ->
corpus.add (keep if novel) -> run oracles -> collect findings.
Baseline run computed once per seed and cached, only when an active oracle needs it."""

from __future__ import annotations

import os
import signal
import threading
import time
from collections.abc import Callable
from random import Random

from blindspot import obs
from blindspot.corpus import Corpus
from blindspot.llm import LLM, has_key, provider
from blindspot.mutate import CompositeMutator, DeterministicMutator, SemanticMutator
from blindspot.oracles import default_oracles, run_oracles
from blindspot.signature import behaviour_signature
from blindspot.types import (
    AgentRun,
    AgentSpec,
    Budget,
    Finding,
    FuzzConfig,
    FuzzResult,
    Mutant,
    Oracle,
    OracleContext,
    RunStats,
)

_AGENT_TIMEOUT_S = 5


class _Timeout(Exception):
    pass


def _run_agent(spec: AgentSpec, text: str) -> AgentRun:
    """Call the target directly. Exceptions become a crash AgentRun; a SIGALRM guard
    catches a genuine hang without paying thread-pool setup on every one of thousands
    of iterations."""
    t0 = time.perf_counter()
    use_alarm = (hasattr(signal, "SIGALRM")
                 and threading.current_thread() is threading.main_thread())
    if use_alarm:
        def _fire(signum, frame):  # noqa: ANN001
            raise _Timeout

        old = signal.signal(signal.SIGALRM, _fire)
        signal.alarm(_AGENT_TIMEOUT_S)
    try:
        return spec.entrypoint(text)
    except _Timeout:
        return AgentRun(input=text, output=None, tool_calls=(), terminal="timeout",
                        latency_s=time.perf_counter() - t0)
    except Exception as exc:  # noqa: BLE001 — a target that throws is a crash finding
        return AgentRun(input=text, output=None, tool_calls=(), terminal="error",
                        error_type=type(exc).__name__, latency_s=time.perf_counter() - t0)
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)


def _build_mutator(cfg: FuzzConfig) -> CompositeMutator:
    sem = None
    p = provider(cfg.provider)
    if has_key(p) and not os.environ.get("BLINDSPOT_NO_SEMANTIC"):
        try:
            sem = SemanticMutator(LLM(p, p.fuzz_model))
        except Exception:  # noqa: BLE001 — degrade to deterministic-only
            sem = None
    return CompositeMutator(DeterministicMutator(), sem)


@obs.span("WORKFLOW", "fuzz")
def run_fuzz(
    spec: AgentSpec,
    cfg: FuzzConfig,
    *,
    oracles: list[Oracle] | None = None,
    on_iteration: Callable[[RunStats], None] | None = None,
) -> FuzzResult:
    rng = Random(cfg.seed)
    corpus = Corpus(spec.seeds, guided=cfg.guided)
    oracles = oracles or default_oracles()
    needs_baseline = any(o.needs_baseline for o in oracles)
    budget = Budget(cfg.judge_budget)
    mutator = _build_mutator(cfg)

    findings: list[Finding] = []
    stats = RunStats(per_oracle={o.name: 0 for o in oracles})
    baseline_cache: dict[str, AgentRun] = {}
    streams: dict[str, object] = {}
    deadline = None if cfg.time_budget_s is None else time.perf_counter() + cfg.time_budget_s
    t_start = time.perf_counter()

    def mutant_for(seed: str) -> Mutant:
        it = streams.get(seed)
        if it is None:
            it = mutator.mutate(seed, rng=rng)
            streams[seed] = it
        return next(it)  # type: ignore[arg-type]

    for i in range(cfg.iterations):
        if deadline is not None and time.perf_counter() >= deadline:
            break
        seed = corpus.next_seed()
        mutant = mutant_for(seed)

        run = _run_agent(spec, mutant.text)
        sig = behaviour_signature(run, granularity=cfg.granularity)
        novel = corpus.add(mutant.text, sig)

        seed_run = None
        if needs_baseline:
            seed_run = baseline_cache.get(seed)
            if seed_run is None:
                seed_run = _run_agent(spec, seed)
                baseline_cache[seed] = seed_run

        ctx = OracleContext(
            seed=seed, seed_run=seed_run, mutant=mutant, mutant_run=run,
            agent=spec.entrypoint, spec=spec, budget=budget,
        )
        got = run_oracles(oracles, ctx)
        for f in got:
            findings.append(f)
            stats.per_oracle[f.oracle] = stats.per_oracle.get(f.oracle, 0) + 1

        stats.iterations = i + 1
        stats.unique_behaviours = len(corpus.signatures)
        stats.findings_total = len(findings)
        stats.wall_s = time.perf_counter() - t_start
        if novel and on_iteration:
            on_iteration(stats)
        elif on_iteration and (i % 25 == 0):
            on_iteration(stats)

    stats.llm_calls, stats.cost_usd, stats.cost_known = _llm_totals(mutator, oracles)
    stats.wall_s = time.perf_counter() - t_start
    return FuzzResult(
        findings=findings,
        corpus=corpus.entries(),
        signatures_seen=corpus.signatures,
        stats=stats,
    )


def _llm_totals(mutator: CompositeMutator, oracles: list[Oracle]) -> tuple[int, float, bool]:
    """Calls and spend across every LLM the run touched. cost_known goes False as
    soon as one of them billed on a model with no published price."""
    calls, cost, known = 0, 0.0, True
    sem = getattr(mutator, "_sem", None)
    for llm in (getattr(sem, "_llm", None), *(getattr(o, "_llm", None) for o in oracles)):
        if llm is None or not llm.calls:
            continue
        calls += llm.calls
        cost += llm.cost_usd
        known = known and llm.priced
    return calls, cost, known
