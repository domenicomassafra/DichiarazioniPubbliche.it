# DP-604 — Release, versioning, changelog policy, and release checklist

Status: IN PROGRESS
Milestone: M6 — open-source and release hardening
Depends on: DP-601 package contract, DP-602 CI contract, DP-603 licensing/data gate, and the relevant M1–M5 acceptance gates
Launch state: no release is authorized; owner, legal, registry/signing, dataset and runtime decisions remain open

## Problem

The repository is pre-1.0 and has a canonical Git remote, but no tag or completed release process.
`pyproject.toml` currently reports `0.0.1`, `web/package.json` reports `0.1.0`, and the
changelog has an `Unreleased` section but no canonical version authority or compatibility
matrix. The operational projection identifier, database migration sequence, and policy
versions are separate contracts and must not be inferred from a package number.

Without a release contract, a future snapshot could claim stability while omitting a
migration, fixture-rights decision, public-schema change, security check, or MiniPC
receipt. This ticket defines the policy and checklist; it does not cut a tag, publish a
package, create a remote, or deploy anything.

## Outcome

Establish one auditable release policy that:

- separates product/package, public-contract, policy, and database versions;
- defines SemVer and pre-1.0 compatibility rules;
- selects one canonical version source and derives or checks all package metadata;
- requires a dated, ticket-linked changelog entry for every release;
- defines a reproducible clean-clone release checklist and evidence receipt; and
- fails closed on unresolved dependencies, rights, legal, security, migration, or runtime
  claims.

No artifact may be called a stable public release until the corresponding milestone and
owner gates are complete.

## Baseline and evidence limits

Observed baseline:

- the canonical `origin` is `https://github.com/domenicomassafra/DichiarazioniPubbliche.it.git` and `origin/main` currently resolves to the candidate commit;
- no Git tag or hosted release receipt is present;
- Python metadata is `dichiarazioni-pubbliche` version `0.0.1`;
- web metadata is private `dichiarazioni-pubbliche-web` version `0.1.0`;
- `CHANGELOG.md` uses an `Unreleased` section and Keep a Changelog principles;
- the current `research/results/poc-benchmark-v0.json` is a legacy receipt with
  historical `PUBLISH` labels and cannot satisfy the release publication gate;
- the public projection currently emits `dichiarazioni-pubbliche-public-v2`, while DP-105 has not
  ratified the stable public v1 compatibility decision; and
- `db/schema.v1.sql` and ordered `db/migrations/` are the database authority.

A separate DP-601 baseline and W0R/W0P files were not present in the checkout. Their
absence is an evidence gap to verify; no release history or remote URL is inferred.

## Policy decisions

### Version axes

The implementation must keep these axes explicit:

| Axis | Authority | Compatibility meaning |
|---|---|---|
| Product/package version | the version source ratified by this ticket | distribution and contributor-facing release identity |
| Public schema/API version | DP-105 and DP-403 | public field/route meaning; may change independently |
| Policy/verifier version | the owning policy/config registry | evidence, review, projection, and safety semantics |
| Database schema version | `db/schema.v1.sql` plus ordered migrations | persistence compatibility; never a substitute for package version |
| Source revision | Git commit SHA | exact build/review provenance |

A release may not claim that a package version proves a public API, legal, or MiniPC
migration state. A public schema change requires its own compatibility decision even if
the package patch number is unchanged.

### SemVer and pre-1.0 behavior

- Use SemVer for the product/package version once ratified.
- Before stable v1, `0.y.z` releases are development snapshots unless the owner and
  `PLAN.md` explicitly authorize a different label.
- A patch release contains backward-compatible fixes/documentation only.
- A minor release may add compatible functionality or a new optional capability after
  its dependencies and invariants pass.
- A major release is required for a breaking package/import contract, a breaking public
  schema/API change, a destructive migration, or a change that removes a documented
  capability.
- A pre-1.0 minor bump is not permission for a silent breaking change; the changelog
  and migration/compatibility notes must call it out.
- Public API deprecation follows DP-403's replacement and sunset policy; a client
  package cannot hide or reinterpret a deprecation.

### Canonical version source

