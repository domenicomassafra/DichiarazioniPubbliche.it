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

**Status (23 October 2026): real Small canary PASS in the owner's MiniPC runtime.**
`proven_in_owner_runtime=true` now reflects an isolated application-worker run,
not the historical 27.2s / 9.6s / ~640MiB benchmark. The original private
synthetic WAV and remote baseline are documented in [#36](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/36#issuecomment-6308454627).
On `udodo`, the CPU adapter and the actual `TRANSCRIPT_ACQUIRE_ASR` worker used
`Systran/faster-whisper-small` revision
`536b0662742c02347bc0e980a01041f333bce120`, weight SHA-256
`3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`
and the authorized 10.6416875s audio SHA-256
`193d473295913b57744379f3472673681aaa557a37402e9cf3f1db7bf50f4e4f`.
The checked private seven-file model receipt had SHA-256
`995eadb3cca201184cb75efec6f31d06fda4aa24ac80dd67a8b3d1c608a3251e`.
The converted-model card declares MIT and names the original
[`openai/whisper-small`](https://huggingface.co/openai/whisper-small), whose model
card declares Apache-2.0. The isolated receipt kept the pinned converted README
and a separate copy of the Apache-2.0 license plus lineage notice. It did not
claim these notices came packaged with the converted snapshot.

Actual inference returned two timestamped segments, exact remote-baseline text
SHA-256 `d40154234bb696988fc60022a2cbfe74c1139feaa7f56980d1ec2b77ab185198`,
including the sensitive 7 / 7.5 billion quantities and both negations.
Measured adapter elapsed 5.683s, child user CPU 13.467s, system CPU 1.835s,
peak child RSS 622188 KiB. The isolated PostgreSQL worker read a current
`ASR_MEDIA` grant bound to the exact synthetic Content and URL, completed the
job, wrote a private transcript variant, two segments and provider receipt
`SUCCESS`, then queued canonicalization. Receipt quality remained
`UNRECONCILED_ASR_CANDIDATE`, publication approval `false`, with zero Content
publication candidates. The route is still excluded from generic URL fallback.

**Production opt-in remains gated:** the PyAV 18.1.0 wheel bundles native FFmpeg;
PyAV source reports BSD-3-Clause, while bundled wheel FFmpeg has GPL/LGPL
obligations (see [upstream issue #2270](https://github.com/PyAV-Org/PyAV/issues/2270)).
Review exact binary notices and obtain the owner's explicit approval before a
persistent deployment. The test ran with an offline, temporary `uv` environment
and an isolated temporary database; it did not confer rights for any actual
third-party Content. No automatic download, publish, or remote ASR occurred.

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
hashed on every attempt. Model receipt and model directory ancestors must not
traverse symlinks or `..` components. No media/model download is implemented.
Native shared `local_inference_slot` prevents concurrent local model work;
the caller checks authorization, rights receipt, duration, input hash, WAV
contract and re-hashes a transient copy before dispatch. Only up to
30 seconds / 1,000,044 bytes per 16kHz mono PCM WAV; model files total
950MiB max / 96 files. Linux MiniPC `udodo` only, CPU int8, 4 compute
threads, one model worker, 6GiB virtual address cap, 100 CPU seconds,
120 wall seconds. Missing dependency/model rights/weight digest blocks the
attempt; busy local inference retries. The optional child inherits no
provider secrets, uses explicit offline flags and local-files-only loading.
The child writes its JSON response into a transient private file with an
RLIMIT_FSIZE cap of 256,000 bytes; native stderr is discarded instead of
captured in unbounded parent-memory pipes. This is an output bound and a 6GiB
virtual-address limit, not a measured real-world RSS acceptance receipt.

The worker takes only manually enqueued `TRANSCRIPT_ACQUIRE_ASR` jobs with
exact provider `faster-whisper-small-local` and route
`local/faster-whisper-small`, private local path, SHA256 and rights fields.
In addition to `local_audio_authorized`, `rights_basis`, and the opaque
`rights_receipt_id`, a local job must carry `rights_record_id` and
`rights_policy_version` for a *current* DP-305 `private_source_rights_record`.
The source-use guard verifies exact `content_id`/canonical URL, policy,
reviewer, current CLEARED receipt, expiry and `ASR_MEDIA` permission **before
inference and again before private persistence**. These job fields are pointers
to existing independent review, never substitutes for that review. A missing,
revoked or superseded record blocks and releases no transcript candidate.
The existing `_acquire_local_asr` persists the private transcript candidate,
segments and source/model hashes, full private response and provider receipt,
with `UNRECONCILED_ASR_CANDIDATE` and no publication approval. The existing
canonicalization/review contract remains authoritative. No public read path
changes and no independent chunker is introduced.

Silero VAD is natively available in `faster-whisper`; it is explicitly off
for this integration until its bundled weight licensing is separately reviewed.
Avoiding a second VAD/chunking mechanism also preserves original timestamps.

## Follow-up before persistent production use

Obtain the owner's decision on native FFmpeg/PyAV GPL/LGPL obligations, install
the reviewed wheel and a durable private model receipt on the MiniPC, and
provide current source-specific rights for any real-world audio. The successful
synthetic canary is evidence of runtime functionality, not authorization to
automatically ingest or publish unrelated source media.
