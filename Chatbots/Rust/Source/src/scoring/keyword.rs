use std::collections::HashSet;

use crate::config::ParserConfig;
use crate::data_model::{make_hit, AnswerHit, Card};
use crate::tokenise::{tokenise, tokenise_to_set};

/// A prepared representation of a candidate question for keyword overlap scoring.
#[derive(Debug, Clone)]
pub struct PreparedQuestion {
    pub guid: String,
    pub deck_path: Vec<String>,
    pub question_preview: String,
    pub token_set: HashSet<String>,
    pub token_count: usize,
}

/// Build a prepared index over candidate cards for keyword overlap scoring.
pub fn prepare_keyword_index(
    candidate_cards: &[Card],
    stopword_set: &std::collections::HashSet<String>,
    parser_config: &ParserConfig,
) -> Vec<PreparedQuestion> {
    let mut prepared_list: Vec<PreparedQuestion> = Vec::with_capacity(candidate_cards.len());
    for card in candidate_cards {
        let token_vector = tokenise(&card.question_text, stopword_set, parser_config);
        let token_set = token_vector.iter().cloned().collect::<HashSet<String>>();
        let prepared_question = PreparedQuestion {
            guid: card.guid.clone(),
            deck_path: card.deck_path.clone(),
            question_preview: card.question_text.clone(),
            token_set,
            token_count: token_vector.len(),
        };
        prepared_list.push(prepared_question);
    }
    prepared_list
}

/// Score candidates by keyword overlap (sum of weights = 1 per overlapping token).
/// Tie-breakers:
/// 1) Greater count of overlapping non-stopword tokens
/// 2) Shorter candidate question by token count
/// 3) Lexicographic order of GUID
pub fn score_keyword_overlap(
    query_text: &str,
    prepared_index: &[PreparedQuestion],
    stopword_set: &std::collections::HashSet<String>,
    parser_config: &ParserConfig,
    top_k: usize,
) -> Vec<AnswerHit> {
    let query_token_set = tokenise_to_set(query_text, stopword_set, parser_config);

    let mut scored_hits: Vec<(AnswerHit, usize, usize)> = Vec::with_capacity(prepared_index.len());

    for prepared_question in prepared_index {
        let overlap_count = query_token_set
            .intersection(&prepared_question.token_set)
            .count();

        if overlap_count == 0 {
            // Baseline disallows stopword weights and gives no phrase boosts; zero overlap → score 0, skip.
            continue;
        }

        let score_value = overlap_count as f32; // default weight = 1 per token
        let answer_hit = make_hit(
            prepared_question.guid.clone(),
            prepared_question.deck_path.clone(),
            Some(prepared_question.question_preview.clone()),
            score_value,
        );

        scored_hits.push((
            answer_hit,
            overlap_count,
            prepared_question.token_count,
        ));
    }

    // Sort with tie-breakers: higher score, then higher overlap, then shorter question, then lexicographic GUID
    scored_hits.sort_by(|left, right| {
        right.0.score.partial_cmp(&left.0.score).unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| right.1.cmp(&left.1)) // greater overlap wins
            .then_with(|| left.2.cmp(&right.2)) // shorter question wins
            .then_with(|| left.0.guid.cmp(&right.0.guid))
    });

    scored_hits
        .into_iter()
        .take(top_k)
        .map(|tuple| tuple.0)
        .collect()
}
