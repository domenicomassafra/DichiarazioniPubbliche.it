"""Private Studio candidate-match inspection and bounded review handoff.

Reads persisted DP-212 match results without re-running models, promoting a
candidate or claiming that an unreviewed match has been approved. The
optional handoff is a private queue entry, never a review_event or publication.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping, Protocol

from dichiarazioni_pubbliche.candidate_matching import (
    MATCHING_VERSION,
    deterministic_match_result_id,
    deterministic_match_run_id,
    matching_input_fingerprint,
    rank_candidate_matches,
)

STUDIO_CANDIDATE_REVIEW_VERSION = "studio-candidate-review-readonly-v1"
_ID = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DISPOSITION = {
    "DUPLICATE_EXTRACTION": "PROPOSE_CLUSTER",
    "SAME_PROPOSITION": "PROPOSE_CLUSTER",
    "RELATED": "NO_CLUSTER",
    "DIFFERENT": "NO_CLUSTER",
    "UNCERTAIN": "HOLD",
}
_METHODS_BY_CLASS = {
    "DUPLICATE_EXTRACTION": {"SOURCE_SELECTOR_OVERLAP"},
    "SAME_PROPOSITION": {"EXACT_NORMALIZED", "LEXICAL_TRIGRAM"},
    "RELATED": {"LEXICAL_TRIGRAM"},
    "DIFFERENT": {"LEXICAL_TRIGRAM"},
    "UNCERTAIN": {"LEXICAL_TRIGRAM"},
}
_SUPPORTING_CODES = {
    "SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT", "HIGH_LEXICAL_OVERLAP",
    "SHARED_ENTITIES", "SHARED_TOPICS", "RELATED_LEXICAL_OR_ENTITY_CONTEXT",
    "AMBIGUOUS_LEXICAL_OVERLAP", "SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE",
}
_CONTRADICTING_CODES = {
    "LOW_LEXICAL_NO_SHARED_CONTEXT", "CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS",
}
_SCOPE_CONFLICT_CODES = {"CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS"}
_SCOPE_SUPPORT_CODES = {"SAME_CLAIM_TYPE", "SAME_TEMPORAL_SCOPE"}
REVIEW_HANDOFF_VERSION = "studio-candidate-private-review-handoff-v1"
_HANDOFF_ACTIONS = frozenset({
    "REVIEW_PROMOTION", "REVIEW_LINK", "REVIEW_REJECT",
    "REVIEW_HOLD", "REVIEW_SPLIT_CLUSTER",
})
_HANDOFF_FIELDS = frozenset({
    "contract_version", "handoff_id", "candidate_id", "run_id",
    "result_id", "input_fingerprint", "action", "actor_ref",
    "credential_id", "credential_fingerprint", "reason_code",
    "review_context_sha256",
    "status", "currentness", "publication_authority", "review_authority",
    "promotion_authority", "receipt_sha256",
})


def _validate_feature_semantics(
    match_class: str, method: str,
    supporting: tuple[str, ...], contradicting: tuple[str, ...],
) -> None:
    """Read the actual classifier's feature contract, not a class label alone."""
    support, contrary = set(supporting), set(contradicting)
    if (
        len(support) != len(supporting) or len(contrary) != len(contradicting)
        or ("SAME_CLAIM_TYPE" in support and "CLAIM_TYPE_MISMATCH" in contrary)
        or ("SAME_TEMPORAL_SCOPE" in support and "TEMPORAL_SCOPE_DIFFERS" in contrary)
    ):
        raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
    primary_support = support - _SCOPE_SUPPORT_CODES
    primary_contrary = contrary - _SCOPE_CONFLICT_CODES
    expected = {
        ("DUPLICATE_EXTRACTION", "SOURCE_SELECTOR_OVERLAP"):
            ({"SAME_CONTENT_SELECTOR", "EXACT_NORMALIZED_TEXT"}, set()),
        ("SAME_PROPOSITION", "EXACT_NORMALIZED"):
            ({"EXACT_NORMALIZED_TEXT"}, set()),
        ("RELATED", "LEXICAL_TRIGRAM"):
            ({"RELATED_LEXICAL_OR_ENTITY_CONTEXT"}, set()),
        ("DIFFERENT", "LEXICAL_TRIGRAM"):
            (set(), {"LOW_LEXICAL_NO_SHARED_CONTEXT"}),
        ("UNCERTAIN", "LEXICAL_TRIGRAM"):
            ({"AMBIGUOUS_LEXICAL_OVERLAP"}, set()),
    }
    if (match_class, method) == ("SAME_PROPOSITION", "LEXICAL_TRIGRAM"):
        if (
            "HIGH_LEXICAL_OVERLAP" not in primary_support
            or not primary_support.intersection({"SHARED_ENTITIES", "SHARED_TOPICS"})
            or not primary_support <= {
                "HIGH_LEXICAL_OVERLAP", "SHARED_ENTITIES", "SHARED_TOPICS"
            }
            or primary_contrary
        ):
            raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")
    elif (primary_support, primary_contrary) != expected.get(
        (match_class, method), (None, None)
    ):
        raise ValueError("STUDIO_CANDIDATE_FEATURE_SEMANTICS_INVALID")


