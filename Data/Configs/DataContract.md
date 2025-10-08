# Data Contract

This document defines the format, structure, and processing expectations for all deck files used in the project. Its purpose is to ensure that any implementation, regardless of language, can process decks deterministically and produce consistent results.

---

## File format

All decks must be stored as plain text files encoded in UTF-8.
Fields are separated by the tab character (`\t`), and lines beginning with `#` represent metadata that should be ignored during parsing.

Columns (1-indexed):

1. guid
2. deck_path (a hierarchical structure separated by `::`, for example `Launch into Computing::Unit 03 - Principles of Computer Science`)
3. question_text
4. answer_text

Example line:

```
#separator:tab
#html:false
#guid column:1
#deck column:2
M%!D@eWnW_	Launch into Computing::Unit 01 - What is Computing?	What is the core definition of computing?	Computing is the process of designing, developing, and applying software and hardware systems to solve real-world problems.
```

---

## Deck generation process

Deck files are produced by exporting notes directly from Anki using the built-in export function. The following export configuration must be applied to ensure compatibility and reproducibility:

| Setting                           | Value                      |
| --------------------------------- | -------------------------- |
| Format                            | Notes in Plain Text (.txt) |
| Include HTML and media references | [ ] Unchecked              |
| Include tags                      | [ ] Unchecked              |
| Include deck name                 | [x] Checked                |
| Include note type name            | [ ] Unchecked              |
| Include unique identifier         | [x] Checked                |

This configuration produces tab-separated files with four columns (guid, deck, question, and answer) and a metadata header.

This choice of export options ensures that:

* All text is plain and free of HTML or media references
* Deck hierarchies are preserved through the inclusion of deck names
* Each card remains uniquely identifiable through the GUID
* Data remains structurally consistent across exports and implementations

Example deck path:
`Data/Decks/LaunchIntoComputingUnit01WhatIsComputing.txt`

---

## Validation

A record is considered invalid and must be skipped and logged if any of the following apply:

* The file does not contain exactly four columns
* The guid field is empty
* The question or answer field is empty after trimming
* A tab character is found inside a field value

Invalid records must be logged with their line number and a reason for exclusion.

---

## Normalisation

The following normalisation rules must be applied consistently:

* Unicode normalisation: NFC
* Text must be lowercased for comparison and matching
* HTML tags must be removed during text preparation, and reserved characters escaped during display
* Leading and trailing whitespace must be removed from all fields

---

## Tokenisation

Text is tokenised according to these principles:

* Split on non-alphanumeric boundaries
* Numeric tokens are retained
* Tokens shorter than two characters are discarded unless numeric
* Stopwords defined in `Data/Configs/Stopwords.txt` are removed
* No stemming or lemmatisation is permitted

---

## Topic scoping

The `deck_path` field defines a hierarchical structure separated by `::`.
When a topic node is selected, all descendant decks within that hierarchy are included as part of the candidate pool.

---

## Matching algorithms

Two matching algorithms are supported and must behave identically across implementations.

### Keyword overlap

Scores are computed as the sum of weights for shared tokens between the user query and the candidate question text.
Non-stopwords carry a weight of 1, while stopwords carry a weight of 0.
Phrase or position-based boosting is not permitted.

### TF-IDF with cosine similarity

* Term frequency (TF): raw term count
* Inverse document frequency (IDF): log((N + 1) / (df + 1)) + 1
* Document and query vectors are normalised using the L2 norm
* Similarity is calculated using cosine distance
* The system returns the top-k highest scoring results

---

## Deterministic tie-breakers

In the event of a tie between candidates, ranking must follow this order:

1. Greater count of overlapping non-stopword tokens
2. Shorter candidate question by token count
3. Lexicographic order of the guid

---

## Performance measurement

Each query must record the following data for benchmarking:

* Timings for each stage (parse, index, preprocessing, ranking, and formatting)
* Total wall-clock time in milliseconds
* Deck size, algorithm name, topic, and top-k results with guid and score
* Peak resident memory in kilobytes, where available

Results must be logged as line-delimited JSON to the designated benchmarking files.

---

## Error handling

Processing must not terminate on malformed records.
Invalid entries should be skipped, and all anomalies logged with sufficient context to permit investigation.
Unreadable files must produce a clear error message and a non-zero exit code.

---

## Security

Deck content must be treated as untrusted input.
HTML or media content must never be rendered or executed.
Implementations must prevent path traversal or access outside the declared data root.
