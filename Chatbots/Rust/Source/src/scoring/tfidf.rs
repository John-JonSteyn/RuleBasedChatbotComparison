use std::collections::HashMap;
use std::collections::HashSet;

use crate::config::ParserConfig;
use crate::data_model::{make_hit, AnswerHit, Card};
use crate::tokenise::{tokenise, tokenise_to_set};

/// A single TF vector for a document (question), with metadata for display.
#[derive(Debug, Clone)]
pub struct DocumentEntry {
    pub guid: String,
    pub deck_path: Vec<String>,
    pub question_preview: String,
    pub term_frequencies: HashMap<String, f32>,
    pub token_count: usize,
}

/// The TF–IDF index with per-document TF maps, global IDF weights, and precomputed norms.
#[allow(dead_code)]
#[derive(Debug, Clone)]
pub struct TfidfIndex {
    pub documents: Vec<DocumentEntry>,
    pub inverse_document_frequency: HashMap<String, f32>,
    pub document_l2_norms: Vec<f32>,
    pub vocabulary_size: usize,
    pub document_count: usize,
}

/// Build a TF–IDF index over the candidate cards (question text only).
/// - TF = raw term count
/// - IDF = log((N + 1) / (df + 1)) + 1
/// - Document vectors L2-normalised during scoring via precomputed norms
pub fn build_tfidf_index(
    candidate_cards: &[Card],
    stopword_set: &HashSet<String>,
    parser_config: &ParserConfig,
) -> TfidfIndex {
    let mut document_entries: Vec<DocumentEntry> = Vec::with_capacity(candidate_cards.len());
    let mut document_frequency_map: HashMap<String, usize> = HashMap::new();

    // 1) Build documents with raw TF and gather DF
    for card in candidate_cards {
        let token_vector = tokenise(&card.question_text, stopword_set, parser_config);
        let token_count = token_vector.len();

        let mut term_counts: HashMap<String, usize> = HashMap::new();
        for token_text in token_vector {
            *term_counts.entry(token_text).or_insert(0) += 1;
        }

        // Increment DF once per unique term in this document
        let unique_terms = term_counts.keys().cloned().collect::<HashSet<String>>();
        for unique_term in unique_terms {
            *document_frequency_map.entry(unique_term).or_insert(0) += 1;
        }

        // Convert usize counts to f32 early for speed later
        let term_frequencies = term_counts
            .into_iter()
            .map(|(term_text, count_value)| (term_text, count_value as f32))
            .collect::<HashMap<String, f32>>();

        let document_entry = DocumentEntry {
            guid: card.guid.clone(),
            deck_path: card.deck_path.clone(),
            question_preview: card.question_text.clone(),
            term_frequencies,
            token_count,
        };
        document_entries.push(document_entry);
    }

    let document_count = document_entries.len();
    let mut inverse_document_frequency: HashMap<String, f32> = HashMap::new();

    // 2) Compute IDF with smoothing: log((N + 1) / (df + 1)) + 1
    for (term_text, document_frequency) in document_frequency_map.into_iter() {
        let numerator = (document_count as f32) + 1.0;
        let denominator = (document_frequency as f32) + 1.0;
        let idf_value = (numerator / denominator).ln() + 1.0;
        inverse_document_frequency.insert(term_text, idf_value);
    }

    // 3) Precompute document vector norms (L2)
    let mut document_l2_norms: Vec<f32> = Vec::with_capacity(document_entries.len());
    for document_entry in &document_entries {
        let mut squared_sum: f32 = 0.0;
        for (term_text, term_frequency) in &document_entry.term_frequencies {
            let idf_value = *inverse_document_frequency.get(term_text).unwrap_or(&0.0);
            let weighted_value = (*term_frequency) * idf_value;
            squared_sum += weighted_value * weighted_value;
        }
        document_l2_norms.push(squared_sum.sqrt());
    }

    let vocabulary_size = inverse_document_frequency.len();

    TfidfIndex {
        documents: document_entries,
        inverse_document_frequency,
        document_l2_norms,
        vocabulary_size,
        document_count,
    }
}

