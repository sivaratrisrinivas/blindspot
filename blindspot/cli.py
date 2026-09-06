"""`blindspot invoice` — point it at an agent, watch it find the failures you never
imagined, then get the regression suite you never wrote."""

from __future__ import annotations

import argparse
import importlib
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table

from blindspot import obs
from blindspot.cluster import cluster, minimise_class, rank
from blindspot.oracles import default_oracles
from blindspot.runner import run_fuzz
from blindspot.types import AgentSpec, FuzzConfig, Granularity, RunStats

console = Console()


def _load_spec(ref: str) -> AgentSpec:
    """Accept 'invoice', 'targets.specs:INVOICE', or 'targets/specs.py:INVOICE'."""
    if ":" in ref:
        mod, attr = ref.split(":", 1)
        mod = mod.removesuffix(".py").replace("/", ".")
    else:
        mod, attr = "targets.specs", ref.upper()
    obj = getattr(importlib.import_module(mod), attr)
    if not isinstance(obj, AgentSpec):
        raise SystemExit(f"{ref} is not an AgentSpec")
    return obj


def _counter(spec_name: str, stats: RunStats, classes: int) -> Table:
    t = Table.grid(padding=(0, 2))
    t.add_column(justify="right", style="bold cyan")
    t.add_column()
    t.add_row("target", spec_name)
    t.add_row("inputs tried", f"{stats.iterations}")
    t.add_row("new behaviours", f"{stats.unique_behaviours}")
    t.add_row("failure classes", f"[bold red]{classes}[/]" if classes else "0")
    t.add_row("elapsed", f"{stats.wall_s:4.1f}s")
    return t


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="blindspot", description=__doc__)
    ap.add_argument("spec", help="agent spec: 'invoice', or 'module:ATTR'")
    ap.add_argument("-n", "--iterations", type=int, default=600)
    ap.add_argument("-p", "--parallelism", type=int, default=8)
    ap.add_argument("-s", "--seed", type=int, default=0)
    ap.add_argument("-g", "--granularity", choices=[g.value for g in Granularity], default="medium")
    ap.add_argument("--judge-budget", type=int, default=30)
    ap.add_argument("--semantic", action="store_true", help="add Groq semantic mutations (slower, ~2s/call)")
    ap.add_argument("--no-judge", action="store_true", help="deterministic oracles only")
    ap.add_argument("--time-budget", type=float, default=None, help="stop after N seconds")
    ap.add_argument("--fix", action="store_true", help="dispatch one AO worker per failure class")
    ap.add_argument("--fix-limit", type=int, default=0, help="cap how many fix workers --fix spawns (0 = all)")
    ap.add_argument("--out", default="run", help="output directory root")
    args = ap.parse_args(argv)

    import os
    if not args.semantic:
        os.environ["BLINDSPOT_NO_SEMANTIC"] = "1"

    traced = obs.init()
    spec = _load_spec(args.spec)
    cfg = FuzzConfig(
        iterations=args.iterations, parallelism=args.parallelism, seed=args.seed,
        granularity=Granularity(args.granularity), judge_budget=args.judge_budget,
        time_budget_s=args.time_budget,
    )
    oracles = [o for o in default_oracles() if not (args.no_judge and o.name == "judge")]

    run_dir = Path(args.out) / f"{spec.name}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    run_dir.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold]Blindspot → {spec.name} agent")
    console.print(f"seeds: {len(spec.seeds)}   oracles: {', '.join(o.name for o in oracles)}"
                  + ("   [dim]· neatlogs on[/]" if traced else "") + "\n")

    state = {"classes": 0}
    with Live(_counter(spec.name, RunStats(), 0), console=console, refresh_per_second=12) as live:
        def on_iter(stats: RunStats) -> None:
            live.update(_counter(spec.name, stats, state["classes"]))

        result = run_fuzz(spec, cfg, oracles=oracles, on_iteration=on_iter)
        classes = rank(cluster(result.findings))
        state["classes"] = len(classes)
        live.update(_counter(spec.name, result.stats, len(classes)))

    for fc in classes:
        minimise_class(fc, spec)

    _reveal(spec, result.stats, classes)

    test_path = run_dir / f"test_blindspot_{spec.name}.py"
    try:
        from blindspot.emit import emit_pytest
        emit_pytest(classes, spec, test_path)
        console.print(f"\n[green]wrote[/] {test_path}  ({_count_tests(classes)} regression tests)")
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[yellow]emit skipped:[/] {exc}")

    try:
        from blindspot.report import write_run
        write_run(run_dir, result)
        console.print(f"[green]wrote[/] {run_dir}/findings.jsonl")
    except Exception:  # noqa: BLE001
        _write_findings_fallback(run_dir, result)

    if args.fix:
        picked = classes[: args.fix_limit] if args.fix_limit else classes
        _dispatch(picked, spec, str(test_path))

    obs.flush()
    return 0


def _reveal(spec: AgentSpec, stats: RunStats, classes: list) -> None:
    console.print()
    console.rule(f"[bold red]{len(classes)} failure classes the tests never covered")
    for i, fc in enumerate(classes, 1):
        ev = fc.minimal_repro.evidence
        console.print(f"\n[bold]{i}. {fc.oracle}[/]  [dim]{fc.id}[/]   "
                      f"[dim](rank {fc.rank_score:.0f}, {len(fc.members)} inputs)[/]")
        console.print(f"   {fc.minimal_repro.summary}")
        console.print(f"   [cyan]repro[/]  {fc.minimal_repro.input!r}")
        if ev.get("mutant_input"):
            console.print(f"   [cyan]after[/]  {ev['mutant_input']!r}   "
                          f"[red]{ev.get('baseline_answer')} → {ev.get('mutant_answer')}[/]")
        if ev.get("reduction_ratio"):
            console.print(f"   [dim]shrunk {ev.get('original_len','?')} → "
                          f"{ev.get('minimal_len','?')} chars ({ev['reduction_ratio']*100:.0f}% smaller)[/]")
    console.print(
        f"\n[dim]{stats.iterations} inputs · {stats.unique_behaviours} behaviours · "
        f"{stats.bugs_per_min:.0f} bugs/min · {stats.llm_calls} llm calls · "
        f"${stats.cost_usd:.4f}[/]"
    )


def _count_tests(classes: list) -> int:
    return sum(min(len({m.input for m in fc.members}), 8) for fc in classes) or 1


def _write_findings_fallback(run_dir: Path, result) -> None:
    import json
    with (run_dir / "findings.jsonl").open("w") as fh:
        for f in result.findings:
            fh.write(json.dumps({
                "oracle": f.oracle, "signature": f.signature, "severity": f.severity,
                "summary": f.summary, "input": f.input, "confidence": f.confidence,
            }) + "\n")
    (run_dir / "stats.json").write_text(json.dumps(result.stats.__dict__, default=str, indent=2))


def _dispatch(classes: list, spec: AgentSpec, test_path: str) -> None:
    try:
        from blindspot.ao import AOClient, dispatch_fixes
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]--fix unavailable:[/] {exc}")
        return
    ao = AOClient()
    ids: list[str] = []
    try:
        ids = dispatch_fixes(classes, spec, ao, test_path=test_path)
    except Exception as exc:  # noqa: BLE001 — partial dispatch is still useful
        console.print(f"[yellow]dispatch interrupted after {len(ids)}:[/] {exc}")
    if ids:
        console.print(f"\n[green]dispatched {len(ids)} AO fix workers:[/] {', '.join(ids)}")
    console.print("[dim]watch them on the AO board; merge the PRs they open[/]")


if __name__ == "__main__":
    raise SystemExit(main())
