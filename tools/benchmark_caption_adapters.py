#!/usr/bin/env python3
"""Offline parser comparison; never accesses YouTube or external media."""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))
from dichiarazioni_pubbliche.caption_adapter import (  # noqa: E402
    parse_transcript_api_snippets, parse_youtube_json3,
)

DONOR = [
    {"text": "Affermazione campione uno", "start": 0.25, "duration": 1.5},
    {"text": "Affermazione campione due", "start": 1.75, "duration": 2.0},
]
JSON3 = {"events": [
    {"segs": [{"utf8": row["text"]}],
     "tStartMs": int(row["start"] * 1000),
     "dDurationMs": int(row["duration"] * 1000)}
    for row in DONOR
]}


def median_ms(parser, payload, *, repeats=5, iterations=4000):
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        for _ in range(iterations):
            parser(payload)
        samples.append((time.perf_counter() - started) * 1000 / iterations)
    return round(statistics.median(samples), 5)


def main():
    donor = parse_transcript_api_snippets(DONOR)
    legacy = parse_youtube_json3(JSON3)
    equivalent = donor == legacy
    if not equivalent:
        raise SystemExit("FAIL: synthetic caption timestamps/text differ")
    failures = 0
    for rows in ([], [{"text": "bad", "start": 1, "duration": 0}],
                 [DONOR[1], DONOR[0]]):
        try:
            parse_transcript_api_snippets(rows)
        except ValueError:
            failures += 1
    if failures != 3:
        raise SystemExit("FAIL: donor validation accepted unsafe fixture")
    print(json.dumps({
        "method": "synthetic-fixture-parse-only", "network_requests": 0,
        "donor_valid_fixtures": 2, "legacy_valid_fixtures": 2,
        "equivalent_segments": equivalent, "rejected_donor_invalid_fixtures": failures,
        "donor_median_parse_ms": median_ms(parse_transcript_api_snippets, DONOR),
        "yt_dlp_json3_median_parse_ms": median_ms(parse_youtube_json3, JSON3),
        "provider_latency_failure_rate_and_cost": "not_measured_without_authorized_source",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
