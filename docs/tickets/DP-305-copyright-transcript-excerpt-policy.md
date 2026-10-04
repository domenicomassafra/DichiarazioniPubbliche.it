# DP-305 — Copyright, transcript, and excerpt publication policy

Status: IN_PROGRESS

Milestone: M3

Depends on: M0 baseline; coordinate with DP-303, DP-304, and DP-503

Launch state: BLOCKED until source-rights decisions and DP-306/DP-307 qualified review
are accepted

This is a product, copyright-safety, and engineering specification, not legal
advice. It does not select a legal exception, quotation right, license, or platform
permission.

## Problem
  The current architecture keeps raw and canonical transcripts internal, records a
`rights_status` for content/evidence, and excludes raw transcript/evidence bodies
from the public projection. Those defaults are necessary but incomplete: source
acquisition, storage, quotation, excerpting, attribution, machine-generated
transcript use, and public republication are different decisions. A technically
accessible source is not automatically a source whose text, audio, video, or
transcript may be republished.

## Outcome
  Specify a rights-aware publication policy in which unknown or unresolved rights
status denies public excerpts; full transcripts and media remain private by
default; any public excerpt is minimal, attributable, time-bounded, exact, and
revalidated at projection time; and a rights complaint or takedown follows the
append-only workflow in DP-303.

## Scope
- Define the relationship between acquisition rights, storage rights, transcript
  rights, quotation/excerpt rights, and public republication rights.
- Define the default public treatment of raw/canonical transcripts, media, source
  segments, and evidence bodies.
- Define a versioned rights registry, excerpt policy, attribution, and projection
  contract.
- Define complaint, correction, hold, and re-review behavior.
- Define tests, data retention requirements, and qualified questions for DP-306.

## Non-goals
- Giving legal advice or declaring that a quotation is fair, licensed, or permitted
  under any law or platform term.
- Publishing a full transcript, podcast, video, audio, or source capture by default.
- Circumventing access controls, paywalls, robots/terms, or platform restrictions.
- Inventing a universal word/character limit; limits must be policy-versioned and
  owner/counsel-approved.
- Replacing provenance review, copyright review, or the public fail-closed gate
  with a rights-status field alone.

## Current baseline
- `transcript_variant.raw_text`, `transcript_segment.text`, and
  `canonical_transcript_segment.canonical_text` are private operational data.
- `content_item.rights_status` and `evidence.rights_status` default to `UNKNOWN`.
- `public_projection.py` emits bounded source/evidence metadata and segment
  provenance, not raw/canonical transcript text or evidence excerpts.
- `docs/18-storage-retention-and-open-data.md` distinguishes internal transcript
  retention from public excerpt/full-transcript publication and says full
  transcript requires policy permission.
- `retention.py` deletes transient media only after durable manifest, transcript,
  provenance, and receipt checks.
- `docs/04-legal-safety-research.md` is explicitly preliminary product research,
  not legal advice, and lists copyright, quotation, platform, and scraping questions
  for qualified review.

## Constitution and non-negotiable constraints
- **C-305-01 — Rights unknown means private:** `UNKNOWN`, expired, missing, or
  contradictory rights status cannot authorize a public excerpt or full transcript.
- **C-305-02 — No substitute republication:** public output links to the source and
  exposes only the minimum approved excerpt/metadata needed for the claim; it does
  not replace the source work.
- **C-305-03 — Exact provenance:** every excerpt is linked to source/content,
  segment, timestamp/range, transcript variant, content hash, and rights-policy
  version; normalization cannot silently alter the quoted wording.
- **C-305-04 — No raw-body leakage:** raw/canonical transcript, media, evidence
  excerpts, provider details, and internal rights notes never enter public JSON,
  JSON-LD, HTML, API, search, or analytics unless a future explicit policy allows
  the exact field.
- **C-305-05 — Fail closed at read time:** rights, attribution, policy, and
  provenance are revalidated when the projection is generated; stale or expired
  clearance omits the excerpt.
- **C-305-06 — Append-only challenge:** a complaint, hold, correction, or retraction
  creates a new event/version and does not erase prior audit history.
