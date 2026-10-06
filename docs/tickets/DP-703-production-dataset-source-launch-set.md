# DP-703 — Production dataset/source launch set and disclosure

Status: IN PROGRESS
Milestone: M7 — stable v1 launch
Depends on: M2 exit criteria (DP-201..DP-207; DP-208 only if the selected path uses diarization) and M3 (DP-301..DP-307); coordinate with DP-603, DP-604, and DP-701
Launch state: BLOCKED until a bounded source set, rights/privacy disposition, provider path, and versioned public snapshot are accepted

## Problem

The project has source-discovery, transcript, queue, evidence, verification, and
projection primitives, but it does not yet have an owner-approved production launch set.
The current registry contains a working YouTube/Pulp path and an example social source;
the live MiniPC baseline has blocked claim/ASR work and zero public dossiers. It would be
unsafe to treat every configured source, every fixture, or every provider result as a
public dataset.

Stable v1 needs a small, explainable set of sources whose content can traverse the same
contracts without manual database surgery, while sources that are unsupported,
rights-uncertain, provider-blocked, or private remain explicit holds. The launch set also
needs a disclosure contract so a reader can understand source, timestamp, method,
limitations, corrections, and rights without seeing private operational data.

## Outcome

Define and approve a bounded launch-set manifest and snapshot contract that:

- identifies the exact sources, source families, content types, people/roles, and
  acquisition/transcript strategies included at v1;
- proves each included source can move from discovery to a safe public projection or a
  documented blocked/hold state through the same contracts;
- separates source-of-record metadata, public-safe excerpts, evidence metadata, and
  private operational artifacts;
- records rights, platform terms, attribution, retention, privacy, and takedown status
  for every included item and source family;
- discloses method, provider/model/use limitations, statement/evidence time semantics,
  review status, and correction/reanalysis links without leaking private data;
- versions the launch snapshot by configuration, policy, schema, source, and content
  hashes; and
- defines a reversible withdrawal/hold/rollback process with a durable receipt.

This ticket does not select a political coverage set, publish a dataset, or mutate the
production registry. It defines the evidence and owner decision needed to do so later.

## Baseline and evidence limits

- [`PLAN.md`](../../PLAN.md) requires at least three source families to run through the
  same M2 contracts and requires provider failure to remain blocked.
- [`config/source-registry.v1.json`](../../config/source-registry.v1.json) is a
  provisional v0 registry, not an approved launch set. The existing Pulp/Pulp-Grillo
  scaffold and Giuliani example are evidence of paths, not clearance for production
  redistribution.
- [`docs/22-runtime-scheduler-and-omniroute-canary.md`](../22-runtime-scheduler-and-omniroute-canary.md)
  records caption-first discovery, bounded scheduler behavior, and the official
  OmniRoute claim-extraction blocker.
- [`docs/23-claim-extraction-benchmark-and-pulp-scaffold.md`](../23-claim-extraction-benchmark-and-pulp-scaffold.md)
  records the private long-form scaffold and zero claims/findings while extraction is
  blocked.
- [`docs/24-processing-worker-costs-and-health-v0.md`](../24-processing-worker-costs-and-health-v0.md)
  records the current blocked queue, cost caps, private transcript boundary, and health
  digest. These values are evidence, not a launch receipt.
- [`docs/18-storage-retention-and-open-data.md`](../18-storage-retention-and-open-data.md)
  separates operational truth, transient media, and public data; it does not grant
  redistribution rights.
- [`docs/04-legal-safety-research.md`](../04-legal-safety-research.md) and DP-301..DP-307
  leave source terms, privacy, copyright, editorial, and AI disclosure decisions open.
- No W0S/W0R/W0O report files were found in this checkout. If an external report is
  supplied, record its stable ID/hash and the exact claims it supports; do not invent a
  launch-set result.

## Scope

### 1. Launch-set manifest

Create one versioned manifest, owned by this ticket, with one row per included source or
source family. Each row must contain:

- stable `source_id`, family/kind, canonical public name, and platform;
- official/feed/locator URLs or controlled references and access policy;
- expected language, content types, duration/size bounds, cadence, and timezone;
- public-interest relevance rule and any excluded/private-life boundary;
- discovery, transcript, speaker, claim, evidence, and verification path;
- provider/model capability, credential class, cost cap, and blocked-state behavior;
- rights/terms/attribution evidence, source contact/notice, and review date;
- data classes that may be retained, excerpted, projected, or exported;
- health/SLO/error category and owner;
- correction, reply, takedown, and re-analysis path; and
- launch state: `INCLUDED`, `HELD`, `EXCLUDED`, or `REMOVED`, with reason and decision ID.

