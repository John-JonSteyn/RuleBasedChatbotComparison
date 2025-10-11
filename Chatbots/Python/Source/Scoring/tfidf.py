from __future__ import annotations

from typing import Dict, List, Tuple
from math import sqrt

from ..dataModel import (
    Card,
    TfidfIndex,
    AnswerHit,
)
from ..config import ParserConfig
from ..normalise import normalise_for_matching
from ..tokenise import tokenise


def build_tfidf_index(
    candidate_cards: List[Card],
    stopwords: set[str],
    parser_config: ParserConfig,
) -> TfidfIndex:
    """
    Build a TF-IDF index for the given candidate cards.
    """
    documents: List[Card] = list(candidate_cards)
    document_count = len(documents)

    term_frequencies_per_document: List[Dict[str, int]] = []
    document_frequency: Dict[str, int] = {}

    for card in documents:
        tokens = tokenise(card.question_text, stopwords, parser_config)
        frequency_map: Dict[str, int] = {}
        for token in tokens:
            frequency_map[token] = frequency_map.get(token, 0) + 1
        term_frequencies_per_document.append(frequency_map)

        seen_terms = set(frequency_map.keys())
        for term in seen_terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1

    idf_map: Dict[str, float] = {}
    for term, df in document_frequency.items():
        from math import log

        if parser_config.idf_smoothing:
            idf_value = log((document_count + 1.0) / (df + 1.0)) + 1.0
        else:
            if df == 0:
                continue
            idf_value = log(document_count / df)
        idf_map[term] = idf_value

    inverted_index: Dict[str, List[Tuple[int, int]]] = {}
    for doc_id, frequency_map in enumerate(term_frequencies_per_document):
        for term, raw_tf in frequency_map.items():
            inverted_index.setdefault(term, []).append((doc_id, raw_tf))

    document_norms: List[float] = [0.0] * document_count
    document_token_counts: List[int] = [card.question_token_count for card in documents]

    for doc_id, frequency_map in enumerate(term_frequencies_per_document):
        sum_of_squares = 0.0
        for term, raw_tf in frequency_map.items():
            idf_value = idf_map.get(term, 0.0)
            weight = raw_tf * idf_value
            sum_of_squares += weight * weight
        document_norms[doc_id] = sqrt(sum_of_squares) if sum_of_squares > 0.0 else 0.0

    return TfidfIndex(
        documents=documents,
        inverted_index=inverted_index,
        idf=idf_map,
        document_norms=document_norms,
        document_token_counts=document_token_counts,
    )


def score_tfidf(
    query_text: str,
    index: TfidfIndex,
    stopwords: set[str],
    parser_config: ParserConfig,
    top_k: int = 1,
) -> List[AnswerHit]:
    """
    Score documents using cosine similarity between query and document TF-IDF vectors.
    """
    if top_k < 1:
        top_k = 1
    if not index.documents:
        return []
    
    normalised_query = normalise_for_matching(query_text, parser_config)
    query_tokens = tokenise(normalised_query, stopwords, parser_config)
    if not query_tokens:
        return []

    query_term_frequency: Dict[str, int] = {}
    for token in query_tokens:
        query_term_frequency[token] = query_term_frequency.get(token, 0) + 1

    query_weights: Dict[str, float] = {}
    sum_of_squares_query = 0.0
    for term, raw_tf in query_term_frequency.items():
        idf_value = index.idf.get(term)
        if idf_value is None:
            continue
        weight = raw_tf * idf_value
        query_weights[term] = weight
        sum_of_squares_query += weight * weight
    query_norm = sqrt(sum_of_squares_query) if sum_of_squares_query > 0.0 else 0.0
    if query_norm == 0.0:
        return []

    document_dot: Dict[int, float] = {}
    document_overlap_count: Dict[int, int] = {}

    for term, query_weight in query_weights.items():
        postings = index.inverted_index.get(term)
        if not postings:
            continue
        idf_value = index.idf.get(term, 0.0)
        for doc_id, raw_tf_in_document in postings:
            document_dot[doc_id] = document_dot.get(doc_id, 0.0) + (query_weight * (raw_tf_in_document * idf_value))
            document_overlap_count[doc_id] = document_overlap_count.get(doc_id, 0) + 1

    if not document_dot:
        return []

    scored_rows: List[Tuple[float, int, int, str]] = []
    for doc_id, dot_value in document_dot.items():
        document_norm = index.document_norms[doc_id]
        if document_norm == 0.0:
            continue
        cosine = dot_value / (document_norm * query_norm)
        overlap = document_overlap_count.get(doc_id, 0)
        question_token_count = index.document_token_counts[doc_id]
        guid = index.documents[doc_id].guid
        scored_rows.append((cosine, overlap, question_token_count, guid))

    scored_rows.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))

    hits: List[AnswerHit] = []
    for cosine, overlap, question_token_count, guid in scored_rows[:top_k]:
        card = _lookup_card_by_guid(index, guid)
        hits.append(
            AnswerHit(
                guid=guid,
                score=float(cosine),
                deck_path=card.deck_path,
                question_preview=_short_preview(card.question_text),
            )
        )
    return hits


def _lookup_card_by_guid(index: TfidfIndex, guid: str) -> Card:
    for card in index.documents:
        if card.guid == guid:
            return card
    raise KeyError(f"GUID not found in index: {guid}")


def _short_preview(text: str, max_length: int = 120) -> str:
    trimmed = text.strip()
    if len(trimmed) <= max_length:
        return trimmed
    return trimmed[: max_length - 1] + "…"
