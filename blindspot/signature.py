"""Behaviour signature: a pure hash, no model. AFL's 'new coverage -> keep input',
moved to behaviour space."""

from __future__ import annotations

from blindspot.types import AgentRun, Granularity


def _retry_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 2:
        return "1-2"
    if n <= 5:
        return "3-5"
    return "6+"


def _arg_shape(args: dict, granularity: Granularity) -> object:
    """Keys and value *types*, never values. FINE keeps nested key sets; COARSE keeps arity only."""
    raise NotImplementedError


def behaviour_signature(run: AgentRun, *, granularity: Granularity = Granularity.MEDIUM) -> str:
    """SHA1 over: ordered (tool name, arg shape) pairs, terminal class, error class,
    retry bucket, escalation flag."""
    raise NotImplementedError
