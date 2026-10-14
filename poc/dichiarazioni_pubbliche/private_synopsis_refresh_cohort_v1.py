"""DP-440 private multi-synopsis offline invalidation across pinned releases.

This only creates opaque, owner-side human recheck tasks. The inputs are
caller-declared public read models and attestations; SHA pins and issuer epochs
are change detectors, NOT authenticated rights, editors, truth or permission.
No source body, URL, statement ID or synopsis text is emitted in the result.
No provider, network, database, public route or publication side effects.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .public_schema import validate_public_bundle
from .public_synopsis_refresh_plan_v1 import (
    _frozen_public_bundle,
    _validate_review,
    plan_synopsis_refresh,
    synopsis_read_sha256,
)
from .public_synopsis_v3 import ApprovedTopicIntersection, PublicSynopsisRead

VERSION = "private-synopsis-refresh-cohort-v1"
_HEX = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,149}$")
_MAX_READS = 32
_MAX_MEMBERSHIPS = 64
_MAX_RELEASE_BYTES = 4_500_000


@dataclass(frozen=True)
class CohortRead:
    read: PublicSynopsisRead
    issuer_epoch: int


@dataclass(frozen=True)
class CohortRelease:
    issuer_ref: str
    issuer_epoch: int
    public_bundle: dict
    reads: dict[tuple[str, str], CohortRead]
    memberships: dict[tuple[str, str], ApprovedTopicIntersection]


@dataclass(frozen=True)
class CohortReviewItem:
    opaque_ref: str
    transition: str  # ADDED | RETIRED | CHANGED | HELD
    reason_codes: tuple[str, ...]
    manual_actions: tuple[str, ...]
    manual_only: bool = True
    source_rights_authority: bool = False
    semantic_entailment_verified: bool = False
    publication_authority: bool = False


@dataclass(frozen=True)
class PrivateSynopsisCohortPlan:
    version: str
    status: str
    previous_release_sha256: str
    current_release_sha256: str
    items: tuple[CohortReviewItem, ...]
    review_item_count: int
    snapshot_sha256: str
    private_only: bool = True
    source_body_count: int = 0
    provider_calls: int = 0
    verdict: None = None
    source_rights_authority: bool = False
    semantic_entailment_verified: bool = False
    publication_authority: bool = False


def _digest(material: object) -> str:
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _exact_json_tree(value: Any, *, depth: int = 0) -> bool:
    """Deny dynamic dict/list subclasses, exotic objects and huge recursion."""
    if depth > 48:
        return False
    if type(value) is str:
        return len(value) <= 1_000_000
    if value is None or type(value) in (int, float, bool):
        return type(value) is not float or (
            value == value and value not in (float("inf"), float("-inf"))
        )
    if type(value) in (tuple, list):
        return len(value) <= 1024 and all(
            _exact_json_tree(part, depth=depth + 1) for part in value
        )
    if type(value) is dict:
        return len(value) <= 1024 and all(
            type(key) is str and _exact_json_tree(part, depth=depth + 1)
            for key, part in value.items()
        )
    return False


def _key(key: Any) -> bool:
    return (
        type(key) is tuple
        and len(key) == 2
        and all(type(part) is str and _OPAQUE.fullmatch(part) for part in key)
    )


def _proof_text(value: Any) -> bool:
    """Mirror the public synopsis authority's trimmed, bounded text rule."""
    return (
        type(value) is str
        and 0 < len(value) <= 150
        and value == value.strip()
        and "\x00" not in value
    )


