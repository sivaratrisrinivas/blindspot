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
        run = ctx.mutant_run
        if run.terminal in ("error", "timeout"):
            kind = run.error_type or run.terminal
            return [Finding(
                oracle=self.name,
                input=ctx.mutant.text,
                summary=f"agent terminated with {run.terminal} ({kind})",
                severity="crash",
                evidence={"terminal": run.terminal, "error_type": run.error_type,
                          "lineage": list(ctx.mutant.lineage)},
                signature=f"crash:{kind}",
            )]
        if run.retries >= LOOP_RETRY_THRESHOLD or len(run.tool_calls) >= LOOP_STEP_THRESHOLD:
            return [Finding(
                oracle=self.name,
                input=ctx.mutant.text,
                summary=f"suspected loop: {run.retries} retries, {len(run.tool_calls)} tool calls",
                severity="crash",
                evidence={"retries": run.retries, "steps": len(run.tool_calls)},
                signature="crash:loop",
            )]
        return []
