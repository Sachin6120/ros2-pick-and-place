#!/usr/bin/env python3
"""
metrics_logger.py
─────────────────
Post-hoc analysis of pick-and-place metrics CSV.

Usage:
    python3 metrics_logger.py analyze                # print summary table
    python3 metrics_logger.py analyze --plot          # + save bar charts
    python3 metrics_logger.py analyze --csv <path>    # custom CSV path
"""

import argparse
import os
import sys

METRICS_CSV = os.path.expanduser("~/.ros/pick_place_metrics.csv")


def analyze(csv_path: str, plot: bool = False):
    try:
        import pandas as pd
    except ImportError:
        print("pandas is required: pip install pandas", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(csv_path):
        print(f"Metrics file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path)
    print(f"\nLoaded {len(df)} records from {csv_path}\n")

    # ── Per-phase summary ──────────────────────────────────────────
    summary = (
        df.groupby("phase")
        .agg(
            count=("success", "count"),
            success_rate=("success", "mean"),
            plan_time_mean=("planning_time_s", "mean"),
            plan_time_std=("planning_time_s", "std"),
            exec_time_mean=("execution_time_s", "mean"),
            exec_time_std=("execution_time_s", "std"),
        )
        .round(4)
    )
    summary["success_rate"] = (summary["success_rate"] * 100).round(1)
    print("── Per-Phase Summary ──")
    print(summary.to_string())
    print()

    # ── Overall ────────────────────────────────────────────────────
    n_trials = df["trial"].nunique()
    # A trial is successful if ALL its phases succeeded
    trial_success = df.groupby("trial")["success"].all()
    overall_rate = trial_success.mean() * 100
    total_plan = df.groupby("trial")["planning_time_s"].sum()
    total_exec = df.groupby("trial")["execution_time_s"].sum()

    print("── Overall ──")
    print(f"  Trials:           {n_trials}")
    print(f"  Full-cycle success rate: {overall_rate:.1f}%")
    print(f"  Avg total planning time: {total_plan.mean():.3f} s")
    print(f"  Avg total execution time: {total_exec.mean():.3f} s")
    print(f"  Avg full cycle time:      {(total_plan + total_exec).mean():.3f} s")
    print()

    # Position error (if populated)
    if "position_error_m" in df.columns:
        errs = pd.to_numeric(df["position_error_m"], errors="coerce").dropna()
        if len(errs) > 0:
            print("── End-Effector Position Error ──")
            print(f"  Mean: {errs.mean():.4f} m")
            print(f"  Std:  {errs.std():.4f} m")
            print(f"  Max:  {errs.max():.4f} m")
            print()

    # ── Plotting ───────────────────────────────────────────────────
    if plot:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib is required for --plot: pip install matplotlib")
            return

        fig, axes = plt.subplots(1, 3, figsize=(15, 5))

        # Planning time per phase
        summary["plan_time_mean"].plot.bar(
            ax=axes[0],
            yerr=summary["plan_time_std"],
            capsize=3,
            color="#4a90d9",
        )
        axes[0].set_title("Planning Time by Phase")
        axes[0].set_ylabel("Seconds")
        axes[0].tick_params(axis="x", rotation=45)

        # Execution time per phase
        summary["exec_time_mean"].plot.bar(
            ax=axes[1],
            yerr=summary["exec_time_std"],
            capsize=3,
            color="#50c878",
        )
        axes[1].set_title("Execution Time by Phase")
        axes[1].set_ylabel("Seconds")
        axes[1].tick_params(axis="x", rotation=45)

        # Success rate per phase
        summary["success_rate"].plot.bar(ax=axes[2], color="#f5a623")
        axes[2].set_title("Success Rate by Phase")
        axes[2].set_ylabel("Percent")
        axes[2].set_ylim(0, 105)
        axes[2].tick_params(axis="x", rotation=45)

        plt.tight_layout()
        out_path = csv_path.replace(".csv", "_plots.png")
        plt.savefig(out_path, dpi=150)
        print(f"Plots saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Pick-and-place metrics analyzer")
    sub = parser.add_subparsers(dest="command")

    analyze_p = sub.add_parser("analyze", help="Analyze metrics CSV")
    analyze_p.add_argument("--csv", default=METRICS_CSV, help="Path to CSV")
    analyze_p.add_argument("--plot", action="store_true", help="Generate plots")

    args = parser.parse_args()
    if args.command == "analyze":
        analyze(args.csv, args.plot)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
