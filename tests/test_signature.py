"""Behaviour-signature tests: it is a pure structural hash, values never leak in."""

from __future__ import annotations

from blindspot.signature import _arg_shape, behaviour_signature
from blindspot.types import AgentRun, Granularity, ToolCall


def _run(tool_calls=(), *, terminal="ok", error_type=None, retries=0, escalated=False):
    return AgentRun(
        input="q",
        output="a",
        tool_calls=tuple(tool_calls),
        terminal=terminal,
        error_type=error_type,
        retries=retries,
        escalated=escalated,
    )


def _tc(name, args, ok=True):
    return ToolCall(name=name, args=args, ok=ok)


def test_identical_runs_hash_identically():
    a = _run([_tc("search", {"q": "widgets", "limit": 10}), _tc("fetch", {"id": 3})])
    b = _run([_tc("search", {"q": "widgets", "limit": 10}), _tc("fetch", {"id": 3})])
    assert behaviour_signature(a) == behaviour_signature(b)


def test_tool_call_order_changes_hash():
    calls = [_tc("search", {"q": "x"}), _tc("fetch", {"id": 1})]
    a = _run(calls)
    b = _run(list(reversed(calls)))
    assert behaviour_signature(a) != behaviour_signature(b)


def test_medium_ignores_arg_values_with_same_shape():
    a = _run([_tc("search", {"q": "widgets", "limit": 10})])
    b = _run([_tc("search", {"q": "sprockets", "limit": 99999})])
    assert behaviour_signature(a, granularity=Granularity.MEDIUM) == behaviour_signature(
        b, granularity=Granularity.MEDIUM
    )


def test_coarse_collides_more_than_fine():
    # Same arity, same one-level type (dict) -> COARSE and MEDIUM collide.
    # Nested keys differ -> FINE separates them.
    a = _run([_tc("call", {"payload": {"a": 1}})])
    b = _run([_tc("call", {"payload": {"b": 2}})])

    assert behaviour_signature(a, granularity=Granularity.COARSE) == behaviour_signature(
        b, granularity=Granularity.COARSE
    )
    assert behaviour_signature(a, granularity=Granularity.MEDIUM) == behaviour_signature(
        b, granularity=Granularity.MEDIUM
    )
    assert behaviour_signature(a, granularity=Granularity.FINE) != behaviour_signature(
        b, granularity=Granularity.FINE
    )


def test_fine_list_uses_length_bucket_not_exact_length():
    a = _run([_tc("call", {"items": [1, 1]})])
    b = _run([_tc("call", {"items": [1, 1, 1]})])  # 2 and 3 share bucket "2-3"
    c = _run([_tc("call", {"items": [1] * 20})])   # bucket "8+"
    assert behaviour_signature(a, granularity=Granularity.FINE) == behaviour_signature(
        b, granularity=Granularity.FINE
    )
    assert behaviour_signature(a, granularity=Granularity.FINE) != behaviour_signature(
        c, granularity=Granularity.FINE
    )


def test_terminal_change_changes_hash():
    a = _run([_tc("t", {"x": 1})], terminal="ok")
    b = _run([_tc("t", {"x": 1})], terminal="timeout")
    assert behaviour_signature(a) != behaviour_signature(b)


def test_error_type_change_changes_hash():
    a = _run([_tc("t", {"x": 1})], terminal="error", error_type="ValueError")
    b = _run([_tc("t", {"x": 1})], terminal="error", error_type="KeyError")
    assert behaviour_signature(a) != behaviour_signature(b)


def test_escalation_change_changes_hash():
    a = _run([_tc("t", {"x": 1})], escalated=False)
    b = _run([_tc("t", {"x": 1})], escalated=True)
    assert behaviour_signature(a) != behaviour_signature(b)


def test_retry_bucket_boundaries():
    base = [_tc("t", {"x": 1})]
    assert behaviour_signature(_run(base, retries=1)) == behaviour_signature(
        _run(base, retries=2)
    )
    assert behaviour_signature(_run(base, retries=2)) != behaviour_signature(
        _run(base, retries=3)
    )


def test_arg_shape_is_hashable_and_deterministic():
    args = {"b": [1, 2], "a": {"z": "s"}, "c": 3}
    for g in Granularity:
        shape = _arg_shape(args, g)
        assert hash(shape) == hash(_arg_shape(dict(reversed(args.items())), g))
