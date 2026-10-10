# DP-705 — v1.0.0 release and public deployment gate

Status: FUTURE
Milestone: M7 — stable v1 launch
Depends on: DP-701, DP-702, DP-703, and DP-704
Launch state: BLOCKED until every launch blocker is closed, the owner authorizes release, and the rollback/public-read proof is complete

## Problem

The repository is pre-1.0, has a confirmed canonical source remote, and has no tag or
release receipt. Python metadata, web metadata, policy/schema versions, and database migrations
are separate compatibility axes. The current operational projection is not yet the
ratified stable public v1 contract, the source/provider/legal/rights gates are open, and
the MiniPC baseline has no public dossier. A version string, successful local test, or
static build is not evidence of a stable public release.

This ticket defines the final release/deployment gate and its operator runbook. It does
not perform brand clearance, create a tag or release, publish a dataset, or deploy a
public site in the current work.

## Outcome

Define an auditable v1.0.0 release packet that permits exactly one future decision:

- `NO-GO`: any required blocker, missing evidence, stale decision, failed check, or
  unresolved owner/external action remains;
- `GO-CANARY`: all gates are closed enough for an explicitly authorized, reversible
  staging/canary operation, with a known rollback; or
- `GO-PUBLIC`: all required gates, owner approvals, public-read proof, and rollback
  proof are complete for the selected deployment.

The packet binds the exact candidate commit, version axes, public projection/schema,
policy and rights decisions, source/disclosure manifest, artifacts, runtime receipt,
monitoring state, and rollback receipt. Only an authorized release operator may execute
the eventual `GO-PUBLIC` path. This ticket itself records no launch approval.

## Baseline and evidence limits

- [`PLAN.md`](../../PLAN.md) defines M7 as stable v1 only after DP-701..DP-704 and says
  all launch blockers must close; it does not require every post-v1 business feature.
- The current checkout has canonical `origin`
  `https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git`, but no release tag,
  package publication or deployment receipt.
- `pyproject.toml` reports a provisional package version and `web/package.json` reports
  a separate provisional web version. DP-604 owns the canonical version policy and
  compatibility mapping; no value is inferred here.
- The operational projection currently reports `dichiarazioni-pubbliche-public-v2`, while DP-105 must
  ratify the stable public v1 contract. The v1/v2 decision cannot be hidden in a release
  label.
- [`docs/29-data-provenance-security-hardening-v2.md`](../29-data-provenance-security-hardening-v2.md)
  records MiniPC hardening and zero publishable dossiers, not public launch readiness.
- OmniRoute claim extraction and Groq ASR remain external blockers in the handoff;
  qualified legal/privacy/rights, brand/domain/handle, M5, and release decisions are
  also open.
- No files named `W0S`, `W0R`, or `W0O` were found in this checkout. External reports may
  be linked only by stable ID/hash and must not be treated as release evidence without
  actual read-back.
- The explicit exclusions for this task prohibit brand clearance, public deployment, and
  tag/release creation. The specification therefore ends at a verified gate packet.

## Scope

### 1. Release identity and candidate manifest

Create a versioned release-candidate manifest that records:

- canonical product/package version source and accepted value, including any independent
  web-component version;
- candidate commit, source remote/authority, build environment, Python/Node/package
  manager versions, lockfile/config hashes, and artifact hashes;
- public schema/API, projection, policy/verifier, and database migration versions as
  separate axes;
- DP-601/602/603/604/605 clean-clone, CI, rights, version, and changelog receipts;
- DP-701 identity/rollback decision, DP-702 legal/security/privacy packet, DP-703
  source/disclosure manifest, and DP-704 rehearsal/rollback receipt;
- source/provider capability and cost state, including every `BLOCKED` or held item;
- public deployment target, owner, access boundary, monitoring/contact owners, and
  maintenance window; and
- the explicit decision state (`NO-GO`, `GO-CANARY`, or `GO-PUBLIC`) and signer/date.

A package version is not proof of public schema compatibility, legal acceptance, provider
health, or MiniPC deployment.

### 2. Release gates

The packet must fail closed unless all applicable gates are evidenced:

1. **Graph and scope:** M0..M6 exit criteria and DP-701..DP-704 dependencies are
   complete; ticket/filename/owner collision and dependency-cycle audits pass.
