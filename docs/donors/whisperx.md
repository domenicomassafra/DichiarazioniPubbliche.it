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
   copy under the existing local-inference mutex, no upload.
2. **Exact Italian Wav2Vec2 CTC Hugging Face snapshot**:
   actual model ID + pinned 40-hex revision, license URL at revision,
   license review and full local-file SHA256 inventory including
   `config.json`, weights `.safetensors` and LICENSE. WhisperX's
   own BSD license says nothing about Wav2Vec2/Torchaudio weight
   rights. In v3.8.6 upstream's default Italian
   `VOXPOPULI_ASR_BASE_10K_IT` resolves through torchaudio
   downloads; this adapter **never selects that default**. It forces
   a local HF model directory + `model_cache_only=True`.
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
Output must contain every expected word in order, with monotonic
finite timestamps, within the WAV and CTC score >=0.70.
Missing/ambiguous words, mismatched numerals/negations, overlap,
untrusted native/model rights or missing assets keep the result on
human review/HOLD. No true precision/recall or resource numbers
are claimed from mocked parser outputs.

**Dependency state:** #164 faster-whisper ASR adapter merged but
the licensed weights and real-audio canary are HOLD (#36);
#166 pyannote diarization and DP-208 #37 remain independent.
#61 DP-317 exact-quote rights gate is OPEN. This seam does not
change any of their requirements.
