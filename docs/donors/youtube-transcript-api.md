# youtube-transcript-api — conditional caption donor (#163)

- **Repository:** https://github.com/jdepoix/youtube-transcript-api
- **Release:** `v1.2.4` (2026-01-29), Git ref commit `505f412a5a691cc1bac6430dd35144222c667598`.
- **License:** MIT; copyright Jonas Depoix and contributors. The upstream license and
  notices remain in the optional installed package. License reference:
  https://github.com/jdepoix/youtube-transcript-api/blob/v1.2.4/LICENSE
- **Import:** optional `[youtube-captions]` extra pinned to `1.2.4`; disabled by
  default. Operators explicitly enable `DP_YOUTUBE_TRANSCRIPT_API=1` after their
  normal source-use clearance. No cookies, authenticated API or proxies configured;
  a session disables inherited proxies, limits requests to HTTPS `www.youtube.com`
  without redirects and bounds connect/read timeouts to 3s/8s, each response to
  2 MiB and elapsed acquisition of each response to roughly 20s (plus a read timeout).
- **Port:** external library calls `YouTubeTranscriptApi().list(id)` then the
  selected `find_manually_created_transcript` or `find_generated_transcript`, and
  `.fetch(preserve_formatting=False)`. No donor source files are copied.
- **Project adapter:** `platform_transcript.py` and `caption_adapter.py` validate
  video ID, source kind, language, finite/non-overlapping timestamps and private
  raw bytes. The existing yt-dlp metadata/probe remains authoritative for the
  permitted source and Italian subtitle selection. The raw JSON donor response is
  stored separately from yt-dlp JSON3. Both retain SHA-256 hashes and millisecond
  segments, with the method/version in capture receipts and variant metadata.
- **Fallback:** missing optional package, unavailable track, timeout, malformed
  timestamps or API breakage revert to existing JSON3 acquisition. Blocks (IP,
  429, challenge, HTTP access denial, redirects, age/playability/consent restriction) raise
  `PlatformAccessRestricted` without trying another client. In v1.2.4 the donor
  wraps HTTP 4xx/5xx as `YouTubeRequestFailed` without retaining the response;
  this error therefore fails closed even if the status was a transient 5xx.
  If the fallback fails, acquisition fails closed. Automatic publication, source
  rights, revalidation, retention and review gates remain unchanged.
- **Known risks:** API relies on an undocumented YouTube interface. Upstream
  issues https://github.com/jdepoix/youtube-transcript-api/issues/612 and
  https://github.com/jdepoix/youtube-transcript-api/issues/593 warrant a reversible
  flag and offline fixtures, with no assumption of live availability.
- **Issue overlap:** #169 independently requests the same donor as a *second*
  acquisition path. This #163 integration selects it as first caption attempt;
  #169 must be reviewed against its own AC and must remain open until accepted.

## #169 — independent secondary-order opt-in (2026-10-20)

- **Reuse:** the *same* upstream release `v1.2.4`, commit
  `505f412a5a691cc1bac6430dd35144222c667598`, MIT (Jonas Depoix and
  contributors), imported only through the existing `new_transcript_client()`;
  upstream https://github.com/jdepoix/youtube-transcript-api and MIT notice above.
  No duplicate donor/HTTP implementation and no copied upstream files.
- **Distinct configurable order:** `DP_YOUTUBE_TRANSCRIPT_API=1` retains #163's
  `youtube-transcript-api -> yt-dlp` first path. Set instead
  `DP_YOUTUBE_TRANSCRIPT_API_SECONDARY=1` for `yt-dlp JSON3 ->
  youtube-transcript-api`, with exactly one API attempt after a verified missing
  or empty JSON3 caption (or absent yt-dlp executable); both flags enabled fail
  at construction. Both unset keeps the original yt-dlp-only behavior.
- **Safety boundary:** API secondary is attempted only for an unavailable selected
  subtitle or a parseable but empty JSON3, never on unknown errors, malformed
  non-JSON server bodies, ambiguous server failures (even when a later diagnostic
  says "no subtitles"), 401/403/429/451,
  IP-block, consent, login, challenge, CAPTCHA, private, region or video denial.
  Access denials fail to `PlatformAccessRestricted` and remain `HELD` in the
  worker; ambiguous failures stop acquisition without a second request;
  donor rejects redirect/foreign caption hosts before an outbound request. Valid
  YouTube video URL is required *before* yt-dlp in secondary mode. No cookies,
  login, proxy, bypass, live fetch or extra aggressive retries introduced.
- **One capture:** selected manual/automatic language, `it-orig` normalization,
  segment timestamps, raw SHA-256, method/version/access_path, prior adapter
  and stable fallback reason (`YT_DLP_CLIENT_MISSING` versus
  `YT_DLP_CAPTION_UNAVAILABLE`) flow through the existing variant, private bytes
  and `CAPTION_CAPTURE` receipts. Zero provider fee and **zero YouTube Data API
  v3 units** remain in the existing canonical receipt writer. Availability
  depends on upstream; all new acceptance fixtures are offline.

## #169 — acquisition rights security fix (20/10/2026)

The actual `ProcessingWorker` caption probe/capture seam now constructs a
`SourceFamilyUseGuard` from `PrivateRightsRegistryStore` (same configured DB).
The required exact rights subject is `source_family=YOUTUBE`, `locator_kind=URL`,
the chosen YouTube video URL and the source `content_id`. A current private
`CLEARED` receipt must explicitly permit **both `FETCH` and `STORE_BODY`**;
missing, expired, revoked, superseded, wrong-content/URL, or unavailable records
block before any caption network request. The worker re-reads both uses after
fetch and before storing raw bytes, recording source-rights fingerprints.
Platform access refusal during probe produces `ACCESS_RESTRICTED` and stops;
it cannot dispatch ASR as an alternate way around an IP/429/consent block.
Existing tests use only explicit synthetic rights fixtures. Neither CI nor the
source-only merge supplies a legal rights record or authorizes live YouTube fetch.