A source row cannot be `INCLUDED` merely because discovery succeeds. It must have an
approved end-to-end path or an owner-approved safe omission path.

### 2. Coverage and identity contract

The v1 set must be small enough to operate and auditable enough to explain. At minimum,
the acceptance packet must:

- include at least three source families through the shared M2 contracts; if fewer are
  technically possible, keep this ticket `BLOCKED` until the owner explicitly changes
  the canonical M2 exit criterion rather than treating an exception as launch approval;
- cover at least one caption/transcript-first path and one bounded fallback or exclusion
  policy;
- preserve source-family identity, content identity, locator identity, and publication
  timestamps separately;
- use non-biometric speaker provenance for every public claim segment;
- include a bounded real-content fixture for deterministic regression and a separately
  labeled live/provider receipt where required; and
- reject broad crawling, hidden source expansion, and provider-specific public semantics.

The source set is not a ranking of people, parties, or sources. Inclusion/exclusion
decisions must be justified by scope, rights, operability, and evidence quality, not
political preference.

### 3. Snapshot and public disclosure

Define a content-addressed launch snapshot with a manifest containing:

- snapshot ID, candidate commit, policy/schema/API versions, source-registry hash, and
  effective configuration hash;
- included source IDs and effective launch-set decision IDs;
- content/locator/transcript/claim/evidence/finding IDs included in the public projection;
- statement, publication, observation, and cutoff timestamps with their distinct meanings;
- source/evidence hashes and bounded metadata, never raw transcript/evidence bodies unless
  a separate rights decision explicitly permits a bounded excerpt;
- provider/model/receipt references allowed by policy, with method and limitation wording;
- review events, correction/reply/reanalysis links, and public visibility state; and
- omitted/held counts and blocker categories without exposing private omission details.

The public method/disclosure must state that retrieval, approval, verification, review,
and publication are separate; that providers may be unavailable; that findings are
claim-level assessments rather than person-level scores or intent findings; and that
corrections are append-only. It must identify the responsible operator/contact and the
applicable source/rights policy once approved.

### 4. Rights, privacy, and lifecycle

Every source and snapshot row must link to:

- DP-603's license/terms inventory and required attribution;
- DP-304's field classification, relevance, retention, rights, and incident decisions;
- DP-305's transcript/excerpt/media policy;
- DP-306/DP-307's accepted legal decisions; and
- DP-502/DP-503/DP-506 operational backup, retention, and cost evidence.

Raw media, full protected transcripts, private submissions, cookies, credentials,
provider prompts, and internal moderation notes remain outside the public snapshot and
Git. A source can be held or omitted without deleting its durable audit history.

### 5. Withdrawal, correction, and rollback

The manifest must define how an owner or authorized reviewer:

- pauses a source or item when rights, privacy, security, or evidence provenance changes;
- records a public omission or approved correction without silently rewriting history;
- regenerates the static projection and removes stale projection-owned artifacts only;
- re-runs the affected review/reanalysis path;
- records before/after snapshot and artifact hashes; and
- restores the prior known-good snapshot if regeneration or deployment fails.

The rollback receipt is required before a launch snapshot can be called releasable.

## Non-goals

- adding a new source family, provider, model, crawler, browser session, or infrastructure;
- selecting a broad or politically balanced source list;
- bypassing platform terms, access controls, copyright, privacy, or provider capability
  gates;
- publishing a public dataset, website, API, package, or release;
- copying raw/private media or full transcripts into Git or the public snapshot;
- turning a blocked provider, missing credential, or unapproved source into a successful
  empty result;
- deleting source history or a prior snapshot to make the current one appear clean; or
- claiming that a fixture, benchmark, or public metadata record is a verified finding.

## Invariants

- Evidence retrieval, approval, verification, finding review, and publication remain
  separate stages.
- A claim is public only when every supporting segment has approved speaker provenance.
- Public output remains a bounded projection and contains no raw operational body by
  default.
- Future evidence cannot silently judge an earlier statement.
- Provider, rights, privacy, source-health, and budget failures produce holds or
  omissions, not weaker verdicts.
- The public read path remains LLM-free and usable with providers offline.
- The MiniPC remains runtime authority for source, snapshot, and service proof.

