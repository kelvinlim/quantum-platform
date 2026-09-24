"""Monotonic clocks used for session timestamps.

DESIGN.md §4: shared monotonic clock; timestamp on arrival.
SystemClock wraps ``time.monotonic_ns``. FakeClock is for tests and
``qp run --auto-press`` so a dry-run does not wait on wall time.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    def monotonic_ns(self) -> int: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class FakeClock:
    """Deterministic monotonic clock. ``sleep`` advances the cursor."""

    def __init__(self, start_ns: int = 0) -> None:
        self._ns = int(start_ns)

    def monotonic_ns(self) -> int:
        return self._ns

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot advance clock backwards")
        self._ns += int(seconds * 1_000_000_000)

    def advance_ns(self, ns: int) -> None:
        if ns < 0:
            raise ValueError("cannot advance clock backwards")
        self._ns += int(ns)
