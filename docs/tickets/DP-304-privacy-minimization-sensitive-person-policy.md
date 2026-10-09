# DP-304 — Privacy, minimization, and sensitive-person policy

Status: IN PROGRESS

Milestone: M3

Depends on: M0 baseline; coordinate with DP-302, DP-303, DP-305, and DP-503

Launch state: BLOCKED until the data inventory, retention rules, and qualified
Italy/EU review are accepted

This is a product, privacy, security, and engineering specification, not legal
advice. It does not select a lawful basis, legal exception, retention period, or
regulatory conclusion.

## Problem
  Dichiarazioni Pubbliche is intended for public figures and public-interest activity, but a public
figure is not a person without privacy. The current runtime retains operational
transcripts, evidence bodies, submitter data, and provenance while the public
projection excludes raw content. There is not yet one explicit data-classification,
minimization, sensitive-person, access, retention, and rights-request contract that
can be enforced consistently across ingestion, intake, projection, and deletion.

## Outcome
  Define a deny-by-default data policy and review gates that collect and publish only
what is necessary for a documented public-role/public-interest record, keep sensitive
or irrelevant private data out of the public projection, preserve append-only
history where required, and make retention, access, correction, and deletion
decisions auditable. The implementation remains blocked where a human legal or
owner decision is missing.

## Scope
- Define public, operational-private, sensitive, derived, and ephemeral data
  classes and field-level handling rules.
- Define the public-interest relevance gate for people, content, claims, evidence,
  replies, and corrections.
- Define special-category, allegation, minor, victim, location, contact, and identity
  handling without inferring traits.
- Define access control, minimization, redaction, retention, legal hold, rights
  request, and incident requirements.
- Define tests and the evidence needed before any public launch.

## Non-goals
- Creating a private-life dossier, political profile, reliability score, or
  biometric identity system.
- Inferring health, religion, sexuality, criminal history, ethnicity, political
  beliefs, or other sensitive traits from content or metadata.
- Deciding GDPR roles, lawful bases, journalistic exemptions, data-subject rights,
  or retention periods.
- Replacing the existing public projection with a database export.
- Deleting source evidence or transcript history merely because a person objects;
  a rights request must follow an approved lifecycle and retain required audit.

## Current baseline
- `PRODUCT.md` scopes the system to public figures and public-interest activity and
  states that private/raw operational data is not public merely because a projection
  exists.
- `person.is_public_figure` is constrained to true, but the current schema does not
  express a complete public-interest relevance or data-sensitivity policy.
- `transcript_variant.raw_text`, `transcript_segment.text`, and
  `canonical_transcript_segment.canonical_text` are private operational data.
- `evidence.excerpt` exists operationally; the current public projection emits
  evidence metadata, not the excerpt.
- `canonical_transcript_segment.sensitive_signature` and
  `publication_blocked` provide a starting point for segment-level hold behavior.
- `retention.py` purges transient media only after manifest, transcript, provenance,
  and receipt durability checks; it does not define a complete rights/retention
  policy.
- `public_projection.py` is an allowlist-based fail-closed boundary and must remain
  the only public data seam.

## Constitution and non-negotiable constraints
- **C-304-01 — Public-interest relevance:** a Person or datum is eligible only
  when its connection to a public role or documented public interest is recorded;
  private-life relevance is excluded by default.
- **C-304-02 — No sensitive inference:** the system does not infer or enrich
  sensitive traits, criminal status, mental state, sexuality, religion, ethnicity,
  political belief, or similar attributes from speech or metadata.
- **C-304-03 — Data minimization:** collect, retain, expose, log, and index the
  least data necessary for the declared purpose; raw content is not a public
  convenience export.
- **C-304-04 — No biometric identification:** no face recognition, voiceprint,
  speaker embedding, or other biometric identity matching is permitted.
- **C-304-05 — Public/private separation:** private submissions, raw transcripts,
  evidence bodies, internal notes, credentials, and provider details cannot enter
  public JSON, JSON-LD, HTML, API, search index, analytics, or error output.
- **C-304-06 — Append-only accountability:** review, access, redaction, hold,
  correction, and deletion decisions are recorded as events; a public version is
  never silently rewritten.
