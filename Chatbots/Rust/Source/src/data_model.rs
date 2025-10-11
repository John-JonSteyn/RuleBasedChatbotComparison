use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fmt;

/// A hierarchical deck path, e.g. ["Launch into Computing", "Unit 03 - Principles of Computer Science"].
pub type DeckPath = Vec<String>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Card {
    pub guid: String,
    pub question_text: String, // normalised for matching (tags stripped, entities decoded, lowercased)
    pub answer_raw: String,    // raw HTML/text for display; never render without escaping
    pub deck_path: DeckPath,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnswerHit {
    pub guid: String,
    pub score: f32,
    pub question_preview: Option<String>,
    pub deck_path: DeckPath,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryRequest {
    pub query_text: String,
    pub topic_text: String,
    pub algorithm_name: String,
    pub top_k: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StageTimings {
    pub parse_milliseconds: f64,
    pub index_milliseconds: f64,
    pub preprocess_milliseconds: f64,
    pub rank_milliseconds: f64,
    pub format_milliseconds: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogRecord {
    pub timestamp_iso: String,
    pub language: String,   // "rust" or "python"
    pub algorithm: String,  // "keyword" or "tfidf"
    pub deck_size: usize,
    pub topic: String,
    pub query_id: String,
    pub query_text: String,
    pub stage_milliseconds: StageTimings,
    pub wall_milliseconds: f64,
    pub rss_kilobytes: Option<u64>,
    pub top: Vec<(String, f64)>,
}

/// Invalid line metadata captured during deck parsing/validation.
#[derive(Debug, Clone)]
pub struct InvalidRecord {
    pub file_path: String,
    pub line_number: usize,
    pub reason: String,
    pub raw_line: String,
}

/// Convert a deck path to a human-readable string (uses "::" separator).
pub fn deck_path_to_string(deck_path: &DeckPath) -> String {
    deck_path.join("::")
}

/// Create a short preview of text, truncated to `max_length` with an ellipsis if needed.
#[allow(dead_code)]
pub fn short_preview(full_text: &str, max_length: usize) -> String {
    if full_text.len() <= max_length {
        full_text.to_string()
    } else if max_length <= 1 {
        "…".to_string()
    } else {
        let cut_index = max_length.saturating_sub(1);
        format!("{}…", &full_text[..cut_index])
    }
}

/// Convenience: build a GUID → Card index for fast lookups.
pub fn build_guid_index(cards: &[Card]) -> HashMap<String, Card> {
    let mut guid_index = HashMap::new();
    for card in cards {
        guid_index.insert(card.guid.clone(), card.clone());
    }
    guid_index
}

/// Optional helper for constructing `AnswerHit`.
pub fn make_hit(guid: String, deck_path: DeckPath, question_preview: Option<String>, score: f32) -> AnswerHit {
    AnswerHit {
        guid,
        deck_path,
        question_preview,
        score,
    }
}

/// Pretty print a hit line (useful during early testing).
impl fmt::Display for AnswerHit {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(preview_text) = &self.question_preview {
            write!(
                formatter,
                "GUID={}  score={:.6}  topic={}  Q: {}",
                self.guid,
                self.score,
                deck_path_to_string(&self.deck_path),
                preview_text
            )
        } else {
            write!(
                formatter,
                "GUID={}  score={:.6}  topic={}",
                self.guid,
                self.score,
                deck_path_to_string(&self.deck_path)
            )
        }
    }
}
