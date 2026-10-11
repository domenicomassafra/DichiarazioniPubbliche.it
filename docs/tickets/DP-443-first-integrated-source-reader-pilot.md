# DP-443 — First complete source-to-reader and correction pilot

Status: FUTURE
Milestone: M4 — public product/API
Depends on: DP-235, DP-312, DP-314, DP-316, DP-317, DP-318, DP-320, DP-321, DP-435, DP-436, DP-437, DP-438, DP-439, DP-440

## Problem

The existing approved-empty public preview and component-level green tests do not prove one real, lawful end-to-end path from source acquisition to original public Statement, optional fact verification, comparisons, Persona × Tema, correction and replay. Bulk historical ingestion must not precede that proof.

## Outcome

Deliver one bounded, signed, real-source pilot with both a positive eligible path and credible negative holds, ending with an explicit GO/NO-GO decision on scaling. This is not v1 public-launch authorization.

## Traceability & constraints

R01, R02, R04–R08, R11–R20, R24–R29, R38–R42; Q9–Q20. Preserve exact original words, separated synopsis/translation, source-use rights, independent facts, speech-act context, non-biometric identities, private/public boundary, immutable lineage, qualified authority and historical DONE receipts.

## Scope

Freeze a small permitted multi-person/language/source matrix. Exercise real Capture→Passage→Candidate, source hash/locator, speech-act and role semantics, verified factual outcome or justified abstention, independent opinion-only Statement, exact public quote, Person/Topic intersections, precomputed dated citations, correction/revocation, output-version and rollback readback. Missing media/source rights or failed evidence remain specifically blocked; no fabricated permit or source. Historical Garlasco 100-item, three-family launch and mega backfill remain separate.

## Non-goals

No bulk crawler, artificial rights clearance, unapproved production publication, implied human approval, self-graded model truth or owner-selected redesign.

## Dependencies and sequencing

Hard dependencies above establish private source, semantic/verification and versioned public contracts. External gates are actual source/use permissions, qualified legal and owner public approval, paid-provider consent if needed, official runtime authority and a real MiniPC readback. DP-243/516 historical expansion must not start before this ticket's explicit accepted GO-for-scaling.

## Acceptance criteria

- [ ] `AC-443.1`: Signed manifest fixes selected real People, sources, language/format, approved use, expected facts/opinions, blocked arms and benchmark references before the pilot.
- [ ] `AC-443.2`: MiniPC store and approved reader reconstruct real source→literal statement source span/version/hash→public API/HTML/search/linked-data consistently, with separate translation/summary, no private leakage.
- [ ] `AC-443.3`: One checkable factual inquiry yields proven result or demonstrated insufficient evidence; a separately approved opinion without Finding is publicly distinguishable, and context/false-attribution negative cases HOLD.
- [ ] `AC-443.4`: Approved Person×Topic intersection, citation-linked synthesis and safe cross-person or longitudinal relation work without request-time LLM; unsupported conclusions are omitted.
- [ ] `AC-443.5`: Corrections, replies, rights revocation and replay update static/site/API/search/cache to one fingerprint and never resurrect unsafe excerpts.
- [ ] `AC-443.6`: Independent gold/error/abstention metrics, qualified publishing authority, privacy review, operation ledger, cost and rollback are evidenced; no forged machine reviewers.
- [ ] `AC-443.7`: An explicit signed GO/NO-GO with real host/commit/rights/source hashes and scope allows or blocks later historical scaling; local fixtures or informational-only preview alone are NO-GO.

## Validation / proof

Future authorized immutable source receipts, MiniPC DB→web/API readback, negative privacy/rights tests, cost ledger, correction/revocation race and rollback. This source-only tranche performs none of those operations.

### Source-only readiness contract — 11 October 2026

`poc/dichiarazioni_pubbliche/first_integrated_pilot_readiness_v1.py` now provides
`evaluate_first_integrated_pilot_readiness(manifest, lineage, proofs)`. It accepts a
**single-sample** frozen `PrivatePilotManifest` from DP-235 and source-only
`PilotLineage` plus bounded, *externally attested but locally unauthenticated*
`PilotProof` references. The lineage binds source/version, Capture, Passage,
original quote, Statement, Git commit, MiniPC host and **distinct** before,
correction and withdrawal projection fingerprints. The sample's DP-235
source/version/rights scope and proposed-state validation must pass.

Twenty positive proof categories require an external reference, signer and digest
for manifest, rights, Capture/Passage, original Statement, factual
result/abstention, separate opinion, Person×Topic, API/HTML/search/linked-data,
correction/reply, revocation, MiniPC reader/DB readback, independent gold,
legal/privacy/editorial review, costs/rollback and explicit scaling decision.
Five negative `HOLD` categories cover unauthorized rights, misattribution,
unsupported inference, revoked replay and private-body leakage. Each stage
must bind to the same immutable manifest/lineage fingerprint; duplicate/stale
receipts, wrong MiniPC host and reused qualified signer are held. Receipts
are never fetched, signed or verified by this source-only module.

**The returned disposition is always `NO-GO`; `scaling_authorized` is always
`False`.** `packet_complete=True` means only that every prescribed receipt
*slot and binding* was supplied with structurally valid metadata, **not** that
the receipts, public readers, source rights, signers, gold independence or
rollback have been authenticated. Operator review must independently check
actual signer identity/signatures, rights scope, source bytes, provenance,
the complete MiniPC PostgreSQL → reader/cache fingerprint readback and any
qualified owner decision. No integration/deploy hook consumes this result.
This deliberately implements one narrow preparatory vertical slice; it does
not prove the full multi-person/language pilot matrix, nor grant dispatch.

Focused verification:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=poc python3 -m unittest discover -s tests -p 'test_dp443_first_integrated_pilot_readiness.py' -v
```

**14/14 PASS** (plus **13/13** related DP-235 tests), synthetic metadata only.
The test for a complete-looking
set of references explicitly requires `NO-GO`, and absent/forged receipts
fail closed. No source/provider/DB/network input or public publication was used.

## Documentation, data, and migration impact

Use existing source/corpus/policy/public projection/ledger systems; capture a versioned end-to-end evidence manifest, not a parallel stack. Keep sensitive content out of Git.

## Completion receipt

2026-10-10: planning only. 2026-10-11: source-only readiness validator and
synthetic regression tests added; **no real pilot executed, all seven AC
remain unchecked**, and there is no authority to scale or release.
