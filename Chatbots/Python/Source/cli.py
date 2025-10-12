from __future__ import annotations

import argparse
import datetime
import sys
from typing import List, Optional

from .config import ParserConfig, load_parser_config, load_stopwords
from .dataModel import (
    AnswerHit,
    Card,
    DeckPath,
    LogRecord,
    StageTimings,
    deck_path_to_string,
)
from .io_decks import load_decks
from .logging_io import log_benchmark, log_error, log_invalid_records
from .normalise import normalise_for_display
from .timing import Stopwatch
from .topics import (
    build_topic_index,
    list_available_topics,
    resolve_topic_string,
    collect_subtree_candidates,
)
from .scoring.keyword import build_guid_index, prepare_keyword_index, score_keyword_overlap
from .scoring.tfidf import build_tfidf_index, score_tfidf

# Constants
DEFAULT_DATA_PATH = "Data/Decks"
DEFAULT_PARSER_CONFIG_PATH = "Data/Configs/Parser.json"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rulebot-py",
        description="Rule-based chatbot over Anki decks (Python, stdlib only).",
    )
    parser.add_argument(
        "--topic",
        required=False,
        help=(
            'Deck path (e.g. "Launch into Computing::Unit 03 - Principles of Computer Science"). '
            "If omitted, all topics are searched."
        ),
    )
    parser.add_argument("--algo", choices=["keyword", "tfidf"], required=True, help="Retrieval algorithm.")
    parser.add_argument("--k", type=int, default=1, help="Number of answers to return (default: 1).")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--interactive", action="store_true", help="Interactive session.")
    mode.add_argument("--query", help="Answer a single query and exit.")

    parser.add_argument("--log", help="Append per-query JSON line logs to this file.")
    parser.add_argument("--invalid-log", default="Logs/errors-py.log", help="Path to invalid record log file.")
    parser.add_argument("--warmup", type=int, default=0, help="Number of warm-up queries before timing.")
    parser.add_argument(
        "--include-subtree",
        type=str,
        choices=["true", "false"],
        help="Override config include_subtree.",
    )
    parser.add_argument("--show-cards", action="store_true", help="Print GUIDs and scores for returned results.")
    return parser.parse_args()


def build_candidate_pool(
    all_cards: List[Card],
    topic_text: str,
    parser_config: ParserConfig,
    include_subtree_override: Optional[bool],
) -> List[Card]:
    topic_index = build_topic_index(all_cards)
    known_topics = list_available_topics(all_cards)
    root_topic: DeckPath = resolve_topic_string(topic_text, parser_config.topic_separator, known_topics)
    include_subtree = parser_config.include_subtree if include_subtree_override is None else include_subtree_override
    candidates = collect_subtree_candidates(topic_index, root_topic, include_subtree=include_subtree)
    return candidates


def format_hits_for_display(hits: List[AnswerHit], guid_index: dict, parser_config: ParserConfig) -> str:
    if not hits:
        return "No results."
    lines: List[str] = []
    for rank, hit in enumerate(hits, start=1):
        card = guid_index.get(hit.guid)
        if not card:
            continue
        topic_string = deck_path_to_string(hit.deck_path)
        question_line = hit.question_preview or card.question_text
        answer_display = normalise_for_display(card.answer_raw, parser_config)
        lines.append(f"{rank}. GUID={hit.guid}  score={hit.score:.6f}  topic={topic_string}")
        lines.append(f"   Q: {question_line}")
        lines.append(f"   A: {answer_display}")
    return "\n".join(lines)


def run_single_query(
    query_text: str,
    algorithm_name: str,
    candidates: List[Card],
    parser_config: ParserConfig,
    stopwords: set[str],
    warmup: int,
    top_k: int,
    log_path: Optional[str],
    deck_size_for_log: int,
    topic_text: str,
    show_cards: bool,
    prepared_keyword_index=None,
    guid_index=None,
    tfidf_index=None,
) -> None:
    if warmup > 0:
        for _ in range(warmup):
            if algorithm_name == "keyword":
                _ = score_keyword_overlap("warmup", prepared_keyword_index, guid_index, stopwords, parser_config, top_k)
            else:
                _ = score_tfidf("warmup", tfidf_index, stopwords, parser_config, top_k)

    stopwatch_total = Stopwatch()
    stopwatch_total.start()

    stopwatch_preprocess = Stopwatch()
    stopwatch_rank = Stopwatch()

    parse_ms = 0.0
    index_ms = 0.0

    stopwatch_preprocess.start()
    preprocess_ms = stopwatch_preprocess.stop()

    stopwatch_rank.start()
    if algorithm_name == "keyword":
        hits = score_keyword_overlap(query_text, prepared_keyword_index, guid_index, stopwords, parser_config, top_k)
    else:
        hits = score_tfidf(query_text, tfidf_index, stopwords, parser_config, top_k)
    rank_ms = stopwatch_rank.stop()

    wall_ms = stopwatch_total.stop()

    print(format_hits_for_display(hits, guid_index, parser_config))
    if show_cards:
        for hit in hits:
            print(f"-> {hit.guid}  score={hit.score:.6f}")

    if log_path:
        stage_timings = StageTimings(
            parse_ms=parse_ms,
            index_ms=index_ms,
            preprocess_ms=preprocess_ms,
            rank_ms=rank_ms,
            format_ms=0.0,
        )
        record = LogRecord(
            timestamp_iso=datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            language="python",
            algorithm=algorithm_name,  # type: ignore[arg-type]
            deck_size=deck_size_for_log,
            topic=topic_text,
            query_id="ad-hoc",
            query_text=query_text,
            stage_ms=stage_timings,
            wall_ms=wall_ms,
            rss_kb=None,
            top=[(hit.guid, float(hit.score)) for hit in hits],
        )
        result_dict = {
            "ts": record.timestamp_iso,
            "lang": record.language,
            "algo": record.algorithm,
            "deck_size": record.deck_size,
            "topic": record.topic,
            "query_id": record.query_id,
            "query": record.query_text,
            "stage_ms": {
                "parse": record.stage_ms.parse_ms,
                "index": record.stage_ms.index_ms,
                "preproc": record.stage_ms.preprocess_ms,
                "rank": record.stage_ms.rank_ms,
                "format": record.stage_ms.format_ms,
            },
            "wall_ms": record.wall_ms,
            "rss_kb": record.rss_kb,
            "top": [{"guid": guid, "score": score} for guid, score in record.top],
        }
        log_benchmark(result_dict, log_path)


