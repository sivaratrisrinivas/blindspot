"""Concrete oracles and the fan-out that runs them over one iteration.
The Oracle protocol itself lives in blindspot.types."""

from __future__ import annotations

from blindspot.oracles.crash import CrashOracle
from blindspot.oracles.judge import JudgeOracle
from blindspot.oracles.metamorphic import MetamorphicOracle
from blindspot.oracles.schema import SchemaOracle
from blindspot.llm import DEFAULT_PROVIDER
from blindspot.types import Finding, Oracle, OracleContext

__all__ = [
    "CrashOracle", "SchemaOracle", "MetamorphicOracle", "JudgeOracle",
    "default_oracles", "run_oracles",
]


def default_oracles(*, judge: JudgeOracle | None = None,
                    provider_name: str = DEFAULT_PROVIDER) -> list[Oracle]:
    """Cheapest / most-certain first. Judge last, and only if nothing proved it."""
    return [CrashOracle(), SchemaOracle(), MetamorphicOracle(),
            judge or JudgeOracle(provider_name=provider_name)]


def run_oracles(oracles: list[Oracle], ctx: OracleContext) -> list[Finding]:
    """Run each oracle in order. If any deterministic oracle fires, the judge is
    skipped for this iteration — a model must not opine on what was already proven."""
    findings: list[Finding] = []
    proven = False
    for oracle in oracles:
        if not oracle.deterministic and proven:
            continue
        got = oracle.check(ctx)
        if got:
            findings.extend(got)
            if oracle.deterministic:
                proven = True
    return findings
