# Benchmark and Analysis Tools

This folder contains two scripts:

* `benchmark.py` — executes a reproducible, parity-focused benchmark across implementations and algorithms, writing row-level and summary CSVs from CLI JSONL logs.
* `analyse.py` — aggregates results from one or more benchmark runs (multiple seeds), computes summaries and speedups, and generates charts and a markdown report.

Both scripts assume decks and configs under `Data/`, and that the command-line apps write JSONL logs when invoked with `--log`.

---

## Prerequisites

* Decks and configs available under `Data/`:

  ```
  Data/
  ├── Decks/                # Anki note exports (plain text)
  └── Configs/
      ├── Parser.json
      └── Stopwords.txt
  ```

* The CLI modules present at:

  * Python CLI module: `Chatbots/Python/Source/cli.py` (invoked as `python -m Chatbots.Python.Source.cli`)
  * Other CLI manifest: `Chatbots/Rust/Source/Cargo.toml` (invoked via `cargo run --manifest-path ...`)

* Python 3.12+ on PATH.

* Cargo/rustc on PATH if you include that implementation in `--implementations`.

### Python packages for the Tools

Install minimal dependencies for the Tools:

```bash
pip install pandas matplotlib tabulate
```

`tabulate` is only needed for pretty markdown tables in `analyse.py`; without it the report falls back to plain text tables.

---

## Adding Decks

To add new data for benchmarking, simply **export decks from Anki** in *Plain Text* format.

### **Export Settings (from Anki)**

When exporting decks, use the following configuration:

* [ ] Include HTML and media references - Not required for text-only benchmarking
* [ ] Include tags - Exclude to simplify parsing
* [x] Include deck name - Required for topic grouping
* [x] Include note type name - Required for consistent field mapping
* [x] Include unique identifier - Required to verify correctness during benchmarking

**Format:**
`Notes in Plain Text (.txt)`

After export, place your deck files under:

```
Data/
└── Decks/
    ├── Deck1.txt
    ├── Deck2.txt
    └── ...
```

Each file will automatically be parsed and indexed using the configuration specified in:

```
Data/Configs/Parser.json
```

---

## Benchmark

The benchmark evaluates implementation performance and parity rather than retrieval quality. It uses deck questions as queries and checks whether the originating card is ranked top-1.

### What it does

1. Loads all decks once using `Data/Configs/Parser.json` to ensure identical preprocessing.
2. Groups cards by deck topic.
3. Deterministically samples a fixed number of questions per deck (`--seed`, `--questions-per-deck`).
4. Splits samples into:

   * topic scope: queries restricted to the card’s own deck/topic subtree,
   * global scope: queries run across all decks (optional).
5. Runs each implementation × algorithm, capturing the latest JSONL log line per query.
6. Extracts top GUID and stage timings, then writes:

   * `results_seed_<N>.csv` (row-level),
   * `summary_seed_<N>.csv` (aggregates).

### Usage

From the repository root.

#### Example: topic-scoped only (default if no scope flags provided)

```bash
python Tools/benchmark.py \
  --seed 42 \
  --questions-per-deck 10 \
  --algorithms keyword,tfidf \
  --implementations python,rust
```

PowerShell:

```powershell
python .\Tools\benchmark.py `
  --seed 42 `
  --questions-per-deck 10 `
  --algorithms keyword,tfidf `
  --implementations python,rust
```

#### Example: topic + global scopes

```bash
python Tools/benchmark.py \
  --seed 123 \
  --questions-per-deck 8 \
  --algorithms tfidf \
  --implementations python,rust \
  --topic-scope \
  --global-scope
```

#### Example: single implementation

```bash
python Tools/benchmark.py \
  --questions-per-deck 5 \
  --implementations python
```

### Command-line options

