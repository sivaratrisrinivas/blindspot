"""`blindspot targets/specs.py:INVOICE` — rich live counters, then the reveal."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    """Load the AgentSpec from a module:attr path, run_fuzz with a rich.Live counter
    (inputs tried / new behaviours / failure classes), then print ranked classes,
    emit the pytest file, and optionally dispatch AO workers with --fix."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