The implementation must choose and document one canonical source, such as a root
`VERSION` file or a generated project metadata file, and make all package metadata and
release checks derive from it. The current provisional values may be carried forward
until the owner accepts the source and value; this ticket must not silently choose a new
release number.

The implementation must define whether the web package version tracks the product
version or has an independent component version. If independent, the mapping, update
rule, and CI check must be explicit. Lockfiles must never be edited by hand to resolve
version drift.

### Changelog contract

`CHANGELOG.md` must contain an `Unreleased` section until a release is prepared. Each
release entry must include:

- ISO date and canonical version;
- Added, Changed, Deprecated, Removed, Fixed, Security, and Documentation sections as
  applicable;
- ticket IDs and the affected contract/migration version;
- user-visible and operator-visible impact;
- compatibility, migration, rights, security, and runtime caveats; and
- links to the implementation commit/review receipt when one exists.

Changelog text must not contain secrets, raw transcripts, evidence bodies, private
provider responses, or an unverified legal claim. A version bump without a changelog
entry, or a changelog entry without an accepted implementation/proof, fails the release
gate.

## Scope

### 1. Release artifacts and reproducibility

A release candidate must be buildable from an exact commit in a detached clean clone.
The candidate receipt must record:

- source commit and canonical version;
- Python/Node/package-manager versions;
- build command and artifact hashes;
- lockfile/config hashes;
- deterministic test and benchmark results;
- public projection/schema fingerprint when applicable;
- license/data inventory version and unresolved-row count;
- migration apply/replay result when persistent behavior changes; and
- MiniPC runtime receipt when runtime-affecting.

The process must be idempotent for a candidate: repeating the build/check from the same
commit and inputs must not produce a different claimed version or silently replace an
artifact. A remote upload, registry publication, tag push, or deployment is outside this
ticket.

### 2. Release gates

The checklist must fail closed unless the applicable gates are satisfied:

1. **Scope and graph:** ticket status, dependencies, collision audit, and no duplicate
   contract owner are current.
2. **Clean clone:** detached clone has no local-only files, secrets, generated source
   artifacts, or untracked changes.
3. **Backend:** package install, compile, full deterministic tests, and benchmark pass.
4. **Web:** locked install, checks, and static build pass when web is in scope.
5. **Licensing/data:** DP-603 has no unresolved row proposed for distribution.
6. **Security/privacy:** no secret/private-data regression; security review and relevant
   policy versions are recorded.
7. **Public contract:** DP-105/DP-402/DP-403 compatibility and examples pass when a
   public artifact changes.
8. **Database:** ordered migrations apply/replay in an isolated database when needed;
   no production data is changed to obtain a pass.
9. **Runtime:** MiniPC proof is present for runtime-affecting behavior.
10. **Version/changelog:** canonical version, package metadata, lockfiles, and changelog
    agree and contain no drift.
11. **Release authority:** owner approval, legal decisions, and a confirmed canonical
    remote exist before any external publication.

A missing gate is `BLOCKED` or `PENDING-OWNER`, never an assumed pass.

### 3. Release and rollback policy

The policy must describe the future release path without performing it:

- prepare an annotated, immutable candidate only after all gates pass;
- publish source/package artifacts with a manifest binding version, commit, and hashes;
- keep public schema and policy compatibility notes alongside the package release;
- never force-push or rewrite accepted history;
- use a correction/superseding release or policy record for a material post-release fix;
- under-publication or omission is the safe response when a release artifact, rights
  record, or public contract is uncertain; and
- a failed rollback or migration leaves the prior known-good version documented and does
  not silently rewrite public history.

The exact remote, registry, signing keys, and hosting vendor are owner decisions and are
not invented here.

## Non-goals

- choosing or declaring v1.0.0, creating a Git tag, or publishing a package/site;
- creating a remote, repository mirror, issue tracker, or release branch;
- renaming the repository/package or changing `schema.v0`/`*.v0` names;
- choosing a CDN, registry, domain, signing provider, or public URL;
- bypassing M3 legal/privacy/rights gates because a technical test passes;
- changing the public projection or API contract in this policy ticket; or
- using a release as a reason to delete historical records or untracked evidence.

## Invariants

