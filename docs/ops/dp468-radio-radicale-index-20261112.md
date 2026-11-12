# DP-468 — Independent publisher speaker-index cross-check

## Timed captions, checked 12 November 2026

The publisher also provides WebVTT captions. The
[live word-alignment receipt](dp468-radio-radicale-vtt-crosscheck-20261112.json)
ties the 16 pinned excerpts to their video segments and caption hashes:
1 exact word-token match, 14 partial, 1 with no three-token contiguous match
(ordinal 50). The reproducible reader is in
tools/dp468_radio_radicale_vtt_crosscheck.py. Recognition errors and shared
source footage prevent independent exact-word or publication approval.
All 16 remain PRIVATE_HOLD.

The held [16 Senato text candidates](dp468-senato-public-v3-source.md#new-first-batch-text-selection-10-november-2026-private-candidate-status) were cross-checked against [Radio Radicale's separate video index](https://www.radioradicale.it/scheda/760686/seduta-310a-xix-legislatura) for sitting 310 (29 May 2025).

`python3 -m tools.dp468_radio_radicale_crosscheck` verifies the actual HTTPS publisher, sitting/date, 16 full speaker names from the Senato card receipt, chronological order and linked, dated video segments. Missing/changed data fails closed. The [live JSON readback](dp468-radio-radicale-crosscheck-20261112.json) records **16/16 index matches**, URL, timestamp and page SHA-256.

This is an independently published **speaker/session index**. It does not attest audio-to-text correspondence for each quote or independent editorial origin of the underlying Senate video feed. It creates no `ATTRIBUTION`, `EXCERPT_PUBLIC`, GDPR, model-review or public-release grant. Every candidate remains `PRIVATE_HOLD` pending those separate decisions and the #413/#98 consumer proof.
