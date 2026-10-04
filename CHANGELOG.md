# Changelog

All notable user-visible and contract-level changes will be documented here once the
project starts publishing versioned releases.

The format follows Keep a Changelog principles and the project intends to use semantic
versioning for stable public contracts.

## [Unreleased]

No released heading exists yet: this repository has no configured Git remote, tag, or
published package. The version below `## [Unreleased]` is a development snapshot and
makes no compatibility promise. See
[`docs/release/versioning-policy.md`](docs/release/versioning-policy.md).

### Added

- canonical product, domain, architecture, governance, and contribution contracts;
- repo-local milestone/ticket planning for the path to stable v1.
- reduced Public/Verify Studio UX architecture with five public templates and two private
  Studio templates.
- real PEP 517 packaging contract: pinned build backend (`setuptools>=68.0,<81.0`),
  explicit `requires-python` bounds, zero runtime dependencies, bounded development
  dependencies, and `dichiarazioni-pubbliche-*` console scripts (DP-601);
- GitHub Actions matrix across Ubuntu and macOS on Python 3.11/3.12/3.13/3.14, plus a
  web job and a repository-contract job, all read-only and credential-free (DP-602);
- a single deterministic contributor-acceptance entry point,
  `tools/check_contributor_acceptance.py`, requiring no network, credentials, or
  PostgreSQL (DP-602);
- versioned, machine-readable fixture/data licensing inventory with a fail-closed
  checker and a human-readable attribution summary (DP-603);
- release policy: a canonical root `VERSION` file, SemVer/pre-1.0 rules, changelog
  discipline, and a runnable fail-closed release checklist (DP-604);
- role-based onboarding guide with separate contributor, maintainer, and
  operator/integrator paths (DP-605);
- packaging contract tests that fail if a `.v0`/POC identifier is renamed as a side
  effect (DP-601).

### Documentation

- documented the honest limitation that repo-relative config/content paths
  (`--fixtures`, `--registry`, `--audit`) need an explicit path under a non-editable
  wheel install; all modules still import from the install (DP-601);
- documented the `.v0`/POC compatibility surface and its DP-106-owned deprecation path
  (DP-601).

### Known blocked items

- release authority is `BLOCKED` — no canonical Git remote, registry, signing key, or
  confirmed public URL; nothing in this change creates one (DP-604);
- six real public-source fixture rows (Raffaele Giuliani and Beppe Grillo content from
  Instagram/TikTok/YouTube) are `blocked` for redistribution: public availability is not
  a grant, and DP-304/DP-305/DP-306/DP-307 review is required before they may ship
  (DP-603);
- the final public security contact remains an owner decision while no remote exists.

### Security / hardening

- strict claim-extraction type validation for segment indices and boolean fields;
- sanitized remote-ASR 4xx errors so upstream response bodies are not retained;
- verification statement-date provenance cannot be overridden by queued payloads.

### Current baseline

- provenance-first ingestion/transcript pipeline;
- deterministic evidence/verification runtime;
- explicit review and finding publication gates;
- non-biometric speaker provenance;
- fail-closed JSON/JSON-LD/HTML public projection;
- append-only correction and right-of-reply lifecycle;
- MiniPC scheduler/worker runtime.