class CandidateMatchReader(Protocol):
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]: ...


class CandidateMatchCurrentReader(CandidateMatchReader, Protocol):
    def load_candidate(self, claim_candidate_id: str) -> Any: ...
    def load_targets(self, claim_candidate_id: str, *, limit: int = 200) -> tuple[Any, ...]: ...


class CandidatePromotionContextReader(Protocol):
    def context(self, candidate_id: str) -> dict[str, Any] | None: ...


def _safe_id(value: object) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("STUDIO_CANDIDATE_REFERENCE_INVALID")
    return value


def _features(value: object, allowed_codes: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 24:
        raise ValueError("STUDIO_CANDIDATE_FEATURES_INVALID")
    codes: list[str] = []
    for entry in value:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("code"), str):
            raise ValueError("STUDIO_CANDIDATE_FEATURE_INVALID")
        code = entry["code"]
        if not _CODE.fullmatch(code) or code not in allowed_codes:
            raise ValueError("STUDIO_CANDIDATE_FEATURE_CODE_INVALID")
        codes.append(code)
    return tuple(codes)


def inspect_candidate_match_run(
    store: CandidateMatchReader,
    *,
    run_id: str,
    claim_candidate_id: str,
) -> dict[str, object]:
    run_id = _safe_id(run_id)
    claim_candidate_id = _safe_id(claim_candidate_id)
    try:
        run = store.get_run(run_id)
        if not isinstance(run, Mapping):
            raise ValueError("STUDIO_CANDIDATE_RUN_MISSING")
        if run.get("id") != run_id or run.get("claim_candidate_id") != claim_candidate_id:
            raise ValueError("STUDIO_CANDIDATE_RUN_BINDING_MISMATCH")
        if run.get("matching_version") != MATCHING_VERSION:
            raise ValueError("STUDIO_CANDIDATE_RUN_VERSION_INVALID")
        fingerprint = run.get("input_fingerprint")
        if not isinstance(fingerprint, str) or not _HASH.fullmatch(fingerprint):
            raise ValueError("STUDIO_CANDIDATE_RUN_FINGERPRINT_INVALID")
        if run_id != deterministic_match_run_id(claim_candidate_id, fingerprint):
            raise ValueError("STUDIO_CANDIDATE_RUN_BINDING_MISMATCH")
        if run.get("status") != "COMPLETED":
            raise ValueError("STUDIO_CANDIDATE_RUN_INCOMPLETE")
        count = run.get("result_count")
        if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= 30:
            raise ValueError("STUDIO_CANDIDATE_RUN_COUNT_INVALID")
        rows = store.load_results(run_id)
        if len(rows) != count:
            raise ValueError("STUDIO_CANDIDATE_RUN_RESULT_MISMATCH")
        results: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        seen_targets: set[tuple[str, str]] = set()
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise ValueError("STUDIO_CANDIDATE_RESULT_INVALID")
            if row.get("matching_version") != MATCHING_VERSION:
                raise ValueError("STUDIO_CANDIDATE_RESULT_VERSION_INVALID")
            if row.get("status") != "CANDIDATE":
                raise ValueError("STUDIO_CANDIDATE_RESULT_STATUS_INVALID")
            result_id = _safe_id(row.get("id"))
            rank = row.get("rank")
            if (result_id in seen_ids or type(rank) is not int or rank != index):
                raise ValueError("STUDIO_CANDIDATE_RESULT_ORDER_INVALID")
            seen_ids.add(result_id)
            match_class = row.get("match_class")
            target_type = row.get("target_type")
            if target_type not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}:
                raise ValueError("STUDIO_CANDIDATE_MATCH_CLASS_INVALID")
            target_id = _safe_id(row.get("target_id"))
            target = (target_type, target_id)
            if (target in seen_targets or
                    result_id != deterministic_match_result_id(run_id, target_type, target_id)):
                raise ValueError("STUDIO_CANDIDATE_RESULT_BINDING_MISMATCH")
            seen_targets.add(target)
            supporting_codes = _features(row.get("supporting_features"), _SUPPORTING_CODES)
            contradicting_codes = _features(row.get("contradicting_features"), _CONTRADICTING_CODES)
            disposition = (
                "HOLD" if _SCOPE_CONFLICT_CODES.intersection(contradicting_codes)
                else _DISPOSITION.get(match_class)
            )
            if (
                match_class not in _DISPOSITION
                or row.get("method") not in _METHODS_BY_CLASS[match_class]
                or row.get("disposition") != disposition
                or (row.get("proposition_cluster_id") is not None) !=
                   (disposition == "PROPOSE_CLUSTER")
            ):
                raise ValueError("STUDIO_CANDIDATE_MATCH_CLASS_INVALID")
            _validate_feature_semantics(
                match_class, row["method"], supporting_codes, contradicting_codes,
            )
            results.append({
                "result_id": result_id,
                "target_id": target_id,
                "target_type": target_type,
                "match_class": match_class,
                "matching_method": row["method"],
                "suggested_disposition": disposition,
                "supporting_feature_codes": supporting_codes,
                "contradicting_feature_codes": contradicting_codes,
                "proposition_cluster_id": _safe_id(row["proposition_cluster_id"])
                if row.get("proposition_cluster_id") is not None else None,
                "promotion_enabled": False,
            })
    except (ValueError, TypeError):
        raise
    except Exception:
        raise RuntimeError("STUDIO_CANDIDATE_MATCH_STORE_UNAVAILABLE") from None

    return {
        "contract_version": STUDIO_CANDIDATE_REVIEW_VERSION,
        "matching_version": MATCHING_VERSION,
        "run_id": run_id,
        "claim_candidate_id": claim_candidate_id,
        "input_fingerprint": fingerprint,
        "currentness": "UNVERIFIED",
        "review_authority": False,
        "publication_authority": False,
        "private_only": True,
        "results": results,
    }


