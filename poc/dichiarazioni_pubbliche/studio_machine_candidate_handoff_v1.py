"""DP-242 private Studio-to-machine *preview*, not an authority or transition.

Two existing persisted read boundaries are reused. No candidate, annotation,
review_event, machine command or public projection is created by this module.
The eventual B authority must independently authenticate and re-read all inputs
in the same transactional fence; these digests are not signatures or write tokens.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from dichiarazioni_pubbliche.studio_candidate_review import (
    inspect_candidate_review_readiness,
)
from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import (
    DiscoveryInboxWorkflow,
    _SELECTED_SQL,
    _present,
)
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    _validated_ref,
    _validated_revision,
)


STUDIO_MACHINE_PREVIEW_VERSION = "studio-machine-candidate-preflight-v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUEST = re.compile(r"[A-Za-z][A-Za-z0-9_:-]{0,127}\Z")


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"STUDIO_MACHINE_{name}_INVALID")
    return value


def _key(value: object) -> str:
    if not isinstance(value, str) or not _REQUEST.fullmatch(value):
        raise ValueError("STUDIO_MACHINE_REQUEST_KEY_INVALID")
    return value


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _receipt(payload: dict[str, object], *, request_key: str) -> dict[str, object]:
    # Digest binds the exact scoped intent but is not a durable replay record,
    # credential, approval, receipt from B, or a permission-bearing token.
    fingerprint = hashlib.sha256(
        _canonical(payload | {"request_key": request_key})
    ).hexdigest()
    return payload | {
        "contract_version": STUDIO_MACHINE_PREVIEW_VERSION,
        "intent_fingerprint": fingerprint,
        "private_only": True,
        "preview_only": True,
        "enqueued": False,
        "source_rights_verified": False,
        "human_review_approved": False,
        "machine_review_approved": False,
        "review_authority": False,
        "dispatch_authorized": False,
        "publication_authority": False,
    }


def _reload_hit(
    workflow: DiscoveryInboxWorkflow, *, collection_id: str, hit_id: str
) -> dict[str, object]:
    """Read one persisted scoped Hit, not a caller-supplied HTML/JSON snapshot."""
    try:
        raw = workflow.store.run(
            _SELECTED_SQL, collection_id=collection_id, selected_ids=hit_id, limit=1
        )
    except Exception:
        raise RuntimeError("STUDIO_MACHINE_DISCOVERY_STORE_UNAVAILABLE") from None
    if not isinstance(raw, str) or len(raw) > 48_000:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID")
    lines = [line for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND")
    try:
        data = json.loads(lines[0])
        if not isinstance(data, dict):
            raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID")
        result = _present(data, collection_id=collection_id)
    except ValueError as exc:
        if str(exc) == "STUDIO_INBOX_COLLECTION_MISMATCH":
            raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND") from None
        raise
    except (TypeError, json.JSONDecodeError):
        raise ValueError("STUDIO_MACHINE_DISCOVERY_RECORD_INVALID") from None
    if result["hit_id"] != hit_id:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SCOPE_NOT_FOUND")
    return result


def preview_discovery_machine_exception(
    workflow: DiscoveryInboxWorkflow,
    *,
    collection_id: str,
    hit_id: str,
    request_key: str,
    expected_revision: int,
    expected_snapshot_sha256: str,
) -> dict[str, object]:
    """Determine a specific private exception for one *real persisted* Hit.

    The retry re-reads the exact SQL selector. It detects an observed change,
    not a transaction lock; no caller may use this preview to enqueue/publish.
    """
    if not isinstance(workflow, DiscoveryInboxWorkflow):
        raise ValueError("STUDIO_MACHINE_DISCOVERY_WORKFLOW_INVALID")
    collection_id = _validated_ref(collection_id)
    hit_id = _validated_ref(hit_id)
    key = _key(request_key)
    revision = _validated_revision(expected_revision, expected=True)
    expected = _sha(expected_snapshot_sha256, "SNAPSHOT")
    first = _reload_hit(workflow, collection_id=collection_id, hit_id=hit_id)
    if first["annotation_revision"] != revision:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_REVISION_CONFLICT")
    if first["snapshot_sha256"] != expected:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_SNAPSHOT_CHANGED")
    if first["queue"] == "AMBIGUOUS_CONTENT_IDENTITY" or first["content_id"] is None:
        action = "INVESTIGATE_CONTENT_IDENTITY"
    elif first["current"] is not True:
        action = "REFRESH_DISCOVERY_PROVENANCE"
    elif first["latest_annotation"] == "REJECTED":
        action = "HOLD_REJECTED_ANNOTATION"
    elif "DISCOVERY_CONTENT_RIGHTS_UNCLEARED" in first["blockers"]:
        action = "REVALIDATE_SOURCE_RIGHTS"
    else:
        action = "REVALIDATE_RIGHTS_AND_AUTHORITY"
    second = _reload_hit(workflow, collection_id=collection_id, hit_id=hit_id)
    if first != second:
        raise ValueError("STUDIO_MACHINE_DISCOVERY_CHANGED_DURING_PREFLIGHT")
    return _receipt(
        {
            "family": "DISCOVERY_HIT",
            "status": "HELD_EXCEPTION",
            "action": action,
            "collection_id": collection_id,
            "hit_id": hit_id,
            "content_id": first["content_id"],
            "queue": first["queue"],
            "annotation_revision": revision,
            "snapshot_sha256": expected,
            "provenance": first["provenance_path"],
            "blockers": tuple(first["blockers"]),
            "requires_fresh_transactional_cas": True,
            "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
        },
        request_key=key,
    )


def preview_candidate_machine_handoff(
    match_store: Any,
    promotion_store: Any,
    *,
    run_id: str,
    claim_candidate_id: str,
    result_id: str,
    request_key: str,
    expected_content_id: str,
    expected_capture_sha256: str,
    expected_input_fingerprint: str,
) -> dict[str, object]:
    """Recompute a persisted match and source reference, refusing stale input.

    Legacy reviewer state is deliberately NOT promoted to machine authority.
    A successful source preflight is HELD until an independent B API/signature,
    rights record and fenced downstream execution actually exist.
    """
    run_id, claim_candidate_id = (
        _validated_ref(run_id),
        _validated_ref(claim_candidate_id),
    )
    result_id = _validated_ref(result_id)
    content_id = _validated_ref(expected_content_id)
    key = _key(request_key)
    capture_sha = _sha(expected_capture_sha256, "CAPTURE_SHA256")
    fingerprint = _sha(expected_input_fingerprint, "INPUT_FINGERPRINT")

    def readback() -> tuple[dict[str, object], dict[str, object]]:
        checked = inspect_candidate_review_readiness(
            match_store,
            promotion_store,
            run_id=run_id,
            claim_candidate_id=claim_candidate_id,
        )
        if (
            checked["currentness"] != "CURRENT"
            or checked["input_fingerprint"] != fingerprint
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_STALE_MATCH")
        if not any(result["result_id"] == result_id for result in checked["results"]):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_RESULT_MISSING")
        try:
            context = promotion_store.context(claim_candidate_id)
        except Exception:
            raise RuntimeError("STUDIO_MACHINE_CONTEXT_STORE_UNAVAILABLE") from None
        if (
            not isinstance(context, Mapping)
            or context.get("candidate_id") != claim_candidate_id
            or context.get("content_id") != content_id
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_CONTENT_SCOPE_MISMATCH")
        passages = context.get("passages")
        if not isinstance(passages, list) or len(passages) > 2:
            raise ValueError("STUDIO_MACHINE_CANDIDATE_PASSAGES_INVALID")
        return checked, dict(context)

    checked, context = readback()
    passages = context["passages"]
    refs = checked.get("source_references")
    if not isinstance(refs, list) or len(refs) != len(passages):
        raise ValueError("STUDIO_MACHINE_CANDIDATE_SOURCE_REFS_INVALID")
    if len(passages) == 1 and isinstance(passages[0], Mapping):
        passage = passages[0]
        first_ref = refs[0]
        if (
            not isinstance(first_ref, Mapping)
            or passage.get("capture_sha256") != capture_sha
            or first_ref.get("capture_sha256") != capture_sha
            or first_ref.get("passage_id") != passage.get("passage_id")
            or first_ref.get("capture_id") != passage.get("capture_id")
        ):
            raise ValueError("STUDIO_MACHINE_CANDIDATE_CAPTURE_BINDING_MISMATCH")
        source = {
            "passage_id": first_ref["passage_id"],
            "capture_id": first_ref["capture_id"],
            "capture_sha256": capture_sha,
        }
        provenance_usable = (
            context.get("candidate_status") in {"CANDIDATE", "DUPLICATE"}
            # A source preflight still needs a coherent, single written
            # occurrence bound to an eligible public Person. Neither the
            # legacy review flags nor match confidence grant B authority.
            and isinstance(context.get("statement_candidate_id"), str)
            and bool(context["statement_candidate_id"])
            and type(context.get("passage_count")) is int
            and context["passage_count"] == 1
            and type(context.get("written_count")) is int
            and context["written_count"] == 1
            and type(context.get("media_count")) is int
            and context["media_count"] == 0
            and passage.get("capture_status") == "CAPTURED"
            and passage.get("capture_hold_status") == "NONE"
            and passage.get("canonical_segment_id") is None
            and passage.get("segment_publication_blocked") is not True
            and isinstance(context.get("speaker_person_id"), str)
            and bool(context["speaker_person_id"].strip())
            and context.get("speaker_is_public") is True
            and bool(first_ref.get("passage_id"))
            and bool(first_ref.get("capture_id"))
        )
    else:
        source = {"passage_id": None, "capture_id": None, "capture_sha256": None}
        provenance_usable = False
    checked_again, context_again = readback()
    if checked_again != checked or context_again != context:
        raise ValueError("STUDIO_MACHINE_CANDIDATE_CHANGED_DURING_PREFLIGHT")
    return _receipt(
        {
            "family": "CLAIM_CANDIDATE_MATCH",
            "status": (
                "HELD_MACHINE_AUTHORITY_UNAVAILABLE"
                if provenance_usable
                else "HELD_SOURCE_OR_ATTRIBUTION"
            ),
            "action": (
                "AWAIT_INDEPENDENT_MACHINE_AUTHORITY"
                if provenance_usable
                else "INVESTIGATE_SOURCE_OR_ATTRIBUTION"
            ),
            "candidate_id": claim_candidate_id,
            "run_id": run_id,
            "result_id": result_id,
            "content_id": content_id,
            "input_fingerprint": fingerprint,
            "review_context_sha256": checked["review_context_sha256"],
            "source": source,
            "requires_fresh_transactional_cas": True,
            "machine_authority_status": "NOT_CONFIGURED_OR_NOT_ATTESTED",
        },
        request_key=key,
    )


__all__ = [
    "STUDIO_MACHINE_PREVIEW_VERSION",
    "preview_discovery_machine_exception",
    "preview_candidate_machine_handoff",
]
