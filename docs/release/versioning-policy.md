# Versioning policy

Implements DP-604. Owner: DP-604. Status: **accepted as a policy; no release value
beyond the carried-forward `0.0.1` is authorized.**

## Canonical version source

The single source of truth for the product/package version is the root **`VERSION`**
file: one line, a SemVer string, no `v` prefix, trailing newline.

Everything else derives from it or is checked against it by
`tools/check_version_consistency.py`, which runs in CI and in the release checklist:

| Surface | Derivation | Check |
|---|---|---|
| `pyproject.toml` `project.version` | must equal `VERSION` | `test_packaging_metadata.py::test_version_matches_the_canonical_version_source` |
| `CHANGELOG.md` top released heading | must be `<version> - <ISO date>` | `tools/check_version_consistency.py` |
| `web/package.json` `version` | independent component version (see below) | `tools/check_version_consistency.py` |

A version bump without a matching changelog entry fails the release gate, and a
changelog entry without an accepted implementation and proof fails it in the other
direction. There is no version authority in `pyproject.toml`, `web/package.json`, or a
lockfile; those are derived or checked surfaces.

### Why `VERSION` and not `pyproject.toml`

`pyproject.toml` is the distribution metadata and is rewritten by packaging changes,
`python -m build`, and future migration work. A release identity that can be changed as
a side effect of an unrelated edit is not auditable. A one-line root file has exactly
one writer per release and is reviewable in a one-line diff.

## Version axes (do not infer one from another)

| Axis | Authority | Compatibility meaning |
|---|---|---|
| Product/package version | `VERSION` | distribution and contributor-facing release identity |
| Public schema/API version | DP-105, DP-403 | public field/route meaning; changes independently |
| Policy/verifier version | owning `config/*.json` and policy registry | evidence, review, projection, safety semantics |
| Database schema version | `db/schema.v1.sql` + `db/migrations/*.sql` | persistence compatibility |
| Source revision | Git commit SHA | exact build/review provenance |

A package bump **does not** prove a public API, policy, or database change, and a
public schema change requires its own compatibility decision even when the package
patch number is unchanged. `dichiarazioni-pubbliche-public-v2` is emitted by the projection builder
today; DP-105 has not ratified the stable public v1 decision, so the package version
must not be read as a public-contract version.

### The web component version is independent

`web/package.json` reports `0.1.0` while `VERSION` reports `0.0.1`. This divergence is
**intentional and recorded**, not drift to be silently forced equal:

- the web package is `private: true` and is never published to a registry;
- it has its own toolchain (Astro/React/TypeScript) with an independent lockfile;
- it is a frontend build surface, not a distribution.

Rule: the web version is bumped only when the frontend's own build surface changes
meaningfully, using the same SemVer rules below, and its change is recorded in the
changelog's Documentation/Changed section. `tools/check_version_consistency.py`
asserts only that both versions are valid SemVer, that they are not equal by accident,
and that the divergence is declared in `docs/release/versioning-policy.md` (this file).

## SemVer and pre-1.0 behavior

SemVer applies (`MAJOR.MINOR.PATCH`).

**Before stable v1, every `0.y.z` version is a development snapshot.** It makes no
compatibility promise and must not be described as stable, production-ready, or
"released". Stable v1 requires the `PLAN.md` M-milestone gates plus owner approval;
`VERSION` reaching `1.0.0` is a consequence of those gates, not a substitute for them.

| Bump | Contains | Must not contain |
|---|---|---|
| PATCH | backward-compatible fixes, documentation, dependency bounds that do not change results | any behavior change |
| MINOR | compatible new functionality or a new optional capability, after its dependencies and invariants pass | a silent breaking change |
| MAJOR | breaking package/import contract, breaking public schema/API change, destructive migration, or removal of a documented capability | — |

**A pre-1.0 MINOR bump is not permission for a silent breaking change.** If a
`0.y.z` change is breaking, the changelog entry must say so explicitly under
`Changed` with a `BREAKING:` prefix, and the compatibility note must state the
replacement. Deprecation of a public API follows DP-403's replacement and sunset
policy; the client package cannot hide or reinterpret a deprecation.

### Bumping the version

1. Edit `VERSION` (one line).
2. Add a dated, ticket-linked `CHANGELOG.md` entry per
   [`changelog-policy.md`](changelog-policy.md).
3. If the frontend build surface changed, bump `web/package.json` too and say why.
4. Run `python3 tools/check_version_consistency.py` and
   `PYTHONPATH=poc python3 -m unittest discover -s tests`.
5. Do **not** hand-edit a lockfile to resolve version drift; regenerate it.

Steps 1–5 produce a *candidate*. Publishing it is gate 11 of
[`checklist.md`](checklist.md) and is `BLOCKED` without a canonical remote and owner
approval.

## Version authority handoff (DP-601 → DP-604)

DP-601 records the provisional version sources; this document is DP-604 accepting them:

| Question | Answer | Owner of any future change |
|---|---|---|
| Python distribution version | root `VERSION`, mirrored in `pyproject.toml` | DP-604, per release |
| Web package version | `web/package.json`, independent | frontend changes, per DP-604 rules |
| Supported interpreters | `pyproject.toml` `requires-python` + classifiers | DP-601 |
| Supported Node | `web/package.json` engines / CI matrix | DP-601, DP-602 |
| Runtime vs dev dependencies | `pyproject.toml` `[project]` vs `[project.optional-dependencies]` | DP-601 |
| Public schema version | projection builder + DP-105 | DP-105 |
| Database version | `db/schema.v1.sql` + ordered migrations | DP-107, DP-106 |

## No external side effect

This policy creates no remote, tag, registry artifact, deployment, or publication. The
remote URL, registry, signing authority, and hosting destination are undecided owner
inputs and are not invented here.