def inspect_candidate_review_readiness(
    store: CandidateMatchCurrentReader,
    promotion_store: CandidatePromotionContextReader,
    *,
    run_id: str,
    claim_candidate_id: str,
    target_limit: int = 200,
) -> dict[str, object]:
    """Check the *current* persisted candidate/target snapshot before handoff.

    It independently recomputes the canonical DP-212 fingerprint and every
    ranked classification/feature. Source wording and private feature values
    remain inside the trusted backend; only safe IDs/codes reach Studio.
    Matching currentness is not a review or DP-117 promotion authorization.
    """
    if type(target_limit) is not int or not 1 <= target_limit <= 200:
        raise ValueError("STUDIO_CANDIDATE_TARGET_LIMIT_INVALID")
    receipt = inspect_candidate_match_run(
        store, run_id=run_id, claim_candidate_id=claim_candidate_id,
    )
    try:
        candidate = store.load_candidate(claim_candidate_id)
        targets = store.load_targets(claim_candidate_id, limit=target_limit)
        if candidate is None or not isinstance(targets, (list, tuple)):
            return receipt | {
                "currentness": "UNVERIFIED", "currentness_reason": "SOURCE_INPUT_UNAVAILABLE",
                "promotion_blockers": ["MATCH_SOURCE_INPUT_UNAVAILABLE"],
                "review_queue_eligible": False,
            }
        current_fingerprint = matching_input_fingerprint(candidate, targets)
        computed = rank_candidate_matches(candidate, targets)
        visible = receipt["results"]
        persisted = store.load_results(run_id)
        current = (
            current_fingerprint == receipt["input_fingerprint"]
            and len(computed) == len(visible) == len(persisted)
        )
        if current:
            for expected, shown, stored in zip(computed, visible, persisted):
                target = expected.target.proposition
                expected_id = deterministic_match_result_id(
                    run_id, target.member_type, target.member_id,
                )
                try:
                    score = float(stored["lexical_score"])
                except (KeyError, ValueError, TypeError, OverflowError):
                    score = float("nan")
                if (
                    shown["result_id"] != expected_id
                    or shown["target_type"] != target.member_type
                    or shown["target_id"] != target.member_id
                    or shown["match_class"] != expected.match.match_class
                    or shown["matching_method"] != expected.match.method
                    or shown["suggested_disposition"] != expected.disposition
                    or shown["proposition_cluster_id"] != expected.cluster_id
                    or tuple(shown["supporting_feature_codes"]) != tuple(
                        feature["code"] for feature in expected.supporting_features
                    )
                    or tuple(shown["contradicting_feature_codes"]) != tuple(
                        feature["code"] for feature in expected.contradicting_features
                    )
                    or stored.get("id") != expected_id
                    or stored.get("rank") != expected.rank
                    or stored.get("supporting_features") != list(expected.supporting_features)
                    or stored.get("contradicting_features") != list(expected.contradicting_features)
                    or not abs(score - expected.match.lexical_score) <= 0.000001
                ):
                    current = False
                    break
        # Read back the exact current DP-117 context. This is for a blocker
        # preview, never a substitute for DP-117's transactional promotion.
        context = promotion_store.context(claim_candidate_id)
        if context is not None and not isinstance(context, Mapping):
            raise ValueError("STUDIO_CANDIDATE_PROMOTION_CONTEXT_INVALID")
        context_snapshot: dict[str, object] = {}
        if context is not None:
            for key in (
                "candidate_id", "candidate_status", "content_id", "promoted_claim_id",
                "statement_candidate_id", "statement_status", "statement_reviewed",
                "claim_candidate_reviewed", "speaker_person_id", "speaker_is_public",
                "passage_count", "written_count", "media_count", "duplicate_target_ids",
            ):
                context_snapshot[key] = context.get(key)
            passages = context.get("passages")
            if isinstance(passages, list):
                context_snapshot["passages"] = [
                    {key: row.get(key) for key in (
                        "passage_id", "capture_id", "capture_sha256",
                        "capture_status", "capture_hold_status", "canonical_segment_id",
                        "segment_status", "segment_publication_blocked",
                    )}
                    for row in passages if isinstance(row, Mapping)
                ]
        context_digest = hashlib.sha256(_canonical(context_snapshot)).hexdigest()
        blockers: list[str] = []
        if not current:
            blockers.append("MATCH_RUN_STALE_OR_CHANGED")
        if context is None:
            blockers.append("PROMOTION_CONTEXT_UNAVAILABLE")
        else:
            state = context.get("candidate_status")
            if state not in {"CANDIDATE", "DUPLICATE"}:
                blockers.append("PROMOTION_CANDIDATE_STATE_BLOCKED")
            if not context.get("claim_candidate_reviewed"):
                blockers.append("PROMOTION_CLAIM_CANDIDATE_NOT_REVIEWED")
            if context.get("statement_status") != "APPROVED" or not context.get("statement_reviewed"):
                blockers.append("PROMOTION_STATEMENT_NOT_REVIEWED")
            if not context.get("speaker_person_id") or not context.get("speaker_is_public"):
                blockers.append("PROMOTION_ATTRIBUTION_MISSING")
            if type(context.get("passage_count")) is not int or context["passage_count"] != 1:
                blockers.append("PROMOTION_PROVENANCE_NOT_ATOMIC")
            if len(context.get("duplicate_target_ids") or []) > 1:
                blockers.append("PROMOTION_AMBIGUOUS_DUPLICATE")
        # DP-117 performs additional channel/quote/rights/reviewer checks and
        # mandatory read-back in its own transaction. Never claim READY here.
        blockers.append("DP117_TRANSACTIONAL_PROMOTION_REVALIDATION_REQUIRED")
        source_refs: list[dict[str, str | None]] = []
        if context is not None:
            passages = context.get("passages")
            if isinstance(passages, list) and len(passages) <= 2:
                for passage in passages:
                    if not isinstance(passage, Mapping):
                        raise ValueError("STUDIO_CANDIDATE_PASSAGE_INVALID")
                    source_refs.append({
                        "passage_id": _safe_id(passage["passage_id"])
                        if passage.get("passage_id") is not None else None,
                        "capture_id": _safe_id(passage["capture_id"])
                        if passage.get("capture_id") is not None else None,
                        "segment_id": _safe_id(passage["canonical_segment_id"])
                        if passage.get("canonical_segment_id") is not None else None,
                        "capture_sha256": str(passage["capture_sha256"])
                        if isinstance(passage.get("capture_sha256"), str)
                        and _HASH.fullmatch(passage["capture_sha256"]) else None,
                    })
        return receipt | {
            "currentness": "CURRENT" if current else "STALE",
            "currentness_reason": "EXACT_INPUT_AND_RESULT_REPLAY" if current else "INPUT_OR_RESULT_CHANGED",
            "review_authority": False,
            "publication_authority": False,
            "promotion_authority": False,
            "review_context_sha256": context_digest,
            "review_queue_eligible": bool(current and context is not None
                                          and context.get("candidate_status") in {"CANDIDATE", "DUPLICATE"}),
            "promotion_blockers": blockers,
            "source_references": source_refs,
        }
    except (ValueError, TypeError):
        raise
    except Exception:
        raise RuntimeError("STUDIO_CANDIDATE_CURRENTNESS_UNAVAILABLE") from None


