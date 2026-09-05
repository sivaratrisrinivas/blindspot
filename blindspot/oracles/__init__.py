"""Oracle protocol lives in blindspot.types. This package holds the concrete oracles
and the fan-out that runs them over one iteration."""

from __future__ import annotations

from blindspot.oracles.crash import CrashOracle
from blindspot.oracles.judge import JudgeOracle
from blindspot.oracles.metamorphic import MetamorphicOracle
from blindspot.oracles.schema import SchemaOracle
from blindspot.types import Finding, Oracle, OracleContext


def default_oracles(*, judge: JudgeOracle | None = None) -> list[Oracle]:
    """Cheapest / most-certain first. Judge last, and only if nothing proved it."""
    return [
        CrashOracle(),
        SchemaOracle(),
        MetamorphicOracle(),
        judge or JudgeOracle(),
    ]


def run_oracles(oracles: list[Oracle], ctx: OracleContext) -> list[Finding]:
    """Run each oracle; if a deterministic oracle fires, skip the judge for this
    iteration (a model must not opine on what was already proven)."""
    raise NotImplementedError
