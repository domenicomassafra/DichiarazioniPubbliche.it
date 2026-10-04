# Changelog policy

Implements DP-604. Owner: DP-604.

`CHANGELOG.md` is the contributor- and operator-facing record of what changed and
whether it is safe. It is a release gate input, not marketing.

## Structure

Keep a Changelog section names, used in this order when applicable:

```text
## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security
### Documentation
```

`[Unreleased]` always exists. Released headings are:

```text
## [0.0.1] - 2026-09-26
```

No `v` prefix, ISO `YYYY-MM-DD` date, newest first.

## Required content per release entry

Every release candidate entry must carry all of the following. A missing element fails
the release gate:

1. **ISO date and canonical version** matching `VERSION`.
2. **Ticket IDs** (`DP-###`) for each change, so a reader can navigate to the spec.
3. **Affected contract axis** — product/package, public schema/API, policy/verifier, or
   database migration — stated explicitly. A package-only bump that does not change the
   public contract should say so.
4. **User-visible and operator-visible impact** — what a reader of the public site sees,
   and what an operator running the daemons must do.
5. **Compatibility note** — whether an upgrade breaks anything, and what replaces what.
6. **Migration note** — ordered migrations applied/replayed, or explicitly "none".
7. **Rights note** — new/changed fixtures or data artifacts and their inventory rows, or
   explicitly "none".
8. **Security note** — any security-relevant change, or explicitly "none".
9. **Runtime note** — MiniPC receipt reference when runtime-affecting, or explicitly
   "Mac-only evidence; MiniPC receipt pending" which **blocks** the release for that
   claim.

## Prohibited content

A changelog entry may not contain:

- secrets, tokens, credentials, or connection strings;
- raw transcript bodies, evidence bodies, or private provider responses;
- names or handles of private individuals beyond those already in a public fixture;
- an unverified legal claim, or a rights determination not recorded in the DP-603
  inventory;
- a claim that a Mac-only check proved runtime behavior;
- a benchmark `PUBLISH` label presented as publication authorization. The historical
  POC benchmark prints `PUBLISH` strings; those are regression labels from a legacy
  receipt and are never a publication contract.

`tools/check_version_consistency.py` enforces the structural rules; the content rules
are reviewed at the checklist's human gates.

## Breaking changes

Prefix the entry with `BREAKING:` under `Changed` and state the replacement, even in a
pre-1.0 minor bump. See [`versioning-policy.md`](versioning-policy.md).

## Deprecation and removal

- A deprecation entry names the replacement and the earliest removal version, and
  follows DP-403's sunset policy.
- The provisional package names (`poc/`, `dichiarazioni_pubbliche`) and the temporary
  DP-106 config fallbacks (`config/*.v0.json`) remain compatibility surfaces.
  Canonical database baselines are now `db/schema.v1.sql` and
  `db/job_queue.v1.sql`.
  `config/*.v0.json`) are **deprecated compatibility identifiers**, not removals. Their
  migration is owned by DP-106. Deprecating them here does not schedule their removal,
  and DP-601/DP-602/DP-604 must not delete or rename them.

## Drift rules

| Situation | Result |
|---|---|
| `VERSION` bumped, no changelog entry | release gate **fails** |
| Changelog entry added, no accepted implementation/proof | release gate **fails** |
| Changelog entry dated after the commit it describes | release gate **fails** |
| Version heading disagrees with `VERSION` | release gate **fails** |
| Release entry still listed under `[Unreleased]` at tag time | release gate **fails** |

Enforced by `tools/check_version_consistency.py` (structure) and
[`checklist.md`](checklist.md) (proof and impact).

## Current state

`CHANGELOG.md` has an `[Unreleased]` section and **no released heading**, because no
release has been cut. This is correct, not incomplete. A canonical source remote now
exists, but the first released heading still requires an owner-approved release candidate.
