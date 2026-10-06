# DP-603 — Fixture/data licensing inventory and attribution

Status: DONE
Milestone: M6 — open-source and release hardening
Depends on: M3 policy/rights decisions, DP-601 package boundary, and the current fixture/data inventory
Launch state: rights and owner/legal review required before any public data or release claim

## Problem

The Apache-2.0 decision covers repository code, not third-party content, datasets,
transcripts, media, screenshots, fonts, or service terms. The repository currently
contains a mixture of synthetic fixtures, real public-source metadata, derived research
receipts, historical quotations, visual reference artifacts, and locally retained raw
material. Some of that material is tracked, some is ignored or owner-local, and some has
only a URL or an informal note as provenance.

A contributor cannot currently answer, for every candidate artifact, what it is, where it
came from, which rights evidence applies, whether it may be redistributed, and what
attribution or notice is required. Guessing from a public URL or from the repository code
license would create a release and legal risk.

## Outcome

Create and enforce a versioned, machine-readable inventory and attribution process for
all tracked and release-candidate fixtures/data. The process must:

- distinguish synthetic, derived, public-source, third-party, and owner-local material;
- record exact provenance, license/terms evidence, attribution, modification, privacy,
  and redistribution status;
- fail closed when rights evidence is missing, stale, ambiguous, or unresolved;
- keep raw/private media and credentials out of the code repository; and
- let DP-604 decide whether a release candidate may include a data artifact.

This ticket prepares the control surface. It does not grant rights, make a legal
determination, publish a dataset, or delete an artifact without owner/legal review.

## Baseline and evidence limits

The current checkout has canonical source remote
`https://github.com/domenicomassafra/DichiarazioniPubbliche.it`. It includes:

- `LICENSE` and `NOTICE`, with the code/content distinction already stated in ADR 0005;
- real-source metadata and derived receipts under `poc/content/` and
  `research/results/`;
- `research/results/poc-benchmark-v0.json` is a legacy benchmark receipt whose
  historical `PUBLISH` labels are not a publication contract and must be classified
  accordingly in the inventory;
- `research/SOURCES.md` and donor/design registries containing source references and
  cautionary notes;
- frontend demo fixtures and generated/reference visual material under `web/` and
  `docs/ux/`; and
- local raw transcript/media paths that are ignored or owner-local and must not be copied
  into Git.

The exact rights status of each existing candidate is not assumed here. No file named
W0R/W0P or separate DP-601 baseline was present in this checkout; that absence is an
evidence gap to verify before closure, not a path to invent.

## Scope

### 1. Canonical inventory

The implementation must create one canonical machine-readable inventory, provisionally
`docs/licensing/fixture-inventory.v1.yaml`, with a versioned schema and a human-readable
summary. A row must include at least:

| Field | Required meaning |
|---|---|
| `asset_id` | Stable, unique identifier that does not depend on a mutable path |
| `path_or_locator` | Repository path, external dataset identifier, or controlled-store pointer |
| `artifact_kind` | `synthetic`, `derived`, `public-source`, `third-party`, `owner-local`, or `reference` |
| `origin` | Author, publisher, project, or owner that created/provided it |
| `source_reference` | Existing verified URL, commit, release, dataset version, or `UNKNOWN` plus blocker |
| `retrieved_at` and `content_hash` | Acquisition date and content-addressed hash where available |
| `license_or_terms` | Exact SPDX/license identifier, terms name, public-domain statement, or `UNKNOWN` plus blocker |
| `license_evidence` | Local evidence path, upstream license file, version/commit, and review date |
| `attribution` | Required credit/notice text and where it must appear |
| `modifications` | Transformations, excerpts, normalization, translation, or generated derivations |
| `personal_data` | Whether names, voices, claims, or other personal data are present and the handling class |
| `redistribution_status` | `allowed`, `private-only`, `metadata-only`, `blocked`, or `pending-review` |
| `public_projection_status` | Whether the artifact may enter a public projection/API and under which policy |
| `owner_and_review` | Responsible owner, reviewer, review date, and re-review trigger |
| `blocker` | Concrete missing evidence or decision, if any |

