use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use crate::data_model::{Card, DeckPath, InvalidRecord};
use crate::normalise::normalise_for_matching;

const TAB_DELIMITER: char = '\t';

/// Find all `.txt` files under a path. If the path is a file, return just that file.
pub fn list_deck_files<P: AsRef<Path>>(data_path: P) -> Result<Vec<PathBuf>> {
    let path_ref = data_path.as_ref();
    if path_ref.is_file() {
        return Ok(vec![path_ref.to_path_buf()]);
    }
    let mut files: Vec<PathBuf> = Vec::new();
    for entry in fs::read_dir(path_ref)
        .with_context(|| format!("Failed to read data directory {}", path_ref.display()))?
    {
        let entry = entry?;
        let entry_path = entry.path();
        if entry_path.is_file() {
            if let Some(extension) = entry_path.extension() {
                if extension.to_string_lossy().eq_ignore_ascii_case("txt") {
                    files.push(entry_path);
                }
            }
        }
    }
    files.sort();
    Ok(files)
}

/// Read a single Anki `.txt` deck file into `Card`s, collecting invalid records.
pub fn read_deck_file<P: AsRef<Path>>(file_path: P) -> Result<(Vec<Card>, Vec<InvalidRecord>)> {
    let path_buf = file_path.as_ref().to_path_buf();
    let file_content = fs::read_to_string(&path_buf)
        .with_context(|| format!("Failed to read deck file {}", path_buf.display()))?;

    let mut cards: Vec<Card> = Vec::new();
    let mut invalid_records: Vec<InvalidRecord> = Vec::new();

    for (zero_based_index, line_text) in file_content.lines().enumerate() {
        let line_number = zero_based_index + 1;

        // Skip metadata header lines
        if let Some(first_char) = line_text.chars().next() {
            if first_char == '#' {
                continue;
            }
        } else {
            // Empty line: skip
            continue;
        }

        // Expect at least 5 columns
        let columns: Vec<&str> = line_text.split(TAB_DELIMITER).collect();
        if columns.len() < 5 {
            invalid_records.push(InvalidRecord {
                file_path: path_buf.display().to_string(),
                line_number,
                reason: format!("Expected at least 5 columns, found {}", columns.len()),
                raw_line: line_text.to_string(),
            });
            continue;
        }

        let guid_text = columns[0].trim();
        let deck_path_text = columns[2].trim();
        let question_html = columns[3].trim();
        let answer_html = columns[4].trim();

        if guid_text.is_empty() {
            invalid_records.push(InvalidRecord {
                file_path: path_buf.display().to_string(),
                line_number,
                reason: "Empty GUID".to_string(),
                raw_line: line_text.to_string(),
            });
            continue;
        }
        if question_html.is_empty() || answer_html.is_empty() {
            invalid_records.push(InvalidRecord {
                file_path: path_buf.display().to_string(),
                line_number,
                reason: "Empty question or answer".to_string(),
                raw_line: line_text.to_string(),
            });
            continue;
        }

        let deck_path: DeckPath = if deck_path_text.is_empty() {
            Vec::new()
        } else {
            deck_path_text
                .split("::")
                .map(|segment| segment.trim().to_string())
                .collect()
        };

        let question_text = normalise_for_matching(question_html);
        let answer_raw = answer_html.to_string();

        let card = Card {
            guid: guid_text.to_string(),
            question_text,
            answer_raw,
            deck_path,
        };

        cards.push(card);
    }

    Ok((cards, invalid_records))
}

/// Load a directory (or single file) of decks and concatenate results.
pub fn load_decks<P: AsRef<Path>>(data_path: P) -> Result<(Vec<Card>, Vec<InvalidRecord>)> {
    let mut all_cards: Vec<Card> = Vec::new();
    let mut all_invalid_records: Vec<InvalidRecord> = Vec::new();

    let files = list_deck_files(&data_path)?;
    if files.is_empty() {
        return Ok((all_cards, all_invalid_records));
    }

    for file_path in files {
        match read_deck_file(&file_path) {
            Ok((mut cards, mut invalids)) => {
                all_cards.append(&mut cards);
                all_invalid_records.append(&mut invalids);
            }
            Err(error) => {
                all_invalid_records.push(InvalidRecord {
                    file_path: file_path.display().to_string(),
                    line_number: 0,
                    reason: format!("Unreadable file: {error}"),
                    raw_line: String::new(),
                });
            }
        }
    }

    Ok((all_cards, all_invalid_records))
}
