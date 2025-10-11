use std::collections::{HashSet, hash_map::RandomState};

use crate::config::ParserConfig;

/// Determine whether a token consists only of digits.
fn token_is_numeric(token_text: &str) -> bool {
    token_text.chars().all(|character| character.is_ascii_digit())
}

/// Split on non-alphanumeric characters, keep only tokens that pass length rules,
/// and remove stopwords if configured. Returns tokens in the original order.
pub fn tokenise(
    input_text: &str,
    stopword_set: &HashSet<String>,
    parser_config: &ParserConfig,
) -> Vec<String> {
    let mut tokens: Vec<String> = Vec::new();
    let mut current_token = String::new();

    // Build tokens using Unicode-aware classification.
    for character in input_text.chars() {
        if character.is_alphanumeric() {
            current_token.push(character.to_ascii_lowercase());
        } else {
            if !current_token.is_empty() {
                tokens.push(current_token.clone());
                current_token.clear();
            }
        }
    }
    if !current_token.is_empty() {
        tokens.push(current_token.clone());
        current_token.clear();
    }

    // Apply length and stopword rules
    let mut filtered_tokens: Vec<String> = Vec::with_capacity(tokens.len());
    for token_text in tokens.into_iter() {
        let token_length = token_text.chars().count();
        let is_numeric = token_is_numeric(&token_text);
        let meets_length_rule =
            token_length >= parser_config.min_token_length || is_numeric;

        if !meets_length_rule {
            continue;
        }
        if parser_config.remove_stopwords && stopword_set.contains(&token_text) {
            continue;
        }
        filtered_tokens.push(token_text);
    }

    filtered_tokens
}

/// As above, but return a set of unique tokens (order not preserved).
pub fn tokenise_to_set(
    input_text: &str,
    stopword_set: &HashSet<String>,
    parser_config: &ParserConfig,
) -> HashSet<String> {
    let sequence_tokens = tokenise(input_text, stopword_set, parser_config);
    sequence_tokens.into_iter().collect::<HashSet<String, RandomState>>()
}
