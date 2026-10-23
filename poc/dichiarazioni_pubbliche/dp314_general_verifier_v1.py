"""DP-314 general fact verifier: checkable / not checkable / false, else HOLD.

The requirement preflight answers *can this proposition be checked with reviewed,
independent, in-time, rights-approved sources?* It deliberately never returns a
verdict. This module turns that preflight into the three classifications the
ticket asks for, and refuses everything else:

* ``VERIFIABLE`` — a requirement profile applies, every required role is covered
  by eligible evidence on independent original roots and source families, and
  the counter-case (the hypothesis that the claim is false) was tested against
  the same eligible set and refuted by the sources.
* ``NOT_VERIFIABLE`` — no profile applies (unknown claim kind) or the claim is
  not a factual proposition. Nothing could make it checkable.
* ``FALSE`` — same eligibility as ``VERIFIABLE``, every eligible observation
  refutes the proposition, and the counter-case is supported by those sources.
* ``HELD`` — everything else: insufficient evidence, conflict, unknown stance,
  missing or ineligible counter-case, non-boolean/shape violations.

Hard boundaries
---------------
``FALSE`` is only ever produced from reviewed eligible evidence *and* a
counter-case proven on that same set: a single unreviewed row can never make a
claim false. Counter-case evidence ids must be a subset of the eligible ids, so
a caller cannot smuggle in an excluded (revoked, stale, unapproved) row.
``private_only`` stays True and ``publication_authority`` stays False: this is a
private work classification, not a public Finding. Stances remain untrusted
operator labels; the module never fetches anything.

Pure and deterministic: no I/O, no network, no database, no clock.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from dichiarazioni_pubbliche.verification_requirements_v1 import (
    RequirementClaim,
    RequirementEvidence,
    preflight_verification_requirements,
)


VERIFIER_VERSION = "dp314-general-verifier-v1"
CLASSIFICATIONS = ("VERIFIABLE", "NOT_VERIFIABLE", "FALSE", "HELD")
COUNTER_OUTCOMES = (
    "SOURCE_SUPPORTS_COUNTER",
    "SOURCE_REFUTES_COUNTER",
    "NOT_OBSERVED",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_MAX_EVIDENCE = 128


@dataclass(frozen=True)
class CounterCase:
    """The tested alternative hypothesis, bound to eligible evidence ids."""

    counter_ref: str
    hypothesis_sha256: str
    outcome: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ClaimVerification:
    status: str
    reason_code: str
    reason_codes: tuple[str, ...]
    claim_id: str
    claim_kind: str
    profile_version: str | None
    required_roles: tuple[str, ...]
    eligible_evidence_ids: tuple[str, ...]
    counter_case_ref: str | None
    snapshot_sha256: str
    verdict: None = None
    private_only: bool = True
    finding_authority: bool = False
    publication_authority: bool = False
    contract_version: str = VERIFIER_VERSION


def _result(
    status: str,
    reason: str,
    claim: RequirementClaim,
    *,
    codes: tuple[str, ...] = (),
    profile_roles: tuple[str, ...] = (),
    eligible: tuple[str, ...] = (),
    counter_ref: str | None = None,
    profile_version: str | None = None,
    snapshot: str = "",
) -> ClaimVerification:
    reason_codes = tuple(sorted({reason, *codes}))
    return ClaimVerification(
        status,
        reason,
        reason_codes,
        claim.claim_id,
        claim.claim_kind,
        profile_version,
        profile_roles,
        eligible,
        counter_ref,
        snapshot,
    )


def _counter_problem(counter: object, eligible: frozenset[str]) -> str | None:
    if type(counter) is not CounterCase:
        return "COUNTER_CASE_REQUIRED"
    if type(counter.counter_ref) is not str or not _REF.fullmatch(counter.counter_ref):
        return "COUNTER_CASE_INVALID"
    if type(counter.hypothesis_sha256) is not str or not _SHA.fullmatch(
        counter.hypothesis_sha256
    ):
        return "COUNTER_CASE_INVALID"
    if type(counter.outcome) is not str or counter.outcome not in COUNTER_OUTCOMES:
        return "COUNTER_CASE_OUTCOME_UNKNOWN"
    if type(counter.evidence_ids) is not tuple or not counter.evidence_ids:
        return "COUNTER_CASE_EVIDENCE_REQUIRED"
    if any(
        type(value) is not str or not _REF.fullmatch(value)
        for value in counter.evidence_ids
    ):
        return "COUNTER_CASE_INVALID"
    if len(set(counter.evidence_ids)) != len(counter.evidence_ids):
        return "COUNTER_CASE_INVALID"
    if not set(counter.evidence_ids) <= eligible:
        return "COUNTER_CASE_EVIDENCE_NOT_ELIGIBLE"
    if counter.outcome == "NOT_OBSERVED":
        return "COUNTER_CASE_NOT_OBSERVED"
    return None


def _digest(
    claim: RequirementClaim,
    evidence: tuple[RequirementEvidence, ...],
    counter: CounterCase | None,
    status: str,
) -> str:
    material = {
        "contract": VERIFIER_VERSION,
        "status": status,
        "claim": asdict(claim),
        "evidence": [asdict(row) for row in sorted(
            evidence, key=lambda row: row.evidence_id
        )],
        "counter": asdict(counter) if counter is not None else None,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).hexdigest()


def classify_claim(
    claim: RequirementClaim,
    evidence: tuple[RequirementEvidence, ...],
    counter_case: CounterCase | None,
) -> ClaimVerification:
    """Classify one claim; anything not fully demonstrated stays HELD."""
    if type(claim) is not RequirementClaim:
        raise ValueError("CLAIM_INPUT_INVALID")
    if type(evidence) is not tuple or len(evidence) > _MAX_EVIDENCE:
        raise ValueError("CLAIM_INPUT_INVALID")
    if any(type(row) is not RequirementEvidence for row in evidence):
        raise ValueError("CLAIM_EVIDENCE_INPUT_INVALID")
    try:
        preflight = preflight_verification_requirements(claim, evidence)
    except ValueError as error:
        return _result(
            "HELD", "CLAIM_INPUT_REJECTED", claim, codes=(str(error),)
        )
    state = preflight.state
    eligible = frozenset(preflight.eligible_evidence_ids)
    snapshot = _digest(claim, evidence, counter_case, state)
    common = {
        "codes": tuple(
            code for code in preflight.reason_codes if code != state
        ),
        "profile_roles": preflight.required_roles,
        "eligible": preflight.eligible_evidence_ids,
        "counter_ref": (
            counter_case.counter_ref
            if type(counter_case) is CounterCase
            and type(counter_case.counter_ref) is str
            else None
        ),
        "profile_version": preflight.version if preflight.required_roles else None,
        "snapshot": snapshot,
    }

    if state == "NOT_CHECKABLE_PROFILE_UNAVAILABLE":
        return _result("NOT_VERIFIABLE", "NO_REQUIREMENT_PROFILE", claim, **common)
    if state == "NON_FACTUAL":
        return _result("NOT_VERIFIABLE", "NOT_A_FACTUAL_CLAIM", claim, **common)
    if state == "NOT_CHECKED":
        return _result("HELD", "CLAIM_NOT_CHECKED", claim, **common)
    if state == "CHECKED_INSUFFICIENT_EVIDENCE":
        return _result("HELD", "EVIDENCE_INSUFFICIENT_OR_EXCLUDED", claim, **common)
    if state == "UNRESOLVED_CONFLICT":
        return _result("HELD", "OBSERVATIONS_CONFLICT", claim, **common)
    if state != "CHECKABLE_PENDING":
        return _result("HELD", "PREFLIGHT_STATE_UNKNOWN", claim, **common)

    eligible_rows = tuple(row for row in evidence if row.evidence_id in eligible)
    stances = {row.stance for row in eligible_rows}
    if not eligible_rows or stances == {"UNKNOWN"}:
        return _result("HELD", "EVIDENCE_STANCE_UNKNOWN", claim, **common)
    problem = _counter_problem(counter_case, eligible)
    if problem is not None:
        return _result("HELD", problem, claim, **common)
    assert isinstance(counter_case, CounterCase)
    if stances == {"REFUTE"} and counter_case.outcome == "SOURCE_SUPPORTS_COUNTER":
        return _result(
            "FALSE", "CLAIM_CONTRADICTED_BY_REVIEWED_EVIDENCE", claim, **common
        )
    if stances == {"SUPPORT"} and counter_case.outcome == "SOURCE_REFUTES_COUNTER":
        return _result(
            "VERIFIABLE", "COUNTER_CASE_REFUTED_BY_SOURCES", claim, **common
        )
    if counter_case.outcome == "SOURCE_SUPPORTS_COUNTER":
        return _result("HELD", "COUNTER_CASE_CONTRADICTED_BY_SOURCES", claim, **common)
    return _result("HELD", "CLASSIFICATION_CONDITIONS_UNMET", claim, **common)


__all__ = [
    "CLASSIFICATIONS",
    "COUNTER_OUTCOMES",
    "ClaimVerification",
    "CounterCase",
    "VERIFIER_VERSION",
    "classify_claim",
]
