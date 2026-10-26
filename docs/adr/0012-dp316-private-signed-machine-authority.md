# ADR 0012 — DP-316 private signed authority before any public cutover

Status: Accepted for private verification only
Date: 2026-10-26

## Context

DP-316 structural hashes are reproducible by a caller. Existing DP-310/311
reviews concern human-oriented events, while the owner has delegated
qualified legal/privacy/release decisions to independent agents. A blind
conversion of those legacy events or of a SHA digest into a machine approval
would break provenance and revocation.

## Decision

Use an opt-in Ed25519 receipt verifier with a pinned, owner-local 0600
public-key registry outside the database. Receipt v2 requires separate
registered keys and signatures for the independent adjudicator and final
machine authority. Both roles bind the exact source/policy/rights scope; the
adjudicator signs the record, case lineage, challenger/evidence/gold and
expiry, and the final authority signs that payload plus the adjudicator
signature and publication-epoch snapshot. Current time is read internally,
not supplied by the caller. Signature verification is an authenticated
**private** decision; public/dispatch authority stays false. Default mode is
legacy, with explicit registry version and reversible machine-mode toggle.
Neither legacy review nor a signed private receipt is auto-migrated.

Release/public-read promotion requires separate independently verified
gold and qualified policy; a PostgreSQL transaction/read adapter that fences
revocation, registry rotation, correction and expired rights; integration
with existing release gates; and a scoped real consumer proof. These remain
HOLD until implemented and independently reviewed. No human approval loop
is introduced.

## Trade-off

A local registry pinned by trusted deployment config has a small interface
and supports exact rollback; it does require synchronized registry and
database epochs before a live public consumer can trust it. Production
migration before that synchronization is forbidden. The core runtime remains
stdlib-only; cryptography is an explicit existing compatible optional
dependency. No signer credential is shipped.

## References

- [DP-316 issue #494](https://github.com/domenicomassafra/DichiarazioniPubbliche.it/issues/494)
- [ADR 0001](0001-provenance-first-fail-closed-publication.md)
- [DP-316 private receipt and evidence](../ops/dp316-signed-private-authority-20261026.md)


## Versioned cutover contract

The additive machine_authority_cutover_v1 selector makes the legacy path,
shadow comparison and machine-only mode explicit. The production projection
revalidator defaults to LEGACY_ONLY; DUAL_READ cannot promote a shadow
receipt, and MACHINE_V1 returns HOLD because the private receipt loader and
DP-320 final-public-read adapter are not yet connected. A rollback requires
an explicit reference and selects only the legacy path. No live mode is
enabled by this ADR.
