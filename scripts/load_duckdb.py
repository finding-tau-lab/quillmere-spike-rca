#!/usr/bin/env python3
"""Optional DuckDB load. Flat files remain source of truth."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "transcripts_clob.csv"
DB = ROOT / "data" / "qsc.duckdb"
INIT = ROOT / "sql" / "init.sql"


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("duckdb not installed; skip. pip install duckdb if you want the warehouse stand-in.")
        print("RCA packet build uses the CSV/transcript files directly.")
        return 0

    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(INIT.read_text(encoding="utf-8"))
    rows = []
    with CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.startswith("#"))
        for r in reader:
            rows.append((r["call_id"], r["transcript_clob"].replace("\\n", "\n")))
    con.executemany("INSERT INTO calls(call_id, transcript_clob) VALUES (?, ?)", rows)
    n = con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    print(f"loaded {n} rows into {DB}")
    # Demo CLOB pull shape (warehouse stand-in):
    # SELECT call_id, transcript_clob AS clob FROM calls WHERE call_id IN (...)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
