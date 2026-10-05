# DP-434 — First-class public Content resource contract

Status: READY

Milestone: M4 — public product/API
Depends on: DP-105, DP-210, DP-401, DP-403

## Problem

DP-407 exposes a source-first Content page by grouping published dossiers on the stable
`source.content_id`. That is safe for content with at least one published finding, but it
is not a first-class Content resource: if the last public finding disappears, the Content
route disappears too. The current projection also has no independently reviewed public
media/embed metadata, duration, content kind, or explicit “public Content, zero published
moments” state.

The public API currently calls `/records/{slug}` a Content-like resource, but it is derived
from one dossier and therefore has the same limitation. DP-407 must not fabricate a player,
infer a content type from a URL, or expose an operational capture/transcript simply to fill
that gap.

## Outcome

Ratify the smallest additive first-class public Content contract so the public site/API can
represent a source item independently of whether it currently has published findings.
Content publication remains fail-closed and must not expose private captures, raw media,
transcript bodies, provider receipts, cookies, archive paths, or operator state.

## Scope

- stable `content_id` and deterministic public slug;
- canonical source URL and approved display title;
- optional source publication date;
- bounded content kind (`VIDEO`, `AUDIO`, `WRITTEN`, `OTHER`) only when reviewed/known;
- optional duration for timed media, with bounded integer semantics;
- optional public media/embed URL only when separately policy-authorized and safe to expose;
- explicit publication/review provenance for the Content resource itself;
- zero-or-more public finding IDs/moments, all referencing projectable findings;
- optional public source methodology fields already ratified elsewhere;
- additive public-v2 compatibility decision and projection fingerprint coverage;
- `/api/v1/records`/record detail alignment so a zero-moment Content is representable;
- static web route generation from the first-class collection rather than only dossier
  grouping.

## Publication gate

A database `content_item` is **not** public merely because it was discovered or captured.
Projection requires an explicit reviewed publication assertion for the Content resource.
The contract must distinguish:

1. public source metadata that may be shown even with zero findings;
2. public finding memberships that already passed the finding gate; and
3. optional public media/embed metadata that needs its own safety/rights decision.

If any required review/provenance is missing, omit the Content. If a finding membership is
invalid or private, omit that membership without leaking that it exists.

## Acceptance criteria

- [ ] `AC-434.1`: an approved Content with zero published findings appears in the public
  projection/API and can produce a deliberate “no published checks” page.
- [ ] `AC-434.2`: a Content with published findings references only projectable finding IDs;
  a private/held finding is indistinguishable from a nonexistent membership.
- [ ] `AC-434.3`: media kind/duration/embed are absent unless explicitly supported by
  reviewed public metadata; the UI never guesses them from URL/extension/platform.
- [ ] `AC-434.4`: raw transcript/canonical transcript/capture bytes/provider receipts/private
  archive paths and evidence bodies cannot enter the public Content structure.
- [ ] `AC-434.5`: pre-DP-434 `dichiarazioni-pubbliche-public-v2` bundles without `contents`
  remain valid; new builders include `contents` in the dataset fingerprint.
- [ ] `AC-434.6`: API/OpenAPI distinguish first-class Content resources from findings and
  continue to work with providers and the operational DB offline.
- [ ] `AC-434.7`: fixtures cover timed media, written source, zero moments, multiple findings,
  withheld media URL, invalid/private membership, correction/retraction membership changes,
  stale/tampered projection, and two Content items with similar titles.
- [ ] `AC-434.8`: full tests, bundle verification, web static build, MiniPC migration/projection
  canary, same-origin API checks, and `git diff --check` pass.

## Non-goals

- publishing captures or transcripts;
- media downloading/hosting;
- inferring a YouTube/TikTok/player URL from a canonical source URL;
- automatic Content approval;
- search/index UI (DP-409/DP-429);
- correction propagation across every surface (DP-431).

## Completion receipt

Pending implementation.
