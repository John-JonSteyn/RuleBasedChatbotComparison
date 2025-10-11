from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional, Literal

DeckPath = Tuple[str, ...]
CandidatePool = List["Card"]
TopicIndex = Dict[DeckPath, List["Card"]]
TokenSet = Set[str]
DocumentId = int
InvertedIndex = Dict[str, List[Tuple[DocumentId, int]]]
IdfMap = Dict[str, float]
SparseVector = Dict[str, float]
AlgorithmName = Literal["keyword", "tfidf"]


@dataclass(frozen=True)
class Card:
    """One Q-A item from a deck export."""
    guid: str
    deck_path: DeckPath
    question_raw: str
    answer_raw: str
    question_text: str
    answer_text: str
    tags: List[str]
    question_token_count: int


@dataclass(frozen=True)
class PreparedQuestion:
    """Cached features for keyword scoring."""
    guid: str
    token_set: TokenSet
    non_stopword_count: int
    question_token_count: int


@dataclass(frozen=True)
class TfidfIndex:
    """TF-IDF state for a candidate pool."""
    documents: List[Card]
    inverted_index: InvertedIndex
    idf: IdfMap
    document_norms: List[float]
    document_token_counts: List[int]


@dataclass(frozen=True)
class AnswerHit:
    """A ranked result."""
    guid: str
    score: float
    deck_path: DeckPath
    question_preview: Optional[str] = None


@dataclass(frozen=True)
class QueryRequest:
    """Resolved query from CLI."""
    topic: DeckPath
    algorithm: AlgorithmName
    k: int
    query_text: str
    query_id: Optional[str] = None


@dataclass(frozen=True)
class StageTimings:
    """Per-query timings (ms)."""
    parse_ms: float
    index_ms: float
    preprocess_ms: float
    rank_ms: float
    format_ms: float


@dataclass(frozen=True)
class LogRecord:
    """Structured log row for one answered query."""
    timestamp_iso: str
    language: Literal["python"]
    algorithm: AlgorithmName
    deck_size: int
    topic: str
    query_id: str
    query_text: str
    stage_ms: StageTimings
    wall_ms: float
    rss_kb: Optional[int]
    top: List[Tuple[str, float]]


@dataclass(frozen=True)
class InvalidRecord:
    """Rejected input line (for error logs)."""
    file_path: str
    line_number: int
    reason: str
    raw_line_preview: str


TIE_BREAKERS_ORDER: Tuple[str, ...] = (
    "more_non_stopword_overlaps",
    "shorter_candidate_question",
    "lexicographic_guid",
)


def deck_path_to_string(deck_path: DeckPath) -> str:
    """Join a DeckPath using '::'."""
    return "::".join(segment.strip() for segment in deck_path if segment.strip())


def string_to_deck_path(text: str) -> DeckPath:
    """Split 'A::B::C' into a DeckPath."""
    parts = [segment.strip() for segment in text.split("::")]
    return tuple(segment for segment in parts if segment)


def short_preview(text: str, max_length: int = 120) -> str:
    """Truncate with an ellipsis if over max_length."""
    trimmed = text.strip()
    if len(trimmed) <= max_length:
        return trimmed
    return trimmed[: max_length - 1] + "…"
