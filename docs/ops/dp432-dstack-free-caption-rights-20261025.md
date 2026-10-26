# DP-432 — DStack free-caption consumer: evidence, use and privacy

Scope: **public YouTube URLs with current source-specific FETCH and STORE_BODY
clearance**, using only caption JSON from an already captioned video. The
existing private transcript variant, timestamped segments, rights-bound SQL
writer, receipt ledger, relevance check and nonpublication policy remain the
authority. A caption is a candidate, not an approved attribution or licence.

## Canonical candidate and interface

- Selection comes from the deployed
  `~/.dstack/catalog/transcription-services.json`, maintained in
  [DStack #166](https://github.com/domenicomassafra/dstack/issues/166) /
  [DStack #182](https://github.com/domenicomassafra/dstack/issues/182).
  The catalog's own [source audit](https://github.com/domenicomassafra/dodo-services/issues/275#issuecomment-6386339637)
  observed YTTranscript.dev's anonymous JSON with six source-language
  millisecond cues on the public sample. The subsequent
  [consolidated audit](https://github.com/domenicomassafra/dodo-services/issues/280)
  records unsuccessful retests. Therefore this adapter does not treat a
  catalog identity or promotional claim as sufficient evidence.
- [Provider's own API documentation](https://yttranscript.dev/docs) defines
  `GET /api/transcript`, the `source=captions` selector and JSON format,
  1 credit per successful fetch, 202 for asynchronous ASR, and
  401/402/404/429 failure paths. We send no credential, no account, no
  upload, no translated request and **never** request `source=auto`,
  `source=asr`, summary, batch or job polling. A bounded GET may succeed in
  guest mode as the dated audit and guarded readback established; its
  availability is not an API SLA.
- [Provider support](https://yttranscript.dev/support) claims 25 guest
  transcripts and timed caption JSON, subject to credits; 429 is a
  backoff signal. The consumer makes at most one attempt per acquisition
  call, never evades a quota/challenge, and falls back to its native
  caption path. A failed or unverified response cannot become evidence.

## Rights, copyright and privacy boundary

- [YouTube's official transcript help](https://support.google.com/youtube/answer/15930243?hl=en)
  limits native transcript availability to captioned videos. The
  [YouTube copyright guide](https://support.google.com/youtube/answer/2797466?hl=en)
  states that public visibility does not grant reproduction or distribution
  rights; author/rights-holder licence or an applicable legal exception must
  be evaluated source by source. The existing DP source-use guard requires
  current clearance and prevents stored raw captions crossing a revoked
  rights boundary. No unreviewed transcript is published.
- The [provider privacy policy](https://yttranscript.dev/privacy)
  (updated September 2026) says guest requests expose IP to metre free
  credits and produced transcripts are stored on EU servers; it claims no
  model training from submitted content. We transfer only an already-public
  YouTube video ID/URL, and only after source-rights and relevance gates.
  Do not send private, personal or unpublished media or credentials.
  Provider retention is external to DP and cannot be controlled by our
  local deletion; source-specific use decisions must account for that.
- Existing local `faster-whisper` requires its separate media-use receipt
  and bounded WAV authorization. Generic URL fallback does not manufacture
  this right or submit a paid Groq request.

## Observed results (Mac Studio resource guard, 25 October 2026)

- Public sample: `https://www.youtube.com/watch?v=jNQXAC9IVRw`.
  Catalog selection: `YTTranscript.dev`, source language `en`.
  Anonymous `source=captions&format=json` actual GET returned a valid
  response with **6 timestamped cue segments**. This establishes transport
  and format on one URL at one time; no claim of complete speech accuracy,
  general uptime or provider contractual permission follows.
- Mocked dispatcher test also proves free-before-native priority, provenance
  on the persisted candidate and zero-dollar receipt. Timeout, quota,
  mismatched video/language and invalid timecodes fall through without
  promoting the remote body.
- DStack #182 remains required to publish and install the canonical
  inventory; a deployed consumer without that file retains its native
  path. Consumer installation and runtime readback belong to root
  orchestration after independent review.