## Launch blockers and exact unblock actions

| ID | Blocker | Exact unblock action | Evidence required | Owner/state |
|---|---|---|---|---|
| B-703-01 | M2 live provider path is blocked | Resolve DP-201, DP-202, and DP-203 on the approved official path, or explicitly hold/exclude every affected source with owner-approved safe behavior. | Meaningful canary, one-parent/benchmark receipt, bounded fan-out receipt, cost and quality thresholds. | Maintainer/provider owner; `EXTERNAL` |
| B-703-02 | Remote-ASR capability is blocked | Configure the approved credential outside Git and complete DP-204, or classify ASR-dependent sources `HELD`/`EXCLUDED`. | Live ASR receipt, cost metadata, fallback and sensitive-token hold proof. | Runtime owner; `EXTERNAL` |
| B-703-03 | No approved source set exists | Select a bounded set using the manifest, run rights/privacy review, and record included/held/excluded reasons. If fewer than three source families are proposed, keep the gate blocked until the canonical M2 exit criterion is explicitly changed by the owner. | Signed launch-set decision, at-least-three-family coverage, owner/reviewer acceptance. | Product owner; `PENDING-OWNER` |
| B-703-04 | Source terms/rights are unresolved | Complete DP-603 inventory and DP-305/DP-307 source-specific disposition for every included source. | Exact terms/license evidence, attribution, excerpt permission, retention and takedown decision. | Owner/counsel; `EXTERNAL` |
| B-703-05 | Privacy/public-interest decisions are unresolved | Close DP-304 field/relevance/retention decisions and run projection leak tests. | Field matrix, relevance record, rights workflow, MiniPC private/public read-back. | Privacy owner; `EXTERNAL` |
| B-703-06 | Public method/disclosure is incomplete | Approve method, AI/provider, limitations, correction, contact, and source-attribution copy against the actual snapshot. | Versioned copy and accepted decision IDs. | Product/editorial owner; `PENDING-OWNER` |
| B-703-07 | Snapshot/rollback is unproven | Build a candidate snapshot, regenerate projection, simulate hold/correction, and restore the prior snapshot with a receipt. | Before/after hashes, file list, restore/read-back, operator sign-off. | Maintainer/operator; `BLOCKED` |
| B-703-08 | W0S/W0R/W0O evidence is absent or unlinked | Locate external milestone reports, record stable IDs/hashes and supported claims, or classify the gap `PENDING-OWNER`. | Evidence index and owner disposition. | Coordinator/product owner; `PENDING-OWNER` |

## Acceptance criteria

- [ ] **AC-703.1 — Versioned manifest:** Every included source/family has a unique stable
  ID, family/kind, effective config hash, launch state, rights/privacy status, provider
  path, health owner, and disclosure decision.
- [ ] **AC-703.2 — Bounded coverage:** The launch set has at least three source families;
  every included path traverses shared discovery, transcript, queue, evidence,
  verification, review, and projection contracts or remains explicitly held. Fewer
  families leave the ticket `BLOCKED` until the canonical M2 exit criterion is changed
  by the owner.
- [ ] **AC-703.3 — Provider honesty:** A blocked OmniRoute route, missing Groq
  credential, source access restriction, or budget cap produces the documented
  `BLOCKED`/`HELD` state and no fabricated claim, finding, or public dossier.
- [ ] **AC-703.4 — Rights/privacy:** DP-603, DP-304, DP-305, and accepted M3 decisions
  cover every included source and public field; unresolved rows cannot be marked included.
- [ ] **AC-703.5 — Disclosure:** The method/disclosure copy identifies source and temporal
  semantics, provider/model use and limitations, review status, correction/reanalysis,
  contact path, and no-intent/no-score boundaries without private data.
- [ ] **AC-703.6 — Snapshot integrity:** The snapshot manifest binds commit, source
  registry, policy/schema/API versions, item IDs, timestamps, hashes, review state, and
  omitted/held counts; its public bundle validates against the approved projection schema.
- [ ] **AC-703.7 — Privacy boundary:** Secret/raw-content scans and projection tests show
  no raw transcript/evidence body, credentials, private reply, internal note, or
  unapproved identity field in the snapshot or public output.
- [ ] **AC-703-8 — Correction/hold path:** A rights/provenance change creates an
  append-only hold/correction/reanalysis path, regenerates stale projection-owned
  artifacts only, and preserves prior history.