2. **Identity:** brand, domains, handles, repository/package labels, and technical
   rename/deprecation decisions are owner-approved; no unowned public identity remains.
3. **Legal/security/privacy:** DP-306/DP-307 decisions and DP-501..508 applicable
   controls are accepted; no open `BLOCKER`, `PENDING-OWNER`, or `EXTERNAL` row affects
   the selected surface.
4. **Rights/data:** DP-603 has no unresolved row proposed for distribution; DP-703's
   source set, disclosure, retention, rights, and takedown decisions are accepted.
5. **Deterministic quality:** compile, full tests, deterministic benchmark, web checks,
   package install, schema/examples, secret/private-data scan, and ticket audits pass
   from a detached clean clone.
6. **Persistence:** ordered migrations apply/replay in an isolated database with
   `ON_ERROR_STOP`; no production mutation is used to obtain a pass.
7. **Runtime:** MiniPC mirror hash, service/queue/health state, source/provider receipts,
   full rehearsal, correction/reanalysis, and public/private read-back are current.
8. **Public projection:** the selected stable schema/API validates against the candidate
   bundle, serves no private fields, remains usable with providers offline, and fails
   closed on stale/tampered/missing data.
9. **Operations:** SLOs, alerts, health digest, backup/restore, retention, cost caps,
   provider outage, incident escalation, and contact paths are exercised or explicitly
   accepted as non-applicable.
10. **Rollback:** the prior known-good candidate/snapshot restores successfully and the
    receipt is signed by the operator and owner.
11. **Authority:** the product owner authorizes the exact release/deployment, the
    canonical remote/registry/hosting/signing decisions are recorded, and no scope
    expansion is implicit.

A missing gate is `NO-GO` or `PENDING-OWNER`, never an assumed pass.

### 3. Deployment and rollout contract

The future authorized operator must follow a staged, reversible sequence:

1. verify the exact candidate and release manifest;
2. apply the approved migration in the selected environment with `ON_ERROR_STOP` and
   retain the migration receipt;
3. deploy the static/public read artifact and, if selected, the read-only API from the
   approved projection only;
4. run a canary/public-read smoke test for manifest, person/topic/content/relation
   resources, correction history, cache validators, and error behavior;
5. inspect the MiniPC/host logs, health, queue, provider, cost, and private/public state;
6. announce or expose only the approved method/disclosure and correction/contact paths;
7. monitor the agreed SLO/alert window and retain the decision receipt; and
8. if any gate fails, stop rollout, apply the rollback procedure, and classify the result
   `NO-GO` or `GO-WITH-HOLDS`.

The public request path must not call an LLM, query operational tables for content, or
fall back to raw/private data. A static host or read adapter may serve only the approved
projection contract.

### 4. Release rollback and incident handling

The release packet must include a rollback receipt with:

- release/candidate ID, commit, version axes, target, operator, and timestamps;
- pre/post database migration and public-bundle hashes;
- backup/snapshot ID and verified restore location;
- exact rollback/hold/omission commands and their exit codes;
- public/private read-back and health/queue state after rollback;
- cache/CDN invalidation or safe retention decision, if a host is selected;
- incident owner, communication decision, and residual blocker; and
- explicit confirmation that prior public history, findings, corrections, replies, and
  review receipts were not silently deleted or rewritten.

A rollback that cannot restore the prior known-good state is a failed release gate, not a
reason to continue serving a possibly unsafe bundle.

## Non-goals

- brand clearance, trademark registration, domain purchase, or handle reservation;
- creating a Git remote, tag, release, package publication, dataset publication, website,
  API deployment, or public intake route in this specification work;
- choosing a hosting/CDN/registry/signing vendor without owner authorization;
- renaming the package, repository, schema, or public identifiers;
- adding a migration, provider, worker, admin service, or infrastructure not required by
  an accepted ticket;
- changing product, legal, privacy, rights, or publication semantics to fit a date;
- treating a local/Mac pass, fixture, benchmark `PUBLISH` label, or empty projection as
  public proof; or
- promising a response time, uptime, compliance status, or launch date not accepted by
  the owner.

## Invariants

- No false launch claim: an unclosed blocker keeps the release state `NO-GO`.
- No automatic publication or fallback verdict under provider, legal, rights, security,
  budget, or runtime failure.
