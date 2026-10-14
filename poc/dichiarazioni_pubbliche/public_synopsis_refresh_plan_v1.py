"""Private DP-440 offline synopsis citation *invalidation* worklist.

Comparisons consume already public, individually validated v3 Statement bundles,
not private capture bodies.  This does NOT authenticate the supplied issuer,
review semantically, synthesize text, authorize reuse or publish anything.
No networking, provider, database or filesystem access.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping

from .public_schema import validate_public_bundle
from .public_synopsis_v3 import (
    VERSION as SYNOPSIS_VERSION,
    ApprovedTopicIntersection,
    PublicSynopsisRead,
)

VERSION = "private-dp440-synopsis-refresh-plan-v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_VALID_KINDS = frozenset({"SOURCE_LIST_ONLY", "REVIEWED_DESCRIPTIVE_SUMMARY"})
_MATERIAL_FIELDS = (
    "original_text",
    "quote_sha256",
    "source_sha256",
    "source_url",
    "source_version",
    "source_title",
    "content_id",
    "statement_date",
    "language",
    "locator",
    "speech_act",
    "endorsed",
    "person_id",
    "review_provenance",
)
_CITATION_FIELDS = frozenset(
    {
        "statement_id",
        "version_id",
        "quote_sha256",
        "source_sha256",
        "source_url",
        "locator",
        "statement_date",
        "language",
    }
)


@dataclass(frozen=True)
class SynopsisRefreshPlan:
    version: str
    status: str
    reason_codes: tuple[str, ...]
    previous_dataset_sha256: str
    current_dataset_sha256: str
    changed_citation_keys: tuple[tuple[str, str], ...]
    removed_citation_keys: tuple[tuple[str, str], ...]
    snapshot_sha256: str
    verdict: None = None
    publication_authority: bool = False
    semantic_entailment_verified: bool = False
    source_rights_authority: bool = False
    private_only: bool = True
    provider_calls: int = 0
    source_body_count: int = 0


def _stamp(value: str) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (
            parsed.astimezone(timezone.utc)
            if parsed.tzinfo and parsed.utcoffset() is not None
            else None
        )
    except (ValueError, TypeError, OverflowError):
        return None


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _frozen_public_bundle(value: Mapping[str, object]) -> dict:
    """Detach validated public rows before any digest or citation dereference.

    Dynamic Mapping/dict subclasses can change nested Statement bytes after
    shallow `dict(...)` validation. This private reference API deliberately
    accepts only ordinary public-projection dicts, then serializes the full
    bounded JSON tree into a new plain dict used throughout reconciliation.
    """
    if type(value) is not dict:
        raise ValueError("REFRESH_PUBLIC_BUNDLE_INVALID")
    try:
        material = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(material.encode("utf-8")) > 4_000_000:
            raise ValueError("too large")
        snapshot = json.loads(material)
        if type(snapshot) is not dict:
            raise ValueError("not an object")
        return snapshot
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("REFRESH_PUBLIC_BUNDLE_INVALID") from exc


def synopsis_read_sha256(read: PublicSynopsisRead) -> str:
    """Digest all emitted read bytes; caller MUST pin this independently.

    The older ``read.fingerprint`` covers review inputs and sentences, but
    alone cannot detect mutation of its mutable nested DTO *after* validation.
    This additive pin binds the exact copy destined for offline reconciliation.
    Its return value is not an issuer signature or publication authority.
    """
    if type(read) is not PublicSynopsisRead:
        raise ValueError("REFRESH_REVIEW_INVALID")
    try:
        encoded = json.dumps(
            asdict(read),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("REFRESH_REVIEW_INVALID") from exc
    return hashlib.sha256(encoded.encode()).hexdigest()


def _validate_review(
    review: PublicSynopsisRead, old: Mapping[str, object]
) -> set[tuple[str, str]]:
    if (
        type(review) is not PublicSynopsisRead
        or review.schema_version != SYNOPSIS_VERSION
        or review.status != "READY_READ_MODEL"
        or not _sha(review.fingerprint)
        or not _sha(review.dataset_sha256)
        or review.dataset_sha256 != old["dataset_sha256"]
        or type(review.provider_calls) is not int
        or review.provider_calls != 0
        or not isinstance(review.snapshot_at, str)
        or review.snapshot_at != old["generated_at"]
        or type(review.sentences) is not tuple
        or not 1 <= len(review.sentences) <= 8
        or type(review.person_id) is not str
        or type(review.topic_id) is not str
        or len(review.person_id) > 150
        or len(review.topic_id) > 150
        or not review.person_id
        or not review.topic_id
    ):
        raise ValueError("REFRESH_REVIEW_INVALID")
    rows = {(r["statement_id"], r["version_id"]): r for r in old["statements"]}
    reviewed: set[tuple[str, str]] = set()
    for sentence in review.sentences:
        if (
            type(sentence) is not dict
            or set(sentence) != {"text", "kind", "citations"}
            or not isinstance(sentence["text"], str)
            or not 0 < len(sentence["text"]) <= 500
            or type(sentence["kind"]) is not str
            or sentence["kind"] not in _VALID_KINDS
            or type(sentence["citations"]) is not list
            or not 1 <= len(sentence["citations"]) <= 12
        ):
            raise ValueError("REFRESH_REVIEW_INVALID")
        for citation in sentence["citations"]:
            if type(citation) is not dict or set(citation) != _CITATION_FIELDS:
                raise ValueError("REFRESH_REVIEW_INVALID")
            key = (citation["statement_id"], citation["version_id"])
            if (
                not all(type(item) is str and 0 < len(item) <= 150 for item in key)
                or key not in rows
            ):
                raise ValueError("REFRESH_REVIEW_INVALID")
            row = rows[key]
            if row["person_id"] != review.person_id or any(
                citation[field] != row[field]
                for field in (
                    "quote_sha256",
                    "source_sha256",
                    "source_url",
                    "locator",
                    "statement_date",
                    "language",
                )
            ):
                raise ValueError("REFRESH_REVIEW_INVALID")
            reviewed.add(key)
    return reviewed


def plan_synopsis_refresh(
    *,
    previous_bundle: Mapping[str, object],
    current_bundle: Mapping[str, object],
    previous_synopsis: PublicSynopsisRead,
    current_membership: ApprovedTopicIntersection,
    expected_previous_dataset_sha256: str,
    expected_current_dataset_sha256: str,
    expected_previous_synopsis_sha256: str,
    expected_previous_synopsis_read_sha256: str,
    now: datetime,
) -> SynopsisRefreshPlan:
    """Determine which old reviewed citations need *human* refresh.

    The three expected digests MUST be retrieved from independent owner state;
    self-pinning from the current mutable objects provides no authentication.
    An unchanged plan does not authorize serving or publication of old text.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("REFRESH_TIMESTAMP_INVALID")
    if not isinstance(previous_bundle, Mapping) or not isinstance(
        current_bundle, Mapping
    ):
        raise ValueError("REFRESH_PUBLIC_BUNDLE_INVALID")
    previous_bundle = _frozen_public_bundle(previous_bundle)
    current_bundle = _frozen_public_bundle(current_bundle)
    try:
        validate_public_bundle(previous_bundle, allow_statement_v3=True)
        validate_public_bundle(current_bundle, allow_statement_v3=True)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("REFRESH_PUBLIC_BUNDLE_INVALID") from exc
    for value, expected in (
        (previous_bundle["dataset_sha256"], expected_previous_dataset_sha256),
        (current_bundle["dataset_sha256"], expected_current_dataset_sha256),
    ):
        if not _sha(expected) or value != expected:
            raise ValueError("REFRESH_PIN_MISMATCH")
    if (
        not _sha(expected_previous_synopsis_sha256)
        or not isinstance(previous_synopsis, PublicSynopsisRead)
        or expected_previous_synopsis_sha256 != previous_synopsis.fingerprint
    ):
        raise ValueError("REFRESH_PIN_MISMATCH")
    if (
        not _sha(expected_previous_synopsis_read_sha256)
        or synopsis_read_sha256(previous_synopsis)
        != expected_previous_synopsis_read_sha256
    ):
        raise ValueError("REFRESH_READ_PIN_MISMATCH")
    reviewed = _validate_review(previous_synopsis, previous_bundle)
    if not isinstance(current_membership, ApprovedTopicIntersection):
        raise ValueError("REFRESH_MEMBERSHIP_INVALID")
    reasons: set[str] = set()
    current_utc = now.astimezone(timezone.utc)
    if (
        current_membership.status != "APPROVED"
        or current_membership.dataset_sha256 != current_bundle["dataset_sha256"]
        or current_membership.person_id != previous_synopsis.person_id
        or current_membership.topic_id != previous_synopsis.topic_id
    ):
        reasons.add("TOPIC_MEMBERSHIP_NOT_CURRENT")
    stamped = _stamp(current_membership.currentness_attested_at)
    expires = _stamp(current_membership.currentness_valid_until)
    snapshot = _stamp(current_bundle["generated_at"])
    if (
        stamped is None
        or expires is None
        or snapshot is None
        or stamped < snapshot
        or stamped > current_utc
        or expires <= stamped
        or snapshot > current_utc
    ):
        reasons.add("TOPIC_MEMBERSHIP_NOT_CURRENT")
    if expires is None or expires <= current_utc:
        reasons.add("TOPIC_MEMBERSHIP_EXPIRED")
    allowed = current_membership.statement_versions
    if (
        type(allowed) is not tuple
        or len(allowed) > 512
        or any(
            type(item) is not tuple
            or len(item) != 2
            or any(type(part) is not str or not 0 < len(part) <= 150 for part in item)
            for item in allowed
        )
        or len(allowed) != len(set(allowed))
    ):
        reasons.add("TOPIC_MEMBERSHIP_NOT_CURRENT")
        allowed = ()
    old_rows = {
        (r["statement_id"], r["version_id"]): r for r in previous_bundle["statements"]
    }
    new_rows = {
        (r["statement_id"], r["version_id"]): r for r in current_bundle["statements"]
    }
    removed = tuple(
        sorted(key for key in reviewed if key not in new_rows or key not in allowed)
    )
    changed = tuple(
        sorted(
            key
            for key in reviewed
            if key in new_rows
            and key in allowed
            and any(
                old_rows[key][field] != new_rows[key][field]
                for field in _MATERIAL_FIELDS
            )
        )
    )
    if removed:
        reasons.add("CITED_STATEMENT_REMOVED_OR_TOPIC_REVOKED")
    if changed:
        reasons.add("CITED_SOURCE_MATERIAL_CHANGED")
    if previous_bundle["dataset_sha256"] != current_bundle["dataset_sha256"]:
        reasons.add("SOURCE_PROJECTION_VERSION_CHANGED")
    # Public dataset digests intentionally omit generated_at. A later projection
    # with otherwise identical rows must not inherit the former snapshot's
    # reviewer-currentness or appear identical to its published synopsis.
    if previous_bundle["generated_at"] != current_bundle["generated_at"]:
        reasons.add("SOURCE_PROJECTION_TIMESTAMP_CHANGED")
    status = (
        "WITHHELD_REVIEW_REQUIRED"
        if "TOPIC_MEMBERSHIP_NOT_CURRENT" in reasons
        or "TOPIC_MEMBERSHIP_EXPIRED" in reasons
        else "RECHECK_REQUIRED"
        if reasons
        else "NO_CHANGE_REVIEW_PENDING"
    )
    material = {
        "version": VERSION,
        "status": status,
        "reasons": sorted(reasons),
        "before": previous_bundle["dataset_sha256"],
        "after": current_bundle["dataset_sha256"],
        "before_generated_at": previous_bundle["generated_at"],
        "after_generated_at": current_bundle["generated_at"],
        "synopsis": previous_synopsis.fingerprint,
        "changed": changed,
        "removed": removed,
    }
    digest = hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()
    return SynopsisRefreshPlan(
        version=VERSION,
        status=status,
        reason_codes=tuple(sorted(reasons)),
        previous_dataset_sha256=previous_bundle["dataset_sha256"],
        current_dataset_sha256=current_bundle["dataset_sha256"],
        changed_citation_keys=changed,
        removed_citation_keys=removed,
        snapshot_sha256=digest,
    )