/// Rank candidates by cosine similarity between the query TF–IDF vector and each document.
/// Tie-breakers (after equal similarity):
/// 1) Greater count of overlapping non-stopword tokens
/// 2) Shorter candidate question by token count
/// 3) Lexicographic order of GUID
pub fn score_tfidf(
    query_text: &str,
    tfidf_index: &TfidfIndex,
    stopword_set: &HashSet<String>,
    parser_config: &ParserConfig,
    top_k: usize,
) -> Vec<AnswerHit> {
    // 1) Tokenise the query and build its TF map
    let query_token_vector = tokenise(query_text, stopword_set, parser_config);
    if query_token_vector.is_empty() {
        return Vec::new();
    }

    let mut query_term_counts: HashMap<String, usize> = HashMap::new();
    for token_text in query_token_vector.iter() {
        *query_term_counts.entry(token_text.clone()).or_insert(0) += 1;
    }

    // 2) Convert to TF–IDF and compute query norm
    let mut query_weighted_map: HashMap<String, f32> = HashMap::new();
    for (term_text, count_value) in &query_term_counts {
        let idf_value = *tfidf_index
            .inverse_document_frequency
            .get(term_text)
            .unwrap_or(&0.0);
        if idf_value == 0.0 {
            continue; // term unseen in the corpus → contributes nothing
        }
        query_weighted_map.insert(term_text.clone(), (*count_value as f32) * idf_value);
    }

    let mut query_squared_sum: f32 = 0.0;
    for weighted_value in query_weighted_map.values() {
        query_squared_sum += weighted_value * weighted_value;
    }
    let query_l2_norm = query_squared_sum.sqrt();
    if query_l2_norm == 0.0 {
        return Vec::new();
    }

    // Prepare set for overlap-based tie-breaker
    let query_token_set = tokenise_to_set(query_text, stopword_set, parser_config);

    // 3) Score each document by cosine similarity
    let mut scored_hits: Vec<(AnswerHit, f32, usize, usize)> = Vec::with_capacity(tfidf_index.documents.len());
    for (document_index, document_entry) in tfidf_index.documents.iter().enumerate() {
        let document_norm = tfidf_index.document_l2_norms[document_index];
        if document_norm == 0.0 {
            continue;
        }

        // Dot product only over query terms present in the document
        let mut dot_product_sum: f32 = 0.0;
        for (term_text, query_weight) in &query_weighted_map {
            if let Some(document_tf) = document_entry.term_frequencies.get(term_text) {
                let idf_value = *tfidf_index
                    .inverse_document_frequency
                    .get(term_text)
                    .unwrap_or(&0.0);
                if idf_value != 0.0 {
                    let document_weight = (*document_tf) * idf_value;
                    dot_product_sum += query_weight * document_weight;
                }
            }
        }

        if dot_product_sum == 0.0 {
            continue;
        }

        let cosine_similarity = dot_product_sum / (query_l2_norm * document_norm);

        // Tie-breakers need overlap count and question length
        let document_token_set = document_entry
            .term_frequencies
            .keys()
            .cloned()
            .collect::<HashSet<String>>();
        let overlap_count = document_token_set
            .intersection(&query_token_set)
            .count();

        let answer_hit = make_hit(
            document_entry.guid.clone(),
            document_entry.deck_path.clone(),
            Some(document_entry.question_preview.clone()),
            cosine_similarity,
        );

        scored_hits.push((
            answer_hit,
            cosine_similarity,
            overlap_count,
            document_entry.token_count,
        ));
    }

    // 4) Sort with tie-breakers: higher similarity, then higher overlap, then shorter question, then lexicographic GUID
    scored_hits.sort_by(|left, right| {
        right.1.partial_cmp(&left.1).unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| right.2.cmp(&left.2)) // greater overlap wins
            .then_with(|| left.3.cmp(&right.3)) // shorter question wins
            .then_with(|| left.0.guid.cmp(&right.0.guid))
    });

    scored_hits
        .into_iter()
        .take(top_k)
        .map(|tuple| tuple.0)
        .collect()
}
