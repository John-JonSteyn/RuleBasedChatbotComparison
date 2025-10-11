use std::{collections::HashSet, fs, path::Path};

use anyhow::{anyhow, Context, Result};
use serde::Deserialize;

#[allow(dead_code)]
#[derive(Debug, Deserialize, Clone)]
pub struct ParserConfig {
    #[serde(default = "default_split_on_non_alnum")]
    pub split_on_non_alnum: bool,
    #[serde(default = "default_keep_digits")]
    pub keep_digits: bool,
    #[serde(default = "default_min_token_length")]
    pub min_token_length: usize,
    #[serde(default = "default_remove_stopwords")]
    pub remove_stopwords: bool,
    #[serde(default)]
    pub stopwords_path: Option<String>,

    #[serde(default = "default_topic_separator")]
    pub topic_separator: String,
    #[serde(default = "default_include_subtree")]
    pub include_subtree: bool,
    
    #[serde(default = "default_idf_smoothing")]
    pub idf_smoothing: bool,
}
fn default_split_on_non_alnum() -> bool {
    true
}
fn default_keep_digits() -> bool {
    true
}
fn default_min_token_length() -> usize {
    2
}
fn default_remove_stopwords() -> bool {
    true
}
fn default_topic_separator() -> String {
    "::".to_string()
}
fn default_include_subtree() -> bool {
    true
}
fn default_idf_smoothing() -> bool {
    true
}

pub fn load_parser_config<P: AsRef<Path>>(path: P) -> Result<ParserConfig> {
    let raw_json = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read Parser.json at {}", path.as_ref().display()))?;

    #[derive(Deserialize)]
    struct MaybeNested {
        #[serde(default)]
        tokenisation: Option<ParserConfig>,
    }

    let parsed_json: serde_json::Value = serde_json::from_str(&raw_json)
        .with_context(|| "Parser.json is not valid JSON")?;

    // Try nested
    if let Ok(nested) = serde_json::from_value::<MaybeNested>(parsed_json.clone()) {
        if let Some(configuration) = nested.tokenisation {
            if configuration.remove_stopwords
                && configuration.stopwords_path.as_deref().unwrap_or("").is_empty()
            {
                return Err(anyhow!(
                    "Stopwords file path is required when remove_stopwords=true"
                ));
            }
            return Ok(configuration);
        }
    }

    // Try flat directly into ParserConfig
    let configuration: ParserConfig = serde_json::from_value(parsed_json)
        .with_context(|| "Parser.json does not match expected schema")?;
    if configuration.remove_stopwords
        && configuration.stopwords_path.as_deref().unwrap_or("").is_empty()
    {
        return Err(anyhow!(
            "Stopwords file path is required when remove_stopwords=true"
        ));
    }
    Ok(configuration)
}

pub fn load_stopwords<P: AsRef<Path>>(path: P) -> Result<HashSet<String>> {
    let content = fs::read_to_string(&path)
        .with_context(|| format!("Failed to read stopwords at {}", path.as_ref().display()))?;
    let mut stopwords_set = HashSet::new();
    for line in content.lines() {
        let trimmed_line = line.trim();
        if trimmed_line.is_empty() || trimmed_line.starts_with('#') {
            continue;
        }
        stopwords_set.insert(trimmed_line.to_lowercase());
    }
    Ok(stopwords_set)
}
