from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Set


@dataclass(frozen=True)
class ParserConfig:
    """
    Parameters controlling normalisation, tokenisation, topic handling,
    and TF-IDF. Populated from Parser.json with safe defaults applied.
    """

    lowercase_for_matching: bool
    strip_html_for_matching: bool
    escape_html_for_display: bool
    decode_html_entities: bool
    trim_whitespace: bool

    split_on_non_alnum: bool
    keep_digits: bool
    min_token_length: int
    remove_stopwords: bool
    stopwords_path: str

    topic_separator: str
    include_subtree: bool

    idf_smoothing: bool
    idf_formula: str
    l2_normalise: bool

    html_entities_map: Dict[str, str]


_DEFAULTS = {
    "lowercase_for_matching": True,
    "strip_html_for_matching": True,
    "escape_html_for_display": True,
    "decode_html_entities": True,
    "trim_whitespace": True,
    "tokenisation": {
        "split_on_non_alnum": True,
        "keep_digits": True,
        "min_token_length": 2,
        "remove_stopwords": True,
        "stopwords_path": "Data/Configs/Stopwords",
    },
    "topic": {
        "separator": "::",
        "include_subtree": True,
    },
    "algorithms": {
        "tfidf": {
            "idf_smoothing": True,
            "idf_formula": "log((N + 1) / (df + 1)) + 1",
            "l2_normalise": True,
        }
    },
    "_html_entities_map": {
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": '"',
        "&apos;": "'",
        "&nbsp;": " ",
    },
}


def load_parser_config(parser_json_path: str) -> ParserConfig:
    """Read Parser.json, apply defaults, and return a ParserConfig object."""
    if not os.path.exists(parser_json_path):
        raise ValueError(f"Parser config not found: {parser_json_path}")

    try:
        with open(parser_json_path, "r", encoding="utf-8") as file_handle:
            raw_data = json.load(file_handle)
    except Exception as exc:
        raise ValueError(f"Failed to read or parse JSON at {parser_json_path}: {exc}") from exc

    lowercase_for_matching = bool(
        raw_data.get("lowercase_for_matching", _DEFAULTS["lowercase_for_matching"])
    )
    strip_html_for_matching = bool(
        raw_data.get("strip_html_for_matching", _DEFAULTS["strip_html_for_matching"])
    )
    escape_html_for_display = bool(
        raw_data.get("escape_html_for_display", _DEFAULTS["escape_html_for_display"])
    )
    decode_html_entities = bool(
        raw_data.get("decode_html_entities", _DEFAULTS["decode_html_entities"])
    )
    trim_whitespace = bool(
        raw_data.get("trim_whitespace", _DEFAULTS["trim_whitespace"])
    )

    tokenisation = raw_data.get("tokenisation", {})
    split_on_non_alnum = bool(
        tokenisation.get(
            "split_on_non_alnum", _DEFAULTS["tokenisation"]["split_on_non_alnum"]
        )
    )
    keep_digits = bool(
        tokenisation.get("keep_digits", _DEFAULTS["tokenisation"]["keep_digits"])
    )
    min_token_length = tokenisation.get(
        "min_token_length", _DEFAULTS["tokenisation"]["min_token_length"]
    )
    if not isinstance(min_token_length, int) or min_token_length < 1:
        raise ValueError(
            f"min_token_length must be a positive integer, got {min_token_length}"
        )
    remove_stopwords = bool(
        tokenisation.get(
            "remove_stopwords", _DEFAULTS["tokenisation"]["remove_stopwords"]
        )
    )
    stopwords_path = tokenisation.get(
        "stopwords_path", _DEFAULTS["tokenisation"]["stopwords_path"]
    )
    if not isinstance(stopwords_path, str) or not stopwords_path:
        raise ValueError("stopwords_path must be a non-empty string")

    topic = raw_data.get("topic", {})
    topic_separator = topic.get("separator", _DEFAULTS["topic"]["separator"])
    if not isinstance(topic_separator, str) or not topic_separator:
        raise ValueError("topic.separator must be a non-empty string")
    include_subtree = bool(
        topic.get("include_subtree", _DEFAULTS["topic"]["include_subtree"])
    )

    tfidf = raw_data.get("algorithms", {}).get("tfidf", {})
    idf_smoothing = bool(
        tfidf.get("idf_smoothing", _DEFAULTS["algorithms"]["tfidf"]["idf_smoothing"])
    )
    idf_formula = tfidf.get(
        "idf_formula", _DEFAULTS["algorithms"]["tfidf"]["idf_formula"]
    )
    if not isinstance(idf_formula, str) or not idf_formula:
        raise ValueError("algorithms.tfidf.idf_formula must be a non-empty string")
    l2_normalise = bool(
        tfidf.get("l2_normalise", _DEFAULTS["algorithms"]["tfidf"]["l2_normalise"])
    )

    html_entities_map = dict(_DEFAULTS["_html_entities_map"])

    if not os.path.isabs(stopwords_path):
        base_dir = os.path.dirname(os.path.abspath(parser_json_path))
        stopwords_path = os.path.normpath(
            os.path.join(base_dir, os.path.basename(stopwords_path))
        )

    return ParserConfig(
        lowercase_for_matching=lowercase_for_matching,
        strip_html_for_matching=strip_html_for_matching,
        escape_html_for_display=escape_html_for_display,
        decode_html_entities=decode_html_entities,
        trim_whitespace=trim_whitespace,
        split_on_non_alnum=split_on_non_alnum,
        keep_digits=keep_digits,
        min_token_length=min_token_length,
        remove_stopwords=remove_stopwords,
        stopwords_path=stopwords_path,
        topic_separator=topic_separator,
        include_subtree=include_subtree,
        idf_smoothing=idf_smoothing,
        idf_formula=idf_formula,
        l2_normalise=l2_normalise,
        html_entities_map=html_entities_map,
    )


def load_stopwords(path: str) -> Set[str]:
    """Read stopwords from file. One per line, case-folded, '#' = comment, blanks ignored."""
    if not os.path.exists(path):
        raise ValueError(f"Stopwords file not found: {path}")

    stopwords: Set[str] = set()
    with open(path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            stopwords.add(stripped.lower())
    return stopwords
