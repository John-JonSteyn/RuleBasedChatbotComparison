# Benchmark Tool

This script executes a reproducible, parity-focused benchmark across the two chatbots. It samples questions from the decks, runs both retrieval algorithms, and records accuracy and timing statistics for later analysis.

The benchmark is designed to evaluate implementation performance and parity rather than retrieval quality. It therefore uses deck questions as the queries and checks whether each implementation returns the originating card as the top-1 result.

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
* The Python CLI available as a module at `Chatbots/Python/Source/cli.py`.
* The other CLI available with a `Cargo.toml` at `Chatbots/Rust/Source/Cargo.toml`.
* Python 3.12+ on PATH.
* Cargo/rustc on PATH (only required if you include that implementation in `--implementations`).

The script writes outputs to:

```
Results/
└── Bench/
    ├── seed_<N>_python.jsonl
    ├── seed_<N>_rust.jsonl
    ├── results_seed_<N>.csv
    └── summary_seed_<N>.csv
```

---

## What the benchmark does

1. Loads all decks once using `Data/Configs/Parser.json` to ensure consistent preprocessing.
2. Groups cards by deck topic.
3. Deterministically samples a fixed number of questions per deck (controlled by `--seed` and `--questions-per-deck`).
4. Splits the samples into:

   * topic scope: query within its own deck/topic subtree,
   * global scope: query across all decks (optional).
5. For each sampled query, runs each implementation and algorithm, capturing the most recent JSONL log line written by the CLI.
6. Extracts the top GUID and stage timings, computes correctness (top-1 equals expected GUID), and writes:

   * a row-level `results_seed_<N>.csv`,
   * an aggregated `summary_seed_<N>.csv` with accuracy and latency percentiles.

No network access is required.

---

## Usage

From the repository root:

### Example 1: topic-scoped only (default if no scope flags are provided)

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

### Example 2: topic + global scopes

```bash
python Tools/benchmark.py \
  --seed 123 \
  --questions-per-deck 8 \
  --algorithms tfidf \
  --implementations python,rust \
  --topic-scope \
  --global-scope
```

### Example 3: benchmark a single implementation

```bash
python Tools/benchmark.py \
  --questions-per-deck 5 \
  --implementations python
```

---

## Command-line options

| Flag                   | Type     | Default                                     | Description                                                    |
| ---------------------- | -------- | ------------------------------------------- | -------------------------------------------------------------- |
| `--seed`               | int      | `42`                                        | Random seed for deterministic sampling of questions.           |
| `--questions-per-deck` | int      | `10`                                        | Number of questions sampled from each deck.                    |
| `--algorithms`         | csv-list | `keyword,tfidf`                             | Which retrieval algorithms to run.                             |
| `--implementations`    | csv-list | `python,rust`                               | Which implementations to run.                                  |
| `--topic-scope`        | flag     | off (but topic-only is the default overall) | Run queries constrained to their own deck/topic subtree.       |
| `--global-scope`       | flag     | off                                         | Run queries against all decks.                                 |
| `--rust-manifest`      | path     | `Chatbots/Rust/Source/Cargo.toml`           | Path to the Cargo manifest when including that implementation. |

Scope behavior: if neither `--topic-scope` nor `--global-scope` is provided, the script runs **topic-only** by default. Add `--global-scope` to include global tests.

---

## Outputs

### JSONL logs (one per implementation)

* `Results/Bench/seed_<N>_python.jsonl`
* `Results/Bench/seed_<N>_rust.jsonl`

These contain the per-query logging emitted by each CLI. The benchmark reads only the **last** non-empty line after each invocation, so the files are truncated before the run.

### Row-level CSV

* `Results/Bench/results_seed_<N>.csv`

Columns:

* seed, implementation, algorithm, scope
* deck_name, deck_card_count
* query_id (expected GUID), query_text
* expected_guid, top_guid, match (true/false)
* wall_ms, rank_ms, parse_ms, index_ms
* timestamp, error

### Summary CSV

* `Results/Bench/summary_seed_<N>.csv`

Aggregations per (implementation, algorithm, scope):

* queries
* accuracy_at_1
* median_wall_ms, p90_wall_ms
* median_rank_ms, p90_rank_ms

---

## Reproducibility

* Sampling is deterministic for a given `--seed`.
* The script uses the same parser configuration as the CLIs to avoid preprocessing drift.
* Topic scope vs global scope is explicit and recorded in the CSV.

---

## Notes and troubleshooting

* If you see encoding errors from subprocess output on Windows, the script suppresses CLI stdout/stderr and relies on JSONL logs instead.
* If a CLI returns a non-zero exit code, the row is recorded with an error message and empty timing fields.
* Ensure the CLIs write per-query JSONL to the provided path via their `--log` flag; otherwise the benchmark will record “No JSONL log line found”.

---

## Extensibility

* Add new implementations by extending the two runner functions and `--implementations` parsing.
* Add new algorithms by expanding the `--algorithms` set and ensuring both CLIs support the option name.
* Additional metrics can be computed by extending `build_summary` or post-processing the CSVs.
