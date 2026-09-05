"""Group findings into failure classes, shrink each, rank them."""

from __future__ import annotations

from blindspot.minimise import minimise
from blindspot.types import AgentSpec, FailureClass, Finding

SEVERITY_WEIGHT = {"crash": 4.0, "contract": 3.0, "semantic": 3.5, "quality": 1.5}


def cluster(findings: list[Finding]) -> list[FailureClass]:
    """Group by (oracle, signature). minimal_repro starts as the shortest member."""
    raise NotImplementedError


def minimise_class(fc: FailureClass, spec: AgentSpec) -> None:
    """Build a still_fails closure (re-run agent, re-run the same oracle, same
    signature comes back) and ddmin fc.minimal_repro.input in place."""
    raise NotImplementedError


def rank(classes: list[FailureClass]) -> list[FailureClass]:
    """rank_score = severity weight * distinct signatures * (1 / minimal length).
    Returns a new list, sorted descending."""
    raise NotImplementedError
