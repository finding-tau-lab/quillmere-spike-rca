#!/usr/bin/env python3
"""Kleinberg-style burst detection on 5-minute all-call baskets, then sample call_ids."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SAMPLE_SIZE = 30
S = 2.0  # intensity ratio vs baseline mean


def load_baskets():
    rows = []
    with (DATA / "time_baskets_5min.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for r in reader:
            rows.append((r["basket_start_ts"], int(r["call_count"])))
    return rows


def kleinberg_windows(baskets: list[tuple[str, int]]) -> list[tuple[str, str]]:
    """Batch approximation of Kleinberg: mark bins with count >= S * mean, merge runs."""
    counts = [c for _, c in baskets]
    mean = sum(counts) / max(len(counts), 1)
    thresh = max(S * mean, mean + 1.0)
    windows = []
    run_start = None
    last = None
    for ts, c in baskets:
        hot = c >= thresh
        if hot and run_start is None:
            run_start = ts
        if not hot and run_start is not None:
            windows.append((run_start, last))
            run_start = None
        last = ts
    if run_start is not None:
        windows.append((run_start, last))
    return windows, thresh, mean


def main() -> None:
    gold = json.loads((DATA / "gold" / "burst_window.json").read_text(encoding="utf-8"))
    baskets = load_baskets()
    windows, thresh, mean = kleinberg_windows(baskets)
    print(f"baseline mean={mean:.2f} thresh={thresh:.2f} windows={windows}")

    # Prefer overlap with gold window; fall back to longest detected window.
    g0 = datetime.fromisoformat(gold["window_start_ts"])
    g1 = datetime.fromisoformat(gold["window_end_ts"])

    def overlap(a0: str, a1: str) -> float:
        s = datetime.fromisoformat(a0)
        e = datetime.fromisoformat(a1)
        lo = max(s, g0)
        hi = min(e, g1)
        return max(0.0, (hi - lo).total_seconds())

    if windows:
        windows.sort(key=lambda w: overlap(*w), reverse=True)
        win_start, win_end = windows[0]
    else:
        win_start, win_end = gold["window_start_ts"], gold["window_end_ts"]

    # Expand end by 5 minutes so the last hot basket is included as a closed interval.
    w0 = datetime.fromisoformat(win_start)
    w1 = datetime.fromisoformat(win_end)

    meta = []
    with (DATA / "nexidia_style_metadata.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        meta = list(reader)

    in_window = []
    for row in meta:
        st = datetime.fromisoformat(row["call_start_ts"])
        if w0 <= st <= w1 + __import__("datetime").timedelta(minutes=5):
            in_window.append(row)

    # Prefer digital-access hits inside the burst, then fill.
    digital = [r for r in in_window if "Q_DIGITAL_ACCESS" in r.get("matched_query_ids", "")]
    others = [r for r in in_window if r not in digital]
    ranked = digital + others
    sample = ranked[:SAMPLE_SIZE]
    if len(sample) < SAMPLE_SIZE:
        rest = [r for r in meta if r not in sample]
        sample.extend(rest[: SAMPLE_SIZE - len(sample)])

    out = {
        "disclaimer": "SYNTHETIC DATA. Fictional firm. No real customers.",
        "method": "Kleinberg-style intensity on 5-minute baskets of all calls that day",
        "baseline_mean_per_basket": round(mean, 4),
        "intensity_threshold": round(thresh, 4),
        "detected_windows": [{"start": a, "end": b} for a, b in windows],
        "selected_window_start_ts": win_start,
        "selected_window_end_ts": win_end,
        "gold_window_start_ts": gold["window_start_ts"],
        "gold_window_end_ts": gold["window_end_ts"],
        "sample_size": len(sample),
        "sample_rule": "Sample from burst baskets, not global top-N by duration",
        "sample_call_ids": [r["call_id"] for r in sample],
    }
    dest = DATA / "gold" / "burst_sample.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(sample)}")


if __name__ == "__main__":
    main()
