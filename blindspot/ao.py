"""Agent Orchestrator client — thin HTTP adapter over the local daemon (port 3011).
One worker session per failure class; that turns the mandatory AO requirement into
the architecture."""

from __future__ import annotations

import os
import time

import httpx

from blindspot.types import AgentSpec, FailureClass

class AOClient:
    """The injectable seam for dispatch_fixes. Spawning is the only call the fix
    loop makes: workers are watched on the AO board, not polled from here."""

    def __init__(self, base_url: str | None = None, project: str = "blindspot") -> None:
        base_url = base_url or f"http://localhost:{os.environ.get('AO_PORT', '3011')}"
        self._c = httpx.Client(base_url=base_url, timeout=httpx.Timeout(90.0, connect=10.0))
        self.project = project

    def spawn_worker(self, name: str, prompt: str, *, model: str = "sonnet") -> str:
        """POST /api/v1/sessions -> session id. Retries once on a slow daemon."""
        body = {
            "projectId": self.project,
            "harness": "claude-code",
            "kind": "worker",
            "model": model,
            "displayName": name[:20],
            "prompt": prompt,
        }
        for attempt in range(2):
            try:
                resp = self._c.post("/api/v1/sessions", json=body)
                return resp.json()["session"]["id"]
            except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                if attempt:
                    raise
                time.sleep(5)
        raise RuntimeError("unreachable")


def dispatch_fixes(
    classes: list[FailureClass],
    spec: AgentSpec,
    ao: AOClient,
    *,
    test_path: str | None = None,
    spawn_gap_s: float = 12.0,
) -> list[str]:
    """One AO worker per failure class. The prompt is self-contained — the emitted
    suite lives under run/ (gitignored) and is not on the worker's branch, so the
    reproducer and the exact invariant are embedded and the worker writes its own
    regression test under tests/. Returns the spawned session ids."""
    module = f"targets/{spec.name}_agent.py"
    ids: list[str] = []
    for i, fc in enumerate(classes):
        if i:
            time.sleep(spawn_gap_s)  # the daemon drops agents spawned back-to-back
        repro = fc.minimal_repro.input
        lines = [
            f"Blindspot found a failure class in the {spec.name} agent ({module}).",
            f"Class: {fc.label}",
            "",
            f"Reproducer input:\n{repro!r}",
        ]
        if fc.oracle == "crash":
            et = fc.minimal_repro.evidence.get("error_type", "an exception")
            lines += [
                "",
                f"On this input the agent raises {et} instead of completing a booking.",
                "Fix the agent so this input produces a valid booking (or a clean, "
                "explicit refusal via terminal='refused') — never an unhandled exception.",
            ]
        elif fc.oracle == "metamorphic":
            mut = fc.minimal_repro.evidence.get("mutant_input")
            a = fc.minimal_repro.evidence.get("baseline_answer")
            b = fc.minimal_repro.evidence.get("mutant_answer")
            lines += [
                "",
                f"This cosmetic variant must book identically but does not:\n{mut!r}",
                f"  original books GL {a!r}, variant books GL {b!r}.",
                "The transform (Unicode look-alike / whitespace / currency reformat / "
                "line reorder / synonym) does not change the real invoice, so both "
                "inputs must book to the SAME GL account. Fix the agent so they do — "
                "by normalising the input, not by special-casing this string.",
            ]
        elif fc.oracle in ("schema", "contract"):
            lines += ["", "The agent's output violates its contract on this input. "
                      "Fix the agent so the contract holds."]
        else:  # judge / quality
            why = fc.minimal_repro.evidence.get("why", fc.label)
            lines += ["", f"A reviewer flagged: {why}", "Fix the agent's behaviour on "
                      "this kind of request."]
        lines += [
            "",
            "Then: add a focused regression test to tests/ that asserts the fixed "
            "behaviour on the reproducer (and, for metamorphic, that both inputs book "
            "the same account). Run `python -m pytest -q` and keep every existing test "
            "green. Do not weaken any assertion. Commit and open a PR.",
        ]
        ids.append(ao.spawn_worker(f"fix-{fc.id}"[:20], "\n".join(lines)))
    return ids