def _membership_shape(proof: ApprovedTopicIntersection) -> bool:
    """Require a complete, injectively reviewed Statement→lineage receipt.

    A digest of self-consistent *malformed* proof bytes is not an
    attestation. The per-synopsis citation rechecker checks membership
    inclusion but not all original lineage/review/attestation fields.
    """
    if (
        not _proof_text(proof.person_id)
        or not _proof_text(proof.topic_id)
        or not _proof_text(proof.review_event_id)
        or not _proof_text(proof.currentness_attestation_id)
        or type(proof.status) is not str
        or proof.status not in {"APPROVED", "PENDING", "HELD", "REVOKED"}
        or type(proof.currentness_attested_at) is not str
        or type(proof.currentness_valid_until) is not str
        or not proof.currentness_attested_at
        or not proof.currentness_valid_until
        or type(proof.statement_versions) is not tuple
        or not 1 <= len(proof.statement_versions) <= 512
        or type(proof.statement_lineages) is not tuple
        or len(proof.statement_lineages) != len(proof.statement_versions)
    ):
        return False
    if any(
        type(pair) is not tuple
        or len(pair) != 2
        or not all(_proof_text(part) for part in pair)
        for pair in proof.statement_versions
    ):
        return False
    if any(
        type(lineage) is not tuple
        or len(lineage) != 3
        or not all(_proof_text(part) for part in lineage)
        for lineage in proof.statement_lineages
    ):
        return False
    version_set = set(proof.statement_versions)
    lineage_keys = {(lineage[0], lineage[1]) for lineage in proof.statement_lineages}
    lineage_ids = {lineage[2] for lineage in proof.statement_lineages}
    return (
        len(version_set) == len(proof.statement_versions)
        and lineage_keys == version_set
        and len(lineage_ids) == len(proof.statement_lineages)
    )


def _release_material(release: CohortRelease) -> dict[str, Any]:
    return {
        "version": VERSION,
        "issuer_ref": release.issuer_ref,
        "issuer_epoch": release.issuer_epoch,
        "public_bundle": release.public_bundle,
        "reads": [
            {
                "key": list(key),
                "issuer_epoch": envelope.issuer_epoch,
                "read": asdict(envelope.read),
            }
            for key, envelope in sorted(release.reads.items())
        ],
        "memberships": [
            {"key": list(key), "membership": asdict(proof)}
            for key, proof in sorted(release.memberships.items())
        ],
    }


def _detach_release(value: CohortRelease) -> CohortRelease:
    """Freeze *all* read DTOs, membership maps and public rows before validation.

    A subclass mapping/read can mutate after caller validation. Refuse every
    subclass at every reachable nested byte and detach into owned plain trees.
    """
    if (
        type(value) is not CohortRelease
        or type(value.issuer_ref) is not str
        or not _OPAQUE.fullmatch(value.issuer_ref)
        or type(value.issuer_epoch) is not int
        or not 0 < value.issuer_epoch < 2**63
        or type(value.public_bundle) is not dict
        or not _exact_json_tree(value.public_bundle)
        or type(value.reads) is not dict
        or type(value.memberships) is not dict
        or len(value.reads) > _MAX_READS
        or len(value.memberships) > _MAX_MEMBERSHIPS
        or any(not _key(key) for key in (*value.reads, *value.memberships))
    ):
        raise ValueError("COHORT_INPUT_INVALID")
    for envelope in value.reads.values():
        if (
            type(envelope) is not CohortRead
            or type(envelope.read) is not PublicSynopsisRead
            or type(envelope.issuer_epoch) is not int
            or type(envelope.read.sentences) is not tuple
            or len(envelope.read.sentences) > 8
            or not _exact_json_tree(asdict(envelope.read))
        ):
            raise ValueError("COHORT_INPUT_INVALID")
    for proof in value.memberships.values():
        if (
            type(proof) is not ApprovedTopicIntersection
            or type(proof.statement_versions) is not tuple
            or len(proof.statement_versions) > 512
            or type(proof.statement_lineages) is not tuple
            or len(proof.statement_lineages) > 512
            or not _exact_json_tree(asdict(proof))
        ):
            raise ValueError("COHORT_INPUT_INVALID")
    # Input-sized before copying to bound worst-case CPU, and no subsequent
    # callbacks into untrusted input are made after the frozen copy is built.
    try:
        snap = CohortRelease(
            issuer_ref=value.issuer_ref,
            issuer_epoch=value.issuer_epoch,
            public_bundle=_frozen_public_bundle(value.public_bundle),
            reads={
                key: CohortRead(
                    read=PublicSynopsisRead(**deepcopy(asdict(envelope.read))),
                    issuer_epoch=envelope.issuer_epoch,
                )
                for key, envelope in value.reads.items()
            },
            memberships={
                key: ApprovedTopicIntersection(**deepcopy(asdict(proof)))
                for key, proof in value.memberships.items()
            },
        )
        # asdict converts tuples to tuples, retaining real typed review data.
        raw = json.dumps(_release_material(snap), ensure_ascii=True, allow_nan=False)
        if len(raw.encode()) > _MAX_RELEASE_BYTES:
            raise ValueError("too large")
        return snap
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("COHORT_INPUT_INVALID") from exc