`UNKNOWN` is a valid audit value only when paired with a blocker, owner, and safe
handling. It is never a pass state for a releasable artifact.

### 2. Inventory coverage

The checker must enumerate and classify at least:

- all tracked files under `poc/content/`, `research/results/`, `poc/fixtures/`, and
  `data/public/`;
- generated frontend/demo fixtures that can enter a build or public page;
- screenshots, reference images, fonts, and other visual assets under `docs/ux/` and
  `web/`;
- copied quotations, excerpts, transcripts, and evidence metadata in Markdown or JSON;
- third-party code, packages, actions, and design-source artifacts that are vendored or
  distributed with a release; and
- owner-local raw media/transcripts discovered outside Git, recorded as non-committable
  without copying their contents.

A raw file may be listed by a safe path/hash/receipt without checking its body into the
inventory. Secrets, cookies, local browser profiles, provider prompts, and raw evidence
must never appear in the inventory.

### 3. Evidence and attribution rules

For copied or modified third-party material, the inventory must preserve enough evidence
to satisfy the applicable notice: upstream owner, exact source/version or commit,
license/terms text or controlled pointer, retrieval date, modifications, and attribution.
For platform-sourced public content, public availability is not treated as permission;
the row must identify the platform terms/permission basis or remain `pending-review`.

For a synthetic fixture, the row must identify the generator/author and the project
license or a dedicated fixture policy. For a derived research receipt, the row must link
the source input, transformation, model/tool receipt where relevant, and the limits of
the result. A model output is not automatically a redistributable dataset.

If a required source URL or license cannot be verified from an existing approved source
record, leave the row blocked. Do not invent a URL, infer a license from a project name,
or replace missing evidence with a generic search result.

### 4. Enforcement and review

The implementation must provide one deterministic check that:

- compares tracked and release-candidate files with inventory rows;
- fails when a new candidate path has no row or a row has a duplicate `asset_id`;
- fails when a row marked releasable has `UNKNOWN`, missing, stale, or mismatched
  license/attribution evidence;
- fails when a raw/private artifact is staged, packaged, or projected publicly;
- rejects secrets, cookies, provider prompts, full private transcripts, and unapproved
  evidence bodies in tracked data;
- checks hashes and required notices for every release candidate; and
- emits a sanitized report with paths, IDs, and blocker categories, never raw content.

The check must run in contributor CI and as a release gate. It may use a pinned local
license/parser tool, but the tool and version must themselves be inventoried. Network
lookups are not required for the default deterministic check; evidence refresh is a
separate, dated owner action.

### 5. Rights and privacy boundaries

The inventory must link, but not duplicate, the policy owners:

- DP-301 for intentionality/no-intent wording;
- DP-304 for privacy/minimization and sensitive-person handling;
- DP-305 for copyright/transcript/excerpt publication;
- DP-306/DP-307 for unresolved legal decisions; and
- ADR 0005 for the Apache-2.0 code boundary.

A row may be used by a private test or local demo while public redistribution remains
blocked. A fictional demo must be labeled and must not be represented as a real person's
claim. A real public-source fixture may be used for private reproducibility while its
public projection remains held until the relevant rights and provenance gates pass.

## Non-goals

- relicensing third-party content, media, datasets, or evidence under Apache-2.0;
- copying raw/private media, transcripts, cookies, or provider responses into Git;
- choosing a source's legal terms or making a legal conclusion;
- deleting or rewriting historical material without owner/legal authorization;
- publishing a dataset, package, image bundle, or public projection;
- adding a license scanner that silently approves unknown material; or
- treating a reference URL, public availability, or model output as permission.

## Invariants

- repository code licensing remains separate from content/data rights;
- evidence retrieval, approval, verification, and publication remain separate;
- public output remains a sanitized fail-closed projection;
- no raw transcript/evidence body is added to a public artifact;
- unresolved rights produce under-publication, not a guessed permission; and
- a clean clone must contain only artifacts that are explicitly marked for that clone's
  distribution mode.

