from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.append(str(Path(__file__).resolve().parents[1] / "Chatbots"))

from Python.Source.config import ParserConfig, load_parser_config, load_stopwords
from Python.Source.io_decks import load_decks
from Python.Source.dataModel import Card, deck_path_to_string

DEFAULT_DATA_PATH = Path("Data/Decks")
DEFAULT_PARSER_CONFIG_PATH = Path("Data/Configs/Parser.json")
DEFAULT_STOPWORDS_PATH = Path("Data/Configs/Stopwords.txt")
DEFAULT_RUST_MANIFEST = Path("Chatbots/Rust/Source/Cargo.toml")
PYTHON_CLI_MODULE = "Chatbots.Python.Source.cli"

LOG_ROOT = Path("Results/Bench")
LOG_ROOT.mkdir(parents=True, exist_ok=True)

@dataclass
class SampleItem:
    """Single benchmark case: which question to ask and what we expect as the top result."""
    deck_topic_text: str
    deck_card_count: int
    expected_guid: str
    query_text: str

@dataclass
class ResultRow:
    """Flattened, analysis-friendly result row for the main CSV."""
    seed: int
    implementation: str
    algorithm: str
    scope: str
    deck_name: str
    deck_card_count: int
    query_id: str
    query_text: str
    expected_guid: str
    top_guid: Optional[str]
    match: bool
    wall_ms: Optional[float]
    rank_ms: Optional[float]
    parse_ms: Optional[float]
    index_ms: Optional[float]
    timestamp: str
    error: Optional[str]

def now_iso() -> str:
    """Return a UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()

def ensure_clean_file(path: Path) -> None:
    """Create parent directory and truncate file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

def tail_last_json_line(path: Path) -> Optional[dict]:
    """Read the last non-empty line and parse JSON; return None if file is empty."""
    try:
        last = None
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                text = line.strip()
                if text:
                    last = text
        return json.loads(last) if last else None
    except FileNotFoundError:
        return None

def calculate_percentile(values: Sequence[float], pct: float) -> float:
    """Simple percentile (inclusive, linear interpolation between closest ranks).”"""
    if not values:
        return float("nan")
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    rank = (pct / 100.0) * (len(data) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(data) - 1)
    fraction = rank - lower
    return data[lower] * (1 - fraction) + data[upper] * fraction

def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None

def _safe_stream_text(proc: subprocess.CompletedProcess, attr: str) -> str:
    """Return a printable string for proc.stdout/proc.stderr even if not captured."""
    value = getattr(proc, attr, None)
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)

def collect_deck_topics(cards: List[Card]) -> Dict[str, List[Card]]:
    """Group cards by their deck topic text (joined with ::)."""
    buckets: Dict[str, List[Card]] = {}
    for card in cards:
        key = deck_path_to_string(card.deck_path)
        buckets.setdefault(key, []).append(card)
    return buckets

def sample_questions_per_deck(
    cards_by_deck: Dict[str, List[Card]],
    questions_per_deck: int,
    rng: random.Random,
) -> List[SampleItem]:
    """Deterministically select question prompts within each deck."""
    samples: List[SampleItem] = []
    for deck_topic_text, deck_cards in sorted(cards_by_deck.items()):
        if not deck_cards:
            continue
        permutation = list(range(len(deck_cards)))
        rng.shuffle(permutation)
        take = min(questions_per_deck, len(deck_cards))
        for i in range(take):
            card = deck_cards[permutation[i]]
            samples.append(
                SampleItem(
                    deck_topic_text=deck_topic_text,
                    deck_card_count=len(deck_cards),
                    expected_guid=card.guid,
                    query_text=card.question_text,
                )
            )
    return samples

def split_scopes(samples: List[SampleItem]) -> Tuple[List[SampleItem], List[SampleItem]]:
    """Split the set into two halves: first half evaluated in topic scope, second half in global scope."""
    half = len(samples) // 2
    return samples[:half], samples[half:]

