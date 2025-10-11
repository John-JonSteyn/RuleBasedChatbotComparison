use anyhow::{anyhow, Context, Result};
use clap::{Arg, ArgAction, Command};
use std::collections::HashMap;
use std::io::{self, Write};

use crate::config::{load_parser_config, load_stopwords, ParserConfig};
use crate::data_model::{
    build_guid_index, deck_path_to_string, AnswerHit, Card, DeckPath, LogRecord, StageTimings,
};
use crate::io_decks::load_decks;
use crate::logging_io::{log_benchmark, log_invalid_records};
use crate::normalise::normalise_for_display;
use crate::timing::Stopwatch;
use crate::topics::{
    build_topic_index, collect_subtree_candidates, list_available_topics, resolve_topic_string,
};
use crate::scoring::keyword::{prepare_keyword_index, score_keyword_overlap, PreparedQuestion};
use crate::scoring::tfidf::{build_tfidf_index, score_tfidf, TfidfIndex};

const DEFAULT_DATA_PATH: &str = "Data/Decks";
const DEFAULT_PARSER_CONFIG_PATH: &str = "Data/Configs/Parser.json";

/// Command-line entry point. Mirrors the Python CLI behaviour.
pub fn run() -> Result<()> {
    let argument_matches = Command::new("rulebot-rust")
        .about("Rule-based chatbot over Anki decks (Rust)")
        // parity with Python: data and parser-config are fixed defaults, not CLI args
        .arg(
            Arg::new("topic")
                .long("topic")
                .required(false)
                .help("Deck path (e.g., \"Launch into Computing::Unit 03 - Principles of Computer Science\"). If omitted, all topics are searched."),
        )
        .arg(
            Arg::new("algo")
                .long("algo")
                .required(true)
                .value_parser(["keyword", "tfidf"])
                .help("Retrieval algorithm."),
        )
        .arg(
            Arg::new("k")
                .long("k")
                .value_parser(clap::value_parser!(usize))
                .default_value("1")
                .help("Number of answers to return (default: 1)."),
        )
        .arg(
            Arg::new("interactive")
                .long("interactive")
                .action(ArgAction::SetTrue)
                .help("Interactive session."),
        )
        .arg(
            Arg::new("query")
                .long("query")
                .help("Answer a single query and exit."),
        )
        .arg(
            Arg::new("log")
                .long("log")
                .help("Append per-query JSON line logs to this file."),
        )
        .arg(
            Arg::new("invalid_log")
                .long("invalid-log")
                .default_value("Logs/errors-rs.log")
                .help("Path to invalid record log file."),
        )
        .arg(
            Arg::new("warmup")
                .long("warmup")
                .value_parser(clap::value_parser!(usize))
                .default_value("0")
                .help("Number of warm-up queries before timing."),
        )
        .arg(
            Arg::new("include_subtree")
                .long("include-subtree")
                .value_parser(["true", "false"])
                .help("Override config include_subtree."),
        )
        .arg(
            Arg::new("show_cards")
                .long("show-cards")
                .action(ArgAction::SetTrue)
                .help("Print GUIDs and scores for returned results."),
        )
        .get_matches();

    // Load configuration and stopwords from fixed paths
    let parser_config =
        load_parser_config(DEFAULT_PARSER_CONFIG_PATH).with_context(|| "Failed to load parser configuration")?;

    let stopword_set = if parser_config.remove_stopwords {
        let stopwords_path = parser_config
            .stopwords_path
            .as_ref()
            .expect("validated by load_parser_config");
        load_stopwords(stopwords_path)?
    } else {
        Default::default()
    };

    // Load decks with timing from the fixed data path
    let mut stopwatch_parse = Stopwatch::new();
    stopwatch_parse.start();
    let (all_cards, invalid_records) = load_decks(DEFAULT_DATA_PATH)?;
    let parse_milliseconds = stopwatch_parse.stop();

    if !invalid_records.is_empty() {
        let invalid_log_path = argument_matches
            .get_one::<String>("invalid_log")
            .expect("has default");
        let _ = log_invalid_records(&invalid_records, invalid_log_path);
    }

    if all_cards.is_empty() {
        return Err(anyhow!(
            "No valid cards were loaded. Check your data path and data contract."
        ));
    }

    // Determine candidate pool: topic subtree if provided, otherwise all cards
    let include_subtree_value = match argument_matches.get_one::<String>("include_subtree") {
        Some(value_text) => value_text == "true",
        None => parser_config.include_subtree,
    };

    let (candidate_cards, topic_label_for_logs): (Vec<Card>, String) = if let Some(requested_topic_text) =
        argument_matches.get_one::<String>("topic")
    {
        let known_topics = list_available_topics(&all_cards);
        let resolved_root_topic: DeckPath = resolve_topic_string(
            requested_topic_text,
            &parser_config.topic_separator,
            &known_topics,
        )
        .map_err(|message| anyhow!(message))?;

        let topic_index = build_topic_index(&all_cards);
        let candidates =
            collect_subtree_candidates(&topic_index, &resolved_root_topic, include_subtree_value);

        if candidates.is_empty() {
            return Err(anyhow!(
                "No candidate cards found for the requested topic."
            ));
        }
        (candidates, requested_topic_text.to_string())
    } else {
        (all_cards.clone(), "<ALL>".to_string())
    };

    println!(
        "Loaded {} cards; {} candidates in topic '{}'.",
        all_cards.len(),
        candidate_cards.len(),
        topic_label_for_logs
    );

    // Build indices with timing
    let mut stopwatch_index = Stopwatch::new();
    stopwatch_index.start();

    let algorithm_name = argument_matches
        .get_one::<String>("algo")
        .expect("required by clap")
        .to_string();

    let guid_index_map: HashMap<String, Card> = build_guid_index(&candidate_cards);
    let mut prepared_keyword_index: Option<Vec<PreparedQuestion>> = None;
    let mut tfidf_index: Option<TfidfIndex> = None;

    let index_milliseconds = if algorithm_name == "keyword" {
        prepared_keyword_index =
            Some(prepare_keyword_index(&candidate_cards, &stopword_set, &parser_config));
        stopwatch_index.stop()
    } else {
        tfidf_index = Some(build_tfidf_index(
            &candidate_cards,
            &stopword_set,
            &parser_config,
        ));
        stopwatch_index.stop()
    };

    // Mode: interactive or single query
    let is_interactive = *argument_matches
        .get_one::<bool>("interactive")
        .expect("set by clap");

    let top_k = *argument_matches
        .get_one::<usize>("k")
        .expect("defaulted by clap");

    let warmup_count = *argument_matches
        .get_one::<usize>("warmup")
        .expect("defaulted by clap");

    let log_path_option = argument_matches.get_one::<String>("log").cloned();

    if is_interactive {
        println!("Interactive mode. Type a question, or 'exit' to exit.");
        let mut input_buffer = String::new();
        loop {
            input_buffer.clear();
            print!("> ");
            let _ = io::stdout().flush();
            if io::stdin().read_line(&mut input_buffer).is_err() {
                println!("\nExiting.");
                break;
            }
            let user_query_text = input_buffer.trim().to_string();
            if user_query_text.eq_ignore_ascii_case("exit") {
                break;
            }
            if user_query_text.is_empty() {
                continue;
            }
            run_single_query(
                &user_query_text,
                &algorithm_name,
                &guid_index_map,
                prepared_keyword_index.as_ref(),
                tfidf_index.as_ref(),
                &parser_config,
                &stopword_set,
                warmup_count,
                top_k,
                log_path_option.as_deref(),
                candidate_cards.len(),
                &topic_label_for_logs,
                *argument_matches.get_one::<bool>("show_cards").unwrap_or(&false),
            )?;
        }
    } else {
        let single_query_text = argument_matches
            .get_one::<String>("query")
            .ok_or_else(|| anyhow!("--query is required unless --interactive is set"))?;
        run_single_query(
            single_query_text,
            &algorithm_name,
            &guid_index_map,
            prepared_keyword_index.as_ref(),
            tfidf_index.as_ref(),
            &parser_config,
            &stopword_set,
            warmup_count,
            top_k,
            log_path_option.as_deref(),
            candidate_cards.len(),
            &topic_label_for_logs,
            *argument_matches.get_one::<bool>("show_cards").unwrap_or(&false),
        )?;
    }

    println!(
        "Parse build: {:.3} ms   Index build: {:.3} ms",
        parse_milliseconds, index_milliseconds
    );

    Ok(())
}