- **C-304-07 — Fail-closed deletion:** missing manifests, receipts, provenance,
  or rights/hold decisions block destructive operations rather than guessing.
- **C-304-08 — Access minimization:** only authorized roles can inspect private
  material, and access is logged without copying the material into logs.

## Policy decisions

| ID | Decision | State |
|---|---|---|
| P-304-01 | Public-figure status alone is not sufficient relevance; each included item must have a recorded public-role or public-interest reason. | Accepted product invariant |
| P-304-02 | Raw/canonical transcripts, evidence excerpts, contact details, exact private locations, and internal moderation material are private by default. | Accepted product invariant |
| P-304-03 | Sensitive categories, allegations, victims, and minors are held for qualified review and are not published merely because a source or model labels them. | Safe product default |
| P-304-04 | Public output contains stable IDs, bounded provenance metadata, approved assessment, and approved correction history; it does not expose hidden sensitivity classifications or internal notes. | Accepted product invariant |
| P-304-05 | Submitter identity and contact data are separated from reply content and are not published without an explicit policy decision. | Safe product default |
| P-304-06 | Retention periods are policy-versioned and owner/counsel-approved; no numeric period is invented in this ticket. | Pending owner/counsel decision |
| P-304-07 | A legal hold, active dispute, or required audit record overrides ordinary deletion until the hold is released by an authorized decision. | Safe product default |
| P-304-08 | A data-subject request can trigger a correction, access, restriction, or deletion workflow, but it cannot directly mutate a public historical version. | Accepted product invariant |

## Data classification contract

| Class | Examples | Default handling | Public projection |
|---|---|---|---|
| `PUBLIC_CORE` | Approved public Person ID/name, public role interval, public source URL, claim/finding IDs, bounded timestamps, approved evidence metadata | Retain and version with provenance | Allowed only through the public allowlist and review gate |
| `PUBLIC_SAFE_TEXT` | Sanitized normalized claim, bounded rationale, approved correction/notice text | Minimize, redact, and review before release | Allowed only when explicitly approved and bounded |
| `OPERATIONAL_PRIVATE` | Raw/canonical transcript text, evidence body/excerpt, prompts, model/provider receipts, internal notes | Encrypted/access-controlled private store; no logs or indexes | Prohibited |
| `SENSITIVE_CANDIDATE` | Health, religion, sexuality, ethnicity, political opinions, criminal allegations/records, mental-health inferences | Hold/quarantine; no automated enrichment; qualified review | Prohibited unless a future policy explicitly allows a sanitized fact |
| `HIGH_RISK_IDENTITY` | Minors, victims, witnesses, exact private location, contact data, identity documents | Do not ingest or publish by default; minimize and escalate | Prohibited |
| `EPHEMERAL` | Downloaded media, failed-job artifacts, temporary request bodies, model cache | TTL and durable-manifest purge; fail closed on uncertainty | Prohibited |
  Classification is a product decision, not a claim that a datum is legally
sensitive. A reviewer may downgrade or reject a candidate, but no model may silently
reclassify a high-risk item as public.

## Engineering requirements
- **E-304-01 — Inventory and policy version:** create a versioned field inventory for
  each class, purpose, source, retention rule, access role, and public projection
  decision. Every public field must have an explicit allowlist entry.
- **E-304-02 — Relevance gate:** before acquisition persistence and again before
  publication, require a structured public-role/public-interest relevance reason;
  absent or stale relevance causes hold/omission.
- **E-304-03 — Sensitivity candidate gate:** use deterministic signals and explicit
  human review to flag possible sensitive/high-risk content. Flags never become
  inferred traits, and an unflagged item is not presumed safe when context is
  ambiguous.
- **E-304-04 — Field-level redaction:** keep raw and normalized text in separate
  private representations; public serializers select only approved fields and
  reject unknown/sensitive fields rather than passing them through.
- **E-304-05 — No public raw content:** JSON, JSON-LD, HTML, API, search, analytics,
  notifications, and errors must exclude transcript text, evidence excerpts, source
  credentials, internal prompts, and private intake data.
- **E-304-06 — Access control and audit:** private records require role-based local
  operator access (or the future authenticated admin service), with actor, purpose,
  time, and outcome recorded. Access logs contain identifiers, not content copies.