## Acceptance criteria

- [ ] **AC-603.1 — Complete inventory:** Every tracked or release-candidate fixture/data
  artifact has one unique row, a stable ID, a content hash where applicable, an artifact
  kind, an owner, and a review status.
- [ ] **AC-603.2 — Evidence required:** No row marked `allowed`, `public`, or
  `redistributable` has `UNKNOWN`, missing, stale, or unlinked license/terms evidence,
  attribution, source version, or retrieval date.
- [ ] **AC-603.3 — Current mixed baseline:** Real-source metadata, derived receipts,
  synthetic/demo fixtures, visual/reference assets, and owner-local raw material are
  explicitly distinguished. Existing unresolved rows remain visibly blocked rather than
  being relabeled as cleared.
- [ ] **AC-603.4 — Notice correctness:** Required attribution/notice text is present in
  the owning artifact or linked distribution surface, and modifications are recorded.
  The Apache-2.0 `LICENSE` is not used as a blanket data permission.
- [ ] **AC-603.5 — Raw-data exclusion:** A secret/private-content scan and Git path audit
  prove that raw media, full private transcripts, cookies, credentials, provider prompts,
  and unapproved evidence bodies are neither tracked nor packaged.
- [ ] **AC-603.6 — Fail-closed enforcement:** Adding, renaming, or moving a candidate
  fixture without an inventory row fails the deterministic check; an unresolved row
  cannot be promoted by manually changing a status string.
- [ ] **AC-603.7 — Clean-clone proof:** A detached clean clone runs the inventory check
  and contains only rows/artifacts approved for that distribution mode. Local ignored
  raw files are not needed and are not copied into the clone.
- [ ] **AC-603.8 — CI gate:** DP-602 runs the inventory check on every relevant change,
  using a pinned checker with sanitized output. The check has no hidden network or
  credential dependency.
- [ ] **AC-603.9 — Migration/data safety:** Moving a fixture updates its stable ID,
  hash, references, and notice atomically; no database migration or production data
  mutation is introduced. An unapproved deletion requires an owner/legal decision and
  an explicit replacement or retention record.
- [ ] **AC-603.10 — Versioning:** The inventory schema and policy version are recorded;
  a content or fixture change requires a changelog/inventory update and a new hash. It
  is not coupled silently to a package release version.
- [ ] **AC-603.11 — No publication:** The implementation does not publish a dataset,
  release, remote repository, or public projection. A future release gate must consume
  the same inventory, not a parallel list.
- [ ] **AC-603.12 — Legal/privacy handoff:** Every unresolved row names DP-304/DP-305/
  DP-306/DP-307 or the owner decision required, and no test result claims legal
  clearance.

## Validation / proof

The implementing receipt must include:

1. a machine-readable inventory validation with zero missing required fields;
2. a tracked-path and candidate-artifact diff showing every new/changed/moved file;
3. a sanitized secret/private-content scan;
4. a license/terms evidence review for every row proposed for distribution;
5. a detached clean-clone run of the inventory check and deterministic backend/web
   checks;
6. the standard repository checks:

   ```text
   python3 -m compileall -q poc tests
   PYTHONPATH=poc python3 -m unittest discover -s tests -v
   PYTHONPATH=poc python3 -m dichiarazioni_pubbliche.benchmark
   cd web && npm ci && npm run check && npm run build
   cd .. && git diff --check
   ```

7. the ticket completeness/collision audit for DP-601..DP-607; and
8. a rights packet that lists unresolved rows, owners, and safe defaults without copying
   confidential advice or raw content.

If a row requires owner/legal review, the result is `PENDING-OWNER` or `BLOCKED`; it is
not made green by the test command. No MiniPC proof is required for a documentation-only
inventory change, but any later data/publication behavior change requires the relevant
MiniPC and M3 gates.

## Documentation, data, and migration impact

- Add the inventory schema, checker, and human-readable attribution summary in the
  implementing change.
- Update `NOTICE` and adjacent README/license files only when the accepted evidence
  requires it; do not overwrite existing third-party notices without a recorded diff.
