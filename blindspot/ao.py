"""Agent Orchestrator client — thin HTTP adapter over the local daemon (port 3011).
One worker session per failure class; that turns the mandatory AO requirement into
the architecture."""

from __future__ import annotations

import os
import time

import httpx

from blindspot.types import AgentSpec, FailureClass

_TERMINAL = ("mergeable", "blocked", "conflicted")


class AOClient:
    def __init__(self, base_url: str | None = None, project: str = "blindspot") -> None:
        base_url = base_url or f"http://localhost:{os.environ.get('AO_PORT', '3011')}"
        self._c = httpx.Client(base_url=base_url, timeout=30.0)
        self.project = project

    def spawn_worker(self, name: str, prompt: str, *, model: str = "sonnet") -> str:
        """POST /api/v1/sessions -> session id."""
        resp = self._c.post(
            "/api/v1/sessions",
            json={
                "projectId": self.project,
                "harness": "claude-code",
                "kind": "worker",
                "model": model,
                "displayName": name[:20],
                "prompt": prompt,
            },
        )
        return resp.json()["session"]["id"]

    def send(self, sid: str, msg: str) -> None:
        """POST /api/v1/sessions/{id}/send."""
        self._c.post(f"/api/v1/sessions/{sid}/send", json={"message": msg})

    def get(self, sid: str) -> dict:
        """GET /api/v1/sessions/{id}."""
        return self._c.get(f"/api/v1/sessions/{sid}").json()["session"]

    def list(self) -> list[dict]:
        """GET /api/v1/sessions."""
        return self._c.get("/api/v1/sessions").json()["sessions"]

    def poll(
        self,
        sid: str,
        *,
        until: tuple[str, ...] = _TERMINAL,
        timeout_s: float = 900,
        interval_s: float = 15,
    ) -> dict:
        """Block until the session reaches a terminal status, opens a PR, or times out."""
        start = time.monotonic()
        while True:
            session = self.get(sid)
            done = (
                session.get("status") in until
                or bool(session.get("prs"))
                or time.monotonic() - start > timeout_s
            )
            if done:
                return session
            time.sleep(interval_s)

    def close(self) -> None:
        self._c.close()


def dispatch_fixes(
    classes: list[FailureClass],
    spec: AgentSpec,
    ao: AOClient,
    *,
    test_path: str | None = None,
) -> list[str]:
    """One AO worker per failure class. The prompt is self-contained — the emitted
    suite lives under run/ (gitignored) and is not on the worker's branch, so the
    reproducer and the exact invariant are embedded and the worker writes its own
    regression test under tests/. Returns the spawned session ids."""
    module = f"targets/{spec.name}_agent.py"
    ids: list[str] = []
    for fc in classes:
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
