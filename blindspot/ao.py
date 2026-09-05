"""Agent Orchestrator client — thin HTTP adapter over the local daemon (port 3011).
One worker session per failure class; that turns the mandatory AO requirement into
the architecture."""

from __future__ import annotations

import os

import httpx

from blindspot.types import AgentSpec, FailureClass

DEFAULT_BASE_URL = f"http://localhost:{os.environ.get('AO_PORT', '3011')}"


class AOClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, project: str = ".") -> None:
        raise NotImplementedError

    def spawn_worker(self, name: str, prompt: str, *, model: str = "sonnet") -> str:
        """POST /api/v1/sessions -> session id."""
        raise NotImplementedError

    def send(self, sid: str, msg: str) -> None:
        """POST /api/v1/sessions/{id}/send."""
        raise NotImplementedError

    def get(self, sid: str) -> dict:
        """GET /api/v1/sessions/{id}."""
        raise NotImplementedError

    def list(self) -> list[dict]:
        """GET /api/v1/sessions."""
        raise NotImplementedError


def dispatch_fixes(
    classes: list[FailureClass],
    spec: AgentSpec,
    ao: AOClient,
    *,
    test_path: str,
) -> list[str]:
    """One worker per class. Prompt = minimal repro + the emitted failing test +
    'make it pass without regressing the rest of the suite'. Returns session ids."""
    raise NotImplementedError
