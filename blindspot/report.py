"""JSONL persistence + the before/after metrics table across agents.
Built as a re-runnable script, not hand assembly (principle: build the lever)."""

from __future__ import annotations

from pathlib import Path

from blindspot.types import FuzzResult


def write_run(run_dir: Path, result: FuzzResult) -> None:
    """findings.jsonl, corpus.jsonl, stats.json."""
    raise NotImplementedError


def metrics_table(run_dirs: list[Path]) -> str:
    """Per agent: failure rate before/after, p95 latency, $/task, crash+timeout count,
    unique classes vs random baseline, minimiser reduction ratio, patch acceptance,
    regression rate. Columns labelled with Track 1's vocabulary: accuracy, reliability,
    cost, speed."""
    raise NotImplementedError
