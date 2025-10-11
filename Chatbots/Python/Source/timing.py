from __future__ import annotations

import time


class Stopwatch:
    """
    Simple stopwatch for measuring elapsed time in milliseconds.
    """

    def __init__(self) -> None:
        self.start_seconds: float = 0.0
        self.end_seconds: float = 0.0
        self.running: bool = False

    def start(self) -> None:
        """Record the start time."""
        self.start_seconds = time.perf_counter()
        self.end_seconds = 0.0
        self.running = True

    def stop(self) -> float:
        """
        Record the end time and return elapsed milliseconds.
        """
        if not self.running:
            raise RuntimeError("Stopwatch must be started before stopping")
        self.end_seconds = time.perf_counter()
        self.running = False
        return self.elapsed_milliseconds()

    def elapsed_milliseconds(self) -> float:
        """
        Return elapsed milliseconds.
        """
        if self.start_seconds == 0.0:
            raise RuntimeError("Stopwatch has not been started")
        end_point = time.perf_counter() if self.running else self.end_seconds
        return (end_point - self.start_seconds) * 1000.0
