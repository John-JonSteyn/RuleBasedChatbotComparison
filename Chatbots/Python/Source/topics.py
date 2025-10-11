from __future__ import annotations

from typing import Dict, Iterable, List, Set

from .dataModel import DeckPath, Card, TopicIndex, deck_path_to_string, string_to_deck_path


def build_topic_index(cards: List[Card]) -> TopicIndex:
    """
    Map each exact deck path node to the cards directly at that node.
    """
    topic_index: TopicIndex = {}
    for card in cards:
        topic_index.setdefault(card.deck_path, []).append(card)
    return topic_index


def list_available_topics(cards: List[Card]) -> List[DeckPath]:
    """
    Return all topic nodes that exist in the corpus, including ancestors.
    Example:
      card path ("A","B","C") contributes ("A"), ("A","B"), ("A","B","C").
    """
    topics: Set[DeckPath] = set()
    for card in cards:
        for depth in range(1, len(card.deck_path) + 1):
            topics.add(card.deck_path[:depth])
    return sorted(topics)


def resolve_topic_string(topic_text: str, topic_separator: str, known_topics: Iterable[DeckPath]) -> DeckPath:
    """
    Convert a topic string like 'A::B::C' to a DeckPath and validate it exists.
    """
    target = string_to_deck_path(topic_text)
    known_set = set(known_topics)
    if target in known_set:
        return target
    raise ValueError(
        f"Topic not found: '{topic_text}'. Provide one of: "
        + ", ".join(sorted(deck_path_to_string(t) for t in known_set))
    )


def path_is_in_subtree(path: DeckPath, root: DeckPath) -> bool:
    """Return True if 'path' is the same as 'root' or lies under it."""
    return len(path) >= len(root) and path[: len(root)] == root


def collect_subtree_candidates(
    topic_index: TopicIndex,
    root_topic: DeckPath,
    include_subtree: bool = True,
) -> List[Card]:
    """
    Return candidate cards for a topic. If include_subtree is True, include all descendants.
    """
    if not include_subtree:
        return list(topic_index.get(root_topic, []))
    candidates: List[Card] = []
    for node_path, node_cards in topic_index.items():
        if path_is_in_subtree(node_path, root_topic):
            candidates.extend(node_cards)
    return candidates


def candidate_counts_by_topic(topic_index: TopicIndex) -> Dict[DeckPath, int]:
    """Return a count of cards directly attached to each exact topic node."""
    return {path: len(cards) for path, cards in topic_index.items()}
