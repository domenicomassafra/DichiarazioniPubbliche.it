#!/usr/bin/env python3
"""One bounded, rights-reviewed official-record intake into private research:garlasco.

The no-flag mode checks two exact original source versions without writing.
--apply-private-intake creates only private Source/Content/Capture/Passage,
HELD Statement Candidate and OPEN Coverage Need. Never creates public authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "poc"))

from dichiarazioni_pubbliche.capture_authorization import private_capture_rights_guard
from dichiarazioni_pubbliche.capture_pipeline import (
    CaptureBodyStore, CaptureEnrichmentPolicy, CapturePipelineStore,
    capture_content, verify_passage_roundtrip,
)
from dichiarazioni_pubbliche.corpus_repository import (
    INSERT_STATEMENT_CANDIDATE_SQL_V1, deterministic_corpus_id,
)
from dichiarazioni_pubbliche.coverage_needs import coverage_need_event_id
from dichiarazioni_pubbliche.garlasco_camera_pilot import CameraSpeechParser, original_versions
from dichiarazioni_pubbliche.ingestion_relevance import (
    append_ingestion_relevance_authority, replay_current_ingestion_relevance,
)
from dichiarazioni_pubbliche.private_capture_rights import SourceFamilyUseGuard
from dichiarazioni_pubbliche.camera_parse_authority import CameraParseAuthority
from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority
from dichiarazioni_pubbliche.queue_store import ClaimEvidenceObservationStore
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject


COLLECTION = "research:garlasco"
FAMILY = "camera_official_stenographic"
POLICY = "dp426-camera-article5-private-text-20261025-v1"
RIGHTS_RECEIPT = "law:633-1941:art5:official-state-acts:text-only"
USES = ("DISCOVER_METADATA", "FETCH", "RESEARCH_CAPTURE_PRIVATE",
        "STORE_BODY", "PARSE_TEXT", "EXTRACT_CANDIDATES")


def _activate_source_scoped_intake(store):
    """Open only the existing collection lane; historic members remain held."""
    snapshot = json.loads(store.run(
        """SELECT json_build_object(
               'status',collection.status,
               'metadata',collection.metadata,
               'historical_unapproved', (
                   SELECT count(*) FROM research_collection_content member
                   WHERE member.collection_id=collection.id
                     AND member.metadata->>'capture_authorized'='false'
               ),
               'historical_unsafe', (
                   SELECT count(*) FROM research_collection_content member
                   JOIN content_item content ON content.id=member.content_id
                   WHERE member.collection_id=collection.id
                     AND member.metadata->>'capture_authorized'='true'
                     AND content.rights_status<>'CLEARED'
               )
           )::text FROM research_collection collection
           WHERE id=:'collection';""", collection=COLLECTION,
    ) or "null")
    if not snapshot or snapshot["historical_unsafe"]:
        raise RuntimeError("DP426_COLLECTION_INTENT_UNVERIFIED")
    if snapshot["status"] == "ACTIVE":
        if snapshot["metadata"].get("dp426_source_scoped_intake") is not True:
            raise RuntimeError("DP426_COLLECTION_ACTIVE_WITHOUT_AUTHORITY")
        return
    if (snapshot["status"] != "PAUSED"
            or snapshot["metadata"].get("pilot_ready") is not False
            or snapshot["metadata"].get("capture_authorized") is not False
            or snapshot["historical_unapproved"] != 18):
        raise RuntimeError("DP426_COLLECTION_PAUSE_GUARD_MISMATCH")
    changed = store.run(
        """UPDATE research_collection
           SET status='ACTIVE', updated_at=now(),
               metadata=metadata || '{"dp426_source_scoped_intake":true}'::jsonb
           WHERE id=:'collection' AND status='PAUSED'
             AND metadata->>'pilot_ready'='false'
             AND metadata->>'capture_authorized'='false'
           RETURNING id;""", collection=COLLECTION,
    )
    if changed != COLLECTION:
        raise RuntimeError("DP426_COLLECTION_ACTIVATION_RACE")


def _identities(store, source):
    source_id = "source:camera-stenografico-dp426"
    content_id = f"content:garlasco:camera:{source['key']}"
    store.run(
        """INSERT INTO source(id,canonical_name,source_type,canonical_url,language,
                              country_code,metadata)
           VALUES (:'id','Camera dei deputati','OFFICIAL_RECORD',
                   'https://www.camera.it/','it','IT',:'metadata'::jsonb)
           ON CONFLICT (id) DO NOTHING;""",
        id=source_id, metadata=json.dumps({"official_state_acts": True, "case": "DP-420A"}),
    )
    store.run(
        """INSERT INTO content_item(id,source_id,source_external_id,canonical_url,
                                    title,language,rights_status,metadata)
           VALUES (:'id',:'source',:'external_id',:'url',:'title','it',
                   'UNKNOWN',:'metadata'::jsonb)
           ON CONFLICT (id) DO NOTHING;""",
        id=content_id, source=source_id, external_id=source["key"], url=source["url"],
        title=f"Camera, XIX legislatura, resoconto stenografico {source['key']}",
        metadata=json.dumps({"official_transcript": True, "private_only": True,
                             "sitting_date": source["date"]}),
    )
    store.run(
        """INSERT INTO research_collection_content(
                collection_id,content_id,inclusion_method,inclusion_version,status,rationale,metadata)
           VALUES (:'collection',:'content','OFFICIAL_ORIGINAL_PILOT','dp426-v1',
                   'INCLUDED','Official parliamentary speech about Garlasco',
                   :'metadata'::jsonb)
           ON CONFLICT (collection_id,content_id) DO NOTHING;""",
        collection=COLLECTION, content=content_id,
        metadata=json.dumps({"capture_authorized": True, "rights_clearance": True,
                             "source_version_sha256": source["sha256"]}),
    )
    raw = store.run(
        """SELECT json_build_object('source',ci.source_id,'url',ci.canonical_url,
                    'member',m.status,'active',r.status,'authorized',m.metadata->'capture_authorized',
                    'source_type',s.source_type,'source_url',s.canonical_url)
           FROM content_item ci JOIN research_collection_content m ON m.content_id=ci.id
           JOIN research_collection r ON r.id=m.collection_id
           JOIN source s ON s.id=ci.source_id
           WHERE ci.id=:'content' AND m.collection_id=:'collection';""",
        content=content_id, collection=COLLECTION,
    )
    row = json.loads(raw or "null")
    if row != {"source": source_id, "url": source["url"],
               "member": "INCLUDED", "active": "ACTIVE", "authorized": True,
               "source_type": "OFFICIAL_RECORD", "source_url": "https://www.camera.it/"}:
        raise RuntimeError("DP426_CONTENT_COLLECTION_IDENTITY_CONFLICT")
    return content_id, source_id


def _record_rights(store, source, content_id):
    subject = RightsSubject(source_family=FAMILY, locator_kind="URL",
                            locator_value=source["url"], content_id=content_id)
    rights_store = PrivateRightsRegistryStore(database_url=store.database_url)
    current = rights_store.read_current(subject)
    if current is None:
        now = datetime.now(timezone.utc)
        current = rights_store.record_rights(
            subject=subject, policy_version=POLICY,
            rights_status="CLEARED", rights_receipt_ref=RIGHTS_RECEIPT,
            permitted_uses=USES,
            attribution_requirements=("ATTRIBUTION_REQUIRED", "NO_PUBLIC_MEDIA"),
            reviewed_at=now.isoformat(), expires_at=(now + timedelta(days=30)).isoformat(),
            reviewer_ref="machine:dp426-primary-legal-source-review",
        )
    if (current.policy_version != POLICY or current.rights_status != "CLEARED"
            or current.rights_receipt_ref != RIGHTS_RECEIPT
            or set(current.permitted_uses) != set(USES)
            or current.version_state != "CURRENT"):
        raise RuntimeError("DP426_SOURCE_RIGHTS_CONFLICT")
    authorized = store.run(
        """UPDATE content_item SET rights_status='CLEARED'
           WHERE id=:'id' AND canonical_url=:'url'
             AND rights_status IN ('UNKNOWN','CLEARED')
           RETURNING id;""",
        id=content_id, url=source["url"],
    )
    if authorized != content_id:
        raise RuntimeError("DP426_CONTENT_RIGHTS_CONFLICT")
    replay = replay_current_ingestion_relevance(
        store.run, content_ref=content_id, canonical_url=source["url"],
    )
    if not replay.allowed:
        if replay.blocker != "INGESTION_RELEVANCE_MISSING":
            raise RuntimeError("DP426_RELEVANCE_CONFLICT")
        append_ingestion_relevance_authority(
            store.run, content_ref=content_id, canonical_url=source["url"],
            relevance_reason="OFFICIAL_RECORD", reviewer_ref="machine:dp426-official-record",
            audit_ref=f"dp426:{source['sha256']}", reviewed_at=datetime.now(timezone.utc).isoformat(),
        )
    return rights_store, subject, current


def _persist(store, body_store, source, fetched, parsed, authority):
    content_id, source_id = _identities(store, source)
    rights, subject, current = _record_rights(store, source, content_id)
    guard = private_capture_rights_guard(
        read_current=rights.read_current, rights_record_id=current.id,
        content_id=content_id, canonical_url=source["url"], source_family=FAMILY,
        read_content_state=store.read_operator_capture_content_state,
    )
    use = SourceFamilyUseGuard(
        read_current=rights.read_current, subject=subject, rights_record_id=current.id,
        policy_version=POLICY, expected_sha256=source["sha256"],
        authenticated_parse_check=lambda content_id, digest: authority.inspect(
            content_id=content_id, capture_sha256=digest, use="PARSE_TEXT",
        )["permitted"],
    )
    guard()
    use.require("FETCH")

    def pinned_fetch(url, *, max_response_bytes):
        if url != source["url"] or len(fetched.body) > max_response_bytes:
            raise RuntimeError("DP426_FETCH_SCOPE_CHANGED")
        guard()
        use.require("FETCH", content_sha256=source["sha256"], media_type=fetched.media_type)
        return fetched

    capture_content(
        content_id=content_id, url=source["url"], store=store, body_store=body_store,
        actor_ref="machine:dp426-official-speech", retention_class="DURABLE_PRIVATE",
        rights_status="CLEARED", parser=CameraSpeechParser(source), fetcher=pinned_fetch,
        enrichment_policy=CaptureEnrichmentPolicy(metadata_enabled=True, archive_enabled=False),
        rights_guard=guard, source_use_guard=use, max_response_bytes=3_000_000,
    )
    capture = store.find_capture(content_id, source["sha256"])
    if (not capture or capture["status"] != "CAPTURED"
            or capture.get("body_purged_at") is not None or not capture.get("body_ref")):
        raise RuntimeError("DP426_PERSISTED_CAPTURE_MISSING")
    captured_body = body_store.read(capture["body_ref"], expected_sha256=source["sha256"])
    if captured_body != fetched.body:
        raise RuntimeError("DP426_PERSISTED_CAPTURE_BYTES_DIFFER")
    quote = parsed.spans[0]
    passage_id = deterministic_corpus_id(
        "passage", capture["id"], CameraSpeechParser.parser_version,
        str(quote.start_char), str(quote.end_char), quote.text_sha256,
    )
    passage = store.run(
        """SELECT json_build_object('id',id,'content',content_id,'capture',capture_id,
                    'sha',text_sha256,'text',private_text,'start',start_char,'end',end_char)::text
           FROM passage WHERE id=:'id';""", id=passage_id,
    )
    selected = json.loads(passage or "null")
    if selected != {"id": passage_id, "content": content_id,
                    "capture": capture["id"], "sha": quote.text_sha256,
                    "text": quote.text, "start": 0, "end": len(quote.text)}:
        raise RuntimeError("DP426_PASSAGE_CAPTURE_BINDING_FAILED")
    from dichiarazioni_pubbliche.corpus_repository import PassageRecord
    if not verify_passage_roundtrip(
        body=captured_body, media_type=fetched.media_type, charset=fetched.charset,
        passage=PassageRecord(
            id=passage_id, content_id=content_id, capture_id=capture["id"],
            selector_type="TEXT_POSITION", start_char=0, end_char=len(quote.text),
            text_sha256=quote.text_sha256, private_text=quote.text,
            language="it", extraction_method=CameraSpeechParser.parser_method,
            extraction_version=CameraSpeechParser.parser_version,
        ), parser=CameraSpeechParser(source),
    ):
        raise RuntimeError("DP426_PRIVATE_PASSAGE_ROUNDTRIP_FAILED")
    if "EXTRACT_CANDIDATES" not in current.permitted_uses:
        raise RuntimeError("DP426_DERIVATION_USE_NOT_GRANTED")
    candidate_id = deterministic_corpus_id("statement-candidate", passage_id, quote.text_sha256)
    state = store.run(
        INSERT_STATEMENT_CANDIDATE_SQL_V1,
        id=candidate_id, content_id=content_id, speaker_person_id="",
        statement_text_hash=quote.text_sha256, normalized_statement=quote.text,
        statement_at="", attribution_method="", extraction_model="",
        extraction_version="dp426-original-direct-held-v1", status="HELD",
        metadata=json.dumps({"speaker_label_original": source["speaker"],
                             "attribution_pending": True, "publication_authorized": False}),
        passage_ids=json.dumps([passage_id]),
    )
    if state not in {"INSERTED", "EXISTING"}:
        raise RuntimeError("DP426_CANDIDATE_WRITE_CONFLICT")
    verified = store.run(
        """SELECT count(*) FROM statement_candidate candidate
           JOIN statement_candidate_passage edge ON edge.statement_candidate_id=candidate.id
           JOIN passage p ON p.id=edge.passage_id AND p.content_id=edge.content_id
           WHERE candidate.id=:'candidate' AND candidate.content_id=:'content'
             AND candidate.status='HELD' AND candidate.speaker_person_id IS NULL
             AND p.id=:'passage' AND p.capture_id=:'capture';""",
        candidate=candidate_id, content=content_id, passage=passage_id,
        capture=capture["id"],
    )
    if verified != "1":
        raise RuntimeError("DP426_PRIVATE_CANDIDATE_READBACK_FAILED")
    return {"source_id": source_id, "content_id": content_id,
            "capture_id": capture["id"], "capture_sha256": source["sha256"],
            "passage_id": passage_id, "passage_sha256": quote.text_sha256,
            "candidate_id": candidate_id, "candidate_status": "HELD",
            "rights_record_id": current.id, "source_url": source["url"]}


def _coverage(store):
    question = ("Locate independent original sources concerning these two parliamentary "
                "descriptions of Garlasco; verify chronology, identity and rights "
                "without treating political interpretations as judicial findings.")
    fingerprint = hashlib.sha256(question.encode()).hexdigest()
    need_id = "coverage-need:" + fingerprint
    state = ClaimEvidenceObservationStore(database_url=store.database_url).upsert_coverage_need(
        id=need_id, collection_id=COLLECTION, atomic_claim_id="", claim_candidate_id="",
        source_intelligence_assessment_id="", need_type="INDEPENDENT_SOURCE",
        requirement_kind="MIN_INDEPENDENT_LINEAGES", requirement_fingerprint=fingerprint,
        question=question, required_roles=json.dumps(["FIRST_PARTY_STATEMENT"]),
        authority_scope=json.dumps({"topic": "Garlasco", "only_originals": True}),
        temporal_constraints="{}", independence_requirement="2", max_attempts="3",
        created_by="SOURCE_INTELLIGENCE",
        metadata=json.dumps({"case": "DP-420A", "private_only": True}),
        created_event_id=coverage_need_event_id(need_id, "CREATED"),
        observed_event_id=coverage_need_event_id(need_id, "OBSERVED_AGAIN", ""),
    )
    return {"coverage_need_id": need_id, "coverage_need_state": state}


def run(*, database_url: str | None, storage_root: Path, apply: bool):
    authority_root = os.environ.get("DICHIARAZIONI_PUBBLICHE_REVIEWER_AUTHORITY_ROOT")
    if not authority_root:
        raise ValueError("DP426_SIGNED_CAMERA_PARSE_AUTHORITY_REQUIRED")
    authority = CameraParseAuthority(
        PrivateRightsRegistryStore(database_url=database_url),
        LocalFileReviewerIdentityAuthority(authority_root),
    )
    observations = original_versions(authority)
    if not apply:
        return {"status": "READY_FOR_PRIVATE_INTAKE",
                "sources": [{"url": s["url"], "sha256": s["sha256"]}
                            for s, _, _ in observations],
                "writes": 0, "publication_authorized": False}
    store = CapturePipelineStore(database_url=database_url)
    _activate_source_scoped_intake(store)
    body_store = CaptureBodyStore(storage_root)
    sources = [_persist(store, body_store, s, fetched, parsed, authority)
               for s, fetched, parsed in observations]
    coverage = _coverage(store)
    return {"status": "PRIVATE_GARLASCO_CHAIN_PERSISTED", "collection_id": COLLECTION,
            "sources": sources, **coverage, "publication_authorized": False,
            "model_called": False, "claim_candidate_created": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DICHIARAZIONI_PUBBLICHE_DATABASE_URL"))
    parser.add_argument("--storage-root", type=Path,
                        default=Path("~/.local/share/dichiarazioni-pubbliche-captures").expanduser())
    parser.add_argument("--apply-private-intake", action="store_true")
    args = parser.parse_args()
    try:
        receipt = run(database_url=args.database_url, storage_root=args.storage_root,
                      apply=args.apply_private_intake)
    except Exception as exc:
        # Do not expose private body paths, local credentials, or psql diagnostics.
        reason = str(exc)
        if not reason.startswith("DP426_"):
            reason = "DP426_PRIVATE_OPERATOR_FAILURE"
        receipt = {"status": "BLOCKED", "reason_code": reason, "publication_authorized": False}
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 2 if receipt["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