- **C-305-07 — Source-safe acquisition:** acquisition obeys the existing safe-fetch,
  allowlist, terms, and access boundaries; technical reachability is not permission.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-305-01 | Public projection contains source URL, timestamps, approved provenance IDs, and claim-level assessment; raw/canonical transcript and media are private by default. | Accepted product invariant |
| P-305-02 | A public excerpt is allowed only when the exact source/segment has an approved, current rights decision and the excerpt passes the policy. | Accepted product invariant |
| P-305-03 | `rights_status=UNKNOWN`, missing receipts, or conflicting source terms produce no public excerpt. | Accepted fail-closed rule |
| P-305-04 | Full transcript publication is out of scope for the baseline and requires a separate qualified decision, source-by-source clearance, and public-schema review. | Safe default; owner/counsel decision required |
| P-305-05 | Excerpts are necessary, proportionate, attributed, time-bounded, and non-substitutive; no universal length is assumed in this ticket. | Safe product default; numeric profile pending |
| P-305-06 | Source terms/API permissions, license receipts, and attribution requirements are stored as private provenance and rechecked at projection time. | Accepted engineering invariant |
| P-305-07 | A copyright/privacy complaint can trigger a private hold and DP-303 review; it cannot automatically delete the operational record or rewrite history. | Safe product default |
| P-305-08 | Machine-generated transcript metadata may be shown only as provenance/method information and never as a claim that the transcript is authoritative or cleared. | Accepted product invariant |

## Rights and excerpt contract
  Each source/content/evidence candidate must have a versioned rights record with:
- source family and exact locator;
- acquisition path and timestamp;
- rights status and evidence receipt (license, permission, contract, or explicit
  unknown/unresolved state);
- permitted acquisition/storage/publication uses, if known;
- attribution and link requirements;
- expiry/review date and reviewer/policy version;
- transcript/ASR provenance and any machine-transcription limitation;
- approved excerpt ranges and public field allowlist, if any.
  A rights record may be private even when the public projection exposes only a
boolean/label such as “source link available.” The public projection must not
expose internal legal reasoning or rights receipts unless explicitly approved.

## Engineering requirements
- **E-305-01 — Rights registry:** add or adapt a versioned rights-policy record
  keyed by source/content/evidence/segment, with a default `UNKNOWN` state and
  explicit review/expiry. Do not treat a source being technically fetchable as
  `ALLOWED`.
- **E-305-02 — Acquisition boundary:** preserve source terms, API/permission
  evidence, and safe-fetch receipt; do not bypass authentication, paywalls, access
  controls, or platform restrictions.
- **E-305-03 — Excerpt planner:** produce only an allowlisted, bounded excerpt
  proposal tied to claim segment IDs, source timestamps, exact wording, language,
  and reason for necessity. It must reject a request for a full transcript or
  substitutive media by default.
- **E-305-04 — Excerpt renderer:** render escaped, attributed text with source
  link, timestamp, and policy version. It must not include adjacent private text,
  provider prompts, evidence body, or hidden transcript fields.
- **E-305-05 — Read-time revalidation:** the public query rechecks rights status,
  expiry, source hash/segment provenance, transcript candidate freshness, and
  required approval. Any mismatch omits the excerpt or dossier under the accepted
  policy.
- **E-305-06 — Source snapshot integrity:** store a content hash and retrieval
  receipt for the observed source; a changed source creates a new version/rights
  review rather than silently reusing the old clearance.
- **E-305-07 — Full-transcript isolation:** keep full transcript access behind the
  private operator boundary and never provide a bulk public export. Any future
  full-transcript request is a separate ticket and legal decision.
- **E-305-08 — Machine-transcript disclosure:** preserve ASR/provider/version and
  uncertainty metadata in private provenance; expose only the bounded method/
  limitation fields allowed by the public schema.
- **E-305-09 — Complaint integration:** route rights complaints to the DP-303
  private correction/takedown/appeal workflow, with a hold that prevents new public
  excerpt generation while review is pending.
