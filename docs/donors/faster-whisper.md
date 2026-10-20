# DP-164 — faster-whisper CPU, private opt-in

Donor: [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper),
upstream Git [tag v1.2.1](https://github.com/SYSTRAN/faster-whisper/releases/tag/v1.2.1),
commit `65882eee9f5cdbeeb2d877f1131d48cf241b327d`
(checked by `git ls-remote`), MIT license. Optional Python dependency
`faster-whisper==1.2.1`; project imports it only in the opted-in private worker
child. Reuse upstream `WhisperModel`/CTranslate2 directly (no upstream source
copies). The MIT donor attribution and notices remain upstream.
Copyright (c) 2023 SYSTRAN; retain upstream `LICENSE` and copyright notice
when redistributing the dependency. No faster-whisper source is vendored.
The donor's MIT license is **not** an assertion that any model, converted weights, Silero VAD assets,
audio fixture or transitive native library is licensed identically.
Before installing the optional extra, review the actual installed wheels
and bundled FFmpeg/PyAV/CTranslate2 binaries for notices and LGPL/GPL terms;
any LGPL/MPL/GPL/AGPL component requires the owner's explicit decision.
See [MIT license](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/LICENSE)
and [PyPI package](https://pypi.org/project/faster-whisper/1.2.1/).

**Status: model and canary BLOCKED.** No approved small-model snapshot,
revision, full weight hashes, license/redistribution notice or authorized real
audio + corresponding remote-ASR baseline has been supplied to this execution.
The historical 27.2s / 9.6s / ~640MiB row in the policy was not a verified
receipt from this dispatcher: the `proven_in_owner_runtime` bit is corrected
to `false`. The route is never selected automatically from the URL-only
fallback queue. DP-204 (#36) remains an independent live-ASR blocker.

## Operator-admitted input

The worker config requires both
`DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_ENABLED=1` and:

- `DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_AUDIO_ROOT`: absolute private
  directory containing already authorized 16kHz mono signed PCM WAV files;
- `DICHIARAZIONI_PUBBLICHE_FASTER_WHISPER_MODEL_RECEIPT`: absolute local
  JSON manifest, outside Git. Its `model_dir` also stays outside Git.

Receipt **schema illustration only**, not permission to obtain weights:

```json
{
  "model_id": "Systran/faster-whisper-small",
  "revision": "0123456789012345678901234567890123456789",
  "model_dir": "/home/udodo/.local/share/dichiarazioni-pubbliche/verified-faster-small",
  "license_spdx": "MIT",
  "license_source_url": "https://example.org/actual-license-at-pinned-revision",
  "license_reviewed": true,
  "files": {
    "LICENSE": "<64 lowercase SHA256 characters>",
    "config.json": "<64 lowercase SHA256 characters>",
    "model.bin": "<64 lowercase SHA256 characters>"
  }
}
```

These are placeholders. Verify actual model/converted weight provenance
and notices independently; if licensing is missing, **do not set reviewed**.
Inventory includes every file (tokenizer, vocab, preprocessor, licenses)
and must match disk exactly. Files and symlinks are checked and SHA-256
hashed on every attempt. No media/model download is implemented.
Native shared `local_inference_slot` prevents concurrent local model work;
the caller checks authorization, rights receipt, duration, input hash, WAV
contract and re-hashes a transient copy before dispatch. Only up to
30 seconds / 1,000,044 bytes per 16kHz mono PCM WAV; model files total
950MiB max / 96 files. Linux MiniPC `udodo` only, CPU int8, 4 compute
threads, one model worker, 6GiB virtual address cap, 100 CPU seconds,
120 wall seconds. Missing dependency/model rights/weight digest blocks the
attempt; busy local inference retries. The optional child inherits no
provider secrets, uses explicit offline flags and local-files-only loading.

The worker takes only manually enqueued `TRANSCRIPT_ACQUIRE_ASR` jobs with
exact provider `faster-whisper-small-local` and route
`local/faster-whisper-small`, private local path, SHA256 and rights fields.
The existing `_acquire_local_asr` persists the private transcript candidate,
segments and source/model hashes, full private response and provider receipt,
with `UNRECONCILED_ASR_CANDIDATE` and no publication approval. The existing
canonicalization/review contract remains authoritative. No public read path
changes and no independent chunker is introduced.

Silero VAD is natively available in `faster-whisper`; it is explicitly off
for this integration until its bundled weight licensing is separately reviewed.
Avoiding a second VAD/chunking mechanism also preserves original timestamps.

## Acceptance still needed

Use an owner-authorized sample already on MiniPC and a separately verified
licensed model snapshot. Record exact sample hash/rights receipt, CPU/RSS,
elapsed time, timestamps, sensitive numerals/negations compared with a
real authorized baseline, private provider receipt ID and any disagreement
`TRANSCRIPT_UNCERTAIN` / publication HOLD. Until this is demonstrated, no
claim of successful actual ASR or usable model benchmarks is made.
