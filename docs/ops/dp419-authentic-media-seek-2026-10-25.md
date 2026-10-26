# DP-419 — original public-domain audio Capture, private segment seek (25 Oct 2026)

## Source provenance and rights

- Original: [JFK Rice University speech Ogg on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Jfk_rice_university_we_choose_to_go_to_the_moon.ogg), uploaded 2 Jan 2010, identifies the **John F. Kennedy Presidential Library & Museum** as its source and Kennedy as author.
- Wikimedia's file page identifies this specific *Ogg* recording as US Government work in the US public domain under 17 USC §105, and marks it with the [Public Domain Mark 1.0](https://creativecommons.org/publicdomain/mark/1.0/).
- [JFK Presidential Library / US National Archives](https://jfk.blogs.archives.gov/2017/09/12/we-choose-to-go-to-the-moon-the-55th-anniversary-of-the-rice-university-speech/) documents the speech and the quotation around 8:30; [NASA](https://www.nasa.gov/image-article/president-john-f-kennedy-rice-university/) confirms the event and quote. These validate identity and historical context; exact word-to-millisecond ASR alignment is **not independently certified by them**.
- [Rice University Archives](https://archives.library.rice.edu/repositories/2/resources/666) separately restricts publication of its own collection and warns that the KHOU broadcast is controlled by KHOU. The pilot **does not** use a Rice/KHOU capture.
- Private, agent-documented source-use clearance for one immutable downloaded Ogg version is exercised only in the disposable PostgreSQL fixture. Production source-rights records and license handling remain independent and can revoke playback. This does not grant public publication.

## Measured original bytes (downloaded 25 Oct 2026, Mac Studio)

| Field | Verified value |
| --- | --- |
| Original bytes URL | `https://upload.wikimedia.org/wikipedia/commons/5/50/Jfk_rice_university_we_choose_to_go_to_the_moon.ogg` |
| SHA-256 | `7486fba805c20bde4d43750bd9c34aee86ab7acfd3854a1d0f3d64f62ae68b27` |
| File length | 17,193,282 bytes |
| Duration (ffprobe) | 1060.249977 seconds |
| Example canonical media interval | 522,000–534,000 ms |
| Decoded excerpt PCM SHA-256 (ffmpeg 16 kHz mono s16le) | `f074540597d87144fcd312cb8e11c15aa0ce6dbcac569f8a0becdd5fb68a98f0` |
| Exact derivation evidence SHA-256 | `d870dce3dfd22e055993e1a21b64aa5fd56c140b45e1d232268c5c857d9125b0` |

The derivation includes immutable Capture SHA, canonical Segment ID, start/end milliseconds, canonical-text SHA and decoded PCM SHA; it proves that audio bytes are decodable at that interval. For the 522–534 s interval, a private local pass of `openai/whisper-tiny.en` over the original 515–545 s audio transcribed the corresponding JFK "We choose to go to the moon ... and do the other things, not because they are easy" passage, with some misrecognized words. This corroborates approximate passage placement, but **does not certify word-level boundaries, transcription accuracy, or speaker identity**. The fixture's Candidate/Passage status remains a synthetic approval assertion. Do not reuse it as an editorially approved quotation or real published statement.

## Boundary and acceptance

The private localhost bearer endpoint `POST /v1/media/playback` re-reads the append-only Capture→Segment binding and its current hold/revocation state, current Capture and Content rights, exact body ref and original bytes SHA, canonical segment text SHA, and a current private source rights record requiring `FETCH`, `STORE_BODY`, `ASR_MEDIA` and `PLAYBACK`. It computes the decoded-audio derivation from the stored bytes afresh, then checks binding and source rights again before replying. Any missing/changed hash, revoked record, held segment, unapproved candidate, missing Capture body or failed audio probe blocks the request.

The endpoint sends the verified original audio bytes and interval headers to the bearer-authenticated operator. The private Studio page creates a session-only `blob:` URL, seeks to the persisted timestamp when browser metadata becomes available, stops at interval end, and revokes the Blob on sign-out, workspace switch, new request or playback error. No public route, source URL, transcript/body, credential, rights receipt or publication permission is exposed by the response. Operators must explicitly press the player; autoplay is disabled.

To replay on a disposable test database, download the *exact* original URL to a private local file and verify its SHA-256 before running:

```sh
LC_ALL=C PYTHONPATH=poc DP419_REAL_MEDIA_PATH=/absolute/private/path/jfk-original.ogg \
  python3 -m unittest tests.test_dp419_real_media_pg_acceptance -v
```

This fixture boots its own PostgreSQL, applies `schema.v1.sql` and migration `031`, inserts a private source-rights record with a 30-day test expiry, stores the exact Ogg bytes in a temporary CaptureBodyStore, and records a derived Capture→Segment evidence digest. It then verifies correct original-byte playback under the bearer, the persisted interval, and a denied read after Capture rights revocation. The companion `tests.test_dp419_media_playback_http` verifies HTTP 401/no token and malformed requests. All disposable rows and body files are removed when the test finishes.

**Operational boundary:** The MiniPC production `content_capture` relation has an *unrelated*, `text/plain` Capture; it is not this Ogg. The isolated MiniPC browser test (Chrome headless, real original Ogg loaded from a temporary loopback fixture) confirms keyboard initiation and actual media `currentTime` seek, without autoplay. The Mac Studio headless decoder cannot confirm `loadedmetadata`, so its native seek is **unverified** and the player fails closed. Neither browser fixture proves a production PostgreSQL Capture with a source-approved Candidate, exact transcript alignment or a persistent production rights grant. Keep the source-bound acceptance and issue open until a current independently verified production binding and complete operator proof are observed.