- **E-305-10 — Retention separation:** apply DP-304/DP-503 retention to raw media,
  transcripts, source snapshots, rights receipts, and public projection artifacts;
  rights metadata cannot authorize unbounded retention.
- **E-305-11 — No new public schema by default:** excerpt fields must be explicitly
  added to the versioned public schema with bounds, examples, and compatibility
  tests; the current projection's no-body default remains valid.
- **E-305-12 — Audit:** record rights decisions, excerpt approvals, holds, and
  takedown outcomes as append-only events with actor, policy version, and affected
  IDs, without copying protected body text into logs.

## Qualified questions

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-305-01 | What quotation/excerpt rights or exceptions apply to each source family and intended public use in Italy/EU? | Determines whether and how much text can be shown. | Publish no excerpt beyond the minimum already approved by a source-specific policy; default to no new excerpt. |
| Q-305-02 | Which source terms, API permissions, licenses, and attribution conditions govern acquisition, storage, transcription, and republication? | Governs source admission and rights status. | Keep unknown/unresolved sources private. |
| Q-305-03 | Do full transcript, audio, video, or derived datasets require separate permission, registration, or notice? | Determines whether a future full-transcript feature is viable. | Full transcript/media publication is out of scope. |
| Q-305-04 | What notice or takedown process must a rights holder receive, and how should a disputed excerpt be held? | Affects DP-303 workflow and public omission. | Accept complaints privately and hold new excerpt output pending review. |
| Q-305-05 | What machine-transcription disclosure, accuracy representation, or source-attribution wording is required? | Affects public method fields and copy. | Show only approved provenance/limitations; no accuracy claim. |
| Q-305-06 | What retention period applies to source snapshots, transcript variants, and rights receipts after a complaint or withdrawal? | Governs evidence preservation and deletion. | Preserve required audit; no unapproved purge. |
| Q-305-07 | Which platform/API terms or access restrictions prohibit automated acquisition even when a public URL exists? | Determines source allowlist and ingestion decisions. | Do not bypass or infer permission; source remains disabled. |

## Launch blockers
- **B-305-01:** No public excerpt may ship for a source/segment whose rights status,
  license/permission receipt, or policy version is unknown, expired, or conflicting.
- **B-305-02:** No full transcript, audio, video, or substitutive source copy may
  launch without a separate qualified decision and source-by-source clearance.
- **B-305-03:** No public serializer may expose raw/canonical transcript, evidence
  body, provider prompt, or internal rights note.
- **B-305-04:** No source terms, access control, or platform restriction may be
  bypassed by ingestion.
- **B-305-05:** DP-306/DP-307 must resolve the source-specific copyright, platform,
  machine-transcript, complaint, and retention questions.
- **B-305-06:** A rights complaint must produce a private hold and append-only
  review trail before any affected public excerpt is removed or replaced.

## Acceptance criteria
- [ ] **AC-305.1:** Rights records default to `UNKNOWN`/private and include source,
  locator, receipt, permitted-use, expiry, attribution, and policy-version fields.
- [ ] **AC-305.2:** A source with unknown, expired, missing, or conflicting rights
  status cannot produce a public excerpt or full transcript through any serializer.
- [ ] **AC-305.3:** An approved excerpt is escaped, attributed, time-bounded, linked
  to exact segment/variant/hash provenance, and limited to the approved public
  fields.
- [ ] **AC-305.4:** Tampering with source hash, segment freshness, rights expiry, or
  review event makes the excerpt/dossier non-projectable until re-reviewed.
- [ ] **AC-305.5:** Public JSON, JSON-LD, HTML, API, search, and analytics contain no
  raw/canonical transcript, evidence body, provider prompt, or internal rights body.
- [ ] **AC-305.6:** A rights complaint creates a private DP-303 hold/event, prevents
  new public excerpt output, and preserves the prior audit/history.
- [ ] **AC-305.7:** Full-transcript requests are rejected by the baseline policy and
  cannot be satisfied by a hidden bulk-export path.
- [ ] **AC-305-8:** A MiniPC canary verifies source-rights decisions, excerpt
  projection, expiry hold, and public-bundle cleanup without exposing protected
  content.

