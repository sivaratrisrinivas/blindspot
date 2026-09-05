"""Crash / hang oracle. Deterministic, free, no baseline."""

from __future__ import annotations

from blindspot.types import Finding, OracleContext

LOOP_RETRY_THRESHOLD = 6
LOOP_STEP_THRESHOLD = 40


class CrashOracle:
    name = "crash"
    deterministic = True
    needs_baseline = False

    def check(self, ctx: OracleContext) -> list[Finding]:
        raise NotImplementedError
