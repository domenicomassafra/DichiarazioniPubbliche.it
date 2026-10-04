# Release documentation

Authoritative release contracts for Dichiarazioni Pubbliche. These documents implement DP-604
(release/versioning policy) and DP-601 (development environment) and are consumed by
the release gate in [`checklist.md`](checklist.md).

| Document | Owner | Purpose |
|---|---|---|
| [`versioning-policy.md`](versioning-policy.md) | DP-604 | SemVer, pre-1.0 rules, version axes, canonical version source |
| [`changelog-policy.md`](changelog-policy.md) | DP-604 | changelog structure, required content, drift rules |
| [`checklist.md`](checklist.md) | DP-604 | the runnable, fail-closed release checklist |
| [`development-environment.md`](development-environment.md) | DP-601 | profiles, supported versions, install/dev path, `.v0` compatibility surface |

## Current release state

**No release exists.** The canonical source remote is
`https://github.com/domenicomassafra/DichiarazioniPubbliche.it`; there is still no release
tag or published package. Release gates that require registry, signing, legal, dataset or
hosting approval remain blocked until their own evidence is complete.

The current provisional version is `0.0.1`, a development snapshot. Per
[`versioning-policy.md`](versioning-policy.md) it makes no compatibility promise.

## Relationship to the licensing gate

Release gate 5 (Licensing/data) consumes
[`../licensing/fixture-inventory.v1.json`](../licensing/fixture-inventory.v1.json).
A release candidate may not ship a data artifact whose row is unresolved. The two
documents are deliberately separate: this directory owns *when* a release happens,
`docs/licensing/` owns *whether a given artifact may ship*.
