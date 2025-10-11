from __future__ import annotations

from typing import List, Set
from .config import ParserConfig


def _emit_token(buffer: List[str], stopwords: Set[str], config: ParserConfig, output: List[str]) -> None:
    """Apply length/stopword rules and append to output if accepted."""
    if not buffer:
        return
    token = "".join(buffer)
    buffer.clear()

    if token in stopwords and config.remove_stopwords:
        return

    if token.isdigit() and config.keep_digits:
        output.append(token)
        return

    if len(token) >= config.min_token_length:
        output.append(token)


def tokenise(text: str, stopwords: Set[str], config: ParserConfig) -> List[str]:
    """
    Split on non-alphanumeric boundaries and return filtered tokens.
    Assumes text was already normalised (e.g., lowercased) upstream.
    """
    if not text:
        return []

    output: List[str] = []
    buffer: List[str] = []

    for character in text:
        if character.isalnum():
            buffer.append(character)
        else:
            _emit_token(buffer, stopwords, config, output)

    _emit_token(buffer, stopwords, config, output)
    return output


def tokenise_to_set(text: str, stopwords: Set[str], config: ParserConfig) -> Set[str]:
    """Tokenise and return a set for fast overlap operations."""
    return set(tokenise(text, stopwords, config))
