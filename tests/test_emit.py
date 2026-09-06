"""emit_pytest writes a runnable, collectable pytest module — one test per class."""

from __future__ import annotations

import subprocess
import sys

from blindspot.emit import emit_pytest
from blindspot.types import FailureClass, Finding
from targets.specs import INVOICE


def _finding(oracle, inp, *, evidence=None, severity="crash"):
    return Finding(
        oracle=oracle,
        input=inp,
        summary=f"{oracle} fired on {inp!r}",
        severity=severity,
        evidence=evidence or {},
        signature=f"{oracle}:sig",
    )


def _fake_classes():
    crash_members = [
        _finding("crash", "Invoice from Åcme Corp for $1,240.00"),
        _finding("crash", "Bill: Globex 1.234,56 EUR"),
        _finding("crash", "Invoice from Åcme Corp for $1,240.00"),  # dupe input
    ]
    meta_members = [
        _finding(
            "metamorphic",
            "Invoice from  Acme  Corp for $1,240.00 dated 2026-03-01.",
            evidence={"baseline_input": "Invoice from Acme Corp for $1,240.00 dated 2026-03-01."},
            severity="semantic",
        ),
    ]
    schema_members = [
        _finding("schema", "Bill: Globex, amount 500 USD, 01/03/2026.", severity="contract"),
    ]
    return [
        FailureClass(
            id="acme-homoglyph",
            oracle="crash",
            label="homoglyph rename crashes booking",
            severity="crash",
            members=crash_members,
            minimal_repro=crash_members[0],
        ),
        FailureClass(
            id="answer drift: rename",
            oracle="metamorphic",
            label="answer changes under entity rename",
            severity="semantic",
            members=meta_members,
            minimal_repro=meta_members[0],
        ),
        FailureClass(
            id="contract-miss",
            oracle="schema",
            label="output misses GL confirmation",
            severity="contract",
            members=schema_members,
            minimal_repro=schema_members[0],
        ),
    ]


def test_emits_compilable_file_with_one_test_per_class(tmp_path):
    classes = _fake_classes()
    out = tmp_path / "generated" / "test_blindspot_invoice.py"

    emit_pytest(classes, INVOICE, out)

    assert out.exists()
    src = out.read_text()
    compile(src, str(out), "exec")

    assert "test_crash_acme_homoglyph" in src
    assert "test_metamorphic_answer_drift_rename" in src
    assert "test_schema_contract_miss" in src
    assert src.count("def test_") == len(classes)
    assert "from targets.specs import INVOICE as SPEC" in src


def test_empty_classes_still_valid(tmp_path):
    out = tmp_path / "test_blindspot_empty.py"
    emit_pytest([], INVOICE, out)
    src = out.read_text()
    compile(src, str(out), "exec")
    assert "def test_blindspot_placeholder()" in src


def test_pytest_can_collect_the_generated_file(tmp_path):
    classes = _fake_classes()
    out = tmp_path / "test_blindspot_invoice.py"
    emit_pytest(classes, INVOICE, out)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode in (0, 5), proc.stdout + proc.stderr
    assert "test_crash_acme_homoglyph" in proc.stdout
    assert "test_metamorphic_answer_drift_rename" in proc.stdout
    assert "test_schema_contract_miss" in proc.stdout
