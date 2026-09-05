"""The fuzz loop. Public entrypoint: run_fuzz(spec, cfg) -> FuzzResult."""

from __future__ import annotations

import time
from random import Random

from blindspot.corpus import Corpus
from blindspot.mutate import CompositeMutator
from blindspot.oracles import default_oracles, run_oracles
from blindspot.signature import behaviour_signature
from blindspot.types import (
    AgentRun,
    AgentSpec,
    Budget,
    FuzzConfig,
    FuzzResult,
    Oracle,
    OracleContext,
    RunStats,
)


def _run_agent(spec: AgentSpec, text: str) -> AgentRun:
    """Call spec.entrypoint with a wall-clock timeout; convert exceptions/timeouts
    into AgentRun(terminal=...) rather than propagating."""
    raise NotImplementedError


def run_fuzz(
    spec: AgentSpec,
    cfg: FuzzConfig,
    *,
    oracles: list[Oracle] | None = None,
    on_iteration=None,        # callback(stats) for the CLI live counters
) -> FuzzResult:
    """Round-robin a seed -> mutate -> run agent (thread pool, cfg.parallelism wide)
    -> signature -> corpus.add -> run active oracles -> collect findings.
    Baseline run computed once per seed and cached when any active oracle needs it."""
    raise NotImplementedError
