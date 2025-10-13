# Benchmark comparison of identical Python and Rust chatbots highlighting performance and development model differences.

With this project, we explore how the design of programming languages influences both the development experience and runtime efficiency by implementing identical rule-based chatbots in Python and in Rust. Each chatbot retrieves answers from structured text files derived from Anki decks, using both keyword-based and TF-IDF search algorithms.

Python was selected for its readability, flexibility and popularity as a rapid development language. Rust was chosen for its compiler-enforced safety, concurrency and performance. The goal was to compare execution speed, scalability, maintainability and development models, while reflecting on how the philosophy of each language affect’s the developer’s workflow and the system’s overall performance – even when both implementations produce functionally identical results.

## Development Model and Syntax

Python and Rust represent two contrasting philosophies in how programming languages organise, represent and enforce correctness.

Python is a multi-paradigm, dynamically typed language that implements procedural, object orientated and functional programming. Its concise syntax prioritises readability and supports rapid experimentation, making it well-suited to iterative development and exploratory coding.

Rust is a statically typed, systems-level language that combines low level control with functional and concurrent programming. Its compiler enforces memory safety and explicit data ownership – preventing common runtime errors. This makes Rust ideal for building efficient, secure software.

```python
def load_stopwords(path: str) -> Set[str]:
    """Read stopwords from file. One per line, case-folded, '#' = comment, blanks ignored."""
    if not os.path.exists(path):
        raise ValueError(f"Stopwords file not found: {path}")

    stopwords: Set[str] = set()
    with open(path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            stopwords.add(stripped.lower())
    return stopwords
```
_Figure 1: Python load_stopwords function – concise, dynamically typed and validated at run time._

```rust
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
```
_Figure 2: Rust load_stopwords function – explicit, statically typed and validated at compile time._

Python implements a more intuitive approach, requiring minimal boilerplate and allows rapid iteration, but defers most validation until runtime. Rust’s implementation is more verbose, enforcing strict type, lifetime and error handling rules to prevent issues such as missing files.

## Ease of Development

Python offers exceptional ease of setup and use. A simple interpreter and text editor are sufficient to begin development, and its Retrieval-Eval-Print Loop allows instant feedback and rapid iteration. This simplicity, together with minimal syntax, enables fast prototyping and experimentation.

Rust, by contrast, requires a more structured environment with Cargo, a manifest file, and explicit dependency management. While this adds setup overhead, it provides strong consistency and reproducibility across systems.

Python’s debugging feedback is less explicit, with errors typically only detected at runtime. Rust provides compiler-guided diagnostics that detect faults before execution and enforces stronger reliability.


```powershell
...\RuleBasedChatbotComparison> python -m Chatbots.Python.Source.cli --algo tfidf --query "What is computing?"
Configuration error: Parser config not found: Data/Configs/Parser.json
```
_Figure 3: Python runtime error when configuration file is missing, demonstrating delayed error detection._

```powershell
...\RuleBasedChatbotComparison> cargo run --manifest-path Chatbots/Rust/Source/Cargo.toml -- --algo tfidf --query "What is computing?"
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.12s
     Running `Chatbots\Rust\Source\target\debug\rulebot-rust.exe --algo tfidf --query "What is computing?"`
Error: Failed to load parser configuration
error: process didn't exit successfully: `Chatbots\Rust\Source\target\debug\rulebot-rust.exe --algo tfidf --query "What is computing?"` (exit code: 1)
```
_Figure 4: Rust compile-time validation preventing execution due to missing configuration, illustrating explicit safety checks._


## Performance Efficiency

In total, 165 queries were executed across 11 decks containing 3’443 potential answers, ensuring equivalent workloads for both implementations.

![Figure 5: Wall-time distribution per implementation](./Results/Bench/Plots/wall_ms_box_topic.png)  
_Figure 5: Wall-time distribution per implementation._

Performance benchmarking revealed substantial differences in latency and scalability between Python and Rust implementations. As show in Figures 5-8, Rust consistently exhibited higher median latency for both keyword and TF-IDF algorithms (0.494-1.294 ms) compared to Python (0.127 – 0.143 ms). This initial cost likely reflects binary startup and Input / Output overhead inherent to compiled execution.

![Figure 6: Scalability (median wall-time vs deck size)](./Results/Bench/Plots/scalability_wall_vs_decksize_topic.png)  
_Figure 6: Scalability (median wall-time vs deck size)_

As seen in Figure 6, Rust exhibited significantly higher overhead when scaling from keyword to TF-IDF queries. This suggests that Rust’s compiled Input / Output and memory management layers introduce fixed setup costs that dominate smaller workloads. Python scales more efficiently with increasing computational complexity because its lightweight, in-memory operations minimise overhead during execution.

![Figure 7: Wall-time histogram per algorithm (single-topic queries)](./Results/Bench/Plots/wall_ms_hist_topic.png) 
_Figure 7: Wall-time histogram per algorithm (single-topic queries)_

Figure 7 shows that Rust’s execution times cluster tightly around the median, indicating deterministic scheduling and minimal runtime variance. Python exhibits a broader distribution, with occasional latency spikes likely caused by garbage collection and interpreter scheduling overhead.

## Scalability and Maintainability

Rust’s statically typed architecture and ownership model foster disciplined development practices, ensuring that systems remain predictable and reproducible as they evolve. In this project, the Rust implementation spanned 1’592 lines of code across 11 modules, including an additional mod.rs script required for submodule organisation. This structure, though more verbose, reinforces modularity and explicit dependency control through Cargo, Rust’s build and package manager. Such rigidity improves long-term stability, particularly in performance-sensitive or safety-critical systems.

The Python implementation, by comparison, comprised 1’338 lines across 10 scripts (around 15.95% fewer lines overall) and required no external setup beyond the interpreter. Its simplicity enables rapid prototyping and experimentation, but this same flexibility can encourage shortcuts and inconsistent design patterns as complexity increases. Over time, such informality may accumulate as technical debt, making scaling and maintenance more challenging, particularly where development discipline is less rigorously enforced.

## Security Implications

Security represents one of the most significant points of divergence between Python and Rust. Rust’s ownership and borrowing framework prevents many common memory-related issues, including null pointer dereferences, buffer overflows, and use-after-free errors. These issues are prevented before the program is allowed to compile, as illustrated in Figure 4, where Rust halts execution due to a missing configuration file—showing its explicit compile-time safety checks.

Python only detects such errors when code paths are executed. As seen in Figure 3, the same missing configuration produces a runtime error, highlighting Python’s reliance on dynamic validation. While this allows greater flexibility, it also increases exposure to runtime failures and dependency-related vulnerabilities.

Cargo’s deterministic build process further strengthens Rust’s security posture compared to Python’s more flexible, but less predictable, package management through pip.

## Conclusion

Although both languages successfully achieved the same functional outcomes, their differing philosophies shape their real-world applicability.

Python will likely remain dominant in domains demanding rapid iteration, data exploration, and research and similar environments in which flexibility and accessibility outweigh raw performance.

Rust offers a stronger foundation for organisations focused on building reliable, secure, and scalable software, where compile-time safety and predictable execution take precedence over rapid prototyping, making it the preferred choice for performance-critical or infrastructure-level systems.
