from __future__ import annotations

from typing import Dict, List, Set, Tuple

from ..dataModel import (
    Card,
    PreparedQuestion,
    AnswerHit,
    deck_path_to_string,
    short_preview,
)
from ..config import ParserConfig
from ..normalise import normalise_for_matching
from ..tokenise import tokenise_to_set


def build_guid_index(cards: List[Card]) -> Dict[str, Card]:
    """Create a guid -> Card lookup for fast result materialisation."""
    return {card.guid: card for card in cards}


def prepare_keyword_index(
    candidate_cards: List[Card],
    stopwords: Set[str],
    parser_config: ParserConfig,
) -> List[PreparedQuestion]:
    """
    For each candidate card, compute and cache the set of non-stopword tokens from the normalised question text.
    """
    prepared: List[PreparedQuestion] = []
    for card in candidate_cards:
        token_set = tokenise_to_set(card.question_text, stopwords, parser_config)
        prepared.append(
            PreparedQuestion(
                guid=card.guid,
                token_set=token_set,
                non_stopword_count=len(token_set),
                question_token_count=card.question_token_count,
            )
        )
    return prepared


def score_keyword_overlap(
    query_text: str,
    prepared_candidates: List[PreparedQuestion],
    guid_index: Dict[str, Card],
    stopwords: Set[str],
    parser_config: ParserConfig,
    top_k: int = 1,
) -> List[AnswerHit]:
    """
    Score candidates by count of overlapping non-stopword tokens between the query and the candidate question. Apply tie-breakers.
    """
    if top_k < 1:
        top_k = 1

    query_norm = normalise_for_matching(query_text, parser_config)
    query_tokens = tokenise_to_set(query_norm, stopwords, parser_config)

    if not query_tokens or not prepared_candidates:
        return []

    scored: List[Tuple[float, int, int, str]] = []
    for prepared in prepared_candidates:
        overlap_count = len(query_tokens.intersection(prepared.token_set))
        score = float(overlap_count)
        if overlap_count == 0:
            pass
        scored.append((score, overlap_count, prepared.question_token_count, prepared.guid))

    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))

    hits: List[AnswerHit] = []
    for score, _overlap, question_token_count, guid in scored[:top_k]:
        card = guid_index[guid]
        hits.append(
            AnswerHit(
                guid=guid,
                score=score,
                deck_path=card.deck_path,
                question_preview=short_preview(card.question_text),
            )
        )
    return hits
