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
    test_path: str,
) -> list[str]:
    """One worker per class. Prompt = minimal repro + the emitted failing test +
    'make it pass without regressing the rest of the suite'. Returns session ids."""
    ids: list[str] = []
    for fc in classes:
        lines = [
            f"Failure class: {fc.label}",
            f"Oracle: {fc.oracle}",
            f"Minimal reproducer input:\n{fc.minimal_repro.input}",
        ]
        if fc.oracle == "metamorphic":
            mutant = fc.minimal_repro.evidence.get("mutant_input")
            lines.append(f"Metamorphic mutant input:\n{mutant}")
            lines.append("Both inputs must produce the same booking.")
        lines.append(f"Failing test: {test_path}")
        lines.append(
            "Fix the target agent under targets/ so the failing test passes. "
            "Do NOT weaken the test or the metamorphic relation. "
            "Keep every other test green. Open a PR."
        )
        ids.append(ao.spawn_worker(f"fix-{fc.id}"[:20], "\n".join(lines)))
    return ids