| Flag                   | Type     | Default                                  | Description                                          |
| ---------------------- | -------- | ---------------------------------------- | ---------------------------------------------------- |
| `--seed`               | int      | `42`                                     | Random seed for deterministic sampling of questions. |
| `--questions-per-deck` | int      | `10`                                     | Number of questions sampled from each deck.          |
| `--algorithms`         | csv-list | `keyword,tfidf`                          | Which retrieval algorithms to run.                   |
| `--implementations`    | csv-list | `python,rust`                            | Which implementations to run.                        |
| `--topic-scope`        | flag     | off (topic-only if neither scope is set) | Restrict queries to their own deck/topic subtree.    |
| `--global-scope`       | flag     | off                                      | Run queries against all decks.                       |
| `--rust-manifest`      | path     | `Chatbots/Rust/Source/Cargo.toml`        | Path to the Cargo manifest for that implementation.  |

Scope behavior: if neither `--topic-scope` nor `--global-scope` is provided, the script runs topic-only.

### Outputs

Written to `Results/Bench/`:

* JSONL logs (truncated at start of run)

  * `seed_<N>_python.jsonl`
  * `seed_<N>_rust.jsonl`
* Row-level CSV

  * `results_seed_<N>.csv`
    Columns: seed, implementation, algorithm, scope, deck_name, deck_card_count, query_id, query_text, expected_guid, top_guid, match, wall_ms, rank_ms, parse_ms, index_ms, timestamp, error
* Summary CSV

  * `summary_seed_<N>.csv`
    Aggregations per (implementation, algorithm, scope): queries, accuracy_at_1, median_wall_ms, p90_wall_ms, median_rank_ms, p90_rank_ms

---

## Analysis

The analysis script ingests all `results_seed_*.csv` files, computes aggregate summaries across seeds, derives speedup ratios, and produces diagnostic charts and a markdown report.

### What it does

* Loads every `Results/Bench/results_seed_*.csv`.
* Computes aggregate accuracy and timing percentiles per (implementation, algorithm, scope).
* Computes median wall-time speedup ratios between implementations for each (algorithm, scope).
* Extracts any error rows for quick triage.
* Generates plots per scope:

  * Accuracy@1 bars,
  * Wall-time box plots,
  * Stacked median stage times (parse/index/rank),
  * Scalability (median wall_ms vs deck size),
  * Wall-time histograms.
* Writes a markdown report linking all figures.

### Usage

From the repository root:

```bash
python Tools/analyse.py
```

PowerShell:

```powershell
python .\Tools\analyse.py
```

### Outputs

Written to `Results/Bench/`:

* Tables

  * `summary_all_seeds.csv` — accuracy and timing percentiles aggregated across seeds
  * `speedup_wall_ms.csv` — median wall-time speedup ratios between implementations
  * `errors_all_seeds.csv` — any rows with non-empty error messages
* Plots (per scope) in `Results/Bench/Plots/`

  * `accuracy_bar_<scope>.png`
  * `wall_ms_box_<scope>.png`
  * `stage_ms_stacked_<scope>.png`
  * `scalability_wall_vs_decksize_<scope>.png`
  * `wall_ms_hist_<scope>.png`
* Report

  * `report_all_seeds.md` — human-readable summary with tables and embedded figure links

### Wall-time distribution (topic scope)
<p align="center">
  <img src="Results/Bench/Plots/wall_ms_box_topic.png" width="560" alt="Wall time box plot (topic scope)" />
</p>

### Stage timing breakdown (median, topic scope)
<p align="center">
  <img src="Results/Bench/Plots/stage_ms_stacked_topic.png" width="560" alt="Stacked median stage timings (parse/index/rank)" />
</p>

### Scalability: wall-time vs deck size (topic scope)
<p align="center">
  <img src="Results/Bench/Plots/scalability_wall_vs_decksize_topic.png" width="560" alt="Median wall time vs deck size" />
</p>

### Wall-time histogram (topic scope)
<p align="center">
  <img src="Results/Bench/Plots/wall_ms_hist_topic.png" width="560" alt="Wall time histogram (topic scope)" />
</p>


---

## Reproducibility

* Sampling and deck selection are seeded and logged.
* Both scripts rely on the same parser configuration used by the CLIs, ensuring preprocessing parity.
* Scope (topic vs global) is explicit in every result row and all aggregates.
