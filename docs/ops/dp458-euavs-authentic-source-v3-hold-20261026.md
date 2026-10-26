# DP-413A / #458 — genuine EU audiovisual source, rights and v3 HOLD (2026-10-26)

**Status: PRIVATE HOLD.** This packet records an authentic, actually persisted MiniPC source and a real DP-413B policy/runner acceptance. It does **not** authorize public reproduction, imply fully verified GDPR compliance, pretend to independently verify acoustic words, or claim genuine Studio playback of a held segment. Related: #413, #97 (inventory only), #425 (DP-419 software already merged), #461 (separate Italian WAV gold), #464 (v3 runner).

## Exact authentic source and provenance

Official EU AVS recording: https://audiovisual.ec.europa.eu/en/media/video/I-293056 — **I-293056**, 16 September 2026, *EP Plenary Session State of the European Union debate 2026 — #SOTEU2026 Statement by Ursula von der LEYEN, EC President*. Producer **European Parliament**, individual rights credit **© European Union, 2026**, Strasbourg EP/Louise-Weiss; public office-holder role corroborated by https://ec.europa.eu/commission/presscorner/detail/ov/SPEECH_26_1868. These prove attribution/role, not every spoken word.

Official original download:
https://vod.prd.commavservices.eu/16/293056/01a0a916-e603-7622-aa35-8ac303177665/qaa.mp4?filename=I-293056_INT-AUDIO.aac

It is **MP4 with a single mono 48 kHz AAC audio stream**, despite the .aac filename and server content-type of "file". Pinned bytes **2,985,951**, duration **332.101333 s**, SHA-256 **225b145412687af1ac0fa7a5f03a010541fcf8cd81be3494418f59614ec57593**. The narrowly scoped private fetch adapter checks exact URL, status, size and digest and normalizes MIME to audio/mp4 without transcoding.

Official VTT:
https://s3.eu-west-1.amazonaws.com/avs-media-prd-jobs/I-293056/I293056-INT-REV1.vtt?filename=I-293056_INT-SUBTITLE.vtt
VTT SHA-256 **2de8e201c68ede5735330bfa9f48b87da0ebdddca679f71ffd6be3d0aa58c2de**. Exact cue **12**, time **00:01:14.669–00:01:18.940** (74669–78940 ms):

> A stronger, more independent Europe is now emerging.

