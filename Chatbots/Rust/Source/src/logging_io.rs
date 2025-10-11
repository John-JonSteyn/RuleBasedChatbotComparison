use std::fs::{create_dir_all, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::Path;

use anyhow::{Context, Result};
use serde_json::to_string;

use crate::data_model::{InvalidRecord, LogRecord};

/// Ensure the parent directory of `file_path` exists. No-op if it already exists.
fn ensure_parent_directory_exists(file_path: &str) -> Result<()> {
    if let Some(parent_directory) = Path::new(file_path).parent() {
        if !parent_directory.as_os_str().is_empty() && !parent_directory.exists() {
            create_dir_all(parent_directory).with_context(|| {
                format!(
                    "Failed to create parent directory for log file: {}",
                    parent_directory.display()
                )
            })?;
        }
    }
    Ok(())
}

/// Append a single line of text to a file, creating it if necessary.
fn append_text_line(file_path: &str, line_text: &str) -> Result<()> {
    ensure_parent_directory_exists(file_path)?;
    let file_handle = OpenOptions::new()
        .create(true)
        .append(true)
        .open(file_path)
        .with_context(|| format!("Failed to open log file for append: {}", file_path))?;

    let mut buffered_writer = BufWriter::new(file_handle);
    buffered_writer
        .write_all(line_text.as_bytes())
        .with_context(|| "Failed to write log line")?;
    buffered_writer
        .write_all(b"\n")
        .with_context(|| "Failed to write newline")?;
    buffered_writer.flush().ok();
    Ok(())
}

/// Write invalid-record entries as human-readable lines.
/// Format: `<file_path>:<line_number>  <reason>\n<raw_line>`
pub fn log_invalid_records(invalid_records: &[InvalidRecord], file_path: &str) -> Result<()> {
    if invalid_records.is_empty() {
        return Ok(());
    }
    for invalid_record in invalid_records {
        let composed_line = format!(
            "{}:{}  {}\n{}",
            invalid_record.file_path,
            invalid_record.line_number,
            invalid_record.reason,
            invalid_record.raw_line
        );
        append_text_line(file_path, &composed_line)?;
    }
    Ok(())
}

/// Append a single benchmark record in JSON Lines format.
pub fn log_benchmark(record: &LogRecord, file_path: &str) -> Result<()> {
    let json_text =
        to_string(record).with_context(|| "Failed to serialise benchmark record to JSON")?;
    append_text_line(file_path, &json_text)
}
