from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = Path("Results/Bench")
PLOTS_DIR = RESULTS_DIR / "Plots"
SUMMARY_ALL_SEEDS_CSV = RESULTS_DIR / "summary_all_seeds.csv"
SPEEDUP_WALL_MS_CSV = RESULTS_DIR / "speedup_wall_ms.csv"
ERRORS_ALL_SEEDS_CSV = RESULTS_DIR / "errors_all_seeds.csv"
REPORT_MD = RESULTS_DIR / "report_all_seeds.md"


def _df_to_markdown_or_text(frame: pd.DataFrame) -> str:
    """Render a DataFrame as markdown if 'tabulate' is available; otherwise fall back to monospaced text."""
    try:
        return frame.to_markdown(index=False)
    except Exception:
        return "```\n" + frame.to_string(index=False) + "\n```"


def load_all_results(results_directory: Path) -> pd.DataFrame:
    """Load and concatenate every results_seed_*.csv into a single analysis DataFrame."""
    csv_paths: List[Path] = sorted(results_directory.glob("results_seed_*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No results_seed_*.csv files found in {results_directory}")

    data_frames: List[pd.DataFrame] = []
    for csv_path in csv_paths:
        data_frame = pd.read_csv(csv_path, dtype=str)
        data_frame["__source_file"] = csv_path.name
        data_frames.append(data_frame)

    combined_results = pd.concat(data_frames, ignore_index=True)

    for column_name in ["wall_ms", "rank_ms", "parse_ms", "index_ms", "deck_card_count"]:
        if column_name in combined_results.columns:
            combined_results[column_name] = pd.to_numeric(combined_results[column_name], errors="coerce")

    if "match" in combined_results.columns:
        combined_results["match_bool"] = combined_results["match"].astype(str).str.lower().eq("true")
    else:
        combined_results["match_bool"] = False

    # Helpful categorical typing
    for column_name in ["implementation", "algorithm", "scope"]:
        if column_name in combined_results.columns:
            combined_results[column_name] = combined_results[column_name].astype("category")

    return combined_results


def aggregate_summary_all_seeds(results_frame: pd.DataFrame) -> pd.DataFrame:
    """Compute accuracy and timing percentiles per (implementation, algorithm, scope) over all seeds."""
    grouped_results = results_frame.groupby(
        ["implementation", "algorithm", "scope"],
        dropna=False,
        observed=False, 
    )

    summary_frame = grouped_results.agg(
        queries=("match_bool", "size"),
        accuracy_at_1=("match_bool", "mean"),
        median_wall_ms=("wall_ms", lambda series: series.dropna().median()),
        p90_wall_ms=("wall_ms", lambda series: series.dropna().quantile(0.90)),
        median_rank_ms=("rank_ms", lambda series: series.dropna().median()),
        p90_rank_ms=("rank_ms", lambda series: series.dropna().quantile(0.90)),
    ).reset_index()

    for column_name in ["accuracy_at_1", "median_wall_ms", "p90_wall_ms", "median_rank_ms", "p90_rank_ms"]:
        summary_frame[column_name] = pd.to_numeric(summary_frame[column_name], errors="coerce")

    return summary_frame


def build_speedup_table(summary_frame: pd.DataFrame) -> pd.DataFrame:
    """Create pairwise median wall-time speedup ratios between implementations for each (algorithm, scope)."""
    wide_implementation = summary_frame.pivot_table(
        index=["algorithm", "scope"],
        columns="implementation",
        values="median_wall_ms",
        aggfunc="first",
        observed=False,
    )

    implementation_names = [
        column for column in wide_implementation.columns
        if pd.api.types.is_numeric_dtype(wide_implementation[column])
    ]
    speedup_rows: List[Tuple[str, str, str, str, float]] = []

    for baseline_implementation in implementation_names:
        for contender_implementation in implementation_names:
            if baseline_implementation == contender_implementation:
                continue
            ratio_series = (wide_implementation[baseline_implementation] / wide_implementation[contender_implementation]).rename("speedup")
            for (algorithm_name, scope_value), ratio_value in ratio_series.items():
                value = float(ratio_value) if pd.notna(ratio_value) else float("nan")
                speedup_rows.append((algorithm_name, scope_value, baseline_implementation, contender_implementation, value))

    speedup_frame = pd.DataFrame(
        speedup_rows,
        columns=["algorithm", "scope", "baseline", "contender", "speedup"]
    ).sort_values(["algorithm", "scope", "baseline", "contender"]).reset_index(drop=True)

    return speedup_frame


def collect_errors(results_frame: pd.DataFrame) -> pd.DataFrame:
    """Extract any rows that contain an error message for quick inspection of failed runs."""
    if "error" not in results_frame.columns:
        return pd.DataFrame(columns=results_frame.columns)
    errors_frame = results_frame[results_frame["error"].fillna("").astype(str).str.len() > 0].copy()
    return errors_frame.sort_values(["implementation", "algorithm", "scope", "deck_name", "query_id"])


def plot_accuracy_bar(results_frame: pd.DataFrame, scope_value: str) -> Optional[Path]:
    """Plot Accuracy@1 bar chart by implementation and algorithm for a given scope."""
    accuracy_data = (
        results_frame[results_frame["scope"] == scope_value]
        .groupby(["implementation", "algorithm"], dropna=False, observed=False)["match_bool"]
        .mean()
        .reset_index()
    )
    if accuracy_data.empty:
        return None

    plt.figure()
    pivot_frame = accuracy_data.pivot(index="algorithm", columns="implementation", values="match_bool")
    pivot_frame.plot(kind="bar")
    plt.ylabel("accuracy_at_1")
    plt.title(f"Accuracy@1 by implementation and algorithm ({scope_value} scope)")
    plt.ylim(0, 1)
    plt.xticks(rotation=0)
    plt.tight_layout()
    output_path = PLOTS_DIR / f"accuracy_bar_{scope_value}.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_wall_ms_box(results_frame: pd.DataFrame, scope_value: str) -> Optional[Path]:
    """Plot wall time distribution as a box plot for each (algorithm, implementation) in a given scope."""
    subset_frame = results_frame[(results_frame["scope"] == scope_value) & results_frame["wall_ms"].notna()]
    if subset_frame.empty:
        return None

    plt.figure()
    algorithm_names = list(subset_frame["algorithm"].dropna().unique())
    implementation_names = list(subset_frame["implementation"].dropna().unique())
    box_data: List[List[float]] = []
    box_labels: List[str] = []

    for algorithm_name in algorithm_names:
        for implementation_name in implementation_names:
            selection = subset_frame[
                (subset_frame["algorithm"] == algorithm_name) &
                (subset_frame["implementation"] == implementation_name)
            ]["wall_ms"].astype(float)
            if selection.empty:
                continue
            box_data.append(selection.values)
            box_labels.append(f"{algorithm_name}\n{implementation_name}")

    if not box_data:
        return None

    plt.boxplot(box_data, showfliers=False)
    plt.xticks(range(1, len(box_labels) + 1), box_labels, rotation=0)
    plt.ylabel("wall_ms")
    plt.title(f"Wall time distribution ({scope_value} scope)")
    plt.tight_layout()
    output_path = PLOTS_DIR / f"wall_ms_box_{scope_value}.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_stage_ms_stacked(results_frame: pd.DataFrame, scope_value: str) -> Optional[Path]:
    """Plot a stacked bar chart of median parse, index, and rank times per (implementation, algorithm)."""
    subset_frame = results_frame[results_frame["scope"] == scope_value]
    if subset_frame.empty:
        return None

    stage_stats = (
        subset_frame.groupby(["implementation", "algorithm"], observed=False)[["parse_ms", "index_ms", "rank_ms"]]
        .median(numeric_only=True)
        .reset_index()
    )
    if stage_stats.empty:
        return None

    label_texts = stage_stats.apply(lambda row: f"{row['algorithm']}\n{row['implementation']}", axis=1)
    parse_values = stage_stats["parse_ms"].fillna(0.0).astype(float).values
    index_values = stage_stats["index_ms"].fillna(0.0).astype(float).values
    rank_values = stage_stats["rank_ms"].fillna(0.0).astype(float).values

    x_positions = range(len(label_texts))
    plt.figure()
    plt.bar(x_positions, parse_values, label="parse_ms")
    plt.bar(x_positions, index_values, bottom=parse_values, label="index_ms")
    plt.bar(x_positions, rank_values, bottom=parse_values + index_values, label="rank_ms")
    plt.xticks(list(x_positions), label_texts)
    plt.ylabel("milliseconds (median)")
    plt.title(f"Stage timing breakdown (median) — {scope_value} scope")
    plt.legend()
    plt.tight_layout()
    output_path = PLOTS_DIR / f"stage_ms_stacked_{scope_value}.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_scalability_wall_vs_decksize(results_frame: pd.DataFrame, scope_value: str) -> Optional[Path]:
    """Plot median wall time versus deck size to visualise scalability for a given scope."""
    subset_frame = results_frame[(results_frame["scope"] == scope_value) & results_frame["wall_ms"].notna()]
    if subset_frame.empty:
        return None

    grouped_frame = (
        subset_frame.groupby(["implementation", "algorithm", "deck_card_count"], observed=False)["wall_ms"]
        .median()
        .reset_index()
    )
    if grouped_frame.empty:
        return None

    plt.figure()
    for (implementation_name, algorithm_name), group_frame in grouped_frame.groupby(["implementation", "algorithm"], observed=False):
        group_sorted = group_frame.sort_values("deck_card_count")
        label_text = f"{algorithm_name} / {implementation_name}"
        plt.plot(group_sorted["deck_card_count"], group_sorted["wall_ms"], marker="o", label=label_text)

    plt.xlabel("deck_card_count")
    plt.ylabel("median wall_ms")
    plt.title(f"Scalability: median wall_ms vs deck size ({scope_value} scope)")
    plt.legend()
    plt.tight_layout()
    output_path = PLOTS_DIR / f"scalability_wall_vs_decksize_{scope_value}.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_wall_histograms(results_frame: pd.DataFrame, scope_value: str) -> Optional[Path]:
    """Plot wall time histograms per (implementation, algorithm) for a given scope to show distribution shape."""
    subset_frame = results_frame[(results_frame["scope"] == scope_value) & results_frame["wall_ms"].notna()]
    if subset_frame.empty:
        return None

    plt.figure()
    for (implementation_name, algorithm_name), group_frame in subset_frame.groupby(["implementation", "algorithm"], observed=False):
        plt.hist(group_frame["wall_ms"].astype(float), bins=30, alpha=0.5, label=f"{algorithm_name}/{implementation_name}")

    plt.xlabel("wall_ms")
    plt.ylabel("count")
    plt.title(f"Wall time histogram ({scope_value} scope)")
    plt.legend()
    plt.tight_layout()
    output_path = PLOTS_DIR / f"wall_ms_hist_{scope_value}.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def write_report_markdown(
    summary_frame: pd.DataFrame,
    speedup_frame: pd.DataFrame,
    scopes: List[str],
    plot_paths_by_scope: Dict[str, Dict[str, Path]],
    errors_frame: pd.DataFrame,
    output_path: Path,
) -> None:
    """Compose a Markdown report with key tables and linked figures for easy sharing."""
    markdown_lines: List[str] = []
    markdown_lines.append("# Benchmark Report")
    markdown_lines.append("")
    markdown_lines.append("This report summarises accuracy and performance across implementations and algorithms, aggregated over all seeds found in Results/Bench.")
    markdown_lines.append("")

    markdown_lines.append("## Summary (all seeds)")
    markdown_lines.append("")
    markdown_lines.append(_df_to_markdown_or_text(summary_frame))
    markdown_lines.append("")

    if not speedup_frame.empty:
        markdown_lines.append("## Speedup Ratios (median wall_ms)")
        markdown_lines.append("")
        markdown_lines.append("speedup = median_wall_ms(baseline) / median_wall_ms(contender) — larger means the contender is faster.")
        markdown_lines.append("")
        markdown_lines.append(_df_to_markdown_or_text(speedup_frame))
        markdown_lines.append("")

    for scope_value in scopes:
        markdown_lines.append(f"## Figures — {scope_value} scope")
        markdown_lines.append("")
        for key_name in ["accuracy_bar", "wall_ms_box", "stage_ms_stacked", "scalability", "wall_ms_hist"]:
            plot_path = plot_paths_by_scope.get(scope_value, {}).get(key_name)
            if plot_path:
                relative_path = Path(plot_path).as_posix()
                markdown_lines.append(f"![{key_name} {scope_value}]({relative_path})")
                markdown_lines.append("")
        markdown_lines.append("")

    if not errors_frame.empty:
        markdown_lines.append("## Errors")
        markdown_lines.append("")
        visible_columns = [c for c in ["implementation", "algorithm", "scope", "deck_name", "query_id", "error"] if c in errors_frame.columns]
        markdown_lines.append(_df_to_markdown_or_text(errors_frame[visible_columns].head(100)))
        if len(errors_frame) > 100:
            markdown_lines.append("")
            markdown_lines.append(f"... {len(errors_frame) - 100} more rows omitted ...")
        markdown_lines.append("")

    output_path.write_text("\n".join(markdown_lines), encoding="utf-8")

