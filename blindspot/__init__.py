"""Blindspot — coverage-guided fuzzer for AI agents."""

from blindspot.types import (
    AgentRun,
    AgentSpec,
    FailureClass,
    Finding,
    FuzzConfig,
    FuzzResult,
    Granularity,
    Mutant,
    ToolCall,
)

__all__ = [
    "AgentRun",
    "AgentSpec",
    "FailureClass",
    "Finding",
    "FuzzConfig",
    "FuzzResult",
    "Granularity",
    "Mutant",
    "ToolCall",
    "run_fuzz",
    "cluster",
    "rank",
    "minimise_class",
    "emit_pytest",
]


def __getattr__(name: str):  # lazy re-export, avoids import cycles during scaffold
    if name == "run_fuzz":
        from blindspot.runner import run_fuzz

        return run_fuzz
    if name in ("cluster", "rank", "minimise_class"):
        import blindspot.cluster as m

        return getattr(m, name)
    if name == "emit_pytest":
        from blindspot.emit import emit_pytest

        return emit_pytest
    raise AttributeError(name)