def pinned_release_digest(value: CohortRelease) -> str:
    """Compute offline digest for separate owner storage; self-pins prove nothing."""
    return _digest(_release_material(_detach_release(value)))


def pinned_membership_digest(proof: ApprovedTopicIntersection) -> str:
    if type(proof) is not ApprovedTopicIntersection or not _exact_json_tree(
        asdict(proof)
    ):
        raise ValueError("COHORT_INPUT_INVALID")
    return _digest(asdict(proof))


def _check_map_pins(
    expected: dict[tuple[str, str], str],
    rows: dict,
    *,
    kind: str,
) -> None:
    if (
        type(expected) is not dict
        or set(expected) != set(rows)
        or any(
            not _key(key) or type(pin) is not str or not _HEX.fullmatch(pin)
            for key, pin in expected.items()
        )
    ):
        raise ValueError(f"COHORT_{kind}_PIN_MISMATCH")
    for key, row in rows.items():
        actual = (
            synopsis_read_sha256(row.read)
            if kind == "READ"
            else pinned_membership_digest(row)
        )
        if not hmac.compare_digest(actual, expected[key]):
            raise ValueError(f"COHORT_{kind}_PIN_MISMATCH")


def _validate_read(
    envelope: CohortRead, key: tuple[str, str], release: CohortRelease
) -> None:
    if envelope.issuer_epoch != release.issuer_epoch:
        raise ValueError("COHORT_ISSUER_REPLAY")
    read = envelope.read
    if (
        (read.person_id, read.topic_id) != key
        or read.dataset_sha256 != release.public_bundle["dataset_sha256"]
        or type(read.provider_calls) is not int
        or read.provider_calls != 0
    ):
        raise ValueError("COHORT_READ_INVALID")
    if read.status == "READY_READ_MODEL":
        if read.snapshot_at != release.public_bundle["generated_at"]:
            raise ValueError("COHORT_READ_INVALID")
        try:
            _validate_review(read, release.public_bundle)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("COHORT_READ_INVALID") from exc
    elif read.status == "WITHHELD":
        if (
            read.fingerprint is not None
            or read.coverage_note is not None
            or read.snapshot_at is not None
            or read.sentences != ()
            or type(read.reason_code) is not str
            or not _OPAQUE.fullmatch(read.reason_code)
        ):
            raise ValueError("COHORT_READ_INVALID")
    else:
        raise ValueError("COHORT_READ_INVALID")


def _validate_release(release: CohortRelease) -> None:
    try:
        validate_public_bundle(release.public_bundle, allow_statement_v3=True)
        if release.public_bundle["schema_version"] != (
            "dichiarazioni-pubbliche-public-v3-statement-opt-in"
        ):
            raise ValueError("legacy")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("COHORT_RELEASE_INVALID") from exc
    for key, envelope in release.reads.items():
        _validate_read(envelope, key, release)
    for key, proof in release.memberships.items():
        if (
            (proof.person_id, proof.topic_id) != key
            or type(proof.dataset_sha256) is not str
            or not _HEX.fullmatch(proof.dataset_sha256)
            or not _membership_shape(proof)
        ):
            raise ValueError("COHORT_MEMBERSHIP_INVALID")


