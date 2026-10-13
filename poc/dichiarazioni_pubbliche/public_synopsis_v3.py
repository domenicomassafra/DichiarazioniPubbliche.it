"""DP-440: opt-in, offline, citation-bound public synopsis read contract.

No synthesis is generated here. Independently reviewed human/editorial text,
topic membership and current published-source authority MUST be supplied by an
authenticated upstream owner. This module rejects inconsistent public facts;
it cannot grant rights or substitute for semantic entailment gold/review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Mapping

from dichiarazioni_pubbliche.public_schema import validate_public_bundle


VERSION = "public-synopsis-v3-opt-in"
MAX_SENTENCES = 8


@dataclass(frozen=True)
class ApprovedTopicIntersection:
    person_id: str
    topic_id: str
    dataset_sha256: str
    statement_versions: tuple[tuple[str, str], ...]
    # Externally reviewed original-source lineages, one per Statement version.
    # Reposted copies cannot manufacture multiple independent sources.
    statement_lineages: tuple[tuple[str, str, str], ...]
    review_event_id: str
    status: str
    currentness_attestation_id: str
    # The independently reviewed public membership/currentness proof has a
    # finite interval. An ID alone cannot attest its continuing validity.
    currentness_attested_at: str
    currentness_valid_until: str


@dataclass(frozen=True)
class ReviewedSynopsisSentence:
    text: str
    source_statement_versions: tuple[tuple[str, str], ...]
    source_quote_sha256: tuple[str, ...]
    review_event_id: str
    kind: str  # SOURCE_LIST_ONLY or REVIEWED_DESCRIPTIVE_SUMMARY


@dataclass(frozen=True)
class PublicSynopsisRead:
    status: str
    reason_code: str
    schema_version: str
    person_id: str
    topic_id: str
    dataset_sha256: str
    fingerprint: str | None
    coverage_note: str | None
    snapshot_at: str | None
    sentences: tuple[dict, ...] = ()
    provider_calls: int = 0


def _text(value: object, max_len: int) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= max_len and value == value.strip() and "\x00" not in value


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _aware_instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None or moment.utcoffset() is None:
            return None
        return moment.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError):
        return None


def prepare_public_synopsis(
    *,
    bundle: Mapping[str, object],
    intersection: ApprovedTopicIntersection,
    reviewed_sentences: tuple[ReviewedSynopsisSentence, ...],
    current_public_dataset_sha256: str,
    coverage_note: str,
    now: datetime,
    min_independent_contents: int = 2,
) -> PublicSynopsisRead:
    """Return a bounded publishable DTO or reason-only WITHHELD read model.

    No raw private source is read, and no 'approved' flag is synthesized.
    """
    if not isinstance(bundle, Mapping) or not isinstance(intersection, ApprovedTopicIntersection) or not isinstance(reviewed_sentences, tuple):
        raise ValueError("SYNOPSIS_INPUT_CONTRACT_INVALID")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("SYNOPSIS_AWARE_TIMESTAMP_REQUIRED")
    if type(min_independent_contents) is not int or not 1 <= min_independent_contents <= 16:
        raise ValueError("SYNOPSIS_SOURCE_THRESHOLD_INVALID")
    # Only an explicitly approved v3 snapshot can be considered. A v2
    # paraphrase may never be promoted to an original-language quote.
    validate_public_bundle(dict(bundle), allow_statement_v3=True)
    if bundle.get("schema_version") != "dichiarazioni-pubbliche-public-v3-statement-opt-in":
        raise ValueError("SYNOPSIS_NEEDS_OPT_IN_VERBATIM_V3")
    published_sha = str(bundle["dataset_sha256"])

    def withheld(reason: str) -> PublicSynopsisRead:
        return PublicSynopsisRead(
            "WITHHELD", reason, VERSION, intersection.person_id,
            intersection.topic_id, published_sha, None, None, None,
        )

    if (not _text(intersection.person_id, 150) or not _text(intersection.topic_id, 150)
        or not _text(intersection.review_event_id, 150)
        or not _text(intersection.currentness_attestation_id, 150)):
        return withheld("SYNOPSIS_MEMBERSHIP_AUTHORITY_MISSING")
    if (intersection.status != "APPROVED" or intersection.dataset_sha256 != published_sha
        or current_public_dataset_sha256 != published_sha):
        return withheld("SYNOPSIS_STALE_OR_UNAPPROVED_SNAPSHOT")
    snapshot_instant = _aware_instant(bundle.get("generated_at"))
    if snapshot_instant is None:
        return withheld("SYNOPSIS_SNAPSHOT_TIMESTAMP_INVALID")
    now_utc = now.astimezone(timezone.utc)
    if snapshot_instant > now_utc:
        return withheld("SYNOPSIS_SNAPSHOT_IN_FUTURE")
    attested_at = _aware_instant(intersection.currentness_attested_at)
    valid_until = _aware_instant(intersection.currentness_valid_until)
    if attested_at is None or valid_until is None or valid_until <= attested_at:
        return withheld("SYNOPSIS_CURRENTNESS_ATTESTATION_INVALID")
    if attested_at < snapshot_instant:
        return withheld("SYNOPSIS_CURRENTNESS_ATTESTATION_STALE")
    if attested_at > now_utc:
        return withheld("SYNOPSIS_CURRENTNESS_ATTESTATION_IN_FUTURE")
    if now_utc >= valid_until:
        return withheld("SYNOPSIS_CURRENTNESS_ATTESTATION_EXPIRED")
    if not _text(coverage_note, 450) or not any(
        word in coverage_note.lower() for word in ("corpus", "raccolt", "copertur")
    ):
        return withheld("SYNOPSIS_COVERAGE_SCOPE_MISSING")
    if not 1 <= len(reviewed_sentences) <= MAX_SENTENCES or not intersection.statement_versions:
        return withheld("SYNOPSIS_NO_APPROVED_SENTENCES")
    allowed = set(intersection.statement_versions)
    if len(allowed) != len(intersection.statement_versions):
        return withheld("SYNOPSIS_DUPLICATE_MEMBERSHIP")
    lineage_ids = {(statement_id, version_id): lineage_id
                   for statement_id, version_id, lineage_id in intersection.statement_lineages}
    if (len(lineage_ids) != len(intersection.statement_lineages)
        or set(lineage_ids) != allowed
        or any(not _text(value, 150) for value in lineage_ids.values())):
        return withheld("SYNOPSIS_LINEAGE_REVIEW_MISSING")
    rows: dict[tuple[str, str], dict] = {}
    for statement in bundle["statements"]:
        key = (statement["statement_id"], statement["version_id"])
        rows[key] = statement
    source_lineages: set[str] = set()
    source_contents: set[str] = set()
    source_urls: set[str] = set()
    source_hashes: set[str] = set()
    rendered = []
    reviewed_ids: set[str] = set()
    for sentence in reviewed_sentences:
        if not isinstance(sentence, ReviewedSynopsisSentence) or not _text(sentence.text, 500):
            return withheld("SYNOPSIS_SENTENCE_UNREVIEWED")
        if (not _text(sentence.review_event_id, 160)
            or sentence.review_event_id in reviewed_ids
            or sentence.kind not in {"SOURCE_LIST_ONLY", "REVIEWED_DESCRIPTIVE_SUMMARY"}
            or not sentence.source_statement_versions
            or len(sentence.source_statement_versions) > 12
            or len(sentence.source_quote_sha256) != len(sentence.source_statement_versions)):
            return withheld("SYNOPSIS_SENTENCE_PROVENANCE_INVALID")
        reviewed_ids.add(sentence.review_event_id)
        cited: list[dict] = []
        if len(set(sentence.source_statement_versions)) != len(sentence.source_statement_versions):
            return withheld("SYNOPSIS_CITATION_DUPLICATE")
        for key, claimed_hash in zip(sentence.source_statement_versions, sentence.source_quote_sha256):
            statement = rows.get(key)
            if key not in allowed or statement is None or statement["person_id"] != intersection.person_id:
                return withheld("SYNOPSIS_CITATION_NOT_PUBLIC_MEMBERSHIP")
            if statement["quote_sha256"] != claimed_hash:
                return withheld("SYNOPSIS_ORIGINAL_QUOTE_CHANGED")
            # The public snapshot may contain valid records observed after the
            # period that this summary claims to cover. Neither a future source
            # nor a later publication may support this as-of-date synopsis.
            cited_date = date.fromisoformat(statement["statement_date"])
            if cited_date > min(snapshot_instant.date(), now_utc.date()):
                return withheld("SYNOPSIS_CITATION_IN_FUTURE")
            if sentence.kind == "REVIEWED_DESCRIPTIVE_SUMMARY" and (
                not statement["endorsed"] or statement["speech_act"] not in {"DIRECT_ASSERTION", "OPINION"}
            ):
                return withheld("SYNOPSIS_REPORTED_SPEECH_NOT_ENDORSEMENT")
            if statement["original_text"] in sentence.text:
                return withheld("SYNOPSIS_VERBATIM_IN_SYNTHESIS")
            source_lineages.add(lineage_ids[key])
            source_contents.add(statement["content_id"])
            source_urls.add(statement["source_url"])
            source_hashes.add(statement["source_sha256"])
            cited.append({
                "statement_id": key[0], "version_id": key[1], "quote_sha256": claimed_hash,
                "source_sha256": statement["source_sha256"], "source_url": statement["source_url"],
                # The validated public bundle can be mutated by a later private
                # source callback. Never retain its locator dictionary by alias:
                # that would change an emitted citation without the read-model
                # fingerprint changing.
                "locator": dict(statement["locator"]), "statement_date": statement["statement_date"],
                "language": statement["language"],
            })
        rendered.append({"text": sentence.text, "kind": sentence.kind, "citations": cited})
    # Distinct hosts, Content IDs and lineage labels do not turn byte-identical
    # mirrored source documents into independent corroborating sources.
    if min(len(source_lineages), len(source_contents), len(source_urls), len(source_hashes)) < min_independent_contents:
        return withheld("SYNOPSIS_TOO_FEW_PUBLISHED_SOURCES")
    # No confidence, opinion score, polarity or reviewer internals in public.
    material = {
        "schema_version": VERSION, "person_id": intersection.person_id,
        "topic_id": intersection.topic_id, "dataset_sha256": published_sha,
        "topic_membership_review": intersection.review_event_id,
        "currentness_attestation": intersection.currentness_attestation_id,
        "currentness_attested_at": attested_at.isoformat(),
        "currentness_valid_until": valid_until.isoformat(),
        "coverage_note": coverage_note, "sentences": rendered,
    }
    return PublicSynopsisRead(
        "READY_READ_MODEL", "SYNOPSIS_OFFLINE_REVIEWED_CITATIONS_READY", VERSION,
        intersection.person_id, intersection.topic_id, published_sha,
        _hash(material), coverage_note, snapshot_instant.isoformat(),
        tuple(rendered), 0,
    )
