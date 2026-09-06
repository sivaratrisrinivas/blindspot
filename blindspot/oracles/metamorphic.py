"""Metamorphic oracle — the heart. Deterministic, needs a baseline run.

Only runs when ctx.mutant.answer_preserving. Compares spec.extract_answer over the
baseline vs the mutant run. A changed answer under an answer-preserving transform is
a proven bug with zero ground truth (the bathroom-scale argument)."""

from __future__ import annotations

from blindspot.types import Finding, OracleContext


# Most semantically significant transform first. The metamorphic signature keys on
# the highest-priority op present, so "homoglyph + cosmetic noise" collapses into one
# class ("the Unicode one") instead of fragmenting per noise combination.
_OP_PRIORITY = (
    "homoglyph_entity",
    "reorder_lines",
    "reformat_currency",
    "reformat_date",
    "synonym_swap",
    "inject_whitespace",
    "pad_context",
)


def _transform_family(lineage: tuple[str, ...]) -> str:
    """One class per dominant relation kind, so 'the Unicode one' is its own cluster
    regardless of which cosmetic transforms rode along with it."""
    for op in _OP_PRIORITY:
        if op in lineage:
            return op
    return "+".join(lineage) if lineage else "identity"


class MetamorphicOracle:
    name = "metamorphic"
    deterministic = True
    needs_baseline = True

    def check(self, ctx: OracleContext) -> list[Finding]:
        if not ctx.mutant.answer_preserving:
            return []
        if ctx.seed_run is None or ctx.spec.extract_answer is None:
            return []
        if ctx.seed_run.terminal != "ok" or ctx.mutant_run.terminal != "ok":
            return []  # a crash under transform is the crash oracle's finding
        before = ctx.spec.extract_answer(ctx.seed_run)
        after = ctx.spec.extract_answer(ctx.mutant_run)
        if before == after:
            return []
        family = _transform_family(ctx.mutant.lineage)
        return [Finding(
            oracle=self.name,
            input=ctx.mutant.text,
            summary=f"answer changed under {family}: {before!r} -> {after!r}",
            severity="semantic",
            evidence={"baseline_input": ctx.seed, "baseline_answer": before,
                      "mutant_answer": after, "transform": list(ctx.mutant.lineage)},
            signature=f"metamorphic:{family}",
        )]
