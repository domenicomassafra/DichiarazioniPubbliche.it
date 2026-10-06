# DP-309 — High-risk assertion and legal-status escalation gate

Status: DONE
Milestone: M3 — Editorial, correction, privacy, and legal policy
Depends on: DP-215, DP-304, DP-306; DP-307 required for final launch decisions; DP-308

Launch state: BLOCKED for final public enablement until applicable DP-306/DP-307 decisions
are accepted. Conservative hold logic may be implemented and tested before then.

## Problem

Some wording errors are disproportionately harmful: confusing investigation/prosecution/
conviction status, attributing criminal conduct to the wrong person, publishing a sensitive
private allegation, or turning a source's allegation into the site's asserted fact.

The product needs a technical escalation boundary so these cases cannot travel through the
ordinary low-risk publication lane merely because generic provenance is present.

## Outcome

Define a versioned high-risk assertion profile that detects/records risk classes and
requires stronger evidence/review conditions or a fail-closed hold. It does not decide the
law; qualified questions remain in DP-306/DP-307.

## Scope

- Define bounded risk classes for at least:
  - criminal/procedural status terminology;
  - allegation of criminal or seriously wrongful conduct;
  - identity-sensitive accusation;
  - health/private/sensitive-person information already governed by DP-304;
  - minors/victims/private incidental persons where DP-304 requires special handling;
  - legal-status claims whose precise term/date/jurisdiction is material.
- Classifiers/signals are triage only. A hit can escalate/hold; a non-hit cannot certify
  safety.
- Legal/procedural terms require a DP-215 requirement profile with the appropriate official
  record, jurisdiction, effective date/status and temporal match.
- Preserve source framing: allegation, charge, investigation, prosecution, conviction,
  acquittal/dismissal or other states must not be normalized into one another.
- A source saying "X alleges Y" does not authorize the product to state Y as fact.
- Require explicit human review and the DP-310 separation rule for `HIGH/LEGAL` cases once
  enabled by policy.
- Any unresolved identity/procedural status produces `HOLD_HIGH_RISK`, not a softer label.

## Non-goals

- No autonomous legal conclusion.
- No inference about guilt, innocence, character, intent or fitness.
- No sensitive-trait inference from unrelated evidence.
- No model confidence threshold that clears a high-risk assertion.

## Acceptance criteria

- [x] **AC-309.1:** High-risk state is explicit/versioned and can only add restrictions;
  absence of a detected token never becomes a safety certification.
- [x] **AC-309.2:** Fixtures distinguish material procedural/legal terms without silently
  mapping them to one generic status.
- [x] **AC-309.3:** A legal-status Finding cannot run/publish without the DP-215 official
  record/scope/time requirements selected by the accepted policy.
- [x] **AC-309.4:** "Source alleges X" remains attributed allegation/reporting context and
  cannot become an unqualified product assertion through normalization.
- [x] **AC-309.5:** Wrong-person/same-name high-risk fixtures remain held through DP-222.
- [x] **AC-309.6:** Sensitive/private/minor/victim cases inherit DP-304 minimization/hold
  rules and cannot be cleared by this ticket alone.
- [x] **AC-309.7:** Every `HIGH/LEGAL` public candidate has an explicit reviewed evidence
  packet and DP-310 review separation, or stays non-public.
- [x] **AC-309.8:** Qualified-policy rows remain linked to DP-306/DP-307 and a code/test pass
  cannot mark them legally `DECIDED`.
- [x] **AC-309.9:** Public serializers never expose internal risk scores/notes.
- [x] **AC-309.10:** Full regression + DP-223 + MiniPC canary pass.

## Validation / proof

Use synthetic legal/procedural fixtures with deliberately wrong terms, dates, jurisdictions,
people and source framing. Prove safe holds before qualified review and exact policy-driven
behavior after accepted decisions. Run standard checks and MiniPC read-back.

## Documentation, data, and migration impact

Record qualified questions/decisions only through DP-306/DP-307. Implementation may add
versioned risk/escalation metadata and requirement-profile links, but no legal opinion or
privileged material belongs in Git.

## Completion receipt

Local `high-risk-assertion-v1` now provides the conservative technical escalation boundary
that this ticket permits before qualified policy closure. It preserves distinct procedural
states (`INVESTIGATED`, `CHARGED`, `PROSECUTED`, `CONVICTED`, `ACQUITTED`, `DISMISSED`),
never treats a no-hit classifier result as a safety certification, and holds legal-status
candidates unless official-record, jurisdiction and effective-time gates pass. Source
allegation framing cannot be normalized into an unqualified product assertion. Identity,
privacy and minor/victim signals only add restrictions. A high-risk candidate also remains
held without an explicit qualified-policy decision reference, human review and DP-310-style
dual-control flag.

