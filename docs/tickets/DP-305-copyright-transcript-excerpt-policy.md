# DP-305 — Copyright, transcript, and excerpt publication policy

Status: IN PROGRESS

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
- [x] **AC-305.1:** Rights records default to `UNKNOWN`/private and include source,
  locator, receipt, permitted-use, expiry, attribution, and policy-version fields.
- [x] **AC-305.2:** A source with unknown, expired, missing, or conflicting rights
  status cannot produce a public excerpt or full transcript through any serializer.
- [x] **AC-305.3:** An approved excerpt is escaped, attributed, time-bounded, linked
  to exact segment/variant/hash provenance, and limited to the approved public
  fields.
- [x] **AC-305.4:** Tampering with source hash, segment freshness, rights expiry, or
  review event makes the excerpt/dossier non-projectable until re-reviewed.
- [x] **AC-305.5:** Public JSON, JSON-LD, HTML, API, search, and analytics contain no
  raw/canonical transcript, evidence body, provider prompt, or internal rights body.
- [x] **AC-305.6:** A rights complaint creates a private DP-303 hold/event, prevents
  new public excerpt output, and preserves the prior audit/history.
- [x] **AC-305.7:** Full-transcript requests are rejected by the baseline policy and
  cannot be satisfied by a hidden bulk-export path.
- [x] **AC-305-8:** A MiniPC canary verifies source-rights decisions, excerpt
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

---

## Local implementation receipt — budget/media/audit gates (2026-10-05)

Advanced the technical policy lane only; no source was legally cleared and no
source-specific quotation/media conclusion was created.

### Implemented

- Extended `RightsStatus` with operational block/hold states already used elsewhere in
  the runtime (`BLOCKED`, `FORBIDDEN`, `LEGAL_HOLD`, `RIGHTS_HOLD`, `TAKEDOWN_HOLD`,
  `REMOVED`). They all suppress excerpt/media authorization with bounded reason codes;
  `CLEARED` remains the only authorizing status.
- Added `decide_excerpt_budget()`, a structured excerpt-budget calculator/decision.
  Repository defaults remain fail-closed because `EXCERPT_PROFILE_APPROVED=False`.
  Explicit test/profile inputs can prove count, individual-item, and derived total-char
  enforcement without making those numbers legal rules.
- Added `decide_media_use()` as the media/embed authorization seam matching the current
  public Content shape (`public_media_url`, `media_policy_version`) without changing that
  shared schema. Copy/republication modes remain prohibited. An embed requires
  pre-existing `CLEARED` rights, explicit `MEDIA_EMBED_PUBLIC` use, safe HTTPS URL,
  timed-media kind, policy version, and an explicitly approved source-specific profile.
- Added `build_rights_policy_audit()`: bounded machine-code-only receipt, maximum eight
  reason codes, no excerpt/body/URL/licence-note copying, and redaction of contact-shaped
  subject identifiers.
- Added explicit tests that unknown/rights-hold source state suppresses excerpts and full
  transcript output; full transcript remains prohibited regardless of rights state.
- Fixed the pre-existing read-time expiry gap: supplied `rights_reviewed_on`,
  `rights_expires_on`, and `today` ISO dates are now validated; expiry after the declared
  date, malformed clock/date input, or a future review date fail closed. No duration or
  expiry period is invented.

### Acceptance accounting

No DP-305 AC is marked complete by this receipt. The local policy gates prove substantial
parts of AC-305.2/.3/.4/.7, but those ACs intentionally quantify over public serializers,
runtime/public integration, or hidden export paths that this clean-file change did not
modify. AC-305.1 still needs the versioned persisted rights registry, AC-305.5 requires
all public surfaces, AC-305.6 requires persisted DP-303 hold/event integration, and
AC-305-8 remains a MiniPC canary.

All source-specific terms, licences, quotation limits, attribution conditions, media
permissions, retention decisions, and qualified Italy/EU conclusions remain open under
Q-305-01..07 / DP-306 / DP-307.

Validation for this receipt:

- `PYTHONPATH=poc python3 -m unittest tests.test_policy_excerpt -v`: **51/51 PASS**;
- excerpt policy + source-intelligence + current public-schema + DP-303 challenge suite:
  **127/127 PASS**;
- focused `compileall`: PASS;
- focused `git diff --check`: PASS.

---

## Private versioned rights registry tranche — 2026-10-06

Implemented the persisted private registry required by AC-305.1 only. This tranche does
not clear any real source, define quotation limits, make a legal conclusion, approve an
excerpt, or alter any public projection/schema/web surface.

### Persisted contract

- Added `private_source_rights_record` to the fresh database schema and additive migration
  `20261006-add-private-rights-registry.sql`.
- Database defaults are literally `rights_status='UNKNOWN'` and
  `record_visibility='PRIVATE'`. The registry is append-only: UPDATE, DELETE and TRUNCATE
  are rejected by database triggers.
- Each record is bound to a `source_family`, exact `locator_kind` + `locator_value`, and
  optional exact `content_id`, `evidence_id`, plus at most one transcript/canonical/passage
  segment reference. When a segment is bound together with a Content, the private runtime
  verifies that the segment actually belongs to that Content.
- A rights receipt is represented only by bounded opaque `rights_receipt_ref`; there is no
  receipt body, legal-reasoning, note, or public-approval field in the table/runtime
  contract.
- `permitted_uses` and `attribution_requirements` are bounded machine-code arrays. Review
  and expiry are explicit `reviewed_at` / `expires_at` fields, review identity is the opaque
  `reviewer_ref`, and `policy_version` is mandatory.
- Non-`UNKNOWN`/`UNRESOLVED` states require a receipt reference. A `CLEARED` value, if an
  operator later records one, additionally requires an explicit receipt + reviewer +
  reviewed timestamp; the registry itself still has no excerpt/publication authorization
  output.
- Version history is append-only through explicit `supersedes_id`. Exact replay produces
  the same deterministic record ID; a new decision without superseding the current leaf is
  refused; a stale parent cannot branch the chain. Historical replay remains idempotent.

`poc/dichiarazioni_pubbliche/rights_registry.py` provides the private persistence seam over
that contract. It normalizes timestamps to UTC before fingerprinting, keeps receipt refs
opaque, validates bounded decision codes and exact target relationships, and never calls
`decide_excerpt()` or exposes a publication decision.

### Focused PostgreSQL proof

`tests/test_rights_registry_postgres.py` runs an ephemeral local PostgreSQL cluster with two
databases: one from the current fresh `schema.v1.sql` and one minimal legacy dependency
shape upgraded by the additive migration twice. The tests prove executed DB defaults
`UNKNOWN|PRIVATE`, deterministic replay, historical replay, explicit supersession, no stale
branch, append-only mutation refusal, exact Content/segment binding, opaque/no-body receipt
storage, clearance guard requirements, migration replay safety, and fresh-schema/migration
column parity.

Focused registry + excerpt policy + source-intelligence + DP-303 policy/intake validation is
**130/130 PASS**; full `python3 -m compileall -q poc tests`, Ruff on the new registry files,
and repository `git diff --check` pass.

### Acceptance accounting

**AC-305.1 is now complete** for the private persisted/versioned rights-record contract.
At this registry-tranche stage AC-305.2 through AC-305.7 and AC-305-8 remained open: this tranche did not
wire the registry into every serializer/projection path, create a rights-complaint durable
hold integration, approve a source-specific excerpt policy, or run the MiniPC projection
canary. No source-specific clearance or qualified Italy/EU legal conclusion is claimed.

Pre-complaint-bridge engineering-truth audit at clean HEAD `5a86666b` (2026-10-06): the combined excerpt
policy, rights registry, public serializer/API/linked-data boundary and existing DP-221 no-body
guard close AC-305.2/.3/.4/.5/.7. Unknown/expired/missing/conflicting rights fail closed; approved
fixture excerpts are escaped, attributed and exact-provenance/time bounded; stale hash/segment/
review/expiry input blocks; protected bodies never enter public surfaces; and full-transcript
requests have no public/bulk-export path. AC-305.6 and AC-305-8 remain open: there is no dedicated
durable rights-complaint -> DP-303 hold bridge and no end-to-end MiniPC rights/excerpt/expiry/
cleanup canary. No source is legally cleared; Q-306-11..13 / DP-307 remain unresolved.