- Public output is sanitized, versioned, projection-only, and LLM-free.
- Public reads remain available from the approved projection when providers are offline.
- Historical public records, corrections, replies, and review events are append-only.
- A version number never proves legal, rights, provider, migration, or runtime state.
- The MiniPC is runtime authority; a Mac or local deployment result is development
  evidence only.

## Launch blockers and exact unblock actions

| ID | Blocker | Exact unblock action | Evidence required | Owner/state |
|---|---|---|---|---|
| B-705-01 | DP-701 identity/clearance packet is open | Complete the owner brand/domain/handle decision and qualified disposition; close technical rename/rollback actions. | Decision IDs, clearance/evidence references, collision audit, accepted mapping. | Owner/counsel; `EXTERNAL` |
| B-705-02 | DP-702 legal/security/privacy packet is open | Close DP-301..307 and applicable M5 controls, or keep the affected surface disabled and record the decision. | Accepted decisions, security/restore/retention/SLO/cost/failure receipts, contact/runbook. | Owner/counsel/operator; `EXTERNAL` |
| B-705-03 | DP-703 source/data/disclosure packet is open | Approve the bounded source set, rights/privacy decisions, disclosure, snapshot, and rollback. | Source manifest, snapshot hashes, disclosure version, rollback receipt. | Product owner; `PENDING-OWNER` |
| B-705-04 | DP-704 rehearsal is incomplete | Run the full MiniPC success, failure, correction, and rollback paths and obtain the signed decision. | Stage/failure receipts, actual read-back, `ROLLBACK_VERIFIED`, `GO-*` decision. | Runtime owner; `BLOCKED` |
| B-705-05 | M2 provider capability is blocked | Close DP-201..204 for the selected launch set or formally hold/exclude every affected path. | Provider/cost/fallback receipts and source-specific disposition. | Provider owner; `EXTERNAL` |
| B-705-06 | Stable public schema/API is not ratified | Close DP-105 and required DP-401..410 contracts; validate JSON, JSON-LD, HTML, and API against the same projection. | Schema/API/version/deprecation receipts and public field allowlist. | Maintainer; `BLOCKED` |
| B-705-07 | M5 controls are incomplete | Implement/prove DP-501..506 and decide DP-507/508 applicability. | Security, restore, retention, SLO, alert, cost, and incident receipts. | Operator; `BLOCKED` |
| B-705-08 | M6 release authority is incomplete | DP-601/602/603/605 are implemented; close DP-604's release-authority gate and any still-applicable DP-606/607 launch dependency for the exact candidate. | Reproducible candidate, inventory, version policy, changelog, clean-clone receipt, and owner release decision. | Maintainer/owner; `BLOCKED` |
| B-705-09 | Registry/hosting/signing/release authority is unapproved | The canonical GitHub remote is confirmed; owner must still confirm the exact publication destinations and least-privilege release/signing authority. | Controlled decision record; do not invent URLs, registries, hosts, signing identities, or keys. | Product owner; `PENDING-OWNER` |
| B-705-10 | Rollback or incident path is unproven | Restore the prior candidate/snapshot, verify public/private state, and obtain operator/owner sign-off. | Rollback receipt, hashes, read-back, incident owner. | Operator; `BLOCKED` |

A blocker is closed only by linked evidence and owner acceptance. Deleting a blocker row,
changing a version number, or adding a disclaimer is not an unblock action.

## Acceptance criteria

- [x] **AC-705.1 — No false claim:** The packet reports `NO-GO` while any required gate,
  external decision, owner action, provider capability, rights row, or runtime proof is
  open; it never describes the baseline as launchable.
- [ ] **AC-705.2 — Version authority:** One canonical version source and its mapping to
  package/web metadata, lockfiles, projection/schema/API, policy, and database migration
  versions are documented and checked; the value `1.0.0` is not hard-coded by this spec.
- [ ] **AC-705.3 — Identity/legal/rights:** DP-701 and DP-702/DP-703 decisions are
  accepted, current, and linked to the exact candidate; no unresolved public name,
  legal, privacy, copyright, platform, or data-rights row affects launch.
- [ ] **AC-705.4 — Clean candidate:** A detached clean clone from the exact candidate
  passes package install, compile, full tests, benchmark, web checks, schema/examples,
  inventory, secret/private-data, link, and ticket collision/cycle audits.
