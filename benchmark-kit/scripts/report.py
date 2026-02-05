import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt


def add_metric(summary_rows, metric, value):
    summary_rows.append({"metric": metric, "value": value})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    coverage_path = os.path.join(args.out, "coverage.csv")
    cache_path = os.path.join(args.out, "cache_eval.csv")
    ranking_path = os.path.join(args.out, "ranking_eval.csv")
    latency_path = os.path.join(args.out, "latency_throughput.csv")
    latency_samples_path = os.path.join(args.out, "latency_samples.csv")

    summary_rows = []

    if os.path.exists(coverage_path):
        coverage = pd.read_csv(coverage_path)
        resolved_pct = coverage["resolved"].mean() * 100 if not coverage.empty else 0
        add_metric(summary_rows, "resolved_pct", round(resolved_pct, 2))
        for key in ["variants", "pathways", "literature", "structure"]:
            if key in coverage.columns:
                add_metric(summary_rows, f"{key}_pct", round(coverage[key].mean() * 100, 2))

    if os.path.exists(cache_path):
        cache = pd.read_csv(cache_path)
        for col in cache.columns:
            add_metric(summary_rows, col, cache[col].iloc[0])

    if os.path.exists(ranking_path):
        ranking = pd.read_csv(ranking_path)
        recall = ranking["hit"].mean() if not ranking.empty else 0
        add_metric(summary_rows, "topk_recall", round(recall, 3))

    if os.path.exists(latency_path):
        latency = pd.read_csv(latency_path)
        for col in latency.columns:
            add_metric(summary_rows, col, latency[col].iloc[0])

    summary = pd.DataFrame(summary_rows)
    summary_file = os.path.join(args.out, "summary.csv")
    summary.to_csv(summary_file, index=False)

    if not summary.empty:
        plt.figure(figsize=(7, 3.6))
        plt.bar(summary["metric"], summary["value"], color="#0f766e")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(os.path.join(args.out, "summary.png"), dpi=150)

    # Coverage chart
    if os.path.exists(coverage_path):
        coverage = pd.read_csv(coverage_path)
        module_cols = [col for col in ["variants", "pathways", "literature", "structure"] if col in coverage.columns]
        if module_cols:
            values = [coverage[col].mean() * 100 for col in module_cols]
            plt.figure(figsize=(6, 3.5))
            plt.bar(module_cols, values, color="#0f766e")
            plt.ylabel("Coverage %")
            plt.title("Module Coverage")
            plt.ylim(0, 100)
            plt.tight_layout()
            plt.savefig(os.path.join(args.out, "coverage_modules.png"), dpi=150)

    # Cache efficiency chart
    if os.path.exists(cache_path):
        cache = pd.read_csv(cache_path)
        if not cache.empty:
            avg_cold = cache["avg_cold"].iloc[0]
            avg_warm = cache["avg_warm"].iloc[0]
            plt.figure(figsize=(5.5, 3.5))
            plt.bar(["cold", "warm"], [avg_cold, avg_warm], color=["#c2410c", "#0f766e"])
            plt.ylabel("Avg latency (s)")
            plt.title("Cache Efficiency")
            plt.tight_layout()
            plt.savefig(os.path.join(args.out, "cache_efficiency.png"), dpi=150)

    # Latency histogram
    if os.path.exists(latency_samples_path):
        samples = pd.read_csv(latency_samples_path)
        if "latency_s" in samples.columns:
            plt.figure(figsize=(6, 3.5))
            plt.hist(samples["latency_s"], bins=20, color="#0f766e", alpha=0.85)
            plt.xlabel("Latency (s)")
            plt.ylabel("Requests")
            plt.title("Latency Distribution")
            plt.tight_layout()
            plt.savefig(os.path.join(args.out, "latency_hist.png"), dpi=150)

    # Throughput + success chart
    if os.path.exists(latency_path):
        latency = pd.read_csv(latency_path)
        if not latency.empty:
            rps = latency.get("rps", pd.Series([0])).iloc[0]
            success = latency.get("success_rate_pct", pd.Series([0])).iloc[0]
            plt.figure(figsize=(6, 3.5))
            plt.bar(["RPS", "Success %"], [rps, success], color=["#0ea5e9", "#16a34a"])
            plt.title("Throughput & Success")
            plt.tight_layout()
            plt.savefig(os.path.join(args.out, "throughput_success.png"), dpi=150)

    # Ranking quality chart
    if os.path.exists(ranking_path):
        ranking = pd.read_csv(ranking_path)
        if not ranking.empty:
            recall = ranking["hit"].mean() * 100
            plt.figure(figsize=(5, 3.5))
            plt.bar(["Top-K recall"], [recall], color="#a855f7")
            plt.ylim(0, 100)
            plt.ylabel("Recall %")
            plt.title("Ranking Quality")
            plt.tight_layout()
            plt.savefig(os.path.join(args.out, "ranking_quality.png"), dpi=150)

    # LinkedIn composite
    panels = []
    for name in [
        "latency_hist.png",
        "coverage_modules.png",
        "cache_efficiency.png",
        "throughput_success.png",
        "ranking_quality.png",
    ]:
        path = os.path.join(args.out, name)
        if os.path.exists(path):
            panels.append(plt.imread(path))

    if panels:
        cols = 2
        rows = (len(panels) + cols - 1) // cols
        plt.figure(figsize=(10, 5 * rows))
        for idx, panel in enumerate(panels, start=1):
            ax = plt.subplot(rows, cols, idx)
            ax.imshow(panel)
            ax.axis("off")
        plt.tight_layout()
        plt.savefig(os.path.join(args.out, "linkedin_board.png"), dpi=150)


if __name__ == "__main__":
    main()
