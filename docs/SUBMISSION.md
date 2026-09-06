# Submission checklist — Syndicate by Maximor, Track 1

## What to submit (confirm the exact format in Discord `#syndicate-project-showcase`)

- [ ] repo link: https://github.com/sivaratrisrinivas/blindspot
- [ ] demo video (≤ 3 min). Script in `docs/DESIGN.md` §12.
- [ ] writeup naming AO usage. Draft in `docs/AO_USAGE.md`.

## The demo, in order

1. `blindspot invoice -n 600 --no-judge` — deterministic, ~10s, finds 6 classes,
   live counters, writes a pytest file. This is the reveal.
2. Zoom the homoglyph class: `Acme Corp $12,500.00 2026-04-01` books to GL 1100,
   `Αcme Corp $12,500.00 2026-04-01` books to GL 6000. One Unicode character.
3. `blindspot invoice --fix --fix-limit 3` — dispatches AO fix workers, one per
   class, 12s apart. Show them on the Kanban board (desktop GUI). PR #7 is a
   completed example if a live worker stalls.
4. `python scripts/metrics.py` — the before/after table, 6 classes → 0.

## Numbers to state

| claim | evidence |
|---|---|
| finds failure classes an eval set misses | 6 planted invoice blind spots, `gate3_recall.py` catches 6/6 across 8 seeds |
| proven bugs, no ground truth | metamorphic oracle, `gate1_metamorphic.py`: 11/11 flagged violations genuine, 0 false positives |
| coverage guidance | `gate2_coverage.py`: measured, does NOT beat random at this scale — say so |
| before / after | `metrics.py`: invoice 44% eval failure rate → 0%, 56% → 100% accuracy |
| AO is the architecture | 5 module PRs + fix PRs; every module built through a worker session |

## Pre-record checklist

- [ ] `AO_PORT=3011 ao daemon` running; `ao status --json` healthy
- [ ] desktop GUI open for the Kanban shot:
      `~/.local/opt/ao-dl/extracted/usr/lib/agent-orchestrator/agent-orchestrator --no-sandbox`
- [ ] `git status` clean, `origin/main` pushed
- [ ] `python -m pytest -q` green (31 tests)
- [ ] `blindspot invoice -n 600 --no-judge` runs clean end to end
- [ ] `GROQ_API_KEY` set (only needed for `--semantic` / `blindspot support`)
- [ ] optional: `NEATLOGS_API_KEY` for the traces shot; `TENSORMUX_API_KEY`

## Known gaps, stated plainly in the video

- Coverage guidance doesn't beat random at toy scale. Reported, not hidden.
- Target agents are toys, so the improvement numbers are toy numbers.
- The judge oracle is probabilistic; on the support agent it leaves a residual
  false positive or two on the repaired agent.
- AO workers spawned back-to-back sometimes stall; the dispatch spaces them 12s
  apart and the mechanism is proven by the merged and open PRs.

## Post-demo

- [ ] merge the fix PRs (or leave open and note them in the writeup)
- [ ] submit before 02:30 IST, not 03:25
