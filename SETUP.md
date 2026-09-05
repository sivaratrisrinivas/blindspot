# Local setup (WSL2 / Ubuntu 22.04)

Project root: `~/workspace/github.com/sivaratrisrinivas/blindspot`

## AO (Agent Orchestrator)
- CLI/daemon: `~/.local/bin/ao` (extracted from the v0.12.11 .deb, no sudo, no libfuse2)
- Desktop GUI: `~/.local/opt/ao-dl/extracted/usr/lib/agent-orchestrator/agent-orchestrator --no-sandbox`
  Confirmed rendering under WSLg. Use this, not `~/.ao/agent-orchestrator.AppImage` (needs libfuse2).

Port 3001 is taken by another dev server on this box, so AO runs on 3011.
`export AO_PORT=3011` is in `~/.bashrc`.

    AO_PORT=3011 nohup ao daemon > ~/.ao/daemon.log 2>&1 &
    curl -s 127.0.0.1:3011/readyz

`ao start` does NOT run headless. It downloads and opens the desktop app. Use `ao daemon`.

Verified: `GET /api/v1/sessions`, `GET /api/v1/projects`, `ao spawn --prompt --name --harness --model`.
`ao doctor` all green. Harnesses installed + authorized: claude-code, codex.

## Inference: three lanes, do not mix them up

Claude Code and Codex here are **subscription accounts, not API keys**. There is no
ANTHROPIC_API_KEY or OPENAI_API_KEY on this machine and there will not be one.
That splits inference into three lanes.

### Lane 1 — fuzzing loop (high volume, latency-critical): Groq
`GROQ_API_KEY` is already set in `~/.bashrc`. OpenAI-compatible endpoint:
`https://api.groq.com/openai/v1`. Measured round trips:

| model | latency | tool calls |
|---|---|---|
| qwen/qwen3.8-27b | 0.39s | yes |
| openai/gpt-oss-120b | 0.44s | yes |
| openai/gpt-oss-20b | 0.53s | yes |

Use this for the systems under test and for the semantic mutator. Nothing else is fast enough.

### Lane 2 — differential oracle: two Groq models, optionally via TensorMux
`qwen/qwen3.8-27b` and `openai/gpt-oss-120b` already disagreed on the first tool-call test
(GL account `1100` vs `"Office Supplies"`), so the oracle has real signal on day one.
Route through TensorMux for the sponsor story and for failover.

### Lane 3 — AO patch workers: the subscription CLIs
`claude -p "..." --model haiku --output-format json` works headless on subscription auth.
So does `codex exec`. Measured: 8.2s for one call, 20.8s for six in parallel (~3.5s effective),
and each spawns a full CLI process (6 calls burned 59s user + 50s sys CPU).

**Far too slow for the fuzz loop. Perfect for the patch workers**, of which there are only
about seven per run, and they cost nothing at the margin on a subscription.

## Python
uv, Python 3.12.10. neatlogs, openai, anthropic, pydantic, httpx, rich, pytest, python-dotenv.
The `openai` SDK points at Groq by setting `base_url`; no separate client needed.

## Still needed
- `NEATLOGS_API_KEY` — https://app.neatlogs.com/
- `TENSORMUX_API_KEY` — https://app.tensormux.com/ ($5 free credit, no card)

Both are sponsor tools and both are worth real points. Neither blocks starting the build:
Groq alone covers lanes 1 and 2, and AO covers lane 3.
