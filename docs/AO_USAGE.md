# Agent Orchestrator usage

The hackathon rule is that every participant uses AO while building. Blindspot uses
it two ways: AO built the tool, and the tool drives AO.

## AO built the tool

After the design sketch (`docs/DESIGN.md`, written in the orchestrating session),
every implementation module was filled in by an AO worker session spawned with
`ao spawn --harness claude-code --model sonnet`. Each worker got a tight prompt
against the frozen contract, worked in its own git worktree, ran its own tests, and
opened a PR. The orchestrating session reviewed and merged.

| Session | Module | Outcome |
|---|---|---|
| blindspot-1 | `signature.py` + tests | PR #1. Branched from a stale `origin/main` (my mistake: I hadn't pushed the scaffold), so the PR carried the whole scaffold as a diff. Closed it, cherry-picked the two real files onto `main`, kept the worker's work. |
| blindspot-3 | `emit.py` + tests | PR #2, merged |
| blindspot-5 | `minimise.py` + tests | PR #3, merged. ddmin, test-first. |
| blindspot-8 | `ao.py` + tests | PR #4, merged. The client this tool uses to drive AO. |
| blindspot-9 | `report.py` + tests | PR #5, merged |
| blindspot-10 | fix worker: `crash:DateFormatError` | PR #6, open. Held open on purpose so the buggy agent stays the demo's "before" state. |
| blindspot-2, 4, 6, 7 | (various) | Failed to attach an agent. The daemon's ACP `session/new` handshake timed out during a period of daemon restart churn. Killed and re-spawned. Worth reporting to the AO team. |

Six productive worker sessions, five PRs, four merged plus one salvaged, plus the
open fix PR. Every line of `blindspot/` except the type sketch came through a
session.

The one process lesson: push `origin/main` before spawning a worker. AO resolves
the branch base from the remote at spawn time, and an unpushed local commit means
the worker branches from the wrong place.

## The tool drives AO

`blindspot <spec> --fix` calls `dispatch_fixes()` in `blindspot/ao.py`, which spawns
one worker per ranked failure class over the daemon's HTTP API
(`POST /api/v1/sessions`). Each worker gets the minimal reproducer and the exact
invariant it broke, fixes the target agent, adds a regression test, and opens a PR.

A run that finds seven failure classes is seven worker sessions on the Kanban
board, moving from building to in-review to ready. That is the demo's second half.

## Running the daemon

```bash
export AO_PORT=3011           # 3001 was taken on this machine
AO_PORT=3011 ao daemon        # headless; `ao start` opens the desktop app instead
ao status --json
```
