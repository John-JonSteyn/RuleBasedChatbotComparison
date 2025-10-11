use std::collections::{BTreeMap, HashMap, HashSet};

use crate::data_model::{Card, DeckPath};

/// Build an index from full deck paths to the cards that live at that path.
pub fn build_topic_index(cards: &[Card]) -> HashMap<DeckPath, Vec<Card>> {
    let mut index: HashMap<DeckPath, Vec<Card>> = HashMap::new();
    for card in cards.iter().cloned() {
        index.entry(card.deck_path.clone()).or_default().push(card);
    }
    index
}

/// Return a sorted list of all unique topic paths present across cards.
pub fn list_available_topics(cards: &[Card]) -> Vec<DeckPath> {
    let mut set: HashSet<DeckPath> = HashSet::new();
    for card in cards {
        if !card.deck_path.is_empty() {
            set.insert(card.deck_path.clone());
        }
    }
    let mut list: Vec<DeckPath> = set.into_iter().collect();
    list.sort();
    list
}

/// Convert a topic string into a DeckPath using the provided separator
pub fn resolve_topic_string(
    topic_text: &str,
    topic_separator: &str,
    known_topics: &[DeckPath],
) -> Result<DeckPath, String> {
    let deck_path: DeckPath = if topic_text.trim().is_empty() {
        Vec::new()
    } else {
        topic_text
            .split(topic_separator)
            .map(|segment| segment.trim().to_string())
            .collect()
    };

    if deck_path.is_empty() {
        return Err("Topic cannot be empty; provide a valid deck path.".to_string());
    }

    if known_topics.iter().any(|path| path == &deck_path) {
        Ok(deck_path)
    } else {
        let mut by_string: BTreeMap<String, ()> = BTreeMap::new();
        for path in known_topics {
            by_string.insert(path.join(topic_separator), ());
        }

        let wanted = deck_path.join(topic_separator);
        let mut suggestions: Vec<String> = by_string
            .keys()
            .filter(|candidate| candidate.starts_with(&deck_path[0]))
            .take(5)
            .cloned()
            .collect();

        if suggestions.is_empty() {
            suggestions = by_string.keys().take(5).cloned().collect();
        }

        let hint = if suggestions.is_empty() {
            String::from("No topics available.")
        } else {
            format!("Did you mean one of:\n- {}", suggestions.join("\n- "))
        };
        Err(format!("Unknown topic: \"{}\"\n{}", wanted, hint))
    }
}

/// Gather candidate cards
pub fn collect_subtree_candidates(
    topic_index: &HashMap<DeckPath, Vec<Card>>,
    root_topic: &DeckPath,
    include_subtree: bool,
) -> Vec<Card> {
    if !include_subtree {
        return topic_index
            .get(root_topic)
            .cloned()
            .unwrap_or_else(Vec::new);
    }

    let mut results: Vec<Card> = Vec::new();
    for (path, cards) in topic_index {
        if path_starts_with(path, root_topic) {
            results.extend(cards.iter().cloned());
        }
    }
    results
}

/// True if `path` has `prefix` as its leading segments.
fn path_starts_with(path: &DeckPath, prefix: &DeckPath) -> bool {
    if prefix.len() > path.len() {
        return false;
    }
    for (index, prefix_segment) in prefix.iter().enumerate() {
        if path[index] != *prefix_segment {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn card_with_path(segments: &[&str]) -> Card {
        Card {
            guid: "g".to_string(),
            question_text: "q".to_string(),
            answer_raw: "a".to_string(),
            deck_path: segments.iter().map(|s| s.to_string()).collect(),
        }
    }

    #[test]
    fn test_build_and_collect() {
        let cards = vec![
            card_with_path(&["A", "B"]),
            card_with_path(&["A", "B", "C"]),
            card_with_path(&["A", "D"]),
            card_with_path(&["X"]),
        ];
        let index = build_topic_index(&cards);

        let exact = collect_subtree_candidates(&index, &vec!["A".into(), "B".into()], false);
        assert_eq!(exact.len(), 1);

        let sub = collect_subtree_candidates(&index, &vec!["A".into()], true);
        assert_eq!(sub.len(), 3);
    }

    #[test]
    fn test_resolve_topic_string() {
        let known = vec![
            vec!["A".into(), "B".into()],
            vec!["A".into(), "D".into()],
            vec!["X".into()],
        ];
        let resolved =
            resolve_topic_string("A::B", "::", &known).expect("should resolve");
        assert_eq!(resolved, vec!["A".into(), "B".into()]);
    }
}