class CandidateReviewerCredentialAuthority(Protocol):
    def identity(self, credential_id: str, *, require_active: bool = True) -> Any: ...


def _canonical(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _digest_handoff(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


class LocalCandidateReviewHandoffQueue:
    """An explicit 0700 operator-only handoff spool, separate from review_event.

    A queue entry requests a later authenticated human decision. It never
    changes claim_candidate, review_event, matching, cluster, or publication.
    Replay reads actual 0600 bytes; it does not reconstruct a model decision.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ValueError("STUDIO_REVIEW_QUEUE_SYMLINK_FORBIDDEN")
        info = self.root.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("STUDIO_REVIEW_QUEUE_ROOT_UNSAFE")

    def _file(self, handoff_id: str) -> Path:
        if not re.fullmatch(r"candidate-review:[0-9a-f]{64}", handoff_id):
            raise ValueError("STUDIO_REVIEW_HANDOFF_ID_INVALID")
        return self.root / (handoff_id + ".json")

    def read(self, handoff_id: str) -> dict[str, object] | None:
        path = self._file(handoff_id)
        try:
            descriptor = os.open(
                path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                getattr(os, "O_CLOEXEC", 0),
            )
        except FileNotFoundError:
            return None
        try:
            details = os.fstat(descriptor)
            if (not stat.S_ISREG(details.st_mode)
                    or details.st_uid != os.geteuid()
                    or stat.S_IMODE(details.st_mode) & 0o077
                    or not 10 <= details.st_size <= 4096):
                raise ValueError("STUDIO_REVIEW_QUEUE_RECEIPT_UNSAFE")
            with os.fdopen(descriptor, "rb", closefd=False) as file:
                encoded = file.read(4097)
        finally:
            os.close(descriptor)
        try:
            value = json.loads(encoded)
        except (UnicodeError, ValueError):
            raise ValueError("STUDIO_REVIEW_QUEUE_RECEIPT_INVALID") from None
        if (not isinstance(value, dict) or set(value) != _HANDOFF_FIELDS
                or value.get("contract_version") != REVIEW_HANDOFF_VERSION
                or value.get("handoff_id") != handoff_id
                or value.get("status") != "QUEUED_FOR_HUMAN_REVIEW"
                or value.get("currentness") != "CURRENT_AT_ENQUEUE"
                or value.get("review_authority") is not False
                or value.get("promotion_authority") is not False
                or value.get("publication_authority") is not False
                or value.get("action") not in _HANDOFF_ACTIONS
                or not _HASH.fullmatch(str(value.get("receipt_sha256")))
                or value["receipt_sha256"] != _digest_handoff({
                    key: val for key, val in value.items() if key != "receipt_sha256"
                })):
            raise ValueError("STUDIO_REVIEW_QUEUE_RECEIPT_TAMPERED")
        return value

    def enqueue(self, payload: dict[str, object]) -> dict[str, object]:
        handoff_id = str(payload["handoff_id"])
        path = self._file(handoff_id)
        complete = payload | {"receipt_sha256": _digest_handoff(payload)}
        encoded = _canonical(complete) + b"\n"
        if len(encoded) > 4096:
            raise ValueError("STUDIO_REVIEW_QUEUE_RECEIPT_TOO_LARGE")
        created = False
        try:
            fd = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                getattr(os, "O_NOFOLLOW", 0), 0o600,
            )
            created = True
        except FileExistsError:
            prior = self.read(handoff_id)
            if prior != complete:
                raise ValueError("STUDIO_REVIEW_QUEUE_RECEIPT_CONFLICT")
            return prior
        try:
            with os.fdopen(fd, "wb", closefd=False) as file:
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            directory_fd = os.open(
                self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
        finally:
            os.close(fd)
        return self.read(handoff_id) or complete


def submit_candidate_review_handoff(
    store: CandidateMatchCurrentReader,
    promotion_store: CandidatePromotionContextReader,
    queue: LocalCandidateReviewHandoffQueue,
    authority: CandidateReviewerCredentialAuthority,
    *,
    run_id: str,
    claim_candidate_id: str,
    result_id: str,
    action: str,
    credential_id: str,
    credential_secret_hex: str,
    reason_code: str,
    expected_input_fingerprint: str,
    expected_review_context_sha256: str | None = None,
) -> dict[str, object]:
    """Human-authorized *enqueue only*; never invoke DP-117 or approve review.

    The caller must be an operator-local authenticated process. The ACTIVE
    off-DB credential must be proven using its secret; a public credential ID
    alone cannot impersonate the named reviewer. The secret is never persisted.
    Before any durable write, the source/target DP-212 fingerprint and ranked
    results are revalidated. A reviewer later rechecks all provenance and the
    DP-117 gate before deciding; enqueue has no approval semantics.
    """
    run_id = _safe_id(run_id)
    claim_candidate_id = _safe_id(claim_candidate_id)
    result_id = _safe_id(result_id)
    credential_id = _safe_id(credential_id)
    if action not in _HANDOFF_ACTIONS:
        raise ValueError("STUDIO_REVIEW_HANDOFF_ACTION_INVALID")
    if not isinstance(reason_code, str) or not _CODE.fullmatch(reason_code):
        raise ValueError("STUDIO_REVIEW_HANDOFF_REASON_INVALID")
    if not isinstance(expected_input_fingerprint, str) or not _HASH.fullmatch(expected_input_fingerprint):
        raise ValueError("STUDIO_REVIEW_HANDOFF_FINGERPRINT_INVALID")
    if (not isinstance(credential_secret_hex, str)
            or not _HASH.fullmatch(credential_secret_hex)):
        raise ValueError("STUDIO_REVIEW_HANDOFF_CREDENTIAL_PROOF_INVALID")
    if expected_review_context_sha256 is not None and (
        not isinstance(expected_review_context_sha256, str)
        or not _HASH.fullmatch(expected_review_context_sha256)
    ):
        raise ValueError("STUDIO_REVIEW_HANDOFF_CONTEXT_FINGERPRINT_INVALID")
    identity = authority.identity(credential_id, require_active=True)
    if (getattr(identity, "status", None) != "ACTIVE"
            or getattr(identity, "credential_id", None) != credential_id
            or not isinstance(getattr(identity, "actor_ref", None), str)
            or not _ID.fullmatch(identity.actor_ref)
            or not isinstance(getattr(identity, "credential_fingerprint", None), str)
            or not _HASH.fullmatch(identity.credential_fingerprint)):
        raise ValueError("STUDIO_REVIEW_HANDOFF_AUTHORITY_INVALID")
    supplied_fingerprint = hashlib.sha256(
        bytes.fromhex(credential_secret_hex),
    ).hexdigest()
    if not hmac.compare_digest(supplied_fingerprint, identity.credential_fingerprint):
        raise ValueError("STUDIO_REVIEW_HANDOFF_CREDENTIAL_PROOF_REFUSED")
    review = inspect_candidate_review_readiness(
        store, promotion_store, run_id=run_id,
        claim_candidate_id=claim_candidate_id,
    )
    if (review["currentness"] != "CURRENT"
            or review["input_fingerprint"] != expected_input_fingerprint
            or (expected_review_context_sha256 is not None
                and review["review_context_sha256"] != expected_review_context_sha256)
            or not review["review_queue_eligible"]):
        raise ValueError("STUDIO_REVIEW_HANDOFF_STALE_OR_BLOCKED")
    selected = next(
        (item for item in review["results"] if item["result_id"] == result_id),
        None,
    )
    if selected is None:
        raise ValueError("STUDIO_REVIEW_HANDOFF_RESULT_NOT_FOUND")
    if action == "REVIEW_LINK" and selected["suggested_disposition"] != "PROPOSE_CLUSTER":
        raise ValueError("STUDIO_REVIEW_HANDOFF_LINK_NOT_SUGGESTED")
    # Recheck the source snapshot and identity before enqueue. The recorded
    # fingerprint remains a proof of checked inputs, not permanent freshness.
    again = inspect_candidate_review_readiness(
        store, promotion_store, run_id=run_id,
        claim_candidate_id=claim_candidate_id,
    )
    identity_again = authority.identity(credential_id, require_active=True)
    if (again["currentness"] != "CURRENT"
            or again["input_fingerprint"] != expected_input_fingerprint
            or again["review_context_sha256"] != review["review_context_sha256"]
            or not again["review_queue_eligible"]
            or identity_again != identity):
        raise ValueError("STUDIO_REVIEW_HANDOFF_CHANGED_DURING_ENQUEUE")
    material = {
        "candidate_id": claim_candidate_id, "run_id": run_id,
        "result_id": result_id, "action": action,
        "input_fingerprint": expected_input_fingerprint,
        "review_context_sha256": review["review_context_sha256"],
        "credential_fingerprint": identity.credential_fingerprint,
    }
    handoff_id = "candidate-review:" + _digest_handoff(material)
    return queue.enqueue({
        "contract_version": REVIEW_HANDOFF_VERSION,
        "handoff_id": handoff_id,
        "candidate_id": claim_candidate_id, "run_id": run_id,
        "result_id": result_id, "input_fingerprint": expected_input_fingerprint,
        "review_context_sha256": review["review_context_sha256"],
        "action": action, "actor_ref": identity.actor_ref,
        "credential_id": credential_id,
        "credential_fingerprint": identity.credential_fingerprint,
        "reason_code": reason_code, "status": "QUEUED_FOR_HUMAN_REVIEW",
        "currentness": "CURRENT_AT_ENQUEUE", "publication_authority": False,
        "review_authority": False, "promotion_authority": False,
    })


__all__ = [
    "STUDIO_CANDIDATE_REVIEW_VERSION", "inspect_candidate_match_run",
    "inspect_candidate_review_readiness",
    "REVIEW_HANDOFF_VERSION", "LocalCandidateReviewHandoffQueue",
    "submit_candidate_review_handoff",
]