- **E-304-07 — Retention scheduler:** define per-class TTL/expiry state, durable
  receipts, legal-hold checks, and a dry-run receipt before deletion. Media purge
  must continue to require complete manifests, transcripts, and provenance.
- **E-304-08 — Rights-request workflow:** represent access, correction, restriction,
  objection, and deletion requests as private append-only cases linked to the
  affected data and policy version. A case outcome cannot be inferred from a
  mutable status column.
- **E-304-09 — Public-history protection:** a rights decision affecting a published
  version produces a reviewed correction, restriction, or public hold event; it
  does not silently erase the historical record.
- **E-304-10 — Security boundaries:** encrypt private stores and transport, keep
  secrets out of Git, and use bounded safe-fetch rules for any evidence retrieval.
  No public or intake path may query operational tables directly.
- **E-304-11 — Retention budgets:** enforce storage and queue limits; a retention
  backlog or failed hold check blocks new ingestion rather than exceeding disk or
  privacy limits.
- **E-304-12 — Incident handling:** define detection, containment, notification
  decision, evidence preservation, and recovery for accidental sensitive-data or
  credential exposure. Do not assume a legal notification deadline here.

## Qualified questions

| ID | Question for the owner/counsel | Why it matters | Until answered |
|---|---|---|---|
| Q-304-01 | What are the controller/processor roles, lawful bases, notices, and journalistic/public-interest conditions for each data class? | Governs collection and public projection. | Keep private data private; no production launch. |
| Q-304-02 | Which sensitive categories, allegations, criminal matters, victims, and minors require special handling or exclusion? | Determines high-risk hold rules. | Hold all detected high-risk candidates; do not infer traits. |
| Q-304-03 | What retention, deletion, restriction, and legal-hold periods apply to each class and jurisdiction? | Governs lifecycle automation. | Use no unapproved automatic deletion; preserve audit. |
| Q-304-04 | What notice, access, correction, objection, and erasure workflow must a subject receive? | Governs rights-request UX and records. | Provide an operator contact path; no self-service mutation. |
| Q-304-05 | Are there conditions for publishing a sanitized fact about a public role even when the underlying material contains sensitive data? | Affects policy exceptions and review. | No exception; public output stays minimized. |
| Q-304-06 | What processor, transfer, security-incident, and breach-notification obligations apply to hosting and vendors? | Affects architecture and incident runbook. | Do not add vendors or claim compliance. |
| Q-304-07 | Which public-figure disambiguation data is necessary, and how should aliases/role intervals be retained? | Affects identity and history privacy. | Store only approved public disambiguation data. |

## Launch blockers
- **B-304-01:** No production dataset or public intake may launch without an approved
  field inventory, purpose/relevance record, retention matrix, and rights workflow.
- **B-304-02:** No sensitive/high-risk candidate may be auto-promoted to public
  output; unresolved classification is a hold.
- **B-304-03:** No raw transcript, evidence body, submitter contact data, exact
  private location, or internal note may appear in a public surface or log.
- **B-304-04:** No biometric identity or sensitive-trait inference may be added.
- **B-304-05:** DP-306/DP-307 must resolve the applicable privacy, sensitive-person,
  retention, and rights questions.
- **B-304-06:** Deletion/retention jobs must have a tested dry-run and fail-closed
  manifest/hold behavior before they can touch production data.

## Acceptance criteria
- [ ] **AC-304.1:** Every persisted and projected field has one classification,
  purpose, access role, retention behavior, and public allowlist decision.
- [x] **AC-304.2:** Public-interest relevance is required before ingestion and
  publication; missing or stale relevance yields a private hold/omission.
- [x] **AC-304.3:** Fixtures for sensitive claims, allegations, minors, victims,
  exact locations, and contact data are quarantined or minimized and never inferred
  into new traits.
- [x] **AC-304.4:** Public JSON, JSON-LD, HTML, API, search, analytics, and logs
  contain no prohibited private fields, even when the operational row is tampered.
- [x] **AC-304-05:** Rights requests create private append-only cases and cannot
  directly edit or delete a published historical version.
- [x] **AC-304.6:** Retention dry-runs prove that incomplete manifests, missing
  receipts, active holds, and failed provenance checks prevent deletion.
- [x] **AC-304-07:** Access tests prove that only authorized roles can inspect private
  content and that access audit records contain no copied body text.
