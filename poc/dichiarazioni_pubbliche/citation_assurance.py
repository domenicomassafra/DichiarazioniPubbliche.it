from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


CITATION_RELATIONS = frozenset(
    {"SUPPORT", "CONTRADICT", "CONTEXT", "LIMITATION", "UPDATE"}
)


def assertion_text_sha256(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        raise ValueError("ASSERTION_TEXT_REQUIRED")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FindingAssertion:
    assertion_id: str
    text: str
    material: bool = True
    required_relation: str = "SUPPORT"

    def __post_init__(self) -> None:
        if not str(self.assertion_id or "").strip():
            raise ValueError("ASSERTION_ID_REQUIRED")
        if not str(self.text or "").strip():
            raise ValueError("ASSERTION_TEXT_REQUIRED")
        if self.required_relation not in CITATION_RELATIONS:
            raise ValueError("ASSERTION_RELATION_INVALID")

    @property
    def text_sha256(self) -> str:
        return assertion_text_sha256(self.text)


@dataclass(frozen=True)
class CitationBinding:
    assertion_id: str
    assertion_text_sha256: str
    evidence_id: str
    relation: str
    observation_id: str | None = None
    passage_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.assertion_id or "").strip():
            raise ValueError("CITATION_ASSERTION_ID_REQUIRED")
        if len(str(self.assertion_text_sha256 or "")) != 64:
            raise ValueError("CITATION_ASSERTION_HASH_INVALID")
        if not str(self.evidence_id or "").strip():
            raise ValueError("CITATION_EVIDENCE_ID_REQUIRED")
        if self.relation not in CITATION_RELATIONS:
            raise ValueError("CITATION_RELATION_INVALID")


@dataclass(frozen=True)
class CitationIssue:
    assertion_id: str
    code: str
    evidence_id: str | None = None


@dataclass(frozen=True)
class CitationAssuranceResult:
    passed: bool
    material_assertion_count: int
    supported_assertion_count: int
    issues: tuple[CitationIssue, ...]


def assure_material_assertions(
    assertions: Iterable[FindingAssertion],
    bindings: Iterable[CitationBinding],
    *,
    approved_evidence_ids: Iterable[str],
    approved_observation_ids: Iterable[str] = (),
) -> CitationAssuranceResult:
    """Fail-closed citation assurance for public Finding assertions.

    The checker deliberately does not evaluate truth. It verifies only that each material
    assertion is bound to already-approved evidence/observations with the required relation
    and to the exact current assertion text hash.
    """

    assertion_rows = tuple(assertions)
    binding_rows = tuple(bindings)
    evidence_ids = frozenset(str(value) for value in approved_evidence_ids)
    observation_ids = frozenset(str(value) for value in approved_observation_ids)

    by_assertion: dict[str, list[CitationBinding]] = {}
    for binding in binding_rows:
        by_assertion.setdefault(binding.assertion_id, []).append(binding)

    issues: list[CitationIssue] = []
    supported = 0
    material = 0
    seen_ids: set[str] = set()

    for assertion in assertion_rows:
        if assertion.assertion_id in seen_ids:
            issues.append(CitationIssue(assertion.assertion_id, "DUPLICATE_ASSERTION_ID"))
            continue
        seen_ids.add(assertion.assertion_id)
        if not assertion.material:
            continue
        material += 1
        rows = by_assertion.get(assertion.assertion_id, [])
        if not rows:
            issues.append(CitationIssue(assertion.assertion_id, "MATERIAL_ASSERTION_UNCITED"))
            continue

        valid = False
        for binding in rows:
            if binding.assertion_text_sha256 != assertion.text_sha256:
                issues.append(
                    CitationIssue(
                        assertion.assertion_id,
                        "ASSERTION_TEXT_HASH_STALE",
                        binding.evidence_id,
                    )
                )
                continue
            if binding.evidence_id not in evidence_ids:
                issues.append(
                    CitationIssue(
                        assertion.assertion_id,
                        "EVIDENCE_NOT_APPROVED_FOR_FINDING",
                        binding.evidence_id,
                    )
                )
                continue
            if (
                binding.observation_id is not None
                and binding.observation_id not in observation_ids
            ):
                issues.append(
                    CitationIssue(
                        assertion.assertion_id,
                        "OBSERVATION_NOT_APPROVED_FOR_FINDING",
                        binding.evidence_id,
                    )
                )
                continue
            if binding.relation != assertion.required_relation:
                issues.append(
                    CitationIssue(
                        assertion.assertion_id,
                        "CITATION_RELATION_MISMATCH",
                        binding.evidence_id,
                    )
                )
                continue
            valid = True

        if valid:
            supported += 1
        else:
            issues.append(CitationIssue(assertion.assertion_id, "NO_COMPATIBLE_CITATION"))

    material_ids = {row.assertion_id for row in assertion_rows if row.material}
    for binding in binding_rows:
        if binding.assertion_id not in material_ids and binding.assertion_id not in seen_ids:
            issues.append(
                CitationIssue(
                    binding.assertion_id,
                    "CITATION_FOR_UNKNOWN_ASSERTION",
                    binding.evidence_id,
                )
            )

    return CitationAssuranceResult(
        passed=(material == supported and not issues),
        material_assertion_count=material,
        supported_assertion_count=supported,
        issues=tuple(issues),
    )


__all__ = [
    "CITATION_RELATIONS",
    "CitationAssuranceResult",
    "CitationBinding",
    "CitationIssue",
    "FindingAssertion",
    "assertion_text_sha256",
    "assure_material_assertions",
]
