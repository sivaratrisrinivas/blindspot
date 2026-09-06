"""Group findings into failure classes, shrink each, rank them."""

from __future__ import annotations

import re

from collections import OrderedDict

from blindspot.minimise import minimise
from blindspot.mutate.deterministic import HOMOGLYPHS, apply_deterministic
from blindspot.oracles.metamorphic import transform_family
from blindspot.types import AgentRun, AgentSpec, FailureClass, Finding

SEVERITY_WEIGHT = {"crash": 4.0, "contract": 3.0, "semantic": 3.5, "quality": 1.5}


def cluster(findings: list[Finding]) -> list[FailureClass]:
    """Group by (oracle, signature). minimal_repro starts as the shortest member;
    class order follows first appearance so runs are reproducible."""
    groups: "OrderedDict[tuple[str, str], list[Finding]]" = OrderedDict()
    for f in findings:
        groups.setdefault((f.oracle, f.signature), []).append(f)

    classes: list[FailureClass] = []
    for (oracle, sig), members in groups.items():
        shortest = min(members, key=lambda m: len(m.input))
        classes.append(FailureClass(
            id=sig.replace(":", "_").replace("+", "_"),
            oracle=oracle,
            label=_label(members),
            severity=members[0].severity,
            members=members,
            minimal_repro=shortest,
        ))
    return classes


def _label(members: list[Finding]) -> str:
    summaries = {m.summary for m in members}
    base = next(iter(summaries))
    return base if len(summaries) == 1 else f"{base}  (+{len(summaries) - 1} variants)"


def minimise_class(fc: FailureClass, spec: AgentSpec, *, unit: str = "word") -> None:
    """Shrink the reproducer in place.

    crash / schema:  ddmin the failing input while the same error / contract miss
                     survives (and the input stays non-degenerate).
    metamorphic:     ddmin the *baseline* input while re-applying the dominant
                     transform to it still flips the agent's answer — this keeps the
                     pair coupled, so the transformed span can never be deleted."""
    if fc.oracle == "crash":
        _minimise_crash(fc, spec, unit)
    elif fc.oracle == "schema":
        _minimise_schema(fc, spec, unit)
    elif fc.oracle == "metamorphic":
        _minimise_metamorphic(fc, spec, unit)
    # judge/quality classes are not deterministically re-checkable; leave as-is


def _minimise_crash(fc: FailureClass, spec: AgentSpec, unit: str) -> None:
    want = fc.minimal_repro.evidence.get("error_type") or _err_of(spec, fc.minimal_repro.input)

    def still_fails(cand: str) -> bool:
        # non-degenerate: keep something that still reads as an invoice attempt
        if not cand.strip() or not any(ch.isdigit() for ch in cand):
            return False
        run = _safe_run(spec, cand)
        return run.terminal in ("error", "timeout") and (run.error_type == want or want is None)

    start = _best_start(fc, still_fails)
    if start is None:
        return
    _apply(fc, minimise(start, still_fails, unit=unit), extra={"error_type": want})


def _minimise_schema(fc: FailureClass, spec: AgentSpec, unit: str) -> None:
    def still_fails(cand: str) -> bool:
        if not cand.strip() or spec.contract is None:
            return False
        run = _safe_run(spec, cand)
        if run.terminal != "ok":
            return False
        try:
            return not bool(spec.contract(run.output))
        except Exception:  # noqa: BLE001
            return True

    start = _best_start(fc, still_fails)
    if start is not None:
        _apply(fc, minimise(start, still_fails, unit=unit))


def _best_start(fc: FailureClass, pred) -> str | None:
    """Shortest member input the predicate already accepts — avoids seeding ddmin
    from a degenerate member it would just return unchanged."""
    for m in sorted(fc.members, key=lambda m: len(m.input)):
        if pred(m.input):
            return m.input
    return fc.minimal_repro.input if pred(fc.minimal_repro.input) else None