## Validation/proof
- **Focused rights/security proof:** unknown/expiry/conflict, attribution,
  escaping, exact-provenance, source-change, full-transcript rejection, projection
  revalidation, and complaint-hold tests.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **Runtime proof:** use an isolated MiniPC canary with synthetic/cleared fixtures;
  inspect the rights receipt, public bundle, stale-file cleanup, and private records.
  Do not use third-party protected material as a test fixture.
- **M3 packet check:** link Q-305-01..07 to DP-306 and carry accepted decisions to
  DP-307.

## Documentation/data/migration impact
- Add a rights registry/excerpt policy, source-family decision log, and complaint
  runbook in the implementing change.
- Reuse `rights_status`, content/segment hashes, review events, and the existing
  private/public boundary; add only bounded, versioned fields if approved.
- Any schema or public-schema change needs additive migration, compatibility tests,
  and MiniPC proof. No third-party media or full transcript is added to Git.
- This specification does not grant rights, clear a source, or publish content.

## Completion receipt
  Pending implementation, source-rights evidence, security/privacy review, MiniPC
proof, and qualified legal closure. The current no-raw-body public projection remains
the implemented baseline.

---

## Implementation receipt — policy lane (2026-09-26)

Status: **fail-closed excerpt/rights gate implemented; NO public excerpt may ship
(launch profile not approved).**

### What was implemented

- `poc/dichiarazioni_pubbliche/policy/excerpt_policy.py` (new, pure/zero-I/O): `RightsStatus`
  (only `CLEARED` authorizes); `decide_excerpt()` (fixed-order fail-closed
  conjunction); `render_attributed_excerpt()` (HTML-escaped, allowlisted public
  fields only, refuses to render unless ALLOWED); `effective_excerpt_cap()`
  (absolute vs 10%-of-source); `dossier_excerpt_budget()`;
  `REQUIRED_ATTRIBUTION_FIELDS`; `ALLOWED_PUBLIC_METHOD_FIELDS`.
- `docs/policy/dp-305-excerpt-policy.md`.
- `tests/test_policy_excerpt.py` (31 tests).

### Key decisions

- `EXCERPT_PROFILE_APPROVED = False`: the ticket forbids inventing a universal
  length limit, so the numeric bounds are an explicit **placeholder** and every
  excerpt is prohibited until an owner/counsel-approved profile exists (B-305-01,
  P-305-05). Tests cover both the current-prohibited and approved behaviors.
- Rights `UNKNOWN`/`UNRESOLVED`/`EXPIRED`/`CONFLICTING`/`REVOKED` all prohibit; there
  is no fetchable-therefore-allowed path (C-305-01, E-305-01).
- Full-transcript and media-copy requests are rejected by construction (C-305-02,
  AC-305.7); a dossier carries at most `MAX_EXCERPTS_PER_DOSSIER` excerpts.
- Attribution + SHA-256 source hash + bounded timestamp window are mandatory; a
  changed source hash or a stale segment omits the excerpt (C-305-03/05, E-305-06).
- The renderer emits only approved public fields and HTML-escapes the excerpt; it
  never emits canonical transcript, evidence body, or rights receipts (C-305-04).
- Machine-transcript method fields are allowlisted; there is no accuracy/confidence/
  score field (E-305-08).
- Rights complaints route to the DP-303 workflow and hold new excerpt output pending
  review (E-305-09).

### Research correction (verified 2026-09-26)

The **public quotation/press exception is Directive 2001/29/EC Art. 5(3)**, not
Directive (EU) 2019/790. CDSM Art. 3/4 are the text-and-data-mining provisions
(verified official headings). A design leaning on CDSM for quotation leans on the
wrong instrument. Which national implementing rules apply per source family remains
Q-306-11, `OPEN`/`BLOCKING`.

### What is NOT claimed

- No rights granted, no source cleared, no quotation declared fair/permitting; no
  full-transcript path; no DB/schema change (E-305-11).
- Source-specific terms, licences, and attribution requirements are unresolved
  (Q-305-01..07, Q-306-11..13).
- MiniPC canary (AC-305.8) is not run; this change is pure policy modules.

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean.
