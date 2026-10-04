# DP-304 — Privacy, minimization, and sensitive-person policy

Status: IN_PROGRESS

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
- [ ] **AC-304.2:** Public-interest relevance is required before ingestion and
  publication; missing or stale relevance yields a private hold/omission.
- [ ] **AC-304.3:** Fixtures for sensitive claims, allegations, minors, victims,
  exact locations, and contact data are quarantined or minimized and never inferred
  into new traits.
- [ ] **AC-304.4:** Public JSON, JSON-LD, HTML, API, search, analytics, and logs
  contain no prohibited private fields, even when the operational row is tampered.
- [ ] **AC-304-05:** Rights requests create private append-only cases and cannot
  directly edit or delete a published historical version.
- [ ] **AC-304.6:** Retention dry-runs prove that incomplete manifests, missing
  receipts, active holds, and failed provenance checks prevent deletion.
- [ ] **AC-304-07:** Access tests prove that only authorized roles can inspect private
  content and that access audit records contain no copied body text.
- [ ] **AC-304-08:** A MiniPC canary verifies private/public field separation, an
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
  inventory (E-304-01), access control/encryption/audit (E-304-06), or incident
  runbook (E-304-12) — all runtime work.
- No production data was mutated.

Repository checks run: `compileall` OK; full suite green (515 tests);
`git diff --check` clean.