def _replay_sites(dominant: str, base: str):
    """Yield every way the dominant answer-preserving transform could be applied to
    `base`. The caller keeps the first one that flips the agent's answer, so the
    minimiser can never delete the span the transform lands on."""
    if dominant == "homoglyph_entity":
        for m in re.finditer(r"[A-Za-z]", base):
            ch = m.group(0)
            if ch in HOMOGLYPHS:
                yield base[:m.start()] + HOMOGLYPHS[ch] + base[m.end():]
    elif dominant == "inject_whitespace":
        for i, ch in enumerate(base):
            if ch == " ":
                yield base[:i] + "  " + base[i + 1:]
    else:
        alt = apply_deterministic(dominant, base)
        if alt != base:
            yield alt


def _minimise_metamorphic(fc: FailureClass, spec: AgentSpec, unit: str) -> None:
    if spec.extract_answer is None:
        return
    lineage = tuple(fc.minimal_repro.evidence.get("transform", ()))
    dominant = transform_family(lineage)
    baseline = fc.minimal_repro.evidence.get("baseline_input") or fc.minimal_repro.input
    unit = "line" if dominant == "reorder_lines" else unit

    def paired(base: str):
        """(mutant, before, after) for the first transform site that flips the answer."""
        if not base.strip():
            return None
        a = spec.extract_answer(_safe_run(spec, base))
        if a is None:
            return None
        for mut in _replay_sites(dominant, base):
            b = spec.extract_answer(_safe_run(spec, mut))
            if b != a:
                return mut, a, b
        return None

    if paired(baseline) is None:
        return  # can't replay this transform deterministically; keep the raw pair
    res = minimise(baseline, lambda s: paired(s) is not None, unit=unit)
    got = paired(res.minimal)
    if got is None:
        return
    mut_min, a, b = got
    fc.minimal_repro = Finding(
        oracle="metamorphic",
        input=res.minimal,
        summary=f"under {dominant}: {a!r} -> {b!r}",
        severity="semantic",
        evidence={**fc.minimal_repro.evidence, "baseline_input": res.minimal,
                  "mutant_input": mut_min, "baseline_answer": a, "mutant_answer": b,
                  "transform": [dominant], "reduction_ratio": res.reduction_ratio,
                  "original_len": res.original_len, "minimal_len": res.minimal_len},
        confidence=1.0,
        signature=fc.minimal_repro.signature,
    )


def _apply(fc: FailureClass, res, *, extra: dict | None = None) -> None:
    fc.minimal_repro = Finding(
        oracle=fc.minimal_repro.oracle,
        input=res.minimal,
        summary=fc.minimal_repro.summary,
        severity=fc.minimal_repro.severity,
        evidence={**fc.minimal_repro.evidence, **(extra or {}),
                  "reduction_ratio": res.reduction_ratio,
                  "original_len": res.original_len, "minimal_len": res.minimal_len},
        confidence=fc.minimal_repro.confidence,
        signature=fc.minimal_repro.signature,
    )


def _err_of(spec: AgentSpec, text: str) -> str | None:
    return _safe_run(spec, text).error_type


def _safe_run(spec: AgentSpec, text: str) -> AgentRun:
    try:
        return spec.entrypoint(text)
    except Exception as exc:  # noqa: BLE001
        return AgentRun(input=text, output=None, tool_calls=(), terminal="error",
                        error_type=type(exc).__name__)


def rank(classes: list[FailureClass]) -> list[FailureClass]:
    """rank_score = severity weight * distinct signatures in the members * (1 / minimal length).
    A shorter reproducer and a broader spread both raise the score."""
    ranked = []
    for fc in classes:
        distinct = len({m.signature for m in fc.members}) or 1
        n_members = len(fc.members)
        min_len = max(len(fc.minimal_repro.input), 1)
        fc.rank_score = (
            SEVERITY_WEIGHT.get(fc.severity, 1.0)
            * (distinct + n_members ** 0.5)
            * (40.0 / min_len)
        )
        ranked.append(fc)
    return sorted(ranked, key=lambda c: c.rank_score, reverse=True)
