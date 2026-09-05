"""Metamorphic oracle — the heart. Deterministic, needs a baseline run.

Only runs when ctx.mutant.answer_preserving. Compares spec.extract_answer over the
baseline vs the mutant run. A changed answer under an answer-preserving transform is
a proven bug with zero ground truth (the bathroom-scale argument)."""

from __future__ import annotations

from blindspot.types import Finding, OracleContext


class MetamorphicOracle:
    name = "metamorphic"
    deterministic = True
    needs_baseline = True

    def check(self, ctx: OracleContext) -> list[Finding]:
        raise NotImplementedError
