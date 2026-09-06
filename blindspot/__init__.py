"""Blindspot — coverage-guided fuzzer for AI agents."""

from blindspot.cluster import cluster, minimise_class, rank
from blindspot.emit import emit_pytest
from blindspot.runner import run_fuzz
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
