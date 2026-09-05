#!/usr/bin/env python3
"""Generate the Quillmere single-day synthetic contact-center corpus.

SEED=20260318. Deterministic. SYNTHETIC DATA ONLY.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20260318
N_CALLS = 350
DAY = datetime(2026, 3, 18, tzinfo=timezone(timedelta(hours=-4)))  # EDT
OPEN_MIN = 8 * 60
CLOSE_MIN = 20 * 60
BURST_START = datetime.fromisoformat("2026-03-18T10:35:00-04:00")
BURST_END = datetime.fromisoformat("2026-03-18T12:10:00-04:00")
N_BURST = 140

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRANS_DIR = DATA / "transcripts"

SITES = ["Los Angeles", "Miami", "Atlanta"]
QUEUES = ["DIGITAL", "SERVICE", "ADVISOR_SUPPORT", "TRANSFERS"]
DISPOSITIONS = ["resolved", "callback", "transfer", "unresolved"]
AGENT_FIRST = [
    "Jordan", "Riley", "Casey", "Avery", "Morgan",
    "Quinn", "Sage", "Cameron", "Hayden", "Reese",
]

QUERY_CATALOG = [
    {
        "query_id": "Q_DIGITAL_ACCESS",
        "query_name": "Digital access failure",
        "query_description": "Caller cannot log in to the client portal or mobile app, hits an error, or the app will not load.",
        "query_logic": 'FIRST90(AND(OR(LIKE("can\'t log in"),LIKE("login failed"),LIKE("app won\'t open"),LIKE("error code")),NOTLIKE("password reset complete")))',
        "category": "digital",
        "notes": "Spike query for 2026-03-18. Opening-problem window only.",
    },
    {
        "query_id": "Q_SPEAK_TO_PERSON",
        "query_name": "Speak to a person",
        "query_description": "Caller asks to leave the IVR or bot and reach a live representative.",
        "query_logic": 'FIRST90(OR(LIKE("speak to a person"),LIKE("talk to someone"),LIKE("representative"),LIKE("transfer me")))',
        "category": "routing",
        "notes": "Secondary bleed when self-service fails.",
    },
    {
        "query_id": "Q_STATEMENT_VISIBILITY",
        "query_name": "Statement or positions not visible",
        "query_description": "Caller can open something but cannot see a statement, positions, or balances in the portal or app.",
        "query_logic": 'FIRST90(AND(OR(LIKE("can\'t see my statement"),LIKE("positions won\'t load"),LIKE("blank balance"),LIKE("nothing showing")),NOTLIKE("statement mailed")))',
        "category": "digital",
        "notes": "Bleed from the same outage story.",
    },
    {
        "query_id": "Q_PASSWORD_HELP",
        "query_name": "Password or reset help",
        "query_description": "Caller wants a password reset or is stuck mid-reset.",
        "query_logic": 'OR(LIKE("reset my password"),LIKE("forgot password"),LIKE("temporary password"))',
        "category": "digital",
        "notes": "Adjacent to access failures; not the spike definition.",
    },
    {
        "query_id": "Q_ADVISOR_REACH",
        "query_name": "Reach my advisor",
        "query_description": "Caller or advisor-desk contact wants a named advisor or desk callback.",
        "query_logic": 'OR(LIKE("my advisor"),LIKE("advisor callback"),LIKE("desk please"))',
        "category": "relationship",
        "notes": "Baseline traffic.",
    },
    {
        "query_id": "Q_TRANSFER_REQUEST",
        "query_name": "Move money or transfer",
        "query_description": "Caller wants to initiate or check a cash or in-kind transfer.",
        "query_logic": 'OR(LIKE("transfer funds"),LIKE("wire"),LIKE("move money"),LIKE("ACH"))',
        "category": "servicing",
        "notes": "Baseline traffic. Do not treat generic 'transfer me' as this query.",
    },
    {
        "query_id": "Q_FEE_QUESTION",
        "query_name": "Fee or billing question",
        "query_description": "Caller asks about advisory fees, a line item, or a billing date.",
        "query_logic": 'OR(LIKE("advisory fee"),LIKE("why was I charged"),LIKE("billing"))',
        "category": "servicing",
        "notes": "Baseline traffic.",
    },
    {
        "query_id": "Q_PROFILE_UPDATE",
        "query_name": "Profile or address update",
        "query_description": "Caller wants to change an address, email, or phone on file.",
        "query_logic": 'OR(LIKE("update my address"),LIKE("change my email"),LIKE("new phone number"))',
        "category": "servicing",
        "notes": "Baseline traffic.",
    },
]


def ts(minutes_from_midnight: float, extra_sec: int = 0) -> datetime:
    base = DAY + timedelta(minutes=minutes_from_midnight, seconds=extra_sec)
    return base


def iso(dt: datetime) -> str:
    return dt.isoformat()


def call_id(n: int) -> str:
    return f"CALL-20260318-{n:06d}"


def acct(rng: random.Random) -> str:
    return f"ACCT-8{rng.randint(1000000, 9999999)}"


def agent_id(rng: random.Random) -> str:
    return f"AGT-2{rng.randint(100, 199)}"


def pick_times(rng: random.Random, in_burst: bool) -> tuple[datetime, datetime, int]:
    if in_burst:
        span = (BURST_END - BURST_START).total_seconds()
        offset = rng.random() * span
        start = BURST_START + timedelta(seconds=offset)
    else:
        # Uniform over open hours, then reject if it landed in burst (resample).
        for _ in range(20):
            minute = OPEN_MIN + rng.random() * (CLOSE_MIN - OPEN_MIN)
            start = ts(minute, rng.randint(0, 59))
            if not (BURST_START <= start < BURST_END):
                break
    duration = int(rng.choice([90, 120, 150, 180, 210, 240, 300, 360, 420, 480]))
    duration += rng.randint(-20, 40)
    duration = max(75, min(duration, 720))
    end = start + timedelta(seconds=duration)
    return start, end, duration


def fmt_mmss(sec: int) -> str:
    return f"{sec // 60:02d}:{sec % 60:02d}"


def build_transcript(rng: random.Random, theme: str, agent: str, duration: int) -> str:
    """Template + slot-fill. Intentionally imperfect speech-to-text."""
    lines = []
    t = 0
    lines.append(f"[{fmt_mmss(t)}] IVR: Thank you for calling Quillmere Service Center.")
    t += rng.randint(18, 45)
    if theme in {"digital", "speak", "statement"} and rng.random() < 0.55:
        lines.append(f"[{fmt_mmss(t)}] CALLER: um can I speak to a person please the menu is not helping")
        t += rng.randint(6, 14)
    lines.append(f"[{fmt_mmss(t)}] AGENT: Quillmere Service Center, this is {agent}. How can I help?")
    t += rng.randint(4, 10)

    openers = {
        "digital": [
            "I can't log in to the app it just spins",
            "login failed again this morning error code something",
            "the app won't open on my phone since last night",
            "portal says invalid user but it worked yesterday",
            "every time I try to sign in I get kicked out",
        ],
        "statement": [
            "I got in I think but I can't see my statement",
            "positions won't load it's just a blank balance",
            "nothing showing under accounts in the app",
            "statements page is empty can you see them on your side",
        ],
        "speak": [
            "I just need to talk to someone the bot kept looping",
            "please transfer me I already tried the app",
            "representative please this is not a password question",
        ],
        "password": [
            "I need to reset my password the email never showed",
            "forgot password and the temporary password expired",
        ],
        "advisor": [
            "can you get a message to my advisor I need a callback",
            "desk please I was told to call the service line first",
        ],
        "transfer": [
            "I want to transfer funds to my bank I started it in the app and it stalled",
            "checking on an ACH I submitted yesterday",
        ],
        "fee": [
            "why was I charged an advisory fee this week I thought it was quarterly",
            "question on billing the line item looks off",
        ],
        "profile": [
            "I need to update my address we moved last month",
            "change my email on file the old one is shut down",
        ],
        "other": [
            "calling about a confirmation I thought I would get",
            "just wanted to confirm you have my mobile number",
        ],
    }
    opener = rng.choice(openers[theme])
    lines.append(f"[{fmt_mmss(t)}] CALLER: {opener}")
    t += rng.randint(5, 16)

    mids = {
        "digital": [
            f"AGENT: I am pulling up the profile now. Are you on the mobile app or the website?",
            f"CALLER: mobile um it says try again later",
            f"AGENT: Understood. I am not seeing a completed password reset on our side.",
            f"CALLER: yeah I didn't finish a reset I just can't get in",
            f"AGENT: There looks to be a wider sign-in issue this morning. Let me document this.",
        ],
        "statement": [
            f"AGENT: Can you tell me whether the header loads or the whole page is blank?",
            f"CALLER: header is there balances are blank positions won't load",
            f"AGENT: Copy. I can see the accounts on my desktop tool.",
            f"CALLER: so it's the app then not my account missing right",
        ],
        "speak": [
            f"AGENT: You are talking to a person now. What did the menu send you through?",
            f"CALLER: digital help then it died I need a representative not a script",
            f"AGENT: I have you. Give me one moment.",
        ],
        "password": [
            f"AGENT: I can send a reset link to the email on file.",
            f"CALLER: okay please the last temporary password bounced",
        ],
        "advisor": [
            f"AGENT: I can request an advisor callback. What is the best number?",
            f"CALLER: the mobile on the profile is fine",
        ],
        "transfer": [
            f"AGENT: I see a transfer request in a pending state. I cannot release it from this line.",
            f"CALLER: so I wait? the app just sat there",
        ],
        "fee": [
            f"AGENT: Fee lines post on a cycle. I can note the question for review.",
            f"CALLER: alright just wanted it flagged",
        ],
        "profile": [
            f"AGENT: I can take the new address. I will repeat it back.",
            f"CALLER: please do I don't want a statement going to the old place",
        ],
        "other": [
            f"AGENT: I have the profile open. What should I confirm?",
            f"CALLER: just that you can reach me if something posts",
        ],
    }
    for chunk in mids[theme]:
        speaker, text = chunk.split(": ", 1)
        # light ASR mess
        if rng.random() < 0.12:
            text = text.replace("the", "teh", 1) if "the" in text else text
        lines.append(f"[{fmt_mmss(t)}] {speaker}: {text}")
        t += rng.randint(4, 12)
        if t > duration - 25:
            break

    closes = [
        "AGENT: I am documenting this and you should get a callback if it is not restored today.",
        "AGENT: Try the app again later this afternoon and call back if it is still down.",
        "AGENT: I noted the profile. Is there anything else?",
        "CALLER: that's all thanks",
        "CALLER: okay um thanks",
        "AGENT: Thank you for calling Quillmere Service Center.",
    ]
    rng.shuffle(closes)
    for chunk in closes[:3]:
        speaker, text = chunk.split(": ", 1)
        if t >= duration - 5:
            break
        lines.append(f"[{fmt_mmss(t)}] {speaker}: {text}")
        t += rng.randint(3, 8)

    return "\n".join(lines) + "\n"


def match_queries(text: str) -> list[str]:
    low = text.lower()
    hits = []
    rules = [
        ("Q_DIGITAL_ACCESS", ["can't log in", "cant log in", "login failed", "app won't open", "app wont open", "error code", "sign in", "kicked out", "invalid user", "just spins"]),
        ("Q_SPEAK_TO_PERSON", ["speak to a person", "talk to someone", "representative", "transfer me"]),
        ("Q_STATEMENT_VISIBILITY", ["can't see my statement", "cant see my statement", "positions won't load", "positions wont load", "blank balance", "nothing showing"]),
        ("Q_PASSWORD_HELP", ["reset my password", "forgot password", "temporary password"]),
        ("Q_ADVISOR_REACH", ["my advisor", "advisor callback", "desk please"]),
        ("Q_TRANSFER_REQUEST", ["transfer funds", "move money", " ach", "ach "]),
        ("Q_FEE_QUESTION", ["advisory fee", "why was I charged", "why was i charged", "billing"]),
        ("Q_PROFILE_UPDATE", ["update my address", "change my email", "new phone number"]),
    ]
    # digital access: require failure language, drop if reset complete
    for qid, needles in rules:
        if qid == "Q_DIGITAL_ACCESS" and "password reset complete" in low:
            continue
        if qid == "Q_TRANSFER_REQUEST" and "transfer me" in low and "transfer funds" not in low and "move money" not in low:
            continue
        if any(n in low for n in needles):
            hits.append(qid)
    return hits


def assign_theme(rng: random.Random, in_burst: bool) -> str:
    if in_burst:
        # 60-70% digital-access language
        return rng.choices(
            ["digital", "statement", "speak", "password", "advisor", "other"],
            weights=[62, 12, 12, 5, 5, 4],
        )[0]
    return rng.choices(
        ["digital", "statement", "speak", "password", "advisor", "transfer", "fee", "profile", "other"],
        weights=[8, 6, 8, 8, 16, 16, 14, 14, 10],
    )[0]


def main() -> None:
    rng = random.Random(SEED)
    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA / "gold").mkdir(parents=True, exist_ok=True)

    with (DATA / "query_catalog.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(QUERY_CATALOG[0].keys()))
        w.writeheader()
        w.writerows(QUERY_CATALOG)

    in_burst_flags = [True] * N_BURST + [False] * (N_CALLS - N_BURST)
    rng.shuffle(in_burst_flags)

    meta_rows = []
    clob_rows = []

    for i in range(1, N_CALLS + 1):
        in_burst = in_burst_flags[i - 1]
        theme = assign_theme(rng, in_burst)
        start, end, duration = pick_times(rng, in_burst)
        cid = call_id(i)
        agent_name = rng.choice(AGENT_FIRST)
        text = build_transcript(rng, theme, agent_name, duration)
        hits = match_queries(text)
        if theme == "digital" and "Q_DIGITAL_ACCESS" not in hits:
            hits.insert(0, "Q_DIGITAL_ACCESS")
        primary = hits[0] if hits else "Q_ADVISOR_REACH"
        if in_burst and theme == "digital":
            primary = "Q_DIGITAL_ACCESS"
            if "Q_DIGITAL_ACCESS" not in hits:
                hits.insert(0, "Q_DIGITAL_ACCESS")

        site = rng.choices(SITES, weights=[34, 33, 33])[0]
        if in_burst:
            queue = rng.choices(QUEUES, weights=[45, 25, 15, 15])[0]
            disp = rng.choices(DISPOSITIONS, weights=[35, 25, 25, 15])[0]
        else:
            queue = rng.choices(QUEUES, weights=[20, 35, 25, 20])[0]
            disp = rng.choices(DISPOSITIONS, weights=[55, 15, 20, 10])[0]

        rel = f"data/transcripts/{cid}.txt"
        (ROOT / rel).write_text(text, encoding="utf-8")

        meta_rows.append(
            {
                "call_id": cid,
                "call_start_ts": iso(start),
                "call_end_ts": iso(end),
                "duration_sec": duration,
                "site": site,
                "queue": queue,
                "agent_id": agent_id(rng),
                "direction": "INBOUND",
                "disposition": disp,
                "primary_query_id": primary,
                "matched_query_ids": "|".join(hits) if hits else "",
                "in_spike_window": "true" if in_burst else "false",
                "transcript_file": rel,
                "transcript_available": "true",
            }
        )
        clob_rows.append(
            {
                "call_id": cid,
                "transcript_clob": text.replace("\n", "\\n"),
                "load_ts": iso(DAY.replace(hour=21, minute=15)),
            }
        )

    meta_rows.sort(key=lambda r: r["call_start_ts"])
    # Re-stamp sequential ids would break file names; keep original ids, sort for csv readability only.

    fields = list(meta_rows[0].keys())
    with (DATA / "nexidia_style_metadata.csv").open("w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DATA. Fictional firm Quillmere Advisory. No real customers.\n")
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(meta_rows)

    with (DATA / "transcripts_clob.csv").open("w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DATA. Warehouse CLOB stand-in. No real customers.\n")
        w = csv.DictWriter(f, fieldnames=["call_id", "transcript_clob", "load_ts"])
        w.writeheader()
        w.writerows(clob_rows)

    # 5-minute baskets 08:00-20:00
    baskets: dict[str, int] = {}
    cursor = ts(OPEN_MIN)
    end_day = ts(CLOSE_MIN)
    while cursor < end_day:
        baskets[iso(cursor)] = 0
        cursor += timedelta(minutes=5)

    for row in meta_rows:
        st = datetime.fromisoformat(row["call_start_ts"])
        bucket_min = (st.hour * 60 + st.minute) // 5 * 5
        bucket = ts(bucket_min)
        key = iso(bucket)
        if key in baskets:
            baskets[key] += 1

    with (DATA / "time_baskets_5min.csv").open("w", newline="", encoding="utf-8") as f:
        f.write("# SYNTHETIC DATA. 5-minute baskets of all 350 calls on 2026-03-18.\n")
        w = csv.writer(f)
        w.writerow(["basket_start_ts", "call_count"])
        for k in sorted(baskets):
            w.writerow([k, baskets[k]])

    print(f"wrote {N_CALLS} calls; burst flagged={sum(1 for r in meta_rows if r['in_spike_window']=='true')}")


if __name__ == "__main__":
    main()