- [ ] **AC-703-9 — Rollback:** A failed or rejected snapshot can be restored to the
  prior known-good bundle with a durable receipt containing before/after hashes, commands,
  actor, time, and read-back result.
- [ ] **AC-703.10 — Runtime proof:** MiniPC runs the approved source/poll and projection
  path in an isolated canary, records queue/source-health state, and reads back the actual
  public/private result.
- [x] **AC-703-11 — No public side effect:** The specification does not publish a dataset,
  remote, API, website, tag, release, or deployment.
- [ ] **AC-703-12 — Handoff:** DP-704 rehearses the approved snapshot and DP-705 can
  consume its manifest, disclosure, and rollback receipt without guessing missing
  evidence.

## Validation / proof

The implementation receipt must run the standard checks from the candidate commit:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

Then run and record:

1. a source-registry/manifest validation for IDs, family coverage, bounds, terms/privacy
   links, and launch states;
2. a deterministic fixture rehearsal for each included family through discovery,
   transcript/hold, and projection without a paid provider;
3. the approved live path only for the bounded canaries required by DP-201..204;
4. a public-schema and private-data leak scan over the candidate snapshot;
5. a hold/correction/reanalysis and stale-artifact regeneration test;
6. a snapshot build twice with identical hashes and a rollback/restore receipt; and
7. a read-only dependency/collision audit for the M2/M3/M6/M7 graph.

The audit must report every `HELD`, `EXCLUDED`, `PENDING-OWNER`, `EXTERNAL`, and
`BLOCKED` row. A clean discovery run, provider success, or fixture pass is not dataset
clearance or publication authorization.

## Documentation, data, and migration impact

- Add the versioned launch-set manifest, evidence index, disclosure copy, snapshot schema,
  and rollback receipt in the implementing change or controlled operator store.
- Do not edit `PLAN.md`; the existing M7 ordering remains canonical.
- Do not mutate production source rows or publish a dataset in this ticket. A later
  snapshot operation must be separately authorized, use additive/ordered migrations where
  relevant, and include MiniPC proof.
- Do not delete prior snapshots or historical receipts without an explicit retention and
  rights decision. A withdrawal/hold is an append-only event.
- Keep code licensing separate from media, transcript, evidence, and dataset rights.

## Completion receipt

Local preparatory preflight semantics added 2026-10-05 in
`launch-set-candidate-v1` / `launch-snapshot-candidate-v1`. This pure seam validates
synthetic candidate source rows only; it does not select, mutate, approve or publish a
production source set. Candidate rows preserve stable source/family identity and explicit
`INCLUDED|HELD|EXCLUDED|REMOVED` state, bounded rights/privacy/provider gate state, decision
refs, discovery/transcript/speaker/evidence/provider path IDs, health owner, disclosure
decision and per-source config fingerprint. An `INCLUDED` row fails closed unless every
required ref is present and rights/privacy/provider gates are `READY`; a candidate with
fewer than three distinct included source families remains mechanically `BLOCKED`.

The synthetic three-family fixture can reach only `READY_FOR_OWNER_REVIEW`; both manifest
and snapshot objects retain `launch_state=BLOCKED` and `launch_authorized=false`, so no
owner approval is inferred. The snapshot candidate deterministically binds candidate
commit, effective config hash, policy/schema/API versions, all/included source IDs, the
launch-set fingerprint, an externally supplied public-projection fingerprint, and held /
omitted counts. Source-ID or source/global-config changes alter the snapshot fingerprint.
The strict row surface rejects unknown fields (including raw-body style additions), while
the snapshot model has no raw body, credential, secret or owner-approval fields.

A pure rollback receipt candidate binds rejected/restore-target snapshot fingerprints,
expected restore projection fingerprint, actor/reason refs and a deterministic receipt
hash, but is explicitly `NOT_EXECUTED` and non-authorizing. It is therefore preparatory
evidence only, not the durable executed/read-back proof required by AC-703-9.

AC-703-11 is locally proven because the implementation is pure and performs no registry,
projection, deployment, release or network mutation. AC-703.1/.2/.3/.4/.5/.6/.7/.8/.9/.10
and .12 remain open for a real owner-selected launch set, provider paths, qualified
rights/privacy/legal decisions, approved disclosure, actual projection/schema validation,
executed rollback/read-back, DP-704 handoff and MiniPC evidence. Launch state remains
`BLOCKED` exactly as declared at the top of this ticket.