def main() -> None:
    args = parse_arguments()

    # Fixed config and data locations
    try:
        parser_config = load_parser_config(DEFAULT_PARSER_CONFIG_PATH)
        stopwords = load_stopwords(parser_config.stopwords_path) if parser_config.remove_stopwords else set()
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        sys.exit(1)

    stopwatch_parse = Stopwatch()
    stopwatch_parse.start()
    try:
        cards, invalid_records = load_decks(DEFAULT_DATA_PATH, parser_config, stopwords)
    except Exception as error:  # pragma: no cover (defensive)
        print(f"Failed to load decks from {DEFAULT_DATA_PATH}: {error}", file=sys.stderr)
        sys.exit(1)
    parse_ms = stopwatch_parse.stop()

    if invalid_records:
        log_invalid_records(invalid_records, args.invalid_log)

    if not cards:
        print("No valid cards were loaded. Check your data path and data contract.", file=sys.stderr)
        sys.exit(1)

    # Determine candidate pool: use topic subtree if provided, otherwise all cards
    if args.topic:
        try:
            candidates = build_candidate_pool(
                cards,
                args.topic,
                parser_config,
                include_subtree_override=(None if args.include_subtree is None else args.include_subtree.lower() == "true"),
            )
            topic_label_for_logs = args.topic
        except ValueError as error:
            print(str(error), file=sys.stderr)
            sys.exit(1)

        if not candidates:
            print("No candidate cards found for the requested topic.", file=sys.stderr)
            sys.exit(1)
    else:
        candidates = cards
        topic_label_for_logs = "<ALL>"

    print(f"Loaded {len(cards)} cards; {len(candidates)} candidates in topic '{topic_label_for_logs}'.")

    # Build GUID -> Card index once for display
    guid_index = build_guid_index(candidates)

    prepared_keyword_index = None
    tfidf_index = None
    stopwatch_index = Stopwatch()
    index_ms = 0.0

    if args.algo == "keyword":
        stopwatch_index.start()
        prepared_keyword_index = prepare_keyword_index(candidates, stopwords, parser_config)
        index_ms = stopwatch_index.stop()
    else:
        stopwatch_index.start()
        tfidf_index = build_tfidf_index(candidates, stopwords, parser_config)
        index_ms = stopwatch_index.stop()

    if args.interactive:
        print("Interactive mode. Type a question, or 'exit' to exit.")
        while True:
            try:
                user_text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break
            command = user_text.lower()
            if command in {"exit"}:
                break
            run_single_query(
                query_text=user_text,
                algorithm_name=args.algo,
                candidates=candidates,
                parser_config=parser_config,
                stopwords=stopwords,
                warmup=args.warmup,
                top_k=args.k,
                log_path=args.log,
                deck_size_for_log=len(candidates),
                topic_text=topic_label_for_logs,
                show_cards=args.show_cards,
                prepared_keyword_index=prepared_keyword_index,
                guid_index=guid_index,
                tfidf_index=tfidf_index,
            )
    else:
        run_single_query(
            query_text=args.query,
            algorithm_name=args.algo,
            candidates=candidates,
            parser_config=parser_config,
            stopwords=stopwords,
            warmup=args.warmup,
            top_k=args.k,
            log_path=args.log,
            deck_size_for_log=len(candidates),
            topic_text=topic_label_for_logs,
            show_cards=args.show_cards,
            prepared_keyword_index=prepared_keyword_index,
            guid_index=guid_index,
            tfidf_index=tfidf_index,
        )

    print(f"Parse build: {parse_ms:.3f} ms   Index build: {index_ms:.3f} ms")


if __name__ == "__main__":
    main()
