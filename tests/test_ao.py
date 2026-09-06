"""AOClient is a thin HTTP adapter; these tests are hermetic — the transport is
a fake exposing .post."""

from __future__ import annotations

from blindspot.ao import AOClient, dispatch_fixes
from blindspot.types import FailureClass, Finding


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeTransport:
    def __init__(self, *, post_payload=None):
        self._post_payload = post_payload
        self.posts: list[tuple[str, dict]] = []

    def post(self, url, json=None):
        self.posts.append((url, json or {}))
        return _Resp(self._post_payload)


def _client(**kwargs):
    c = AOClient(base_url="http://test")
    c._c = _FakeTransport(**kwargs)
    return c


def _finding(oracle, inp, *, evidence=None):
    return Finding(
        oracle=oracle,
        input=inp,
        summary=f"{oracle} on {inp!r}",
        severity="crash",
        evidence=evidence or {},
        signature=f"{oracle}:sig",
    )


def _fc(fc_id, oracle, inp, *, evidence=None):
    f = _finding(oracle, inp, evidence=evidence)
    return FailureClass(
        id=fc_id,
        oracle=oracle,
        label=f"{fc_id} label",
        severity="crash",
        members=[f],
        minimal_repro=f,
    )


def test_spawn_worker_posts_envelope_and_returns_id():
    c = _client(post_payload={"session": {"id": "blindspot-7"}})

    sid = c.spawn_worker("fix-really-long-name-here", "do the thing", model="haiku")

    assert sid == "blindspot-7"
    url, body = c._c.posts[0]
    assert url == "/api/v1/sessions"
    assert body["projectId"] == "blindspot"
    assert body["harness"] == "claude-code"
    assert body["kind"] == "worker"
    assert body["model"] == "haiku"
    assert body["prompt"] == "do the thing"
    assert len(body["displayName"]) <= 20


def test_dispatch_fixes_spawns_one_worker_per_class_with_distinct_names():
    calls: list[tuple[str, str]] = []

    class _AO:
        def spawn_worker(self, name, prompt, *, model="sonnet"):
            calls.append((name, prompt))
            return f"session-{len(calls)}"

    classes = [
        _fc("crash-homoglyph", "crash", "Invoice from Åcme",
            evidence={"error_type": "DateFormatError"}),
        _fc(
            "answer-drift",
            "metamorphic",
            "Invoice from Acme  Corp",
            evidence={"mutant_input": "Invoice from Åcme Corp",
                      "baseline_answer": "1100", "mutant_answer": "6000"},
        ),
        _fc("schema-miss", "schema", "Bill: Globex 500 USD"),
    ]

    class _Spec:
        name = "invoice"

    ids = dispatch_fixes(classes, _Spec(), _AO(), spawn_gap_s=0)

    assert ids == ["session-1", "session-2", "session-3"]
    names = [n for n, _ in calls]
    assert len(set(names)) == 3
    assert all(len(n) <= 20 for n in names)

    meta_prompt = calls[1][1]
    assert "Invoice from Åcme Corp" in meta_prompt
    assert "SAME GL account" in meta_prompt
    assert "open a pr." in meta_prompt.lower()
    assert "targets/invoice_agent.py" in meta_prompt

    crash_prompt = calls[0][1]
    assert "DateFormatError" in crash_prompt
    assert "mutant" not in crash_prompt.lower()