/// Run a single query end-to-end (warm-up, score, print, optional benchmark log).
#[allow(clippy::too_many_arguments)]
fn run_single_query(
    query_text: &str,
    algorithm_name: &str,
    guid_index_map: &HashMap<String, Card>,
    prepared_keyword_index_option: Option<&Vec<crate::scoring::keyword::PreparedQuestion>>,
    tfidf_index_option: Option<&crate::scoring::tfidf::TfidfIndex>,
    parser_config: &ParserConfig,
    stopword_set: &std::collections::HashSet<String>,
    warmup_count: usize,
    top_k: usize,
    log_path_option: Option<&str>,
    candidate_deck_size_for_log: usize,
    topic_text_for_log: &str,
    show_cards_flag: bool,
) -> Result<()> {
    if warmup_count > 0 {
        for _ in 0..warmup_count {
            if algorithm_name == "keyword" {
                let _ = score_keyword_overlap(
                    "warmup",
                    prepared_keyword_index_option.expect("built earlier"),
                    stopword_set,
                    parser_config,
                    top_k,
                );
            } else {
                let _ = score_tfidf(
                    "warmup",
                    tfidf_index_option.expect("built earlier"),
                    stopword_set,
                    parser_config,
                    top_k,
                );
            }
        }
    }

    let mut stopwatch_total = Stopwatch::new();
    stopwatch_total.start();

    let mut stopwatch_rank = Stopwatch::new();
    stopwatch_rank.start();

    let answer_hits: Vec<AnswerHit> = if algorithm_name == "keyword" {
        score_keyword_overlap(
            query_text,
            prepared_keyword_index_option.expect("built earlier"),
            stopword_set,
            parser_config,
            top_k,
        )
    } else {
        score_tfidf(
            query_text,
            tfidf_index_option.expect("built earlier"),
            stopword_set,
            parser_config,
            top_k,
        )
    };

    let rank_milliseconds = stopwatch_rank.stop();
    let wall_milliseconds = stopwatch_total.stop();

    println!("{}", format_hits_for_display(&answer_hits, guid_index_map));
    if show_cards_flag {
        for answer_hit in &answer_hits {
            println!("-> {}  score={:.6}", answer_hit.guid, answer_hit.score);
        }
    }

    if let Some(log_file_path) = log_path_option {
        let stage_timings = StageTimings {
            parse_milliseconds: 0.0,
            index_milliseconds: 0.0,
            preprocess_milliseconds: 0.0,
            rank_milliseconds: rank_milliseconds,
            format_milliseconds: 0.0,
        };
        let benchmark_record = LogRecord {
            timestamp_iso: chrono::Utc::now().to_rfc3339(),
            language: "rust".to_string(),
            algorithm: algorithm_name.to_string(),
            deck_size: candidate_deck_size_for_log,
            topic: topic_text_for_log.to_string(),
            query_id: "ad-hoc".to_string(),
            query_text: query_text.to_string(),
            stage_milliseconds: stage_timings,
            wall_milliseconds: wall_milliseconds,
            rss_kilobytes: None,
            top: answer_hits
                .iter()
                .map(|answer_hit| (answer_hit.guid.clone(), answer_hit.score as f64))
                .collect(),
        };
        let _ = log_benchmark(&benchmark_record, log_file_path);
    }

    Ok(())
}

/// Format result hits like Python: rank, GUID, score, topic, full Q and full escaped A.
fn format_hits_for_display(
    answer_hits: &[AnswerHit],
    guid_index_map: &HashMap<String, Card>,
) -> String {
    if answer_hits.is_empty() {
        return "No results.".to_string();
    }
    let mut output_lines: Vec<String> = Vec::new();
    for (rank_index, answer_hit) in answer_hits.iter().enumerate() {
        if let Some(card) = guid_index_map.get(&answer_hit.guid) {
            let topic_text = deck_path_to_string(&answer_hit.deck_path);
            let question_line = answer_hit
                .question_preview
                .clone()
                .unwrap_or_else(|| card.question_text.clone());
            let answer_display = normalise_for_display(&card.answer_raw);

            output_lines.push(format!(
                "{}. GUID={}  score={:.6}  topic={}",
                rank_index + 1,
                answer_hit.guid,
                answer_hit.score,
                topic_text
            ));
            output_lines.push(format!("   Q: {}", question_line));
            output_lines.push(format!("   A: {}", answer_display));
        }
    }
    output_lines.join("\n")
}
