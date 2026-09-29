# quillmere-spike-rca

Replaced a 50-minute manual review of speech-analytics alerts with a burst-sampled packet: 30 calls from the spike window, full transcripts, structured RCA in 12–15 minutes (~70% faster), same-day answer for ops leadership.

This public repo is a synthetic reconstruction of that method. Fictional firm (Quillmere). No real customer data, no employer code, no vendor affiliation.

What this shows:

1. Ingest Nexidia-style call metadata (demo extract, not a NICE product).
2. Bucket all calls that day into 5-minute baskets.
3. Run Kleinberg-style burst detection and sample **from the burst**, not a random 20.
4. Pull full transcripts from a warehouse CLOB stand-in (flat files here; optional DuckDB).
5. Emit one JSON packet a reviewer attaches to Copilot to draft a 3-bullet RCA.

It does **not** ship model output. It does **not** use real customer audio or employer code.

## Spike story (fixed)

- Date: **2026-03-18**
- Overnight **client-portal / mobile-app login failures**
- Query that spikes: `Q_DIGITAL_ACCESS`
- Secondary bleed: speak-to-a-person, statement/positions not visible

## How to run

```bash
python3 scripts/generate_synthetic_data.py
python3 scripts/burst_sample.py
python3 scripts/load_duckdb.py          # optional
python3 scripts/build_rca_packet.py
python3 scripts/check_forbidden_terms.py
python3 scripts/mock_rca.py
```

Then attach `output/rca_packet_2026-03-18_Q_DIGITAL_ACCESS.json` to Copilot and paste the one line in `output/ATTACH_THIS.txt`.

Seed is `20260318`. Regenerating the corpus is deterministic.

## Why sample 30

A common floor practice is ~20 calls by hand. Thirty IDs from the burst window is still small enough to read and deeper than a convenience sample of the longest calls.

## What this is not

- Not a real broker or contact center, and not tax-season analysis
- Not a production speech-query library
- Not a live warehouse or vendor connection string
- Not a live model call

## License

MIT
