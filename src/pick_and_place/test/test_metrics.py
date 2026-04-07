#!/usr/bin/env python3
"""
test_metrics.py
───────────────
Validation script that can be run standalone (outside ROS) to verify
the metrics CSV is well-formed and compute aggregate statistics.

Also usable as a quick smoke-test after a batch run.

Usage:
    python3 test_metrics.py                         # default CSV path
    python3 test_metrics.py --csv /path/to/file.csv
"""

import argparse
import csv
import os
import sys

METRICS_CSV = os.path.expanduser("~/.ros/pick_place_metrics.csv")

REQUIRED_COLUMNS = [
    "trial",
    "phase",
    "planning_time_s",
    "execution_time_s",
    "success",
]

EXPECTED_PHASES = [
    "home",
    "pre_grasp",
    "grasp_approach",
    "lift",
    "transport",
    "place",
    "retreat",
    "return_home",
]


def validate(csv_path: str) -> bool:
    if not os.path.exists(csv_path):
        print(f"FAIL: file not found — {csv_path}")
        return False

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) == 0:
        print("FAIL: CSV is empty")
        return False

    # Check required columns
    for col in REQUIRED_COLUMNS:
        if col not in rows[0]:
            print(f"FAIL: missing column '{col}'")
            return False

    print(f"OK: {len(rows)} rows, columns present")

    # Check trials
    trials = sorted(set(int(r["trial"]) for r in rows))
    print(f"OK: {len(trials)} trial(s) found — {trials}")

    # Check phases per trial
    all_ok = True
    for t in trials:
        trial_rows = [r for r in rows if int(r["trial"]) == t]
        phases = [r["phase"] for r in trial_rows]
        for ep in EXPECTED_PHASES:
            if ep not in phases:
                print(f"WARN: trial {t} missing phase '{ep}'")
                all_ok = False

    # Check success values
    successes = sum(1 for r in rows if r["success"] == "True")
    failures = sum(1 for r in rows if r["success"] == "False")
    print(f"OK: {successes} successful phases, {failures} failed phases")

    # Check timing values are numeric and non-negative
    for r in rows:
        for col in ["planning_time_s", "execution_time_s"]:
            try:
                val = float(r[col])
                if val < 0:
                    print(f"WARN: negative {col} in trial {r['trial']}/{r['phase']}")
                    all_ok = False
            except (ValueError, TypeError):
                print(f"WARN: non-numeric {col} in trial {r['trial']}/{r['phase']}")
                all_ok = False

    # Aggregate stats
    plan_times = [float(r["planning_time_s"]) for r in rows if r["planning_time_s"]]
    exec_times = [float(r["execution_time_s"]) for r in rows if r["execution_time_s"]]

    if plan_times:
        avg_plan = sum(plan_times) / len(plan_times)
        print(f"  Avg planning time:  {avg_plan:.4f} s")
    if exec_times:
        avg_exec = sum(exec_times) / len(exec_times)
        print(f"  Avg execution time: {avg_exec:.4f} s")

    # Full-cycle success rate
    trial_success = {}
    for r in rows:
        t = int(r["trial"])
        if t not in trial_success:
            trial_success[t] = True
        if r["success"] != "True":
            trial_success[t] = False

    full_ok = sum(1 for v in trial_success.values() if v)
    print(f"  Full-cycle success: {full_ok}/{len(trial_success)} trials")

    if all_ok:
        print("\nVALIDATION PASSED")
    else:
        print("\nVALIDATION PASSED WITH WARNINGS")

    return True


def main():
    parser = argparse.ArgumentParser(description="Validate pick-place metrics CSV")
    parser.add_argument("--csv", default=METRICS_CSV, help="Path to metrics CSV")
    args = parser.parse_args()
    ok = validate(args.csv)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
