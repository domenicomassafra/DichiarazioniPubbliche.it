"""DP-443 private, source-only evidence packet preflight.

This checks bounded shape and cross-references supplied by an external operator.
It neither authenticates attestations nor queries sources, MiniPC, readers or DB.
Even a structurally complete packet is NO-GO pending independent validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Sequence

from dichiarazioni_pubbliche.bounded_private_pilot_manifest_v1 import (
    PrivatePilotManifest,
    validate_private_pilot_manifest,
)


VERSION = "first-integrated-pilot-readiness-v1"

# Each stage is an independent external receipt; a test fixture is never evidence.
POSITIVE_STAGES = (
    "SIGNED_MANIFEST",
    "SOURCE_RIGHTS",
    "CAPTURE_PASSAGE",
    "ORIGINAL_STATEMENT",
    "FACTUAL_ABSTENTION",
    "OPINION_SEPARATION",
    "PERSON_TOPIC",
    "READER_API",
    "READER_HTML",
    "READER_SEARCH",
    "READER_LINKED_DATA",
    "CORRECTION_REPLY",
    "REVOCATION_REPLAY",
    "MINIPC_READBACK",
    "INDEPENDENT_GOLD",
    "LEGAL_REVIEW",
    "PRIVACY_REVIEW",
    "EDITORIAL_AUTHORITY",
    "COST_ROLLBACK",
    "SIGNED_SCALING_DECISION",
)
NEGATIVE_STAGES = (
    "RIGHTS_DENIED_HOLD",
    "MISATTRIBUTION_HOLD",
    "UNSUPPORTED_INFERENCE_HOLD",
    "REVOKED_REPLAY_HOLD",
    "PRIVATE_LEAK_HOLD",
)
_ALL_STAGES = frozenset(POSITIVE_STAGES + NEGATIVE_STAGES)
_SIGNER_INDEPENDENCE = (
    "SIGNED_MANIFEST",
    "INDEPENDENT_GOLD",
    "LEGAL_REVIEW",
    "PRIVACY_REVIEW",
    "EDITORIAL_AUTHORITY",
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_HOST = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.-]{0,127}\Z")
_EXTERNAL_REF = re.compile(
    r"(?:urn:[a-zA-Z0-9][a-zA-Z0-9:._-]{5,239}|https://[^\s?#]{6,239})\Z"
)
MAX_PROOFS = 48


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _external_ref(value: object) -> bool:
    return (
        isinstance(value, str)
        and _EXTERNAL_REF.fullmatch(value) is not None
        and len(value) <= 256
    )


@dataclass(frozen=True)
class PilotLineage:
    sample_id: str
    content_id: str
    language: str
    source_sha256: str
    capture_sha256: str
    passage_sha256: str
    quote_sha256: str
    statement_sha256: str
    reader_fingerprint_sha256: str
    correction_fingerprint_sha256: str
    revocation_fingerprint_sha256: str
    git_commit: str
    minipc_host: str


@dataclass(frozen=True)
class PilotProof:
    stage: str
    outcome: str
    sample_id: str
    receipt_ref: str
    signer_ref: str
    receipt_sha256: str
    manifest_sha256: str
    lineage_sha256: str
    observed_host: str | None = None


@dataclass(frozen=True)
class PilotReadiness:
    disposition: str
    packet_complete: bool
    scaling_authorized: bool
    blockers: tuple[str, ...]
    version: str = VERSION


def fingerprint_pilot_lineage(
    lineage: PilotLineage,
    manifest: PrivatePilotManifest,
) -> str:
    """Local binding checksum only: does not verify original text or signatures."""
    return hashlib.sha256(
        json.dumps(
            {
                "version": VERSION,
                "manifest_sha256": manifest.manifest_sha256,
                "lineage": asdict(lineage),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _manifest_ok(manifest: object) -> bool:
    if not isinstance(manifest, PrivatePilotManifest):
        return False
    try:
        validate_private_pilot_manifest(manifest)
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _lineage_ok(lineage: object, manifest: PrivatePilotManifest) -> bool:
    if not isinstance(lineage, PilotLineage):
        return False
    sample = manifest.samples[0]
    if (
        lineage.sample_id != sample.sample_id
        or lineage.content_id != sample.content_id
        or lineage.language != sample.language
        or lineage.source_sha256 != sample.source_version_sha256
    ):
        return False
    fingerprints = (
        lineage.source_sha256,
        lineage.capture_sha256,
        lineage.passage_sha256,
        lineage.quote_sha256,
        lineage.statement_sha256,
        lineage.reader_fingerprint_sha256,
        lineage.correction_fingerprint_sha256,
        lineage.revocation_fingerprint_sha256,
    )
    if not all(map(_sha, fingerprints)):
        return False
    # Identical captured/source or verbatim quote/statement bytes are legitimate.
    # A correction/withdrawal, however, must change the public projection version.
    public_versions = fingerprints[-3:]
    if len(set(public_versions)) != len(public_versions):
        return False
    if not isinstance(lineage.git_commit, str) or not _COMMIT.fullmatch(
        lineage.git_commit
    ):
        return False
    return (
        isinstance(lineage.minipc_host, str)
        and _HOST.fullmatch(lineage.minipc_host) is not None
        and lineage.minipc_host not in {"localhost", "127.0.0.1"}
    )


def evaluate_first_integrated_pilot_readiness(
    manifest: PrivatePilotManifest | None,
    lineage: PilotLineage | None,
    proofs: Sequence[PilotProof] = (),
) -> PilotReadiness:
    """Require one bounded positive case and its explicit negative holds.

    Ref strings and checksums are caller assertions, not authenticated evidence.
    Every result is NO-GO: this preflight cannot grant publication or scaling.
    """
    blocks: set[str] = {"UNVERIFIED_EXTERNAL_AUTHORITY"}
    manifest_verified = _manifest_ok(manifest)
    if not manifest_verified:
        blocks.add("MANIFEST_INVALID")
    elif len(manifest.samples) != 1:
        blocks.add("MANIFEST_SCOPE_INVALID")
    elif manifest.review_status != "PROPOSED" or manifest.hold_reasons:
        blocks.add("MANIFEST_HELD")
    elif not isinstance(
        manifest.samples[0].rights_reference, str
    ) or not manifest.samples[0].rights_reference.startswith("rights:"):
        blocks.add("RIGHTS_REF_INVALID")

    valid_manifest = manifest_verified and len(manifest.samples) == 1
    valid_lineage = bool(valid_manifest and _lineage_ok(lineage, manifest))
    if not valid_lineage:
        blocks.add("LINEAGE_INVALID")

    if not isinstance(proofs, (tuple, list)) or len(proofs) > MAX_PROOFS:
        blocks.add("PROOF_COUNT_EXCEEDED")
        return PilotReadiness("NO-GO", False, False, tuple(sorted(blocks)))

    expected_lineage = (
        fingerprint_pilot_lineage(lineage, manifest) if valid_lineage else None
    )
    seen: set[str] = set()
    receipt_refs: list[str] = []
    receipt_hashes: list[str] = []
    signers: dict[str, str] = {}
    for proof in proofs:
        if not isinstance(proof, PilotProof):
            blocks.add("PROOF_TYPE_INVALID")
            continue
        stage = proof.stage
        if not isinstance(stage, str) or stage not in _ALL_STAGES:
            blocks.add(
                f"UNKNOWN_STAGE:{stage!s}"
                if isinstance(stage, str)
                else "UNKNOWN_STAGE"
            )
            continue
        if stage in seen:
            blocks.add(f"DUPLICATE:{stage}")
            continue
        seen.add(stage)
        if proof.outcome != ("HOLD" if stage in NEGATIVE_STAGES else "PASS"):
            blocks.add(f"OUTCOME_INVALID:{stage}")
        if (
            not _external_ref(proof.receipt_ref)
            or not _external_ref(proof.signer_ref)
            or not _sha(proof.receipt_sha256)
        ):
            blocks.add(f"RECEIPT_INVALID:{stage}")
        else:
            receipt_refs.append(proof.receipt_ref)
            receipt_hashes.append(proof.receipt_sha256)
        if not valid_manifest or proof.manifest_sha256 != manifest.manifest_sha256:
            blocks.add(f"MANIFEST_BINDING_INVALID:{stage}")
        if (
            not valid_lineage
            or proof.lineage_sha256 != expected_lineage
            or proof.sample_id != lineage.sample_id
        ):
            blocks.add(f"LINEAGE_BINDING_INVALID:{stage}")
        if stage == "MINIPC_READBACK" and (
            not valid_lineage or proof.observed_host != lineage.minipc_host
        ):
            blocks.add(f"MINIPC_HOST_INVALID:{stage}")
        if stage in _SIGNER_INDEPENDENCE and _external_ref(proof.signer_ref):
            signers[stage] = proof.signer_ref

    if len(set(receipt_refs)) != len(receipt_refs) or len(set(receipt_hashes)) != len(
        receipt_hashes
    ):
        blocks.add("RECEIPT_REUSED")
    if len(set(signers.values())) != len(signers):
        blocks.add("QUALIFIED_SIGNER_NOT_INDEPENDENT")
    for missing in _ALL_STAGES - seen:
        blocks.add(f"MISSING:{missing}")

    packet_complete = blocks == {"UNVERIFIED_EXTERNAL_AUTHORITY"}
    return PilotReadiness("NO-GO", packet_complete, False, tuple(sorted(blocks)))
