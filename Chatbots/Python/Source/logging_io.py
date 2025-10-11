from __future__ import annotations

import os
import json
import datetime
from typing import Iterable, List

from .dataModel import InvalidRecord


def _ensure_directory_exists(path: str) -> None:
    """Create parent directories for a file path if they do not exist."""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def log_invalid_records(invalid_records: Iterable[InvalidRecord], output_path: str) -> None:
    """
    Append invalid record entries to a log file.
    """
    if not invalid_records:
        return
    _ensure_directory_exists(output_path)
    with open(output_path, "a", encoding="utf-8") as handle:
        for record in invalid_records:
            handle.write(
                f"[{datetime.datetime.utcnow().isoformat()}Z] "
                f"file={record.file_path} line={record.line_number} "
                f"reason={record.reason} preview={record.raw_line_preview}\n"
            )


def log_error(message: str, output_path: str) -> None:
    """Append a simple error message to the log file."""
    _ensure_directory_exists(output_path)
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.datetime.utcnow().isoformat()}Z] ERROR {message}\n")


def log_benchmark(result: dict, output_path: str) -> None:
    """
    Append one benchmark result to a log file in JSON lines format.
    This should contain timings, memory use, algorithm name, and deck size.
    """
    _ensure_directory_exists(output_path)
    line = json.dumps(result, ensure_ascii=False)
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_benchmarks(log_path: str) -> List[dict]:
    """Read all benchmark results from a JSON lines log file."""
    if not os.path.exists(log_path):
        return []
    results: List[dict] = []
    with open(log_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                results.append(json.loads(raw_line))
            except json.JSONDecodeError:
                continue
    return results