This code does not make or record a legal decision. At that receipt stage AC-309.7 remained open until every
`HIGH/LEGAL` public candidate is literally required to carry both a current reviewed packet
and the applicable DP-310 review separation; AC-309.10 likewise remained open for DP-223/full/MiniPC
acceptance. Final public enablement remains BLOCKED on DP-307 as stated above.

Persisted reviewed-packet receipt 2026-10-06: the private
`private_high_risk_review_packet` ledger and
`high_risk_review_persistence.py` now record the exact bounded review inputs and canonical
`evaluate_high_risk_candidate` output for a record/Finding version. Source and normalized
text bodies are not persisted; their SHA-256 bindings, source/normalized allegation framing,
identity/privacy/sensitive/minor-victim inputs, opaque privacy/official-record/jurisdiction/
effective-time/human-review references, policy/input/output bindings and decision
reason/risk classes are. Rows are append-only and superseding. Replay re-runs the canonical
evaluator on current caller-supplied text and rejects stale record versions, changed inputs,
tampered lineage or mismatched evaluator output.

The packet does not infer DP-307 authority. With no qualified DP-307 acceptance,
`policy_decision_ref` stays null and replay remains `HOLD_HIGH_RISK`; an opaque reference
cannot make an unaccepted decision qualified. The DP-309/DP-310 cycle break is also preserved:
a synthetic future-qualified packet with every other gate satisfied and
`dual_control_approved=false` has exactly
`HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED`, leaving DP-310 to prove independent dual control.
Focused high-risk/persistence/review/eligibility tests are **53/53 PASS**, including disposable
PostgreSQL migration replay, fresh-schema parity, append-only enforcement, stale/tamper
detection and the missing-DP-307 hold. This receipt does not close AC-309.7 or AC-309.10.

Isolated MiniPC receipt 2026-10-06: the exact local DP-309 runtime files were copied to
`/tmp/dp309-reviewed-packet.1WJU8A` on the MiniPC and exercised only against a disposable
PostgreSQL 18.6 cluster created under that temporary tree; no runtime database, production
data or provider was accessed. Remote SHA-256 matched the local files for
`high_risk_assertion.py` (`eb2ca7be…2cf1`),
`high_risk_review_persistence.py` (`4f60a68e…8cc4`), the migration
(`f6c64942…d4cc`) and the focused test (`eb0b61fc…ac48`). The MiniPC run was
**10/10 PASS** and covered missing DP-307 -> `HOLD_HIGH_RISK`, the otherwise-complete
future-qualified packet -> sole `HOLD_HIGH_RISK_DUAL_CONTROL_REQUIRED` while dual control
is still false, stale record-version/input rejection, tamper rejection and append-only
update/delete/truncate protection. The test also replayed migration/fresh-schema parity and
migration idempotence. No canary PostgreSQL process remained afterward and the complete
temporary tree was removed. This is runtime proof of the private packet contract only:
At that MiniPC receipt stage AC-309.7 remained open because every public `HIGH/LEGAL` candidate
was not yet wired through this packet + DP-310 path, and AC-309.10 remained open for its full
DP-223/regression gate.

AC-309.9 serializer proof 2026-10-06: a focused audit found and closed one concrete leak path:
reviewed `corrections[].changed_fields` was copied as an open dictionary into the public JSON
projection, allowing internal high-risk score/note, reviewer actor-ref, credential fingerprint
and private high-risk reason fields to escape. The public boundary now drops a contaminated
correction and the public schema independently rejects a fingerprint-valid dossier containing
the same internal-only material. Focused tests cover projection JSON, written bundle artifacts,
HTML, ClaimReview/projection JSON-LD, RDF/N-Triples and all relevant public API read routes;
**5/5 PASS**. Existing projection/schema/API/linked-data regression set: **144/144 PASS**.
The dedicated web search serializer proof injects the same private sentinels and proves they are
absent (`check-high-risk-public-serializers.mjs` PASS); the existing `npm run check:search` also
remains green. A production-style Astro static build from the sanitized projection completed
successfully and a recursive `dist/` scan found none of the private sentinels or
`HOLD_HIGH_RISK_*` reason codes. No public risk score or high-risk decision field was introduced.

Final closure receipt at clean HEAD `5a86666b` (2026-10-06): production projection requires the
current append-only DP-309 reviewed packet plus DP-310/311 authority-attested review separation
before a `HIGH/LEGAL` candidate can serialize, closing AC-309.7. AC-309.10 is closed by the clean
**1720/1720** suite, deterministic benchmark **5/5**, DP-223/projection/citation **22/22**,
isolated MiniPC M3 canary (**346 tests** + benchmark **5/5**) and PostgreSQL rerun **69/69**.
Engineering completion does not qualify or decide any legal-policy row: without accepted DP-307
authority the runtime continues to hold the affected candidate.