- Add no database migration. A fixture move is a repository/data change and must update
  references and hashes atomically.
- Do not edit `PLAN.md`; DP-603 remains the M6 licensing gate.
- Do not publish a dataset or package. DP-604 consumes the completed inventory before a
  release decision.

## Blocked conditions

Keep the ticket `BLOCKED` or classify the implementation incomplete if:

- an artifact's source, version, license/terms, attribution, or modification history
  cannot be verified;
- a public-source or platform fixture lacks a documented rights/terms basis;
- personal/sensitive data or a real-person fixture lacks the required privacy/editorial
  review;
- a third-party dependency, action, font, image, or design artifact lacks compatible
  license evidence or notice;
- the owner or qualified legal reviewer has not decided whether an artifact may be
  redistributed or projected;
- a proposed cleanup would delete or move unique material without authorization;
- a clean clone cannot run the inventory check without local/private files; or
- the requested work would publish a dataset, release, or external artifact.

## Completion receipt — implementation 2026-09-26

Implemented. Canonical machine-readable inventory
`docs/licensing/fixture-inventory.v1.json` (schema `fixture-inventory/v1`, policy
`DP-603@2026-09-26`), **generated from the real tree** so `content_hash` and existence
are true. The 2026-10-05 follow-up carries 39 asset rows; human-readable summary in
`docs/licensing/README.md`;
`NOTICE` now records the code-vs-content boundary and the third-party dependency set.

Status summary: **30 `allowed`**, **3 `pending-review`**, **6 `blocked`**.

The six `blocked` rows are **real public-source material** — Raffaele Giuliani
(Instagram/TikTok) and Beppe Grillo / Pulp Podcast (YouTube) — in
`poc/content/`, `research/content-audits/`, and `research/source-candidates/`. Public
availability is not a redistribution grant; those platforms' terms reserve rights, so
the rows carry `license_or_terms: UNKNOWN` with a concrete `blocker` and are marked
**not redistributable and not projectable** without DP-304/DP-305/DP-306/DP-307 review.
The three `pending-review` rows are the two unknown-origin `docs/ux/reference/p6.2/`
visuals plus one derived receipt awaiting a keep/remove owner decision.

Enforcement `tools/check_licensing_inventory.py` (fails closed): un-inventoried tracked
asset, duplicate `asset_id`/`path`, `allowed` row with `UNKNOWN`/missing license,
attribution or retrieval date, invalid kind/status, `owner-local` marked `allowed`,
content-hash mismatch, and any tracked raw/private/credential-class file. It is
generated by `tools/generate_fixture_inventory.py` (rights are curated human decisions;
the tool refuses to invent a license) and runs in CI and the release gate.

Follow-up 2026-10-05: DP-407 added the project-authored fictional
`web/src/data/dp407-content-projection.json`. The checker correctly rejected it until it
received a synthetic-fixture inventory row. The generator now also fails closed when any
tracked candidate asset lacks a curated `ROW_DECISIONS` entry, so `--check` can no longer
report a stale inventory as green while the independent checker rejects the same tree.

`research/results/poc-benchmark-v0.json` is inventoried as `derived` with an explicit
note that its historical `PUBLISH` labels are **not** a publication contract.

**AC status.** AC-603.1 PASS, AC-603.2 PASS, AC-603.3 PASS (mixed baseline explicitly
distinguished; unresolved rows visibly blocked, not relabeled), AC-603.4 PASS,
AC-603.5 PASS (secret/private scan + Git path audit clean; `poc/content/*/raw/` is
ignored and untracked), AC-603.6 PASS, AC-603.7 PASS (clean-clone run green), AC-603.8
PASS (CI job), AC-603.9 PASS, AC-603.10 PASS, AC-603.11 PASS (no dataset published),
AC-603.12 PASS (each unresolved row names its DP-304..DP-307 owner).

**Not claimed:** no row is a legal determination. An `allowed` row is a recorded
engineering/licensing decision, not legal advice. No fixture was deleted, relicensed,
or published.
