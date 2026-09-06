"""Behaviour signature: a pure hash, no model. AFL's 'new coverage -> keep input',
moved to behaviour space."""

from __future__ import annotations

import hashlib

from blindspot.types import AgentRun, Granularity


def _retry_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 2:
        return "1-2"
    if n <= 5:
        return "3-5"
    return "6+"


def _len_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 3:
        return "2-3"
    if n <= 7:
        return "4-7"
    return "8+"


def _fine_value(value: object) -> object:
    """Recursive shape of a single value: dicts -> sorted nested key/type tuples,
    lists -> (sorted element types, length bucket), scalars -> type name."""
    if isinstance(value, dict):
        return ("dict", tuple(sorted(
            (str(k), _fine_value(v)) for k, v in value.items()
        )))
    if isinstance(value, (list, tuple)):
        elem_types = tuple(sorted({type(v).__name__ for v in value}))
        return ("list", elem_types, _len_bucket(len(value)))
    return type(value).__name__


def _arg_shape(args: dict, granularity: Granularity) -> object:
    """Keys and value *types*, never values. FINE keeps nested key sets; COARSE keeps arity only."""
    if granularity is Granularity.COARSE:
        return ("argc", len(args))
    if granularity is Granularity.MEDIUM:
        return tuple(sorted(
            (str(k), type(v).__name__) for k, v in args.items()
        ))
    return tuple(sorted(
        (str(k), _fine_value(v)) for k, v in args.items()
    ))


def behaviour_signature(run: AgentRun, *, granularity: Granularity = Granularity.MEDIUM) -> str:
    """SHA1 over: ordered (tool name, arg shape) pairs, terminal class, error class,
    retry bucket, escalation flag."""
    payload = (
        tuple((tc.name, _arg_shape(tc.args, granularity)) for tc in run.tool_calls),
        run.terminal,
        run.error_type or "",
        _retry_bucket(run.retries),
        run.escalated,
    )
    return hashlib.sha1(repr(payload).encode("utf-8")).hexdigest()
