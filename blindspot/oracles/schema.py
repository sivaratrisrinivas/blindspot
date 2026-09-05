"""Output-contract oracle. Deterministic, no baseline. Uses spec.contract."""

from __future__ import annotations

from blindspot.types import Finding, OracleContext


class SchemaOracle:
    name = "schema"
    deterministic = True
    needs_baseline = False

    def check(self, ctx: OracleContext) -> list[Finding]:
        raise NotImplementedError