def run_python_cli(
    algorithm_name: str,
    query_text: str,
    topic_text_or_none: Optional[str],
    log_file: Path,
) -> subprocess.CompletedProcess:
    command = [
        sys.executable, "-m", PYTHON_CLI_MODULE,
        "--algo", algorithm_name,
        "--k", "1",
        "--log", str(log_file),
    ]
    if topic_text_or_none:
        command.extend(["--topic", topic_text_or_none])
    command.extend(["--query", query_text])

    return subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

def run_rust_cli(
    algorithm_name: str,
    query_text: str,
    topic_text_or_none: Optional[str],
    rust_manifest_path: Path,
    log_file: Path,
) -> subprocess.CompletedProcess:
    command = [
        "cargo", "run", "--manifest-path", str(rust_manifest_path), "--",
        "--algo", algorithm_name,
        "--k", "1",
        "--log", str(log_file),
    ]
    if topic_text_or_none:
        command.extend(["--topic", topic_text_or_none])
    command.extend(["--query", query_text])

    return subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )

def extract_top_guid_from_jsonl(last_record: dict) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Read the most recent per-query JSON record and pull out top GUID and stage timings."""
    top_value = last_record.get("top")
    top_guid: Optional[str] = None
    if isinstance(top_value, list) and top_value:
        first = top_value[0]
        if isinstance(first, dict):
            top_guid = first.get("guid")
        elif isinstance(first, (list, tuple)) and len(first) >= 1:
            top_guid = first[0]

    wall_ms = last_record.get("wall_ms") or last_record.get("wallMilliseconds")
    stage_ms = last_record.get("stage_ms") or last_record.get("stageMilliseconds") or last_record.get("stage_milliseconds") or {}
    parse_ms = stage_ms.get("parse") or stage_ms.get("parse_ms") or stage_ms.get("parseMilliseconds") or stage_ms.get("parse_milliseconds")
    index_ms = stage_ms.get("index") or stage_ms.get("index_ms") or stage_ms.get("indexMilliseconds") or stage_ms.get("parse_milliseconds")
    rank_ms = stage_ms.get("rank") or stage_ms.get("rank_ms") or stage_ms.get("rankMilliseconds") or stage_ms.get("rank_milliseconds")

    return top_guid, _to_float(wall_ms), _to_float(rank_ms), _to_float(parse_ms), _to_float(index_ms)

def run_benchmark(
    seed: int,
    questions_per_deck: int,
    implementations: List[str],
    algorithms: List[str],
    do_topic_scope: bool,
    do_global_scope: bool,
    rust_manifest_path: Path,
) -> Tuple[Path, Path]:
    """Top-level coordinator for one seeded run."""
    rng = random.Random(seed)

    parser_config: ParserConfig = load_parser_config(str(DEFAULT_PARSER_CONFIG_PATH))
    stopwords = load_stopwords(str(DEFAULT_STOPWORDS_PATH)) if parser_config.remove_stopwords else set()
    all_cards, invalid_records = load_decks(str(DEFAULT_DATA_PATH), parser_config, stopwords)

    if not all_cards:
        raise RuntimeError("No cards loaded from Data/Decks — cannot benchmark.")

    cards_by_deck = collect_deck_topics(all_cards)
    samples_all = sample_questions_per_deck(cards_by_deck, questions_per_deck, rng)
    topic_samples, global_samples = split_scopes(samples_all)

    python_log_path = LOG_ROOT / f"seed_{seed}_python.jsonl"
    rust_log_path = LOG_ROOT / f"seed_{seed}_rust.jsonl"
    ensure_clean_file(python_log_path)
    ensure_clean_file(rust_log_path)

    results_csv_path = LOG_ROOT / f"results_seed_{seed}.csv"
    summary_csv_path = LOG_ROOT / f"summary_seed_{seed}.csv"
    ensure_clean_file(results_csv_path)
    ensure_clean_file(summary_csv_path)

    results: List[ResultRow] = []

    def execute_case(
        implementation: str,
        algorithm_name: str,
        scope_label: str,
        sample: SampleItem,
    ) -> ResultRow:
        timestamp = now_iso()
        log_file = python_log_path if implementation == "python" else rust_log_path

        try:
            if implementation == "python":
                completed = run_python_cli(
                    algorithm_name=algorithm_name,
                    query_text=sample.query_text,
                    topic_text_or_none=(sample.deck_topic_text if scope_label == "topic" else None),
                    log_file=log_file,
                )
            else:
                completed = run_rust_cli(
                    algorithm_name=algorithm_name,
                    query_text=sample.query_text,
                    topic_text_or_none=(sample.deck_topic_text if scope_label == "topic" else None),
                    rust_manifest_path=rust_manifest_path,
                    log_file=log_file,
                )
        except Exception as exc:
            return ResultRow(
                seed=seed,
                implementation=implementation,
                algorithm=algorithm_name,
                scope=scope_label,
                deck_name=sample.deck_topic_text if scope_label == "topic" else "<ALL>",
                deck_card_count=sample.deck_card_count if scope_label == "topic" else len(all_cards),
                query_id=sample.expected_guid,
                query_text=sample.query_text,
                expected_guid=sample.expected_guid,
                top_guid=None,
                match=False,
                wall_ms=None,
                rank_ms=None,
                parse_ms=None,
                index_ms=None,
                timestamp=timestamp,
                error=f"Invocation error: {exc}",
            )

        if completed.returncode != 0:
            stderr_text = _safe_stream_text(completed, "stderr")
            stdout_text = _safe_stream_text(completed, "stdout")
            return ResultRow(
                seed=seed,
                implementation=implementation,
                algorithm=algorithm_name,
                scope=scope_label,
                deck_name=sample.deck_topic_text if scope_label == "topic" else "<ALL>",
                deck_card_count=sample.deck_card_count if scope_label == "topic" else len(all_cards),
                query_id=sample.expected_guid,
                query_text=sample.query_text,
                expected_guid=sample.expected_guid,
                top_guid=None,
                match=False,
                wall_ms=None,
                rank_ms=None,
                parse_ms=None,
                index_ms=None,
                timestamp=timestamp,
                error=f"Non-zero exit ({completed.returncode})"
                      f"{' | stderr: ' + stderr_text if stderr_text else ''}"
                      f"{' | stdout: ' + stdout_text if stdout_text else ''}",
            )

        last_record = tail_last_json_line(log_file)
        if last_record is None:
            return ResultRow(
                seed=seed,
                implementation=implementation,
                algorithm=algorithm_name,
                scope=scope_label,
                deck_name=sample.deck_topic_text if scope_label == "topic" else "<ALL>",
                deck_card_count=sample.deck_card_count if scope_label == "topic" else len(all_cards),
                query_id=sample.expected_guid,
                query_text=sample.query_text,
                expected_guid=sample.expected_guid,
                top_guid=None,
                match=False,
                wall_ms=None,
                rank_ms=None,
                parse_ms=None,
                index_ms=None,
                timestamp=timestamp,
                error="No JSONL log line found after execution.",
            )

        top_guid, wall_ms, rank_ms, parse_ms, index_ms = extract_top_guid_from_jsonl(last_record)
        is_match = (top_guid == sample.expected_guid)

        return ResultRow(
            seed=seed,
            implementation=implementation,
            algorithm=algorithm_name,
            scope=scope_label,
            deck_name=sample.deck_topic_text if scope_label == "topic" else "<ALL>",
            deck_card_count=sample.deck_card_count if scope_label == "topic" else len(all_cards),
            query_id=sample.expected_guid,
            query_text=sample.query_text,
            expected_guid=sample.expected_guid,
            top_guid=top_guid,
            match=is_match,
            wall_ms=wall_ms,
            rank_ms=rank_ms,
            parse_ms=parse_ms,
            index_ms=index_ms,
            timestamp=timestamp,
            error=None,
        )

    for algorithm_name in algorithms:
        if do_topic_scope:
            for sample in topic_samples:
                for implementation in implementations:
                    results.append(execute_case(implementation, algorithm_name, "topic", sample))
        if do_global_scope:
            for sample in global_samples:
                for implementation in implementations:
                    results.append(execute_case(implementation, algorithm_name, "global", sample))

    with results_csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "seed", "implementation", "algorithm", "scope",
            "deck_name", "deck_card_count", "query_id", "query_text",
            "expected_guid", "top_guid", "match",
            "wall_ms", "rank_ms", "parse_ms", "index_ms",
            "timestamp", "error",
        ])
        for row in results:
            writer.writerow([
                row.seed, row.implementation, row.algorithm, row.scope,
                row.deck_name, row.deck_card_count, row.query_id, row.query_text,
                row.expected_guid, row.top_guid if row.top_guid is not None else "",
                "true" if row.match else "false",
                _fmt_num(row.wall_ms), _fmt_num(row.rank_ms),
                _fmt_num(row.parse_ms), _fmt_num(row.index_ms),
                row.timestamp, row.error or "",
            ])

    summary_rows = build_summary(results)
    with summary_csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "seed", "implementation", "algorithm", "scope", "queries",
            "accuracy_at_1", "median_wall_ms", "p90_wall_ms",
            "median_rank_ms", "p90_rank_ms",
        ])
        for s in summary_rows:
            writer.writerow(s)

    return results_csv_path, summary_csv_path

def _fmt_num(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.3f}"

def build_summary(results: List[ResultRow]) -> List[List]:
    """Aggregate by (implementation, algorithm, scope)."""
    out: List[List] = []
    grouped: Dict[Tuple[str, str, str], List[ResultRow]] = {}
    for r in results:
        key = (r.implementation, r.algorithm, r.scope)
        grouped.setdefault(key, []).append(r)

    for (implementation, algorithm, scope), rows in sorted(grouped.items()):
        wall_list = [r.wall_ms for r in rows if r.wall_ms is not None]
        rank_list = [r.rank_ms for r in rows if r.rank_ms is not None]
        accuracy = sum(1 for r in rows if r.match) / len(rows) if rows else float("nan")
        median_wall = calculate_percentile([float(x) for x in wall_list], 50.0) if wall_list else float("nan")
        p90_wall = calculate_percentile([float(x) for x in wall_list], 90.0) if wall_list else float("nan")
        median_rank = calculate_percentile([float(x) for x in rank_list], 50.0) if rank_list else float("nan")
        p90_rank = calculate_percentile([float(x) for x in rank_list], 90.0) if rank_list else float("nan")

        out.append([
            results[0].seed if results else "",
            implementation, algorithm, scope, len(rows),
            f"{accuracy:.3f}",
            _fmt_num(median_wall), _fmt_num(p90_wall),
            _fmt_num(median_rank), _fmt_num(p90_rank),
        ])
    return out

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bench-rulebots",
        description="Reproducible parity benchmark across implementations and algorithms."
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed used to choose questions.")
    parser.add_argument("--questions-per-deck", type=int, default=10, help="Number of questions to sample per deck.")
    parser.add_argument("--algorithms", default="keyword,tfidf", help="Comma-separated list: keyword, tfidf.")
    parser.add_argument("--implementations", default="python,rust", help="Comma-separated list: python, rust.")
    parser.add_argument("--topic-scope", action="store_true", help="Run topic-scoped queries.")
    parser.add_argument("--global-scope", action="store_true", help="Run global-scope queries.")
    parser.add_argument("--rust-manifest", default=str(DEFAULT_RUST_MANIFEST), help="Path to Cargo.toml.")
    return parser.parse_args()

def main() -> None:
    args = parse_args()

    algorithms = [a.strip() for a in args.algorithms.split(",") if a.strip()]
    implementations = [i.strip() for i in args.implementations.split(",") if i.strip()]
    do_topic = args.topic_scope or not args.global_scope
    do_global = args.global_scope

    results_csv_path, summary_csv_path = run_benchmark(
        seed=args.seed,
        questions_per_deck=args.questions_per_deck,
        implementations=implementations,
        algorithms=algorithms,
        do_topic_scope=do_topic,
        do_global_scope=do_global,
        rust_manifest_path=Path(args.rust_manifest),
    )

    print(f"Results CSV: {results_csv_path}")
    print(f"Summary CSV: {summary_csv_path}")

if __name__ == "__main__":
    main()