- [x] **AC-304-08:** A MiniPC canary verifies private/public field separation, an
  approved sanitized projection, a rights-request hold, and a safe retention
  decision without mutating unrelated records.

## Validation/proof
- **Focused privacy/security proof:** classification, relevance, redaction,
  projection leak, rights-request, access audit, retention/hold, and incident
  fixture tests.
- **Repository checks:** `python3 -m compileall -q poc tests`,
  `PYTHONPATH=poc python3 -m unittest discover -s tests -v`,
  `PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark`, and
  `git diff --check`.
- **Runtime proof:** inspect the MiniPC private store, public bundle, logs, queue,
  and retention dry-run receipt; prove no prohibited data crosses the projection.
- **M3 packet check:** link Q-304-01..07 to DP-306 and carry accepted decisions to
  DP-307.

## Documentation/data/migration impact
- Add a field-classification/relevance/retention matrix and rights/incident runbook
  in the implementing change.
- Reuse existing `publication_blocked`, `sensitive_signature`, `rights_status`,
  `review_event`, and retention manifest seams where they satisfy the contract.
- Add only additive, bounded schema fields or policy metadata when required; no
  destructive migration is part of this specification.
- Production data must not be rewritten to make a privacy or rights test pass.

## Completion receipt
  Pending implementation, privacy/security review, MiniPC proof, and qualified legal
closure. No privacy conclusion or production deletion is claimed here.

---

## Implementation receipt — policy lane (2026-09-26)

Status: **deny-by-default classification/minimization/retention/rights decisions
implemented; lawful basis, retention periods, and rights workflow remain BLOCKING.**

### What was implemented

- `poc/dichiarazioni_pubbliche/policy/privacy_policy.py` (new, pure/zero-I/O): the six
  `DataClass` values with a `PUBLIC_PROJECTABLE_CLASSES` allowlist;
  `decide_projection()` (fixed-order deny-by-default gate);
  `contains_high_risk_marker` / `contains_sensitive_marker` / `contains_pii_shape`
  (quarantine signals only, never traits); `minimize_public_fieldset()`;
  `retention_decision()` (returns a class, never a number);
  `rights_request_outcome()`; `assert_no_trait_inference()`.
- `docs/policy/dp-304-privacy-policy.md`.
- `tests/test_policy_privacy.py` (32 tests).

### Key decisions

- Public projection is allowlisted: only `PUBLIC_CORE` (with review) and
  `PUBLIC_SAFE_TEXT` (with explicit approval) can ever be allowed. Sensitive,
  high-risk, operational-private, and ephemeral classes are prohibited.
- A field named like a private field (raw/canonical text, excerpt, note, credential)
  is refused even if a serializer mislabels it `PUBLIC_CORE`.
- Public-interest relevance is required and a **public-figure flag is explicitly not
  a valid reason** (P-304-01).
- Markers produce a **human hold**, never a published trait; no marker can become a
  `DataClass` (C-304-02).
- `RETENTION_PERIODS_APPROVED = False`: no retention number is invented (P-304-06);
  only `EPHEMERAL` is purge-eligible and a legal hold overrides everything. Existing
  `retention.py` manifest fail-closed checks are untouched.
- A rights request never mutates a published historical version; deletion/restriction
  on a published version becomes a `REVIEWED_PUBLIC_HOLD` (E-304-09, C-304-06).

### What is NOT claimed

- No GDPR role, lawful basis, special-category condition, retention period, or
  rights outcome (Q-304-01..07, Q-306-08..10 `OPEN`/`BLOCKING`).
- This is a name-based deny list + marker heuristics, **not** the full field
  inventory (E-304-01), authenticated access-enforcement surface/encryption, or incident
  runbook (E-304-12). The pure E-304-06 authorization/audit seam is implemented below,
  but runtime persistence/integration remains open.
- No production data was mutated.

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean.

---

## Local implementation receipt — private access/minimization seam (2026-10-05)

Implemented and proved the previously outstanding pure `E-304-06` access/audit seam
without changing schema, public projection/API/web, queue/ledger, or shared dirty runtime
files:

- `PrivateAccessRole` aligns its operational/reviewer names with the existing DP-303
  `OPERATOR` / `TRIAGE_REVIEWER` / `DECISION_REVIEWER` / `APPEAL_REVIEWER` vocabulary;
  `PrivateAccessPurpose`, `PrivateAccessMode`, request/decision
  objects and `decide_private_access()` provide a closed, fail-closed authorization
  contract for **read-only** private inspection. Unknown roles, purposes, modes, data
  classes, malformed actors, and malformed field requests are denied.
- Generic local operations cannot inspect `SENSITIVE_CANDIDATE` or
  `HIGH_RISK_IDENTITY`; an already-classified sensitive/high-risk item requires a bounded
  review/rights/correction purpose or explicit incident response. The helper consumes the
  classification and never derives a trait from content.
- `LOG`, `EXPORT`, `MUTATE`, and `DELETE` are never authorized by this seam. An active
  legal hold may accompany an authorized read but never relaxes that read-only boundary.
- `build_private_access_audit()` records only bounded identifiers, purpose, outcome,
  timestamp, requested-field **count**, policy version, and hold flag. Requested field
  names/body values are not copied; contact-shaped identifiers and non-timestamp text are
  replaced with generic placeholders.
- Fixed a separate minimization leak in the same pure policy: schema fields named like
  `religion`, `criminal_history`, `victim_status`, or `mental_health` are now prohibited
  even if a caller mislabels them `PUBLIC_CORE`, and `minimize_public_fieldset()` removes
  them. This is field-name minimization, not sensitive-trait inference.

Proof:

- `PYTHONPATH=poc python3 -m unittest tests.test_policy_privacy -v`: **44/44 PASS**;
- privacy + challenge + retention + corpus-retention + right-of-reply boundary suite:
  **110/110 PASS**;
- focused `compileall`: PASS;
- focused `git diff --check`: PASS.

This closes the **pure policy/helper portion** of E-304-06, but AC-304-07 remains open
until an actual private runtime/admin inspection path is wired through this authority and
its persisted audit receipt is tested end-to-end. AC-304.1 (complete field inventory),
AC-304.2 (end-to-end ingestion/publication relevance), AC-304.4 (all public/log
surfaces), AC-304-05 (persisted append-only rights cases), AC-304.6 (complete deletion
receipt/hold matrix), and AC-304-08 (MiniPC canary) also remain open. No legal basis,
retention period, rights outcome, or regulatory conclusion is asserted.

---

## Local implementation receipt — persisted publication-decision binding (2026-10-06)

Implemented the private persisted DP-304 publication-decision seam that can later be
consumed by DP-308 without making the public projection itself an authority:

- `privacy_publication_decision` is an additive, private, append-only ledger with one
  linear supersession chain per `(subject_ref, record_ref, field_name)`. Each review is
  bound to an opaque `record_version`; that value is a binding supplied by the caller,
  not proof that the caller supplied the canonical Finding/version authority.
- Each record persists the data class, exact relevance reason, explicit safe-text
  approval flag, privacy-policy version, bounded reviewer/audit references, review
  sequence/supersession, canonical decision/reasons, and an exact projection-input
  digest. The text body itself is not persisted; its SHA-256 participates in the exact
  input binding.
- `PrivacyPublicationDecisionStore.append_review()` derives the decision only by calling
  canonical `privacy_policy.decide_projection()`; callers do not supply an ALLOW/HOLD/
  PROHIBIT result. `replay_current()` re-runs that same canonical policy over the current
  bounded input and requires the current caller-supplied record-version binding, current
  policy version, exact input digest, intact append-only chain, and matching persisted
  decision before an ALLOW can survive replay.
- Missing decisions, superseded/record-version-stale decisions, and changed inputs yield
  `HOLD_FOR_REVIEW`; malformed/tampered chains or a persisted decision that disagrees with
  canonical replay yield `PROHIBIT`. Unknown data classes remain `PROHIBIT`. A relevance
  reason of `IS_PUBLIC_FIGURE` remains a hold and cannot authorize publication.
- Fresh-schema parity is present in `db/schema.v1.sql` and the additive migration
  `20261006-add-privacy-publication-decision-ledger.sql`; both include insert-chain
  validation plus UPDATE/DELETE/TRUNCATE append-only guards.

Focused disposable-PostgreSQL proof:

- migration-path + fresh-schema replay, missing decision, `UNKNOWN`, public-figure-only
  relevance, explicit safe-text approval, exact-input staleness/body non-persistence,
  supersession/record-version staleness, privacy-policy-version staleness, append-only
  mutation rejection, fabricated integrity tamper, and additive-migration replay:
  **9/9 PASS**;
- privacy/schema/runtime/launch focused regression: **93/93 PASS** before the additional
  policy-version-staleness case; focused and repository-wide `compileall`: PASS;
  deterministic benchmark: **5/5 PASS**; `git diff --check`: PASS;
- full local discovery suite was attempted after the shared DP-305 rights-registry lane
  landed in the dirty tree: **1656 tests, 31 setup errors**. The observed failures are
  caused by pre-existing test cleanup paths that issue `TRUNCATE ... CASCADE` after
  `private_source_rights_record` acquired a no-TRUNCATE append-only trigger; PostgreSQL
  raises from `reject_private_source_rights_record_mutation()`. This is a shared-tree
  DP-305 test-isolation blocker, so no full-suite-green claim is made here.

No AC checkbox was closed by this tranche alone. At the time of this receipt,
**AC-304.2 remained open** because ingestion-wide relevance enforcement and the actual
public-projection consumption path were not yet wired; the later 2026-10-08 production
acceptance receipt below supersedes that specific blocker. AC-304.1, AC-304.4, AC-304-05,
AC-304.6, AC-304-07, and AC-304-08 also retained their then-current blockers. This tranche
does not select a lawful basis,
retention period, owner/counsel decision, sensitive trait, or reviewer identity authority,
and it does not change `public_projection`.

Final engineering-truth audit at clean HEAD `5a86666b` (2026-10-06): AC-304.3 is closed by
the sensitive/high-risk/minor/victim/location/contact fixtures that only quarantine/minimize and
never derive a new trait. AC-304.6 is closed by the current retention/corpus-retention fail-closed
dry-run matrix. AC-304.1/.2/.4/-05/-07/-08 remain open: complete field inventory,
ingestion-wide relevance, all-surface privacy/log proof, persisted rights-request cases, wired
private-admin access authority, and the composite MiniPC privacy/rights/retention canary are not
yet proven. Q-306-08..10 / DP-307 remain unresolved; no lawful basis, retention period or rights
outcome is asserted.

---

## Finalization receipt — machine-provable privacy boundary (2026-10-07)

This tranche closes only machine-verifiable privacy/minimization requirements. It does not
select a lawful basis, legal retention period, data-subject-rights outcome, or regulatory
conclusion; the launch-level qualified questions and DP-306/DP-307 blockers remain unchanged.

### Persisted private rights/access seams

- `privacy_rights_case` + `privacy_rights_case_event` are private append-only ledgers. The
  runtime can open a bounded `ACCESS/CORRECTION/RESTRICTION/OBJECTION/DELETION` case and append
  only `OPEN_PRIVATE`, `REVIEW_PENDING`, or `PUBLIC_HISTORY_HOLD_REQUIRED` safety events. The
  requester reference is stored only as SHA-256; no request body is persisted by this seam.
  Deterministic-ID replays revalidate the persisted row before trusting a conflict, identical
  hold retries are idempotent, and an exact concurrent replay converges on one successor event.
- A rights request aimed at an already-published record does not mutate the public historical
  row. The disposable-PostgreSQL acceptance snapshots a `PUBLISH` Finding byte-for-byte before
  and after opening a deletion request and appending the public-history hold requirement; the
  Finding is unchanged, while UPDATE/DELETE/TRUNCATE attempts against the rights ledgers fail.
  This closes **AC-304-05** as an engineering invariant only, not as a legal-rights decision.
- `private_access_audit_event` is a private append-only audit ledger containing policy version,
  bounded actor/record identifiers, purpose, outcome, timestamp, field **count**, and hold flag.
  It has no requested-field-name or body column. `PrivacyRightsAccessStore.inspect_private_field()`
  is a closed read-only allowlist over operational-private body fields and evaluates the existing
  `decide_private_access()` authority before reading. Unknown roles, wrong classifications,
  field mismatches, non-allowlisted fields, invalid audit timestamps, and incompatible
  deterministic audit-ID conflicts return no body; the verified audit write occurs before an
  authorized read. This closes **AC-304-07** for the implemented local operator/runtime seam.

