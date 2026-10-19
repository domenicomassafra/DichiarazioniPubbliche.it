# youtube-transcript-api — conditional caption donor (#163)

- **Repository:** https://github.com/jdepoix/youtube-transcript-api
- **Release:** `v1.2.4` (2026-01-29), Git ref commit `505f412a5a691cc1bac6430dd35144222c667598`.
- **License:** MIT; copyright Jonas Depoix and contributors. The upstream license and
  notices remain in the optional installed package. License reference:
  https://github.com/jdepoix/youtube-transcript-api/blob/v1.2.4/LICENSE
- **Import:** optional `[youtube-captions]` extra pinned to `1.2.4`; disabled by
  default. Operators explicitly enable `DP_YOUTUBE_TRANSCRIPT_API=1` after their
  normal source-use clearance. No cookies, authenticated API or proxies configured;
  a session disables inherited proxies and bounds connect/read timeouts to 3s/8s.
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
  429, challenge) raise `PlatformAccessRestricted` without trying another client.
  If the fallback fails, acquisition fails closed. Automatic publication, source
  rights, revalidation, retention and review gates remain unchanged.
- **Known risks:** API relies on an undocumented YouTube interface. Upstream
  issues https://github.com/jdepoix/youtube-transcript-api/issues/612 and
  https://github.com/jdepoix/youtube-transcript-api/issues/593 warrant a reversible
  flag and offline fixtures, with no assumption of live availability.
- **Issue overlap:** #169 independently requests the same donor as a *second*
  acquisition path. This #163 integration selects it as first caption attempt;
  #169 must be reviewed against its own AC and must remain open until accepted.
