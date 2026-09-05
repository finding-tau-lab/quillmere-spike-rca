#!/usr/bin/env python3
"""Build the Copilot-ready RCA JSON packet from synthetic files."""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output"
QUERY_ID = "Q_DIGITAL_ACCESS"
STOP = ["um", "uh", "like", "you know", "okay", "alright", "thank you", "please hold"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def phrases(text: str) -> list[str]:
    words = tokenize(text)
    stop = set(STOP + ["the", "a", "an", "to", "i", "you", "it", "is", "and", "of", "in", "on", "for", "my", "this", "that"])
    keep = [w for w in words if w not in stop and len(w) > 2]
    out = []
    for i in range(len(keep) - 1):
        out.append(f"{keep[i]} {keep[i+1]}")
    return out


def highlight(text: str) -> list[str]:
    needles = [
        "can't log in", "cant log in", "login failed", "app won't open",
        "error code", "won't load", "blank balance", "speak to a person",
        "transfer me", "invalid user", "try again later",
    ]
    low = text.lower()
    return [n for n in needles if n in low]


COPILOT_PROMPT = """You are writing a 3-bullet RCA for Quillmere Service Center leadership about a speech-query spike.

This JSON is SYNTHETIC. Do not invent a real firm, vendor outage, or product not supported by the sampled transcripts.

How to read query_logic:
Use query_logic_guide. Evaluate the tree inside-out. FIRST90 limits where in the call a match counts. NOTLIKE cuts false positives; it is not how you find the problem.

How to use lexicon:
Ignore lexicon.stopwords. Treat lexicon.top_keywords and lexicon.top_phrases as clues, not conclusions.

How to use sampled_calls:
Transcripts are evidence only. Quote or paraphrase what callers and agents actually said. Do not invent outages, error codes, or vendors that do not appear in the text.

Return only:
Bullet 1 — What changed in the calls (observable language / failure mode)
Bullet 2 — Most likely operational cause, hedged to the evidence
Bullet 3 — Recommended next action for the floor or digital team in the next 24 hours
No preamble. No extra sections.
"""


def main() -> None:
    catalog = {r["query_id"]: r for r in read_csv(DATA / "query_catalog.csv")}
    meta = {r["call_id"]: r for r in read_csv(DATA / "nexidia_style_metadata.csv")}
    sample_doc = json.loads((DATA / "gold" / "burst_sample.json").read_text(encoding="utf-8"))
    gold = json.loads((DATA / "gold" / "burst_window.json").read_text(encoding="utf-8"))
    q = catalog[QUERY_ID]

    hits = sum(1 for r in meta.values() if QUERY_ID in r.get("matched_query_ids", ""))
    sampled = []
    blob_for_lex = []
    for cid in sample_doc["sample_call_ids"]:
        row = meta[cid]
        path = ROOT / row["transcript_file"]
        text = path.read_text(encoding="utf-8")
        blob_for_lex.append(text)
        sampled.append(
            {
                "call_id": cid,
                "call_start_ts": row["call_start_ts"],
                "site": row["site"],
                "queue": row["queue"],
                "duration_sec": int(row["duration_sec"]),
                "matched_query_ids": [x for x in row["matched_query_ids"].split("|") if x],
                "highlighted_terms": highlight(text),
                "transcript": text,
            }
        )

    kw = Counter()
    ph = Counter()
    for text in blob_for_lex:
        for w in tokenize(text):
            if w not in STOP and len(w) > 3:
                kw[w] += 1
        for p in phrases(text):
            ph[p] += 1
    # drop ultra-common filler still slipping through
    for noise in ["quillmere", "service", "center", "calling", "agent", "caller"]:
        kw.pop(noise, None)

    packet = {
        "packet_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "SYNTHETIC DATA. Fictional firm. No real customers.",
        "alert": {
            "alert_date": "2026-03-18",
            "query_id": QUERY_ID,
            "query_name": q["query_name"],
            "query_description": q["query_description"],
            "query_logic": q["query_logic"],
            "hits_on_day": hits,
            "notes": "Single-day spike. Intra-day burst used for sampling.",
        },
        "query_logic_guide": {
            "dialect": "quillmere-demo-v1",
            "operators": {
                "LIKE": "Phrase or close spoken variant is present.",
                "NOTLIKE": "Exclude calls where this phrase is present.",
                "AND": "All children must match.",
                "OR": "Any child may match.",
                "FIRST90": "Inner condition must occur in the first 90 seconds of the call.",
                "NEAR": "Terms occur within n seconds of each other.",
            },
            "how_to_read": "Evaluate the tree inside-out. FIRST90 limits where in the call a match counts. NOTLIKE is for false-positive cuts, not for finding the problem.",
        },
        "burst": {
            "method": "Kleinberg burst detection on 5-minute baskets of all calls that day",
            "basket_minutes": 5,
            "window_start_ts": sample_doc.get("selected_window_start_ts", gold["window_start_ts"]),
            "window_end_ts": sample_doc.get("selected_window_end_ts", gold["window_end_ts"]),
            "sample_size": len(sampled),
            "sample_rule": "Sample from burst baskets, not global top-N by duration",
        },
        "lexicon": {
            "stopwords": STOP,
            "top_keywords": [w for w, _ in kw.most_common(12)],
            "top_phrases": [p for p, _ in ph.most_common(12)],
        },
        "sampled_calls": sampled,
        "copilot_prompt": COPILOT_PROMPT.strip(),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "rca_packet_2026-03-18_Q_DIGITAL_ACCESS.json"
    dest.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    (OUT / "ATTACH_THIS.txt").write_text(
        "Read the attached JSON and follow the copilot_prompt field exactly.\n",
        encoding="utf-8",
    )
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
