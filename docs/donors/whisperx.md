# DP-165 — WhisperX forced alignment, private opt-in

**Donor:** [m-bain/whisperX](https://github.com/m-bain/whisperX),
[v3.8.6 (2026-05-25)](https://github.com/m-bain/whisperX/releases/tag/v3.8.6),
tag commit `3ccc17b8de34f305300f8a3fd3c9f76ba820c0d0`,
[BSD-2-Clause](https://github.com/m-bain/whisperX/blob/v3.8.6/LICENSE);
copyright (c) 2024 Max Bain. Reuse through the upstream
`whisperx.load_align_model` and `whisperx.align` Python APIs: **no
vendored code**. Upstream package is optional and not installed by
the default/contributor profile. Preserve the upstream BSD copyright,
license conditions and disclaimer for any distribution of its package.

**Scope:** `whisperx_alignment_private.py` accepts one *already
authorized* bounded private WAV (16 kHz, mono PCM16, <=30 seconds)
and an existing exact transcript. It aligns *word times only*.
It never transcribes, diarizes, identifies speakers, discovers media,
downloads an asset, creates a review event or publishes anything.
A caller must invoke `propose_whisperx_alignment` explicitly with
`DICHIARAZIONI_PUBBLICHE_WHISPERX_ENABLED=1`.
No scheduled worker or fallback provider is wired to this POC.

The existing `align_parliamentary_intervention` always runs first.
Official timestamp ranges win unconditionally. The existing exact-text
locator is carried in `AlignmentProposal.fallback`, unmodified. An
acoustic result offers `REVIEW_CANDIDATE` only, plus individual word
times and their original upstream *scores* (non-calibrated CTC heuristic).
Never use those scores as probability of truth, exact quote authority,
or proof of audio speaker identity. `TranscriptCandidate` is mapped
with `source_kind=UNVERIFIED` and private provenance. The candidate
must **not** be sent to `reconcile_candidates` as independent ASR
evidence; its text is the existing transcript. `publication_blocked`
is always true and `source_span_review_ready` always false. The
separate `SourceSpanReviewStore.record_transcript_review` requires
a human reviewer to check the original audio and current source
variant/segment binding before `HUMAN_AUDIO_VERIFIED` is possible.
No automatic `source_span_review` event is created.

## Mandatory rights and dependency gates

Operator must separately verify and attest **before enabling**:

1. Source WAV rights receipt, source variant/segment hashes and existing
   transcript hash; file stays below an absolute private `audio_root`.
   Revalidate hash and PCM contract on every call, use an ephemeral
   copy under the existing local-inference mutex, no upload. In addition to
   historical `authorization=True` and `rights_receipt_id`, the caller **must**
   provide `authorization_guard` bound to the *current authoritative source-use
   decision* for this exact capture/variant/segment and permitted alignment
   purpose. The guard must raise on missing, expired or revoked rights; explicit
   `False` also denies. The adapter invokes it before any private model/audio
   read, after WAV staging and immediately after the child process exits, before
   returning any `REVIEW_CANDIDATE`. Exceptions become a private generic HOLD
   without leaking original error text. A syntactically valid receipt ID or an
   inert callback is never independent proof of source authorization.
2. **Exact Italian Wav2Vec2 CTC Hugging Face snapshot**:
   actual model ID + pinned 40-hex revision, license URL at revision,
   license review and full local-file SHA256 inventory including
   `config.json`, weights `.safetensors` and LICENSE. WhisperX's
   own BSD license says nothing about Wav2Vec2/Torchaudio weight
   rights. In v3.8.6 upstream's default Italian
   `VOXPOPULI_ASR_BASE_10K_IT` resolves through torchaudio
   downloads; this adapter **never selects that default**. It forces
   a local HF model directory + `model_cache_only=True`.

   **Read-only Italian weight audit (2026-10-20; no model downloaded):**
   [torchaudio's Italian VoxPopuli model documentation](https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.VOXPOPULI_ASR_BASE_10K_IT.html)
   explicitly states **CC BY-NC 4.0** for its weights. This upstream
   default cannot be treated as BSD-licensed with WhisperX.
   [Meta's Italian XLSR-53 CTC model](https://huggingface.co/facebook/wav2vec2-large-xlsr-53-italian/tree/e2760fe9ade861421db16f4548f6c0d48568ae0c)
   declares Apache-2.0, revision `e2760fe9ade861421db16f4548f6c0d48568ae0c`,
   LFS `pytorch_model.bin` SHA-256
   `4269323aa508e549f42ea661bf946c5340d1b3e85d4fe20461d8808f4928e0ad`
   (1,262,104,215 bytes). The independent
   [Jonatas Grosman Italian model](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-italian/tree/dab04a3e00d8326052f3fb22a6ff276b822f6131)
   declares Apache-2.0, revision `dab04a3e00d8326052f3fb22a6ff276b822f6131`,
   LFS SHA-256 `14040a54d1e0caecd8b2271fdd2d96653be45702c7bc8765354140d864fb445a`
   (1,262,114,199 bytes). Both card inventories were read via the official
   Hugging Face metadata API; their main snapshots include large PyTorch
   pickle weights, not the required safe-tensors model+LICENSE files. Both
   exceed this adapter's 1 GiB total inventory bound. Their cards refer
   to Common Voice; the [Mozilla terms](https://commonvoice.allizom.org/en/terms)
   describe CC0 for Common Voice data, but the exact historical training
   release, all upstream pretraining rights and artifact conversion require
   independent owner sign-off. Neither candidate has been adopted or benchmarked.
3. Separate installed dependency/wheel notices and licensing approval,
   including `torch`, `torchaudio`, `torchcodec`, `transformers`,
   `nltk`, and WhisperX's transitive `pyannote-audio`/FFmpeg stack.
   `native_notices_reviewed` is required in the private manifest.
   The upstream `pyproject.toml` includes PyTorch 2.8, torchaudio
   2.8 and pyannote.audio >=4.0; installation is held while any
   LGPL/MPL/GPL/AGPL obligation is unreviewed. There is no new
   optional dependency in project packaging yet.
4. Offline NLTK `punkt_tab` language asset, with its separate
   distribution/license audit. Upstream `align` calls
   `nltk.download('punkt_tab')` if absent: the adapter replaces
   that download with a raising function; missing asset causes HOLD.
   Local model Hugging Face/transformer loads run with offline flags.
   The [NLTK data license inventory](https://github.com/nltk/nltk_data/blob/550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/DATASET-LICENSES.md)
   explicitly lists `punkt_tab` among **unknown/ambiguous** dataset licenses;
   the NLTK data repository's Apache-2.0 license is **not** the individual
   trained asset's license. Its [official index](https://github.com/nltk/nltk_data/blob/550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/index.xml)
   records `punkt_tab.zip` SHA-256
   `e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106`.
   Asset provisioning stays on HOLD pending explicit rights clearance.
5. CPU/RSS/wall and accuracy benchmark on a rights-cleared, long-form
   Italian fixture including digits, negations, speaker overlap,
   and drift against timestamped human audio. Until that fixture
   exists, only synthetic contract/parse tests are meaningful.

Example *schema only*, never an authorization or actual model:

```json
{
  "model_id": "operator-reviewed/local-italian-wav2vec2",
  "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "model_dir": "/path/to/operator-reviewed/local/model",
  "license_spdx": "Apache-2.0",
  "license_source_url": "https://example.org/pinned-model-license",
  "license_reviewed": false,
  "native_notices_reviewed": false,
  "files": {
    "config.json": "<actual SHA256>",
    "model.safetensors": "<actual SHA256>",
    "LICENSE": "<actual SHA256>"
  }
}
```

The runtime refuses the example (false attestations); no model
weights, real media, NLTK asset or inference dependency have been
downloaded/installed. The isolated child runs CPU-only with four
threads, 6 GiB address-space, 100 CPU seconds, 120 wall seconds.
The child writes stdout to a mode-restricted ephemeral file under the private
work directory with a 256,000-byte kernel `RLIMIT_FSIZE`; stderr is discarded,
never buffered in parent memory or returned to an operator. Parent checks the
file size before reading at most 256,001 bytes and parsing JSON. Oversize,
timeout or nonzero child exit remain HOLD; this avoids the unbounded parent
pipe capture of the previous subprocess implementation.
Output must contain every expected word in order, with monotonic
finite timestamps, within the WAV and CTC score >=0.70.
The private candidate identity also includes SHA-256 of its accepted word
strings, millisecond boundaries and heuristic scores. Repeated identical
output replays under the same ID; changed timings cannot reuse that ID.
Missing/ambiguous words, mismatched numerals/negations, overlap,
untrusted native/model rights or missing assets keep the result on
human review/HOLD. No true precision/recall or resource numbers
are claimed from mocked parser outputs.
The upstream [WhisperX #1449](https://github.com/m-bain/whisperX/issues/1449)
(opened 2026-07-11; still open at this audit) reports wildcard CTC behavior
for digits and punctuation in versions 3.8.3–3.8.6; this reinforces the
need for independently timed gold on Italian numbers and punctuation before
any attribution or publication. No upstream patch was copied or made.

**Dependency state:** #164 faster-whisper ASR adapter merged but
the licensed weights and real-audio canary are HOLD (#36);
#166 pyannote diarization and DP-208 #37 remain independent.
#61 DP-317 exact-quote rights gate is OPEN. This seam does not
change any of their requirements.

## DP-359 — independent word-time baseline (2026-10-25)

The private operator canary requires a separately sourced, independently
annotated **word timeline** whenever the transcript has no authoritative
official start/end range. The source and each word/start/end millisecond value
are included in the private manifest and bound to its SHA-256. The operator
must verify the annotation source and the rights of the actual audio separately;
a self-authored JSON field is not evidence of an independent acoustic gold.
Official media ranges still win, even without a reference.

Add the following top-level object to the existing canary manifest for a
non-official transcript (illustrative values only; not a clearance or gold):

```json
"reference": {
  "source": "https://example.org/licensed-independent-word-annotations",
  "max_boundary_error_ms": 100,
  "words": [
    {"word": "Non", "start_ms": 100, "end_ms": 250},
    {"word": "aumenteremo", "start_ms": 250, "end_ms": 800},
    {"word": "7", "start_ms": 850, "end_ms": 1000},
    {"word": "tasse", "start_ms": 1000, "end_ms": 1400}
  ]
}
```

The baseline must have one token for every original transcript word in order,
integer milliseconds, non-overlapping intervals within the WAV, and a
per-run tolerance of 0–250 ms. After the already protected local WhisperX
child completes, the canary compares every word's *start and end* with the
reference. Missing or changed words return
`WHISPERX_REFERENCE_WORD_MISMATCH`; a boundary exceeding the tolerance
returns `WHISPERX_REFERENCE_BOUNDARY_MISMATCH`. Both are private HOLD with
exit 2; no candidate/word string is exposed. A matching run reports
`reference_sha256`, `max_boundary_error_ms` and
`boundary_tolerance_ms`, while remaining `UNVERIFIED` and
`publication_blocked=true`. The existing source-use guard remains mandatory
at every inference boundary.

For the real canary an agent must independently establish source provenance,
current `ASR_MEDIA` rights, media and annotation digests, a licensed Italian
CTC word model and its complete native dependencies. Deterministic synthetic
tests verify this comparison only; they are **not** evidence of real acoustic
accuracy, RSS or inference speed.

## Current-rights seam and operator canary (2026-10-23)

`whisperx_alignment_rights.py` is the only supported way to build the
`authorization_guard` the adapter demands. A job flag, a syntactically valid
receipt ID, a lambda returning `None` or an inert callback are not rights: the
guard re-reads the current DP-305 record for the exact URL/Content subject and
requires the private `ASR_MEDIA` use. Unknown record, receipt or policy
mismatch, revoked status, expired review, non-current version and a missing
permitted use all fail closed with a stable `SOURCE_USE_*` or
`WHISPERX_ALIGNMENT_*` code before any private model or audio read.

- Production caller: `read_alignment_rights_scope(store=<PsqlRuntime>, …)`
  followed by `registry_alignment_authorization_guard(scope, store=…)`. The
  registry is re-read before the first private read, after WAV staging and
  after the child exits; a revocation anywhere in between returns no candidate.
- Private canary: `tools/dp165_alignment_canary.py --manifest …` performs one
  rights-bound alignment from a pinned operator attestation and prints a
  machine receipt only (`manifest_sha256`, `audio_sha256`,
  `transcript_sha256`, `rights_guard_reads`, status or HOLD code, candidate
  ID), never transcript text, audio paths or manifest content. Exit 0 = receipt
  produced, 2 = adapter HOLD, 3 = invalid manifest or rights scope.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 tools/dp165_alignment_canary.py \
  --manifest /private/dp165/manifest.json --receipt /private/dp165/receipt.json
```

`current` is always the real clock, so a manifest cannot pin a past instant
and revive an expired source review.

The command refuses on a non-Linux work host
(`WHISPERX_HOST_OR_OPT_IN_REQUIRED`) and without the explicit opt-in; the
alignment service host is the MiniPC. A pinned attestation is a canary
convenience, never production authority: production runs resolve the live
registry through `PsqlRuntime`. Still HOLD for Italian CTC weights and native
notice clearance, one authorized private WAV and the measured CPU/RSS/precision
run; nothing here promotes a timestamp or publishes a candidate.

## DP-359 / #462 — 26 October 2026 CTC native-rights outcome

The [pinned Italian CTC candidates, inherited weight-rights audit, exact native
notice gaps, MiniPC resource measurements and tested private HOLD](whisperx-ctc-licensing-2026-10-26.md)
are documented separately. The recorded decision is **NO_GO for local model
provisioning** until an actually permissive checkpoint, a full LICENSE and file
hash inventory, and the installed wheel/native/asset rights have been verified.
The existing private fail-closed adapter and public consumer are unchanged.