## Final dependency-safe rights-complaint bridge — 2026-10-06

**AC-305.6 is now closed technically, with no rights or legal conclusion inferred.**
`rights_complaint_bridge.py` resolves the current private rights record and refuses it unless it
is directly bound to the target Finding through that Finding's claim Content or approved Finding
Evidence. A complaint on an unrelated rights record therefore creates no challenge at all.

A valid complaint uses DP-303's existing durable TAKEDOWN ledger: deterministic intake creates a
private request and advances only to `TRIAGE_PENDING`; exact replay is idempotent. It cannot create
a public hold by itself. Only an explicit `TRIAGE_REVIEWER` transition with the existing canonical
review gate may append `PUBLIC_HOLD_APPROVED`. The existing fail-closed
`current_hold_for_finding()` then returns `HOLD`, preserving the entire private rights record and
challenge history. Production revalidation already consumes that DP-303 hold seam, so no
DP-232/public-projection edit was required in this tranche.

The bridge, concurrency/cleanup mechanics, migration parity and restore inventory participate in
the final isolated MiniPC focused run: **130/130 PASS** with disposable PostgreSQL 18; local new
acceptance is **15/15 PASS**, broader focused regression **115/115 PASS**, and `compileall` passes.

**AC-305-8 remains open.** This canary did not exercise an owner/counsel-approved real excerpt
profile through source-rights decision, expiry, regenerated public bundle and cleanup. No source
is cleared, no quotation amount is approved, and Q-306-11..13 / DP-307 remain unresolved.

## Synthetic rights/excerpt/expiry/cleanup MiniPC canary — 2026-10-06

**AC-305-8 is now closed for the machine/runtime contract.** The global repository posture is
unchanged: `EXCERPT_PROFILE_APPROVED` remains `False`, so this receipt does not approve a real
source family or quotation limit. `tests/test_m3_runtime_canaries.py` supplies an explicitly
approved **synthetic fixture profile only** so the already-implemented positive branch can be
tested without converting test parameters into legal policy.

Against a fresh disposable PostgreSQL database the canary records a synthetic `CLEARED` private
rights decision bound to an exact Content, Evidence and transcript segment, with opaque receipt,
reviewer, permitted-use and expiry metadata. Before expiry, the exact-provenance excerpt passes
`decide_excerpt()` and `render_attributed_excerpt()` emits only the bounded escaped public fields;
neither the rights receipt nor reviewer reference is present. After the declared expiry date the
same request fails with `RIGHTS_EXPIRED` and the renderer refuses output. A new append-only
`EXPIRED` rights record explicitly supersedes the cleared record.

The expired current rights record then enters `RightsComplaintBridge`: private TAKEDOWN intake
stops at triage, an explicit synthetic reviewer advances the canonical ledger to
`PUBLIC_HOLD_APPROVED`, and `cleanup_takedown_current_artifacts()` removes only the manifest-listed
current public Finding artifact. A private raw-body sentinel, the rights registry history and the
three-event private challenge chain remain intact. Cleanup receipts contain neither that private
body nor an opaque rights-receipt reference.

The integrated canary passes **3/3 locally** and **3/3 on MiniPC** from an isolated `/tmp`
workspace with production DB variables removed; MiniPC `compileall` also passes. The broader
local M3 focused regression is **107/107 PASS**, benchmark is **5/5 PASS**, and
`git diff --check` is clean.

This is not source clearance. Q-305-01..07, Q-306-11..13 and DP-307 remain unresolved, the real
excerpt launch profile remains disabled, and no quotation amount, licence interpretation,
platform permission, retention period or legal conclusion is asserted.