### Public/private leak proof

- Existing high-risk serializer fixtures contaminate an operational projection row with private
  reviewer/high-risk fields and prove removal/rejection across projection JSON, dossier and
  projection JSON-LD, HTML, RDF/N-Triples, written public bundle, and all public API routes; a
  fingerprint-valid bypass returns a generic 503 without private material.
- DP-221/DP-305 boundary fixtures independently prove private source/paraphrase/summary/
  translation bodies are removed before every public serializer. The persisted PostgreSQL
  attribution acceptance also carries private alias/identifier/source-ref values through the
  operational database and proves they do not escape the projected dossier.
- The web search serializer check passes with contaminated high-risk sentinels absent. Public
  intake/challenge log receipts and private-store error receipts are bounded and redact private
  body/contact/fingerprint/error sentinels. No separate analytics or notification emitter exists
  in the current public runtime; therefore there is no additional public payload surface to
  authorize implicitly. This closes **AC-304.4** for the current implemented surfaces; adding a
  future analytics/notification surface would require a new allowlist/leak proof.

### Validation and MiniPC canary

- Local privacy policy + persisted publication-decision + new rights/access runtime:
  **59/59 PASS** on disposable PostgreSQL 17.11; fresh `schema.v1.sql` plus the additive
  `20261007-add-privacy-rights-access-ledgers.sql` migration replay twice successfully.
  A separate disposable migration audit also proves HEAD-before-DP-304 schema -> additive
  migration replay twice has the same three-table column shape as the fresh-schema path.
- Local serializer/log/retention boundary set: **52/52 PASS**; persisted PostgreSQL private
  attribution/source-ref leak check: **1/1 PASS**; web high-risk search serializer: **PASS**.
- Refreshed isolated MiniPC `/tmp` bundle after the replay/conflict hardening, with production
  database/provider variables removed, uses Python 3.14.4 and disposable PostgreSQL 18.6:
  **71/71 PASS** across privacy policy, rights/access
  persistence, high-risk public serializers, media retention and corpus-retention. The temporary
  bundle/database is removed afterward; no deployment mirror, provider, production database, or
  production record is touched. This proves the four required AC-304-08 machine canary elements:
  private/public separation, sanitized projection, private rights-request hold, and fail-closed
  safe retention decision. **AC-304-08 is closed.**
- Final shared-tree integration runs **1788/1788 PASS**. That run initially exposed the three new
  durable privacy tables as absent from the checked-in backup/restore inventory; the inventory and
  restore verifier were then extended fail-closed to all **97** repository-declared persistent
  tables, with focused backup/restore/privacy regression **25/25 PASS**. This is local integration
  proof only. The subsequent `dbca603` production promotion applied the privacy migration twice,
  converged at **97/97** live/repository tables with all three new ledgers empty, and passed the
  post-migration **97-table** disposable restore drill; the detailed runtime receipt is recorded in
  DP-502/DP-604.

### Remaining blockers

- **AC-304.1 remains open:** the repository still lacks the required exhaustive field-level
  inventory covering every persisted/projected field with classification, purpose, access role,
  retention behavior and public allowlist decision. The existing name-based policy is not that
  inventory, and no legal retention period is invented here.
- Q-304/Q-306/DP-307 qualified legal, retention, notice, and rights-workflow questions remain
  external blockers. No lawful-basis, legal-retention, or legal-rights conclusion is claimed.

## Production acceptance receipt — persisted ingestion relevance (2026-10-08)

This receipt supersedes the AC-304.2 blocker recorded in the 2026-10-07 finalization receipt.
It closes **AC-304.2 as an engineering invariant for the current production acquisition and
publication paths only**. It does not decide whether any person/content is legally in the public
interest, select a lawful basis, or authorize publication.

- Candidate commit `4c93246f5f91ec5b29d710aa1dc73c80be732d8a` adds append-only
  `privacy_ingestion_relevance_authority` and `privacy_ingestion_acquisition_permit` ledgers.
  Authority reasons are bounded to the implemented policy vocabulary and remain private. A permit
  is bound to the reviewed content identity, operation kind/ref and the still-current authority;
  missing, conflicting, stale or superseded authority fails closed.
