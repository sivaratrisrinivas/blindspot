"""Output-contract oracle. Deterministic, no baseline. Uses spec.contract.
Only runs on a cleanly-terminated run — a contract miss on a crashed run is the
crash oracle's finding, not a second bug."""

from __future__ import annotations

from blindspot.types import Finding, OracleContext


class SchemaOracle:
    name = "schema"
    deterministic = True
    needs_baseline = False

    def check(self, ctx: OracleContext) -> list[Finding]:
        spec = ctx.spec
        run = ctx.mutant_run
        if spec.contract is None or run.terminal != "ok":
            return []
        try:
            ok = bool(spec.contract(run.output))
        except Exception as exc:  # noqa: BLE001 — a contract that throws is itself a violation
            ok = False
            run_note = f"contract raised {type(exc).__name__}"
        else:
            run_note = "contract returned False"
        if ok:
            return []
        return [Finding(
            oracle=self.name,
            input=ctx.mutant.text,
            summary=f"output violates contract: {run_note}",
            severity="contract",
            evidence={"output": run.output, "note": run_note,
                      "lineage": list(ctx.mutant.lineage)},
            signature="schema:contract",
        )]
