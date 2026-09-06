"""JSONL persistence for one fuzz run."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from blindspot.types import FuzzResult


def write_run(run_dir: Path, result: FuzzResult) -> None:
    """findings.jsonl, corpus.jsonl, stats.json. Overwrites; creates run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)

    with (run_dir / "findings.jsonl").open("w") as fh:
        for f in result.findings:
            fh.write(json.dumps({
                "oracle": f.oracle,
                "signature": f.signature,
                "severity": f.severity,
                "summary": f.summary,
                "input": f.input,
                "confidence": f.confidence,
                "evidence": f.evidence,
            }, default=str) + "\n")

    with (run_dir / "corpus.jsonl").open("w") as fh:
        for entry in result.corpus:
            fh.write(json.dumps(entry) + "\n")

    stats = asdict(result.stats)
    stats["bugs_per_min"] = result.stats.bugs_per_min
    (run_dir / "stats.json").write_text(json.dumps(stats, indent=2, default=str))
