from __future__ import annotations

from typing import Dict
from .config import ParserConfig


def strip_html_tags(text: str) -> str:
    """Remove any '<__>' sequences."""
    if not text:
        return ""
    in_tag = False
    output_chars: list[str] = []
    for character in text:
        if character == "<":
            in_tag = True
            continue
        if character == ">":
            if in_tag:
                in_tag = False
            else:
                output_chars.append(character)
            continue
        if not in_tag:
            output_chars.append(character)
    return "".join(output_chars)


def decode_basic_entities(text: str, entity_map: Dict[str, str]) -> str:
    """Replace a fixed set of HTML entities defined in the config."""
    if not text:
        return ""
    for entity in sorted(entity_map.keys(), key=len, reverse=True):
        text = text.replace(entity, entity_map[entity])
    return text


def escape_angle_brackets(text: str) -> str:
    """Escape '<' and '>' for safe display."""
    if not text:
        return ""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def normalise_for_matching(text: str, config: ParserConfig) -> str:
    """Produce plain text for matching based on config flags."""
    if text is None:
        return ""
    result = text
    if config.strip_html_for_matching:
        result = strip_html_tags(result)
    if config.decode_html_entities:
        result = decode_basic_entities(result, config.html_entities_map)
    if config.lowercase_for_matching:
        result = result.lower()
    if config.trim_whitespace:
        result = result.strip()
    return result


def normalise_for_display(text: str, config: ParserConfig) -> str:
    """Produce safe text for display based on config flags."""
    if text is None:
        return ""
    result = text
    if config.decode_html_entities:
        result = decode_basic_entities(result, config.html_entities_map)
    result = escape_angle_brackets(result)
    if config.trim_whitespace:
        result = result.strip()
    return result