def _opaque_ref(key: tuple[str, str], secret: bytes) -> str:
    return hmac.new(
        secret,
        json.dumps(["synopsis-cohort", *key], separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()


def _current_plan(
    previous: CohortRelease,
    current: CohortRelease,
    key: tuple[str, str],
    previous_read: PublicSynopsisRead | None,
    current_read: PublicSynopsisRead | None,
    now: datetime,
):
    membership = current.memberships.get(key)
    if membership is None:
        return None
    use_read = (
        previous_read
        if previous_read and previous_read.status == "READY_READ_MODEL"
        else current_read
    )
    if use_read is None or use_read.status != "READY_READ_MODEL":
        return None
    old_bundle = (
        previous.public_bundle if use_read is previous_read else current.public_bundle
    )
    try:
        return plan_synopsis_refresh(
            previous_bundle=old_bundle,
            current_bundle=current.public_bundle,
            previous_synopsis=use_read,
            current_membership=membership,
            expected_previous_dataset_sha256=old_bundle["dataset_sha256"],
            expected_current_dataset_sha256=current.public_bundle["dataset_sha256"],
            expected_previous_synopsis_sha256=use_read.fingerprint,
            expected_previous_synopsis_read_sha256=synopsis_read_sha256(use_read),
            now=now,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("COHORT_REFRESH_INVALID") from exc


def plan_synopsis_refresh_cohort(
    *,
    previous: CohortRelease,
    current: CohortRelease,
    expected_previous_release_sha256: str,
    expected_current_release_sha256: str,
    expected_previous_read_sha256: dict[tuple[str, str], str],
    expected_current_read_sha256: dict[tuple[str, str], str],
    expected_previous_membership_sha256: dict[tuple[str, str], str],
    expected_current_membership_sha256: dict[tuple[str, str], str],
    opaque_key: bytes,
    now: datetime,
) -> PrivateSynopsisCohortPlan:
    """Plan bounded private review without writing, acquiring or approving data.

    All expected SHA pins come from a separately authenticated owner issuer,
    never rehashed input within the same trust boundary.
    """
    if (
        type(opaque_key) is not bytes
        or not 32 <= len(opaque_key) <= 128
        or type(now) is not datetime
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise ValueError("COHORT_INPUT_INVALID")
    previous = _detach_release(previous)
    current = _detach_release(current)
    if (
        previous.issuer_ref != current.issuer_ref
        or current.issuer_epoch <= previous.issuer_epoch
    ):
        raise ValueError("COHORT_ISSUER_REPLAY")
    if (
        type(expected_previous_release_sha256) is not str
        or type(expected_current_release_sha256) is not str
        or not _HEX.fullmatch(expected_previous_release_sha256)
        or not _HEX.fullmatch(expected_current_release_sha256)
        or not hmac.compare_digest(
            _digest(_release_material(previous)), expected_previous_release_sha256
        )
        or not hmac.compare_digest(
            _digest(_release_material(current)), expected_current_release_sha256
        )
    ):
        raise ValueError("COHORT_RELEASE_PIN_MISMATCH")
    _check_map_pins(expected_previous_read_sha256, previous.reads, kind="READ")
    _check_map_pins(expected_current_read_sha256, current.reads, kind="READ")
    _check_map_pins(
        expected_previous_membership_sha256, previous.memberships, kind="MEMBERSHIP"
    )
    _check_map_pins(
        expected_current_membership_sha256, current.memberships, kind="MEMBERSHIP"
    )
    _validate_release(previous)
    _validate_release(current)
    entries: list[CohortReviewItem] = []
    for key in sorted(
        previous.reads.keys()
        | current.reads.keys()
        | previous.memberships.keys()
        | current.memberships.keys()
    ):
        old = previous.reads.get(key)
        new = current.reads.get(key)
        previous_read = old.read if old else None
        current_read = new.read if new else None
        membership = current.memberships.get(key)
        membership_changed = previous.memberships.get(key) != membership
        planned = _current_plan(
            previous, current, key, previous_read, current_read, now
        )
        # An issuer-supplied new READY DTO must itself still be covered by
        # the *current* reviewed membership. Rechecking only the old
        # citations would mislabel revoked new citations as merely CHANGED.
        current_guard = (
            _current_plan(current, current, key, current_read, current_read, now)
            if current_read is not None and current_read.status == "READY_READ_MODEL"
            else None
        )
        reasons: set[str] = set()
        actions = {
            "SOURCE_RIGHTS_EXTERNAL_REVIEW_REQUIRED",
            "EDITORIAL_ENTAILMENT_EXTERNAL_REVIEW_REQUIRED",
            "PUBLICATION_EXTERNAL_APPROVAL_REQUIRED",
        }
        # An absent *read and membership* is a retired cohort entry, not a
        # live membership proof. An explicitly held membership, or a missing
        # membership for an extant read, instead requires a HOLD.
        invalid_membership = (membership is None and new is not None) or (
            membership is not None
            and (
                membership.status != "APPROVED"
                or membership.dataset_sha256 != current.public_bundle["dataset_sha256"]
            )
        )
        if planned is not None:
            reasons.update(planned.reason_codes)
            invalid_membership |= planned.status == "WITHHELD_REVIEW_REQUIRED"
        if current_guard is not None:
            reasons.update(current_guard.reason_codes)
            if current_guard.status != "NO_CHANGE_REVIEW_PENDING":
                invalid_membership = True
                reasons.add("CURRENT_READY_READ_DEPENDENCY_NOT_VALID")
        if membership_changed:
            reasons.add("TOPIC_REVIEW_RECEIPT_CHANGED")
        if current_read is not None and current_read.status == "WITHHELD":
            reasons.add("CURRENT_READ_WITHHELD")
            invalid_membership = True
        if membership is not None and current_read is None:
            # A currently reviewed Person×Topic with no read in either
            # inventory must not silently disappear from the worklist.
            # This also holds a vanished current read while its membership
            # remains asserted (rather than incorrectly treating it retired).
            reasons.add("CURRENT_MEMBERSHIP_READ_MISSING")
            actions.add("NEW_SYNOPSIS_REVIEW_REQUIRED")
            invalid_membership = True
        if invalid_membership:
            transition = "HELD"
            reasons.add("CURRENT_REVIEW_OR_MEMBERSHIP_HELD")
            actions.add("REVIEW_HELD_COHORT_SYNOPSIS")
        elif old is None:
            transition = "ADDED"
            reasons.add("SYNOPSIS_ADDED")
            actions.add("NEW_SYNOPSIS_REVIEW_REQUIRED")
        elif new is None:
            transition = "RETIRED"
            reasons.add("SYNOPSIS_RETIRED")
            actions.add("RETIRED_SYNOPSIS_REVIEW_REQUIRED")
        elif (
            synopsis_read_sha256(previous_read) != synopsis_read_sha256(current_read)
            or membership_changed
            or planned is not None
            and planned.status != "NO_CHANGE_REVIEW_PENDING"
        ):
            transition = "CHANGED"
            reasons.add("SYNOPSIS_OR_DEPENDENCY_CHANGED")
            actions.add("REVIEW_CHANGED_SYNOPSIS_AND_DEPENDENCIES")
        else:
            continue
        entries.append(
            CohortReviewItem(
                opaque_ref=_opaque_ref(key, opaque_key),
                transition=transition,
                reason_codes=tuple(sorted(reasons)),
                manual_actions=tuple(sorted(actions)),
            )
        )
    items = tuple(sorted(entries, key=lambda item: item.opaque_ref))
    material = {
        "version": VERSION,
        "old": expected_previous_release_sha256,
        "new": expected_current_release_sha256,
        "items": [asdict(item) for item in items],
    }
    return PrivateSynopsisCohortPlan(
        version=VERSION,
        status="MANUAL_RECHECK_REQUIRED" if items else "IDLE_NO_AUTHORITY",
        previous_release_sha256=expected_previous_release_sha256,
        current_release_sha256=expected_current_release_sha256,
        items=items,
        review_item_count=len(items),
        snapshot_sha256=_digest(material),
    )
