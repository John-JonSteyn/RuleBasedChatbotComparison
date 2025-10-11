# Rust Chatbot CLI

This command-line application retrieves answers from structured decks of educational content.  
It accepts a query, identifies the most relevant card or cards, and displays ranked results according to the selected retrieval algorithm.

---

## Installation

Ensure Rust and Cargo are installed with the following minimum versions:

```
rustc >= 1.77.0
cargo >= 1.77.0
````

You can install or update the toolchain using:

```bash
rustup update
````

Then, build and run the project from the repository root:

```bash
cargo build --manifest-path Chatbots/Rust/Source/Cargo.toml
```

---

## Usage

```bash
cargo run --manifest-path Chatbots/Rust/Source/Cargo.toml -- \
  --algo tfidf \
  --topic "Launch into Computing::Unit 05 - Data Science and Storage" \
  --query "What is big data?"
```

---

## Parameters

| Flag           | Description                                                                                                                       |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `--algo`       | Retrieval algorithm to use. Options: `keyword` or `tfidf`.                                                                        |
| `--topic`      | Deck topic path (for example, `"Launch into Computing::Unit 05 - Data Science and Storage"`). If omitted, all decks are searched. |
| `--query`      | Query text to retrieve matching answers.                                                                                          |
| `--k`          | Number of top answers to return (default: 1).                                                                                     |
| `--log`        | Optional path to write benchmark or query logs.                                                                                   |
| `--show-cards` | Displays unique identifiers and relevance scores for retrieved cards.                                                             |

---

## Configuration

Decks, parser settings, and stopword definitions are stored under the `Data/` directory:

```
Data/
├── Decks/
├── Configs/
│   ├── Parser.json
│   └── Stopwords.txt
```

These files define the preprocessing, tokenisation, and filtering rules applied before retrieval.

```
