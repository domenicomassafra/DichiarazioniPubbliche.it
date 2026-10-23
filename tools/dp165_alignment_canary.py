"""DP-165 operator canary: one private, rights-bound WhisperX alignment run.

Usage: python3 tools/dp165_alignment_canary.py --manifest /private/manifest.json
The manifest pins the authorized WAV, the transcript, the model receipt, the
source variant/segment hashes and the current DP-305 source-use record. The
command prints a machine receipt only: never transcript text, audio paths or
the private manifest content. Exit 0 = a HOLD/REVIEW candidate receipt was
produced, 2 = the adapter held, 3 = the manifest or the rights scope is invalid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.parliamentary_alignment import ParliamentaryIntervention
from dichiarazioni_pubbliche.rights_registry import (
    PrivateRightsRecord, RightsSubject, rights_subject_fingerprint,
)
from dichiarazioni_pubbliche.whisperx_alignment_private import (
    ENABLE, VERSION, AlignmentHold, propose_whisperx_alignment,
)
from dichiarazioni_pubbliche.whisperx_alignment_rights import (
    ALIGNMENT_SOURCE_USE, AlignmentRightsScope, alignment_authorization_guard,
)

CANARY_VERSION = "dp165-alignment-canary-v1"
EXIT_RECEIPT, EXIT_HELD, EXIT_INVALID = 0, 2, 3


class CanaryManifestInvalid(ValueError):
    pass


def _section(raw: Any, name: str, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise CanaryManifestInvalid(f"MANIFEST_{name.upper()}_INVALID")
    return raw


def _text(raw: dict[str, Any], key: str, label: str) -> str | None:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise CanaryManifestInvalid(f"MANIFEST_{label.upper()}_INVALID")
    return value


@dataclass(frozen=True)
class CanaryJob:
    intervention: ParliamentaryIntervention
    scope: AlignmentRightsScope
    record: PrivateRightsRecord
    clock: datetime
    audio_path: str
    audio_root: Path
    audio_sha256: str
    duration_seconds: float
    rights_basis: str
    rights_receipt_id: str
    consent_confirmed: bool
    model_receipt_path: Path
    source_variant_id: str
    source_segment_id: str
    source_variant_sha256: str
    source_segment_sha256: str
    language: str
    overlap_observed: bool
    timeout_seconds: int
    manifest_sha256: str


def _record_and_scope(raw: dict[str, Any], *, content_id: str, url: str,
                       payload: dict[str, str]) -> tuple[PrivateRightsRecord, AlignmentRightsScope]:
    subject = RightsSubject(
        source_family=_text(raw, "source_family", "rights_record_source_family") or "",
        locator_kind="URL", locator_value=url, content_id=content_id,
    )
    uses = raw.get("permitted_uses")
    attribution = raw.get("attribution_requirements", ())
    if (not isinstance(uses, list) or not uses
            or any(not isinstance(item, str) for item in uses)
            or not isinstance(attribution, list)
            or any(not isinstance(item, str) for item in attribution)):
        raise CanaryManifestInvalid("MANIFEST_RIGHTS_RECORD_POLICIES_INVALID")
    record = PrivateRightsRecord(
        id=payload["rights_record_id"],
        subject_fingerprint=rights_subject_fingerprint(subject),
        source_family=subject.source_family, locator_kind="URL", locator_value=url,
        content_id=content_id, evidence_id=None, transcript_segment_id=None,
        canonical_segment_id=None, passage_id=None,
        rights_status=_text(raw, "rights_status", "rights_record_status") or "",
        rights_receipt_ref=payload["rights_receipt_id"],
        permitted_uses=tuple(uses), attribution_requirements=tuple(attribution),
        reviewed_at=_text(raw, "reviewed_at", "rights_record_reviewed_at") or "",
        expires_at=_text(raw, "expires_at", "rights_record_expires_at") or "",
        reviewer_ref=_text(raw, "reviewer_ref", "rights_record_reviewer_ref") or "",
        policy_version=payload["rights_policy_version"],
        record_visibility="PRIVATE", supersedes_id=None,
        version_state=_text(raw, "version_state", "rights_record_version_state") or "",
    )
    scope = AlignmentRightsScope(
        subject=subject, rights_record_id=record.id,
        policy_version=record.policy_version,
        rights_receipt_ref=record.rights_receipt_ref or "",
    )
    return record, scope


def load_job(manifest_path: Path) -> CanaryJob:
    try:
        raw_bytes = manifest_path.read_bytes()
        manifest = json.loads(raw_bytes)
    except (OSError, ValueError) as exc:
        raise CanaryManifestInvalid("MANIFEST_UNREADABLE") from exc
    if not isinstance(manifest, dict):
        raise CanaryManifestInvalid("MANIFEST_ROOT_INVALID")
    if manifest.get("manifest_version") != CANARY_VERSION:
        raise CanaryManifestInvalid("MANIFEST_VERSION_UNSUPPORTED")
    _section(manifest, "root", (
        "manifest_version", "intervention", "audio", "source", "model",
        "rights", "options",
    ))
    speech = _section(manifest["intervention"], "intervention", (
        "intervention_id", "session_id", "official_speaker_ref",
        "official_speaker_name", "transcript_text", "source_url",
        "source_version", "official_start_ms", "official_end_ms",
    ))
    audio = _section(manifest["audio"], "audio", (
        "path", "root", "sha256", "duration_seconds",
    ))
    source = _section(manifest["source"], "source", (
        "variant_id", "segment_id", "variant_sha256", "segment_sha256",
    ))
    model = _section(manifest["model"], "model", ("receipt_path",))
    rights = _section(manifest["rights"], "rights", (
        "basis", "receipt_id", "consent_confirmed", "content_id",
        "canonical_url", "record_id", "policy_version", "record",
    ))
    options = _section(manifest["options"], "options", (
        "language", "overlap_observed", "timeout_seconds",
    ))
    payload = {
        "rights_record_id": _text(rights, "record_id", "rights_record_id") or "",
        "rights_policy_version": _text(rights, "policy_version", "rights_policy") or "",
        "rights_receipt_id": _text(rights, "receipt_id", "rights_receipt_id") or "",
    }
    content_id = _text(rights, "content_id", "rights_content_id") or ""
    url = _text(rights, "canonical_url", "rights_canonical_url") or ""
    record_raw = _section(rights["record"], "rights_record", (
        "source_family", "rights_status", "permitted_uses", "attribution_requirements",
        "reviewed_at", "expires_at", "reviewer_ref", "version_state",
    ))
    record, scope = _record_and_scope(
        record_raw, content_id=content_id, url=url, payload=payload)
    # "Current" is always the real clock: a manifest cannot pin a past instant
    # and revive an expired source review.
    clock = datetime.now().astimezone()
    duration = audio.get("duration_seconds")
    timeout = options.get("timeout_seconds", 120)
    consent = rights.get("consent_confirmed", False)
    overlap = options.get("overlap_observed", False)
    if (type(duration) not in {int, float} or type(timeout) is not int
            or type(consent) is not bool or type(overlap) is not bool):
        raise CanaryManifestInvalid("MANIFEST_SCALAR_TYPES_INVALID")
    start, end = speech.get("official_start_ms"), speech.get("official_end_ms")
    if (start is not None and type(start) is not int) or (end is not None and type(end) is not int):
        raise CanaryManifestInvalid("MANIFEST_OFFICIAL_RANGE_INVALID")
    try:
        intervention = ParliamentaryIntervention(
            intervention_id=_text(speech, "intervention_id", "intervention_id") or "",
            session_id=_text(speech, "session_id", "session_id") or "",
            official_speaker_ref=_text(speech, "official_speaker_ref", "speaker_ref") or "",
            official_speaker_name=_text(speech, "official_speaker_name", "speaker_name") or "",
            transcript_text=_text(speech, "transcript_text", "transcript_text") or "",
            source_url=_text(speech, "source_url", "source_url") or "",
            source_version=_text(speech, "source_version", "source_version") or "",
            official_start_ms=start, official_end_ms=end,
        )
    except ValueError as exc:
        raise CanaryManifestInvalid(str(exc)) from exc
    return CanaryJob(
        intervention=intervention, scope=scope, record=record, clock=clock,
        audio_path=_text(audio, "path", "audio_path") or "",
        audio_root=Path(_text(audio, "root", "audio_root") or ""),
        audio_sha256=_text(audio, "sha256", "audio_sha256") or "",
        duration_seconds=float(duration),
        rights_basis=_text(rights, "basis", "rights_basis") or "",
        rights_receipt_id=payload["rights_receipt_id"],
        consent_confirmed=consent,
        model_receipt_path=Path(_text(model, "receipt_path", "model_receipt") or ""),
        source_variant_id=_text(source, "variant_id", "variant_id") or "",
        source_segment_id=_text(source, "segment_id", "segment_id") or "",
        source_variant_sha256=_text(source, "variant_sha256", "variant_sha256") or "",
        source_segment_sha256=_text(source, "segment_sha256", "segment_sha256") or "",
        language=_text(options, "language", "language") or "",
        overlap_observed=overlap, timeout_seconds=timeout,
        manifest_sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )


def run_canary(job: CanaryJob, *, enabled: bool) -> dict[str, Any]:
    """One private run; the pinned attestation is re-read at every boundary."""
    reads = {"count": 0}

    def read_current(subject: RightsSubject) -> PrivateRightsRecord | None:
        reads["count"] += 1
        if rights_subject_fingerprint(subject) != job.record.subject_fingerprint:
            return None
        return job.record

    guard = alignment_authorization_guard(job.scope, read_current=read_current)
    receipt: dict[str, Any] = {
        "canary": CANARY_VERSION, "adapter_version": VERSION,
        "manifest_sha256": job.manifest_sha256,
        "rights_authority": "PINNED_OPERATOR_ATTESTATION",
        "rights_record_id": job.scope.rights_record_id,
        "rights_policy_version": job.scope.policy_version,
        "rights_use": ALIGNMENT_SOURCE_USE,
        "audio_sha256": job.audio_sha256,
        "transcript_sha256": job.intervention.transcript_sha256,
        "rights_guard_reads": 0,  # live authority reads, not adapter calls
        "publication_blocked": True,
    }
    if job.intervention.official_start_ms is None:
        # Surface the precise SOURCE_USE_* reason to the operator. The adapter
        # deliberately collapses guard failures into one generic hold code.
        # Official ranges skip this: they win without any rights or inference.
        guard()
    original = os.environ.get(ENABLE)
    if enabled:
        os.environ[ENABLE] = "1"
    try:
        proposal = propose_whisperx_alignment(
            job.intervention, audio_path=job.audio_path, audio_root=job.audio_root,
            audio_sha256=job.audio_sha256, duration_seconds=job.duration_seconds,
            rights_basis=job.rights_basis, rights_receipt_id=job.rights_receipt_id,
            authorization=True, consent_confirmed=job.consent_confirmed,
            authorization_guard=guard,
            model_receipt_path=job.model_receipt_path,
            source_variant_id=job.source_variant_id,
            source_segment_id=job.source_segment_id,
            source_variant_sha256=job.source_variant_sha256,
            source_segment_sha256=job.source_segment_sha256,
            language=job.language, overlap_observed=job.overlap_observed,
            timeout_seconds=job.timeout_seconds,
        )
    finally:
        if enabled:
            if original is None:
                os.environ.pop(ENABLE, None)
            else:
                os.environ[ENABLE] = original
    receipt["rights_guard_reads"] = reads["count"]
    receipt["status"] = proposal.status
    receipt["status_kind"] = "HOLD" if proposal.candidate is None else "REVIEW_CANDIDATE"
    receipt["blockers"] = list(proposal.blockers)
    receipt["publication_blocked"] = proposal.publication_blocked
    if proposal.candidate is not None:
        receipt["candidate_id"] = proposal.candidate.candidate_id
        receipt["candidate_source_kind"] = proposal.candidate.source_kind
        receipt["word_count"] = len(proposal.words)
        receipt["first_word_ms"] = proposal.words[0].start_ms
        receipt["last_word_ms"] = proposal.words[-1].end_ms
        receipt["alignment_output_sha256"] = proposal.provenance["alignment_output_sha256"]
        receipt["source_span_review_ready"] = proposal.source_span_review_ready
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DP-165 private alignment canary")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--enabled", action="store_true",
                        help="set the opt-in switch for this single run")
    arguments = parser.parse_args(argv)
    try:
        job = load_job(Path(arguments.manifest))
    except CanaryManifestInvalid as exc:
        print(json.dumps({"status": "INVALID_MANIFEST", "code": str(exc)}))
        return EXIT_INVALID
    try:
        receipt = run_canary(job, enabled=arguments.enabled)
    except AlignmentHold as exc:
        print(json.dumps({
            "canary": CANARY_VERSION, "status": "HELD", "hold_code": str(exc),
            "manifest_sha256": job.manifest_sha256,
            "rights_authority": "PINNED_OPERATOR_ATTESTATION",
            "rights_record_id": job.scope.rights_record_id,
            "publication_blocked": True,
        }))
        return EXIT_HELD
    body = json.dumps(receipt, sort_keys=True)
    if arguments.receipt:
        Path(arguments.receipt).write_text(body + "\n", encoding="utf-8")
    print(body)
    return EXIT_RECEIPT


if __name__ == "__main__":
    raise SystemExit(main())