def plot_algorithmic_scaling(summary_frame: pd.DataFrame) -> Optional[Path]:
    """Create a bar chart of TF-IDF ÷ Keyword median wall_ms per implementation."""
    topic_only = summary_frame[summary_frame["scope"] == "topic"].copy()
    if topic_only.empty:
        return None

    pivot = topic_only.pivot_table(
        index="implementation",
        columns="algorithm",
        values="median_wall_ms",
        aggfunc="first",
        observed=False,
    )

    if not {"keyword", "tfidf"}.issubset(pivot.columns):
        return None

    ratio = (pivot["tfidf"] / pivot["keyword"]).rename("tfidf_over_keyword").to_frame()

    out_csv = RESULTS_DIR / "algorithmic_scaling.csv"
    ratio.reset_index().to_csv(out_csv, index=False)

    plt.figure()
    ratio["tfidf_over_keyword"].plot(kind="bar")
    plt.ylabel("Scaling ratio (TF-IDF ÷ Keyword)")
    plt.title("Algorithmic scaling per implementation (topic scope)")
    plt.tight_layout()
    out_png = PLOTS_DIR / "algorithmic_scaling.png"
    plt.savefig(out_png, dpi=150)
    plt.close()

    return out_png


def main() -> None:
    """Load results, compute summaries, generate plots, and write a Markdown report."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    results_frame = load_all_results(RESULTS_DIR)

    summary_all_seeds_frame = aggregate_summary_all_seeds(results_frame)
    summary_all_seeds_frame.to_csv(SUMMARY_ALL_SEEDS_CSV, index=False)

    speedup_wall_ms_frame = build_speedup_table(summary_all_seeds_frame)
    speedup_wall_ms_frame.to_csv(SPEEDUP_WALL_MS_CSV, index=False)

    errors_all_seeds_frame = collect_errors(results_frame)
    errors_all_seeds_frame.to_csv(ERRORS_ALL_SEEDS_CSV, index=False)

    scope_values = sorted(results_frame["scope"].dropna().unique())
    plot_paths_by_scope: Dict[str, Dict[str, Path]] = {}
    for scope_value in scope_values:
        scope_plot_paths: Dict[str, Path] = {}
        path_accuracy = plot_accuracy_bar(results_frame, scope_value)
        if path_accuracy:
            scope_plot_paths["accuracy_bar"] = path_accuracy
        path_box = plot_wall_ms_box(results_frame, scope_value)
        if path_box:
            scope_plot_paths["wall_ms_box"] = path_box
        path_stacked = plot_stage_ms_stacked(results_frame, scope_value)
        if path_stacked:
            scope_plot_paths["stage_ms_stacked"] = path_stacked
        path_scalability = plot_scalability_wall_vs_decksize(results_frame, scope_value)
        if path_scalability:
            scope_plot_paths["scalability"] = path_scalability
        path_hist = plot_wall_histograms(results_frame, scope_value)
        if path_hist:
            scope_plot_paths["wall_ms_hist"] = path_hist
        plot_paths_by_scope[scope_value] = scope_plot_paths

    write_report_markdown(
        summary_frame=summary_all_seeds_frame,
        speedup_frame=speedup_wall_ms_frame,
        scopes=scope_values,
        plot_paths_by_scope=plot_paths_by_scope,
        errors_frame=errors_all_seeds_frame,
        output_path=REPORT_MD,
    )

    algo_scaling_path = plot_algorithmic_scaling(summary_all_seeds_frame)
    if algo_scaling_path:
        print(f"Saved algorithmic scaling plot to: {algo_scaling_path}")
        print(f"Wrote: {RESULTS_DIR / 'algorithmic_scaling.csv'}")

    print(f"Wrote: {SUMMARY_ALL_SEEDS_CSV}")
    print(f"Wrote: {SPEEDUP_WALL_MS_CSV}")
    print(f"Wrote: {ERRORS_ALL_SEEDS_CSV}")
    print(f"Wrote: {REPORT_MD}")
    print(f"Saved plots to: {PLOTS_DIR}")


if __name__ == "__main__":
    main()