- Current runtime acquisition seams are gated before externally acquired material can become
  durable: scheduler source/content/job commit revalidates the permit under one PostgreSQL
  transaction/advisory lock; research discovery persists only after a current permit; existing
  fact-check discovery requires an explicit reviewer-supplied relevance handoff rather than
  deriving authority from provider results; curated written intake rechecks before source/content
  mutation; capture rechecks after fetch and before body/capture persistence; transcript/platform
  resolution, caption and ASR paths check before network work and again before durable result
  persistence; source revalidation checks current relevance before materializing a new capture.
  Missing/stale authority therefore becomes `BLOCKED`/private omission rather than a fabricated
  relevance decision.
- Publication remains independently fail-closed through the persisted privacy-publication decision
  boundary proven by the earlier receipt. The new ingestion authority does not auto-promote or
  replace that publication decision.
- Frozen local integration on the exact code candidate ran **1803/1803 PASS**, deterministic
  benchmark **5/5**, repository/contributor acceptance PASS, compileall PASS and `git diff --check`
  PASS. The canonical launch preflight remained `NO-GO` with 41 blockers.
- An isolated MiniPC `/tmp` candidate derived from the commit reported **99** repository-declared
  persistent tables and passed the DP-304 ingestion/scheduler/capture/curated/fact-check/
  revalidation/worker selection **101/101** on disposable PostgreSQL 18. The migration
  `20261007-add-privacy-ingestion-relevance-authority.sql` SHA-256 is
  `d60e209f9afab0d274a41236d1763e870d2517f503ec999e9a9575c0f00bfdec` and replayed twice.
- Before production migration, backup set `20261007T225439Z` captured the then-current **97-table**
  database; dump SHA-256
  `2a7941ad1d7a8f4a53ece70d405ccbe7049a10bfe6cd2f35e3324d10ba0f8156` and manifest SHA-256
  `2bbfe67070f30c910b18f403e41720b62517f33f5c145995a98b57c7d40ca082`.
  Production held 50 content rows and 9 findings, while the public projection remained 0 dossiers
  at dataset fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`.
- Only the additive relevance migration was then applied, twice with `ON_ERROR_STOP`. Live and
  repository inventories converged at **99/99** tables. Both new production ledgers remained
  exactly **0 rows**: no fake reviewer/public-interest authority or permit was seeded. Existing
  content stayed 50, findings stayed 9, and the public projection file/dataset fingerprint stayed
  unchanged with 0 dossiers. Legacy rows therefore remain private/unapproved unless a real review
  creates authority; they were not retroactively blessed to make this acceptance pass.
- The 21 changed candidate files were synchronized to the non-Git MiniPC mirror while worker/source
  timers were suspended and no corresponding service was active. The live mirror then passed
  compileall, the same **101/101** focused suite, benchmark **5/5**, and the three timers were
  returned to `active`.
- Post-migration backup set `20261007T225628Z` contains **99** manifest tables with both relevance
  ledgers at 0 rows; dump SHA-256
  `f2f103e89e469538ab987e75e3dcaf68d3fd66488eca79db229d34444ad7fc96` and manifest SHA-256
  `004be1763d784c812447b06a2a2198c5fcbabf8781834cb85b43098f31721108`.
  A disposable PostgreSQL 18 restore reproduced all **99/99** table row counts exactly and matched
  the backed-up public projection fingerprint `501348d9638ee3c4d929205d2e6dca7eb2c8a552ac006dee837ea032a739ae7a`;
  the throwaway cluster was removed afterward.

AC-304.1 and the Q-304/Q-306/DP-307 qualified legal/privacy decisions remain open, so DP-304 stays
`IN PROGRESS` and this receipt is not launch or legal-compliance authority.

2026-10-09 follow-up: the operator's private Capture content gate previously
coerced missing or malformed PostgreSQL aggregate safety counts to zero.
It now requires nonnegative, exact integer values for inactive-Collection
and forbidden-membership counts, denying unknown/malformed states before
acquisition. Local RED→GREEN regression covers omitted, null, boolean,
string, floating and negative counts. This does not change lawful basis,
approve retention or resolve Q-306/DP-307; DP-304 remains IN PROGRESS.
