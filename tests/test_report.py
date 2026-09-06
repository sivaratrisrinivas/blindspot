"""report.py: JSONL persistence + cross-agent metrics table."""

from __future__ import annotations

import json

from blindspot.report import write_run
from blindspot.types import Finding, FuzzResult, RunStats


def _result() -> FuzzResult:
    findings = [
        Finding(
            oracle="crash",
            input="drop table bookings;",
            summary="target raised KeyError",
            severity="crash",
            evidence={"mutant": "boom", "error": "KeyError"},
            signature="crash:KeyError",
        ),
        Finding(
            oracle="metamorphic",
            input="book me a flt to NYC",
            summary="answer changed under paraphrase",
            severity="semantic",
            evidence={"baseline": "NYC", "mutant": "LAX"},
            confidence=0.7,
            signature="metamorphic:answer-drift",
        ),
    ]
    stats = RunStats(
        iterations=40,
        unique_behaviours=12,
        findings_total=2,
        per_oracle={"crash": 1, "metamorphic": 1},
        llm_calls=3,
        cost_usd=0.0021,
        wall_s=30.0,
    )
    return FuzzResult(
        findings=findings,
        corpus=["seed one", "seed two mutated", "seed three"],
        signatures_seen={"crash:KeyError", "metamorphic:answer-drift"},
        stats=stats,
    )


def test_write_run_emits_three_files(tmp_path):
    run_dir = tmp_path / "invoice-20260906T000000Z"
    write_run(run_dir, _result())

    findings_p = run_dir / "findings.jsonl"
    corpus_p = run_dir / "corpus.jsonl"
    stats_p = run_dir / "stats.json"
    assert findings_p.exists() and corpus_p.exists() and stats_p.exists()

    lines = findings_p.read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert set(obj) >= {"oracle", "signature", "severity", "summary", "input",
                            "confidence", "evidence"}

    assert [json.loads(x) for x in corpus_p.read_text().splitlines()] == [
        "seed one", "seed two mutated", "seed three",
    ]

    stats = json.loads(stats_p.read_text())
    assert stats["iterations"] == 40
    assert "bugs_per_min" in stats
    assert stats["bugs_per_min"] == 4.0


def test_write_run_overwrites(tmp_path):
    run_dir = tmp_path / "invoice-x"
    write_run(run_dir, _result())
    write_run(run_dir, _result())
    assert len((run_dir / "findings.jsonl").read_text().splitlines()) == 2
