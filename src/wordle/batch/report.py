"""Markdown report with summary graphs."""

from __future__ import annotations

from pathlib import Path

from wordle.batch.metrics import PuzzleResult


def generate_markdown_report(
    results: list[PuzzleResult],
    summary: dict,
    reports_dir: Path,
    mode: str = "a",
) -> Path:
    """Write report.md and PNG graphs into reports_dir. Returns the report path."""
    graphs_dir = reports_dir / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    _write_graphs(summary, graphs_dir)

    mode_label = "Investigation + Hail-Mary" if mode == "a" else "Hail-Mary Only"
    report_path = reports_dir / "report.md"
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Wordle Solver Report Mode {mode.upper()} ({mode_label})\n\n")
        fh.write(f"Tested on {summary['total_puzzles']} official Wordle answers.\n\n")
        fh.write("---\n\n")

        fh.write("## Summary\n\n")
        fh.write("| Metric | Value |\n|---|---|\n")
        fh.write(f"| Total puzzles | {summary['total_puzzles']} |\n")
        fh.write(f"| Solved | {summary['solved']} |\n")
        fh.write(f"| Failed | {summary['failed']} |\n")
        fh.write(f"| Solve rate | {summary['solve_rate']:.1%} |\n")
        fh.write(f"| Average turns (solved) | {summary['average_turns_solved']:.2f} |\n")
        fh.write(f"| Median turns (solved) | {summary['median_turns_solved']:.1f} |\n")
        fh.write(f"| 90th percentile turns | {summary['p90_turns_solved']:.1f} |\n")
        fh.write("\n")

        fh.write("## Solve Rate\n\n")
        fh.write("![Solve Rate](graphs/solve_rate.png)\n\n")
        if mode == "a":
            fh.write(
                "Mode A learns letters in the first 3 turns, then picks the best candidate. "
                "Discover fast, then commit.\n\n"
            )
        else:
            fh.write(
                "Mode B commits immediately. Every guess is the best candidate. "
                "No discovery, no hesitation.\n\n"
            )

        fh.write("## Turns Distribution\n\n")
        fh.write("![Turns Distribution](graphs/turns_histogram.png)\n\n")
        fh.write(
            "Each bar shows how many puzzles were solved in that many turns. "
            "Anything beyond turn 6 is a failure.\n\n"
        )

        if summary["top_failures"]:
            fh.write(f"## Failures ({summary['failed']} puzzles)\n\n")
            fh.write("| Secret | Guesses tried |\n|---|---|\n")
            for item in summary["top_failures"][:10]:
                guesses = " → ".join(item["words_tried"])
                fh.write(f"| `{item['secret']}` | {guesses} |\n")
            fh.write("\n")

    return report_path


def _write_graphs(summary: dict, graphs_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _write_histogram(summary, graphs_dir, plt)
    _write_pie(summary, graphs_dir, plt)


def _write_histogram(summary: dict, graphs_dir: Path, plt) -> None:
    hist = summary["turns_histogram"]
    turns = list(hist.keys())
    counts = [hist[t] for t in turns]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(turns, counts, color="#4C72B0", edgecolor="white")
    ax.set_xlabel("Turns taken")
    ax.set_ylabel("Puzzles solved")
    ax.set_title("Turns Distribution")
    for bar, count in zip(bars, counts):
        if count:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 4,
                str(count),
                ha="center",
                va="bottom",
                fontsize=9,
            )
    fig.tight_layout()
    fig.savefig(graphs_dir / "turns_histogram.png", dpi=100)
    plt.close(fig)


def _write_pie(summary: dict, graphs_dir: Path, plt) -> None:
    solved = summary["solved"]
    failed = summary["failed"]

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(
        [solved, failed],
        labels=[f"Solved ({solved})", f"Failed ({failed})"],
        colors=["#55A868", "#C44E52"],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax.set_title("Solve Rate")
    fig.tight_layout()
    fig.savefig(graphs_dir / "solve_rate.png", dpi=100)
    plt.close(fig)
