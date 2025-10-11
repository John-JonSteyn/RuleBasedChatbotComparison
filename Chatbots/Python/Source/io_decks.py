from __future__ import annotations

import os
from typing import List, Tuple

from .dataModel import Card, InvalidRecord, DeckPath
from .config import ParserConfig
from .normalise import normalise_for_matching
from .tokenise import tokenise


MAX_PREVIEW_CHARS = 120


def list_deck_files(data_path: str) -> List[str]:
    """Return a sorted list of .txt files under data_path (file or directory)."""
    if not os.path.exists(data_path):
        raise ValueError(f"Data path not found: {data_path}")

    if os.path.isfile(data_path):
        return [data_path] if data_path.lower().endswith(".txt") else []

    files: List[str] = []
    for root, _directories, file_names in os.walk(data_path):
        for file_name in file_names:
            if file_name.lower().endswith(".txt"):
                files.append(os.path.join(root, file_name))
    files.sort()
    return files


def split_deck_path(raw: str, separator: str) -> DeckPath:
    """Split a deck path string into a DeckPath tuple."""
    parts = [segment.strip() for segment in raw.split(separator)]
    return tuple(segment for segment in parts if segment)


def preview_raw_line(raw_line: str) -> str:
    """Return a truncated preview of a raw line for error logs."""
    raw_line = (raw_line or "").rstrip("\n\r")
    return raw_line[:MAX_PREVIEW_CHARS]


def parse_record_fields(raw_line: str) -> List[str]:
    """Split a raw line into tab-separated fields."""
    return raw_line.split("\t")


def validate_record(parts: List[str]) -> Tuple[bool, str]:
    """Check if a record has the expected structure and non-empty fields."""
    if len(parts) < 5:
        return False, "too few columns (<5)"
    if len(parts) > 6:
        return False, "too many columns (>6) or TAB inside a field"
    guid = parts[0].strip()
    question_html = parts[3].strip()
    answer_html = parts[4].strip()
    if not guid:
        return False, "empty guid"
    if not question_html:
        return False, "empty question"
    if not answer_html:
        return False, "empty answer"
    return True, ""


def read_deck_file(
    file_path: str,
    parser_config: ParserConfig,
    stopwords: set[str],
) -> Tuple[List[Card], List[InvalidRecord]]:
    """Read one deck file and return valid Cards and InvalidRecords."""
    cards: List[Card] = []
    invalid_records: List[InvalidRecord] = []

    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            line_number = 0
            for raw_line in handle:
                line_number += 1
                if not raw_line or raw_line.startswith("#"):
                    continue

                parts = parse_record_fields(raw_line)
                is_valid, reason = validate_record(parts)
                if not is_valid:
                    invalid_records.append(
                        InvalidRecord(
                            file_path=file_path,
                            line_number=line_number,
                            reason=reason,
                            raw_line_preview=preview_raw_line(raw_line),
                        )
                    )
                    continue

                guid = parts[0].strip()
                deck_path_raw = parts[2].strip()
                question_raw = parts[3].rstrip("\n\r")
                answer_raw = parts[4].rstrip("\n\r")
                tags_raw = parts[5].strip() if len(parts) == 6 else ""

                deck_path = split_deck_path(deck_path_raw, parser_config.topic_separator)

                question_text = normalise_for_matching(question_raw, parser_config)
                answer_text = normalise_for_matching(answer_raw, parser_config)

                if not question_text or not answer_text:
                    invalid_records.append(
                        InvalidRecord(
                            file_path=file_path,
                            line_number=line_number,
                            reason="empty after normalisation",
                            raw_line_preview=preview_raw_line(raw_line),
                        )
                    )
                    continue

                tags = [tag.strip().lower() for tag in tags_raw.split(",") if tag.strip()] if tags_raw else []

                question_tokens = tokenise(question_text, stopwords, parser_config)
                question_token_count = len(question_tokens)

                cards.append(
                    Card(
                        guid=guid,
                        deck_path=deck_path,
                        question_raw=question_raw,
                        answer_raw=answer_raw,
                        question_text=question_text,
                        answer_text=answer_text,
                        tags=tags,
                        question_token_count=question_token_count,
                    )
                )
    except UnicodeDecodeError as exception:
        invalid_records.append(
            InvalidRecord(
                file_path=file_path,
                line_number=0,
                reason=f"unicode decode error: {exception}",
                raw_line_preview="",
            )
        )
    except OSError as exception:
        invalid_records.append(
            InvalidRecord(
                file_path=file_path,
                line_number=0,
                reason=f"file read error: {exception}",
                raw_line_preview="",
            )
        )

    return cards, invalid_records


def load_decks(
    data_path: str,
    parser_config: ParserConfig,
    stopwords: set[str],
) -> Tuple[List[Card], List[InvalidRecord]]:
    """Load all deck files under data_path and return combined Cards and InvalidRecords."""
    all_cards: List[Card] = []
    all_invalid_records: List[InvalidRecord] = []

    for file_path in list_deck_files(data_path):
        cards, invalid_records = read_deck_file(file_path, parser_config, stopwords)
        all_cards.extend(cards)
        all_invalid_records.extend(invalid_records)

    return all_cards, all_invalid_records
