"""JSONL persistence + the before/after metrics table across agents.

Built as a re-runnable script, not hand assembly (principle: build the lever)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from blindspot.types import FuzzResult

_COLUMNS = (
    "agent",
    "inputs",
    "behaviours",
    "classes",
    "crash+timeout",
    "bugs/min",
    "llm calls",
    "$ cost",
)

_NOTE = (
    "accuracy = booking correctness; reliability = crash+timeout count; "
    "cost = $/run; speed = bugs/min"
)


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


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _row(run_dir: Path) -> list[str]:
    agent = run_dir.name.split("-")[0]
    stats_path = run_dir / "stats.json"
    if not stats_path.exists():
        return [agent, "(no data)", "", "", "", "", "", ""]

    stats = json.loads(stats_path.read_text())
    findings = _read_jsonl(run_dir / "findings.jsonl")
    classes = len({f.get("signature", "") for f in findings})
    crashes = sum(1 for f in findings if f.get("severity") == "crash")

    return [
        agent,
        str(stats.get("iterations", 0)),
        str(stats.get("unique_behaviours", 0)),
        str(classes),
        str(crashes),
        f"{stats.get('bugs_per_min', 0.0):.2f}",
        str(stats.get("llm_calls", 0)),
        f"${stats.get('cost_usd', 0.0):.4f}",
    ]


def metrics_table(run_dirs: list[Path]) -> str:
    """Plain-text aligned table, one row per run dir. Copy-pasteable into markdown.

    Columns labelled with Track 1's vocabulary: accuracy, reliability, cost, speed.
    """
    rows = [list(_COLUMNS)] + [_row(Path(d)) for d in run_dirs]
    widths = [max(len(r[i]) for r in rows) for i in range(len(_COLUMNS))]

    def fmt(r: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip()

    lines = [fmt(rows[0]), "  ".join("-" * w for w in widths)]
    lines += [fmt(r) for r in rows[1:]]
    lines += ["", _NOTE]
    return "\n".join(lines)