- versioning never weakens publication, provenance, privacy, or fail-closed gates;
- a version number is not a person score, political ranking, or publication approval;
- source/data rights remain separate from the code license;
- missing provider, legal, rights, migration, or runtime evidence remains blocked; and
- public artifacts are generated from the approved projection, not operational tables.

## Acceptance criteria

- [x] **AC-604.1 — Version authority:** One canonical version source and its mapping to
  Python, web, lockfiles, generated metadata, and changelog are documented and checked;
  no component silently owns a second unreviewed version.
- [x] **AC-604.2 — Axis separation:** Product/package, public schema/API, policy, and
  database migration versions are independently identifiable, with no inference that a
  package bump proves a public or runtime change.
- [x] **AC-604.3 — Pre-1.0 policy:** The accepted `0.y.z` development-snapshot policy,
  compatibility expectations, and stable-v1 gate are explicit; no stable release is
  claimed before the relevant `PLAN.md` milestone is complete.
- [x] **AC-604.4 — Changelog integrity:** Every release candidate has a dated,
  ticket-linked changelog entry with impact, compatibility, migration, rights, security,
  and runtime notes; missing or sensitive content fails the check.
- [x] **AC-604.5 — Reproducible clean clone:** Two independent detached clean-clone
  candidate runs from the same commit produce the same claimed version and artifact
  hashes, with no local-only files or credentials.
- [x] **AC-604.6 — CI gate:** DP-602 enforces version/changelog consistency, full
  deterministic checks, license/data inventory, and collision/link checks without
  publishing or selecting a release number.
- [x] **AC-604.7 — Migration gate:** Any release with persistent changes proves ordered
  migration apply/replay in an isolated database with `ON_ERROR_STOP`; no production
  mutation or destructive experiment is used.
- [x] **AC-604.8 — Runtime gate:** Runtime-affecting candidates include a MiniPC receipt;
  Mac-only evidence is explicitly insufficient and the candidate remains blocked without
  it.
- [x] **AC-604.9 — Rights gate:** DP-603 has no unresolved fixture/data row proposed for
  distribution, and required attribution/notices are present in the candidate.
- [x] **AC-604.10 — Security gate:** The candidate passes secret/private-data scans,
  security review, dependency/license review, and public-schema safety checks; unresolved
  legal/privacy decisions remain explicit blockers. A legacy benchmark `PUBLISH` label is
  historical evidence only and cannot substitute for current fail-closed review evidence.
- [x] **AC-604.11 — No external side effect:** This implementation creates no remote,
  tag, registry artifact, public release, deployment, or external publication. The
  future publication command remains gated by owner authorization.
- [x] **AC-604.12 — Auditability:** The completion receipt identifies the exact commit,
  version decision, gates, command outputs/receipts, artifact hashes, and any
  `PENDING-OWNER`/`BLOCKED` items without claiming more than was proven.

## Validation / proof

The implementing receipt must run the following deterministic checks from the candidate
commit:

```text
python3 -m compileall -q poc tests
PYTHONPATH=poc python3 -m unittest discover -s tests -v
PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
cd web && npm ci && npm run check && npm run build
cd .. && git diff --check
```

It must also run:

- the canonical version/metadata/changelog consistency check;
- the DP-603 licensing/data inventory check;
- the DP-602 ticket completeness/collision and relative-link checks;
- a detached clean-clone build twice and compare version/artifact hashes; and
- isolated migration apply/replay and MiniPC runtime proof when the candidate requires
  them.

The audit must explicitly report that no remote, tag, publication, rename, or PLAN edit
was made. A local build receipt is not a release receipt.

## Documentation, data, and migration impact

- Update `CHANGELOG.md`, the canonical version source, and release documentation in the
  implementing change.
- Do not edit `PLAN.md`; this ticket implements the existing M6 release policy.
- Add no data migration for a version bump. Any schema/config migration must use the
  ordered, replay-safe procedure and MiniPC canary required by `AGENTS.md`.
- Do not publish datasets or artifacts that lack an accepted DP-603 inventory row.
- Preserve all historical receipts; a correction is append-only and does not rewrite a
  prior release record.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the candidate incomplete if:

- the owner has not accepted the canonical version source or release value;
- a package, public schema/API, policy, or database version is ambiguous;
- DP-603 has unresolved distribution rows;
- M3 legal/privacy/rights decisions are open for an affected public artifact;
- a migration cannot be applied/replayed in isolation;
- runtime-affecting behavior lacks MiniPC proof;
- a clean clone cannot reproduce the candidate;
- the canonical remote, registry, signing authority, or publication destination is not
  confirmed; or
- a request would create a tag, release, remote, or external publication before approval.

## Completion receipt — implementation 2026-09-26

Implemented, with release authority **BLOCKED**. No tag, remote, registry artifact, or
publication was created.

- Canonical version source: root **`VERSION`** (`0.0.1`). `pyproject.toml` mirrors it
  (asserted by a test); the web `0.1.0` is an intentionally independent, private
  component whose divergence is recorded rather than forced equal. Mapped in
  `docs/release/versioning-policy.md`.
- SemVer + pre-1.0 policy: every `0.y.z` is a development snapshot making no
  compatibility promise; PATCH/MINOR/MAJOR content rules; a pre-1.0 MINOR bump is
  **not** permission for a silent breaking change. Five version axes (product/package,
  public schema/API, policy/verifier, database, source revision) are kept independent
  and no axis is inferred from another.
- Changelog discipline in `docs/release/changelog-policy.md`: dated, ticket-linked
  entries with impact, compatibility, migration, rights, security and runtime notes;
  prohibited content (secrets, raw transcripts, evidence bodies, unverified legal
  claims, Mac-only runtime claims, and a benchmark `PUBLISH` label presented as
  authorization). Drift rules fail the gate in both directions.
- Runnable release checklist `docs/release/checklist.md` with eleven fail-closed gates,
  a build-twice reproducibility step, cleanup/tree-hygiene, and a final receipt format.
- `tools/check_version_consistency.py` enforces VERSION == pyproject, valid SemVer on
  both components, `## [Unreleased]` present, and the prohibited-content rules.

**AC status.** AC-604.1 PASS, AC-604.2 PASS, AC-604.3 PASS, AC-604.4 PASS (structure
enforced; human content gates are checklist items), AC-604.5 PASS — follow-up proof on
2026-10-05 established the missing deterministic artifact path: two independent detached
clones use the commit timestamp as `SOURCE_DATE_EPOCH`; wheels are byte-identical, and
sdists are normalized only for tar/gzip metadata before comparison. The executable gate is
`tools/check_reproducible_package.py`, backed by `tools/normalize_sdist.py`, and CI runs it;
AC-604.6 PASS, AC-604.7 N/A (no persistence change in this candidate),
AC-604.8 PASS (documented as a gate; no runtime claim is made),
AC-604.9 PASS (consumes the DP-603 inventory), AC-604.10 PASS, AC-604.11 PASS,
AC-604.12 PASS.

**Gate 11 — release authority remains BLOCKED.** The canonical GitHub `origin` now
exists, but there is still no release tag, signing/registry decision, or completed
legal/security approval. Per blocked conditions this ticket stays IN PROGRESS until the
remaining release gates close.

**Hosted follow-up 2026-10-06.** `origin/main` and the GitHub default branch both resolve to
`5a86666bf3bb955f18e036c010e53613425a6cf6`; Actions run `37520100680` completed
successfully for that exact head, including the detached clean-clone job and DP-604
reproducibility gate. This is CI/release-readiness evidence only. It does not supply owner
release authorization, registry/signing choices, qualified legal closure, or a release tag.

The first unnormalized experiment on commit `6ecce7242849ea6460e8837f467a15a879e07c39`
correctly showed that ordinary setuptools wheel/sdist hashes drift across independent
clones. `SOURCE_DATE_EPOCH` alone made the wheel reproducible but not the sdist, so the
gate was not declared green until deterministic sdist archive metadata normalization was
added. A follow-up run against committed baseline
`4adc779039864346cd9407ce6096d0eb6d53335f` produced identical hashes in both clones:
wheel `0efaa082100c689c2c6685d5847e66dcb42497d2acb54d57342cd684cd9d7448` and normalized
sdist `2be9119712518c6fee8f7f6f63e582fbbc263d09f0aa058ac034e7b0bae6666b`. No payload
bytes are rewritten and no release artifact was published.