Quoted UTF-8 SHA-256 **5678722cae3853f90810d5825d8b5a1f1b17592245a3650b179ff67afd840a96**. Source-page HTML snapshot SHA **beab7064afc49ee2bf5db09fd4fddcdd1109d753f34aa3f17a284a44f5f52eeb**; general terms snapshot SHA **1cc14d28ad34c001ac8c1274e903fbffd36cfaebab3551e641b70580fbe32f01**. Private snapshots: Mac Studio /tmp/dp458-source-20261026/ (0700). **Publisher caption is not independent audible-word alignment.** An offline independent Whisper tiny.en run (cached OpenAI model via Transformers, no external ASR provider or additional downloaded weights; [model card](https://huggingface.co/openai/whisper-tiny.en), Apache-2.0) around 65–90 seconds recognized "And the stronger, more independent Europe is now emerging" at approximately 75–80 seconds. This independently supports the **minute-scale location**, but not exact literal agreement with the publisher's "A stronger...", nor a calibrated word-level confidence. Thus the canonical segment stays TRANSCRIPT_UNCERTAIN and publication_blocked=true.

## Dated, use-specific rights/privacy/retention

* Item source-specific conditions: https://audiovisual.ec.europa.eu/en/media/video/I-293056 (European Parliament producer; European Union copyright 2026). General official policy: https://audiovisual.ec.europa.eu/en/conditions-of-use ; EC Decision 2011/833/EU: https://eur-lex.europa.eu/eli/dec/2011/833/oj ; license https://creativecommons.org/licenses/by/4.0/legalcode .
* For EU-owned audiovisual copyright, unless a specific item notice overrides, the general site policy specifies **CC BY 4.0 International**, with credit, modification disclosure and no distortion. The license is not geographically limited to the US; that copyright position supports a bounded private research copy in Italy/EU. Do not generalize the separate JFK/Rice US public-domain status.
* Explicit **exclusions** in the Commission AVS conditions: moral rights, personality/image/privacy/publicity, embedded third-party copyrighted work, logos/trademarks and possibly music. Item-specific copyright notice and public provenance do **not** settle all these rights. Therefore public audio or short quote **not cleared** without the necessary contextual, faithful attribution, third-party, privacy and legal basis checks.
* Privacy sources: https://audiovisual.ec.europa.eu/en/data-protection and GDPR https://eur-lex.europa.eu/eli/reg/2016/679/oj (Arts 5, 6, 17, 21 where applicable). The AVS privacy page explains **the Commission's own** processing under Regulation 2018/1725; it is **not** this application's own Article 6 lawful basis or its retention schedule. The identifiable public-office-holder is speaking in an official public capacity, but project-specific necessity, Article 6 ground/balancing and data-subject rights must be established separately before public use. No profiling or biometric recognition was conducted.
* Operational private source use is scoped to pinned record and private processing. Registered **CURRENT** rights policy **dp458-eu-avs-private-media-20261026-v1**, grant **private-rights:ec01d8e73ecb6a844b509486bb9c9a9146f5d6c76fe517d37509babe5c0840e1**, attribution codes **CC_BY_4_ATTRIBUTION**, **NO_PUBLIC_MEDIA**, **PUBLIC_QUOTE_REVIEW_REQUIRED**. Seven current private uses: **DISCOVER_METADATA, FETCH, STORE_BODY, ASR_MEDIA, PLAYBACK, PARSE_TEXT, RESEARCH_CAPTURE_PRIVATE**. The last requires the dedicated private capture rights guard rather than generic SourceFamilyUseGuard. EXCERPT_PUBLIC returns **SOURCE_USE_PUBLIC_POLICY_REQUIRED**.
* Granted private right expires **2026-11-02T19:33:59.925100+00:00**. Fresh rights/revocation checks must occur on each access. A seven-day rights expiry is **not** automatic blob deletion. The restricted blob store is /home/udodo/.local/share/dichiarazioni-pubbliche/dp458/capture-bodies/ ; private runner journal is sibling dp413b-v3-actual.sqlite3. Operational retention/purge at expiry, revocation, loss of purpose or data-subject request remains a separately enforceable task; never silently renew, use expired rights, or retain personal bytes indefinitely without a separate lawful schedule. Logs/docs must omit DSN/tokens/cookies.

## Actual PostgreSQL IDs / immutable readback

source: source:dp458:euavs
person: person:dp458:ursula-von-der-leyen
content: content:dp458:euavs:I-293056
capture: capture:54d2574575b6b1d7fa21dc2adae5f4b7155b5d38274b5de43c2c7350b5c25955
variant: variant:dp458:I-293056:int-vtt
transcript: transcript:dp458:I-293056:cue12
canonical: canonical:dp458:I-293056:cue12
passage: passage:dp458:I-293056:cue12
Statement Candidate: statement:dp458:I-293056:cue12

Captured via actual CapturePipelineStore, CaptureBodyStore, capture_content, private capture rights/relevance and exact SHA-pinned HTTPS; **not** direct content_capture INSERT. The private body was read back and hashed against the same original. Candidate **HELD**, canonical **TRANSCRIPT_UNCERTAIN** and publication blocked, real binding rows **0**. The authentic cue #12 was originally misparsed as 00:00:14.669–00:00:18.940 instead of 00:01:14.669–00:01:18.940. Independent offline ASR identified the mismatch (the earlier interval audibly contained the Dickens/French Revolution passage); on 26 October the existing private HELD, unbound canonical and transcript rows were corrected with guarded old-time compare-and-set, and a **timing_correction_v2** metadata audit storing *both* old/new ms and unchanged VTT SHA. The candidate and passage extraction version is now **dp458-original-source-v2**. No previously approved/bound/published identity was rewritten, and no new Capture or rights grant was created. PostgreSQL uniqueness on (content_id,segment_index) rules out a parallel second canonical row for cue 12. This is a specifically documented v2 correction, not silent provenance substitution.

Readback (runs with installed project modules and staged source script, no credentials printed):
~~~bash
ssh minipc 'systemd-run --user --wait --pipe --collect --property=EnvironmentFile=/home/udodo/.config/dichiarazioni-pubbliche/runtime.env --property=WorkingDirectory=/home/udodo/src/DichiarazioniPubbliche.it /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc /usr/bin/python3 /tmp/dp458_real_source_packet.py'
~~~
**26 October actual output/exit:** 0, status VERIFIED_PRIVATE_HOLD, correct source/VTT/quote SHA, binding_count=0, private-use rights current, public_quote_rights=HOLD, independent_alignment=HOLD, publication_authorized=false.

Real existing DP-413B v3 policy and persistent runner, same original persisted candidate:
~~~bash
ssh minipc 'systemd-run --user --wait --pipe --collect --property=EnvironmentFile=/home/udodo/.config/dichiarazioni-pubbliche/runtime.env --property=WorkingDirectory=/home/udodo/src/DichiarazioniPubbliche.it /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc /usr/bin/python3 /tmp/dp458_v3_acceptance.py'
~~~
**26 October actual output/exit:** 0, **policy HOLD** reasons **WORDING, RIGHTS_PRIVACY, INDEPENDENT_REVIEW**; policy version autonomous-publication-413-v1, current v2 fingerprint **d953c858f5769e997091374c90e46f7f3dacaa316392ba83f287940743a73eeb**. Persistent runner **HOLD** reason **CHALLENGE_STATUS_UNKNOWN**, same fingerprint, private journal **2 version-linked events** (v1 incorrect timestamp HOLD followed by corrected v2 HOLD), live public v2 DRAFT/zero dossiers; public_v2_readbacks=2 on correction rerun. There is **no trusted challenge adapter, no verified second independently identified approved model**, and no v3 public write/withdraw/CDN fence. The only current approved route is antigravity/gemini-3.8-flash-tiered; separate agent labels with the **same model** cannot simulate independence. No real review approvals or publication were claimed. After merge/install, replay from versioned tools instead of perpetual /tmp copies.

### Independent code-review P2 remediation (same private evidence, 2026-10-26)

The first independent review on PR #527 head 214d702 identified two reproducible P2 gaps: a two-process/non-atomic cue correction, and insufficient verification of all linked text/speaker rows. The correction now performs the two timestamp CAS updates inside **one PostgreSQL DO statement**, with a checked current HELD candidate and absent binding guard and exception rollback on either mismatch. It will not rewrite an APPROVED/bound canonical record. The full readback now checks the **actual original VTT bytes** stored privately at MiniPC `/home/udodo/.local/share/dichiarazioni-pubbliche/dp458/I-293056_INT-SUBTITLE.vtt` (mode 0600, SHA-256 `2de8e201c68ede5735330bfa9f48b87da0ebdddca679f71ffd6be3d0aa58c2de`), exact cue 12 and its timestamp/quote, as well as caption variant/raw transcript, canonical exact text, speaker identity and passage. The private snapshot is acquired by hash-pinned official fetch when absent; it is never part of public repo content or public API. Regression tests include wrong-speaker/wrong-transcript and altered VTT checks, plus one-transaction SQL evidence.

## Byte→decoded PCM interval proof, caveats, negatives

Actual stored private Capture bytes decoded at the corrected **74669–78940 ms** interval on MiniPC FFmpeg **8.0.1-3ubuntu2**, proof algorithm **capture-decoded-pcm-s16le-16000-v1**: new v2 interval PCM SHA **d0cd7d7558fbb63679b30fccb03f095ad99d23835e5b24fa3b26f5215cfa5cf2**; evidence SHA **aa9ae4599e5f1a7d90c92a5ddd26d39992cb5017de79709522aec188cb0cb635**. Current proof JSON is private **original-media-interval-proof-v2.json** (0600). The earlier **14.669–18.940** proof (PCM SHA 85cc65..., evidence SHA abda493...) is retained as historical diagnostic evidence ONLY and is **not** proof of the selected quote. Tampered digest returned **MEDIA_PROOF_CAPTURE_MISMATCH**; hypothetical in-memory revoked rights (without DB mutation) returned **SOURCE_USE_REVOKED**. Proof JSON stored private, mode 0600.

At the previous **incorrect 14-second interval**, the same original Mac Studio FFmpeg **9.0.2** decoded to a different PCM SHA **607aa37cd59ae8d8c7b6d69a43254b1e686794f22c7735b63e1d93d61a772eb1** / evidence SHA **9b3b52e72a19afb24951b08e22537ba480ff05ac113d878a3f1aa34c0e8960e5** from MiniPC FFmpeg 8's same **incorrect** interval. Cross-FFmpeg resampling is decoder-build-specific; the new correct v2 interval has not been compared across both machines. Neither byte derivation nor a caller-supplied binding digest verifies the spoken text/acoustic alignment or speaker identity.

## Real browser acceptance gap and correct fail-closed decision

The PostgreSQL record_media_capture_segment_binding function requires the canonical segment to be RESOLVED and not publication-blocked. Our real candidate is deliberately TRANSCRIPT_UNCERTAIN, thus **no binding was inserted (count 0)** and actual authenticated Studio browser keyboard/native currentTime seek on **this same persisted source** is **not proven**. UI fixtures using real original bytes are merely browser/media capability tests, not authorization. Do not flip status, forge binding, metadata flags, second model, privacy clearance or review receipts to make seek succeed. HOLD/revocation prevents private retrieval; public publication remains forbidden. Owner need not grant per-source human permission; the missing independent acoustic evidence / actual authenticated browser proof must be resolved autonomously or remain a stated unsatisfied criterion.


### Live authenticated Studio loopback / browser capability — actual negative checks

The versioned read-only script tools/dp458_studio_hold_probe.py was run against the **actual production MiniPC PostgreSQL**, immutable Capture and private body root, starting a one-off authenticated StudioLoopbackServer bound to 127.0.0.1 with an ephemeral bearer value that was **never printed**:

~~~bash
ssh minipc 'systemd-run --user --wait --pipe --collect --property=EnvironmentFile=/home/udodo/.config/dichiarazioni-pubbliche/runtime.env --property=WorkingDirectory=/home/udodo/src/DichiarazioniPubbliche.it /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc:/tmp /usr/bin/python3 /tmp/dp458_studio_hold_probe.py'
~~~

Exit **0** and JSON: status **REAL_STUDIO_LOOPBACK_MEDIA_HOLD**, GET login HTTP **200**, unauthenticated playback **401**, authenticated playback **503** (no binding row; server deliberately returns generic backend-unavailable message), no binary media returned, Cache-Control **no-store, private**, no original URL/SHA/token in error response, publication_authorized=false. The non-200 response proves *fail-closed*, not a successful seek. The 503 for an absent binding is a diagnostic/status distinction, **not** evidence of outage.

The existing Chrome/Node accessibility harness was executed against a **fixture HTTP server returning the real unmodified I-293056 AAC/MP4 bytes** and the corrected-script change was not yet propagated to that fixture's first run (the first test used 14669–18940 ms). That first real-blob Chrome run exited **1** with "original media bytes must prove native currentTime seek"; a diagnostic run gave **Decoder audio non disponibile: nessun seek verificato**, with media src removed, hidden, paused, currentTime=0. This is a genuine **negative** decoder/capability result and **not** an authenticated database end-to-end test. The Chrome test must be rerun with 74669–78940 ms after decoder support is demonstrated; even if that succeeds, independent acoustic verification and true version-bound binding still remain necessary. Do not equate an isolated browser fixture with private Studio authority.


### Real persisted MiniPC Chrome browser loopback — authenticated HOLD (2026-10-26)

A **separate live browser acceptance**, unlike the mock HTTP/Chrome fixture, was run on the actual MiniPC with the authentic PostgreSQL candidate, current rights, the installed StudioLoopbackServer reading original private Capture storage, and the system's genuine /usr/bin/google-chrome via Chrome DevTools Protocol. The standalone executable is tools/dp458_studio_browser_hold.mjs; one temporary browser profile and one private token were destroyed afterwards. The browser was bound to the actual 127.0.0.1:18777 listener, with no reverse proxy or public exposure. An unbound real candidate is deliberately **not** made playable.

Reproduction after the script is available on the MiniPC checkout, with a new private 0600 ephemeral token generated on that same host and never printed:

~~~bash
# MiniPC: create the private token using mode 0600 in the existing 0700 root.
python3 - <<'PY'
import os, secrets
from pathlib import Path
p=Path.home()/".local/share/dichiarazioni-pubbliche/dp458/studio-browser-token"
fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
try: os.write(fd,secrets.token_hex(32).encode())
finally: os.close(fd)
PY
systemd-run --user --unit=dp458-browser-hold --collect   --property=EnvironmentFile=/home/udodo/.config/dichiarazioni-pubbliche/runtime.env   --property=WorkingDirectory=/home/udodo/src/DichiarazioniPubbliche.it   /usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc   /usr/bin/python3 -m dichiarazioni_pubbliche.studio_local_api     --port 18777     --token-file /home/udodo/.local/share/dichiarazioni-pubbliche/dp458/studio-browser-token     --capture-body-root /home/udodo/.local/share/dichiarazioni-pubbliche/dp458/capture-bodies
/home/udodo/.nvm/versions/node/v24.18.0/bin/node tools/dp458_studio_browser_hold.mjs
systemctl --user stop dp458-browser-hold.service
rm /home/udodo/.local/share/dichiarazioni-pubbliche/dp458/studio-browser-token
~~~

Observed **exit 0** with the tested script staged in /tmp: status REAL_PERSISTED_STUDIO_BROWSER_FAIL_CLOSED, keyboard activation **true**, authenticated /v1/media/binding **HTTP 503** and /v1/media/playback **HTTP 503** (the missing persisted binding produces generic backend-unavailable API responses), original media **never returned to the browser**, no media src/blob, audio hidden/paused, native currentTime **0**, no autoplay, no page text or private media URL leak, browser token input cleared, native_seek **NOT_AUTHORIZED**, publication_authorized **false**. The installed browser page reports preload=metadata before activation but has **no media src and makes no media request before user action**; do not misreport preload=none for this installed build. The 503 is a generic service error code rather than a precise rights reason: the independent DB readback binding_count=0 and the real v3 HOLD provide the source-specific explanation. After the test the actual listener was stopped (port 18777 no listener), private ephemeral token deleted, and disposable Chrome profiles cleaned (0 remaining).

This fulfills a **real browser negative HOLD and leakage/autoplay/keyboard proof** on the persisted record, but **does not fulfill positive native currentTime seek acceptance**. A separate independently aligned, genuinely version-bound current Capture→Segment proof and a supported browser decoder are still necessary. No source-use/publication clearance is inferred from the browser having loaded the Studio page.