- [ ] **AC-705.5 — Migration/runtime:** Ordered migrations apply/replay in isolation;
  MiniPC mirror, services, queue, health, provider receipts, and public/private read-back
  match the candidate receipt.
- [ ] **AC-705-6 — Projection safety:** The candidate public projection is sanitized,
  versioned, stable-contract compatible, provider-offline usable, and fail-closed on
  missing/stale/tampered/incompatible state.
- [ ] **AC-705-7 — Rehearsal and correction:** DP-704's success, failure, correction/
  reanalysis, and replay receipts are complete and signed.
- [ ] **AC-705-8 — Rollback:** The release packet contains a tested rollback receipt with
  pre/post hashes, restore commands, read-back, incident owner, and preserved history.
- [ ] **AC-705-9 — Authority:** The product owner records the exact release/deployment
  authorization, target, maintenance window, monitoring owner, and go/no-go decision.
- [ ] **AC-705-10 — No unapproved side effect:** This ticket does not clear a brand,
  create a tag/release, publish a package/dataset, create a remote, or deploy a public
  service; any such action is a separately authorized execution.
- [ ] **AC-705-11 — Post-release criteria:** The future operator defines canary smoke,
  SLO/alert window, rollback threshold, correction/contact path, and final read-back;
  failure moves the state to `NO-GO`/`GO-WITH-HOLDS`, never silent continuation.
- [ ] **AC-705-12 — Audit handoff:** DP-704 and the M7 packet can be independently
  checked from stable IDs, hashes, and sanitized receipts without reading private
  evidence bodies or privileged advice.

## Validation / proof

The release-candidate receipt must run, from the exact candidate commit:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm run check && npm run build
cd .. && git diff --check
```

It must additionally include:

1. detached clean-clone package/import/CLI/web/demo proof;
2. canonical version/metadata/changelog consistency and DP-603 inventory checks;
3. ticket completeness, dependency-cycle, filename-ID, owner, and public-contract
   collision audits;
4. schema/examples/API/public projection validation and private-data scans;
5. isolated migration apply/replay with `ON_ERROR_STOP` when applicable;
6. DP-704 MiniPC full rehearsal, failure, correction, replay, and rollback receipts;
7. selected-host canary smoke and rollback/read-back in the future authorized execution;
8. a release decision record with all open/closed blockers and signer/date.

The receipt must explicitly state that no brand clearance, public deployment, tag, or
release was performed by this specification. A local build, empty public projection, or
legacy benchmark `PUBLISH` label is not release proof.

## Documentation, data, and migration impact

- Add the release-candidate manifest, gate index, deployment runbook, rollback receipt,
  and post-release checklist in the implementing/authorized release change.
- Do not edit `PLAN.md`; M7 sequencing remains canonical.
- Do not create a version bump, tag, remote, package, dataset, or public deployment in
  this specification. DP-604 and the owner own the final version/release value.
- Any migration required by the candidate follows the ordered, replay-safe procedure and
  isolated/MiniPC proof. Never mutate production data to make a release check pass.
- Preserve public history and audit receipts. A rollback or correction is append-only and
  must not silently rewrite prior records.
- Keep code license, data/content rights, brand/domain ownership, and provider terms as
  separate release gates.

## Completion receipt

Pending DP-701..DP-704 closure, M2..M6 exit evidence, owner release authority, clean
candidate proof, MiniPC runtime/rehearsal/rollback receipts, and an explicit go/no-go
decision. This ticket does not claim brand clearance, public deployment, a v1.0.0 tag,
or a stable public release.

### Local no-false-release preflight receipt — 2026-10-05

The repository now has a side-effect-free `launch-preflight-v1` checker wired into the
standard contributor acceptance path. It binds current ticket/legal/evidence state into a
deterministic receipt and reports `NO-GO` while any required gate is incomplete. Even a
synthetic state with every mechanical gate complete can reach only `PENDING-OWNER`; the
checker can never authorize `GO-CANARY` or `GO-PUBLIC`. Version strings, local tests and a
package/web build therefore cannot satisfy release authority. This proves AC-705.1 only;
all remaining release, rehearsal, rollback, owner and deployment ACs stay open.

## Checkpoint 2026-10-10 — future activation boundary

Keep FUTURE until all v1 gates close and explicit release authority, migration/release artifact, rollback and live readback are accepted. A clean pushed `main` or refreshed six-page informational site is NOT v1.0.0 deployment.
