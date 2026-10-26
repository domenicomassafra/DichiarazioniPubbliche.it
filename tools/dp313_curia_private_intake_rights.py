"""Case-scoped private source, collection and current rights-registration gate."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore
from dichiarazioni_pubbliche.ingestion_relevance import (
    append_ingestion_relevance_authority, replay_current_ingestion_relevance,
)
from dichiarazioni_pubbliche.rights_registry import PrivateRightsRegistryStore, RightsSubject
from tools.dp313_curia_private_readback import SOURCE_ECLI, SOURCE_SHA256, SOURCE_URL

COLLECTION = "research:curia-dp313"
SOURCE_ID = "source:curia-eu-case-law"
CONTENT_ID = "content:curia:C-622-24-P:IT"
FAMILY = "curia-case-law-c-622-24-p"
POLICY = "dp313-curia-anonymized-private-case-law-20261026-v1"
RIGHTS_RECEIPT = "https://curia.europa.eu/site/jcms/qua1_6625/"
USES = ("FETCH", "RESEARCH_CAPTURE_PRIVATE", "STORE_BODY", "PARSE_TEXT", "EXTRACT_CANDIDATES")
PARSER_VERSION = "dp313-curia-exact-procedural-spans-v1"


def _identities(store: CapturePipelineStore) -> None:
    """Idempotent case-scoped registry with exact canonical URL checks."""
    store.run(
        """INSERT INTO research_collection(id,slug,name,scope_text,status,policy_version,metadata)
           VALUES (:'id','curia-dp313-private','CURIA DP-313 private judicial research',
                   'Anonymized C-622/24 P procedural orders','ACTIVE',:'policy',
                   '{"private_only":true,"publish_authority":false}'::jsonb)
           ON CONFLICT (id) DO NOTHING;""", id=COLLECTION, policy=POLICY,
    )
    store.run(
        """INSERT INTO source(id,canonical_name,source_type,canonical_url,language,country_code,metadata)
           VALUES (:'id','Court of Justice of the European Union','OFFICIAL_RECORD',
                   'https://juris.curia.europa.eu/','it','EU',
                   '{"public_judicial_record":true}'::jsonb)
           ON CONFLICT (id) DO NOTHING;""", id=SOURCE_ID,
    )
    store.run(
        """INSERT INTO content_item(id,source_id,source_external_id,canonical_url,title,
                                    language,rights_status,metadata)
           VALUES (:'id',:'source',:'ecli',:'url','CJEU C-622/24 P, 25 June 2026',
                   'it','UNKNOWN','{"private_only":true,"anonymized_party":true}'::jsonb)
           ON CONFLICT (id) DO NOTHING;""",
        id=CONTENT_ID, source=SOURCE_ID, ecli=SOURCE_ECLI, url=SOURCE_URL,
    )
    store.run(
        """INSERT INTO research_collection_content(
                   collection_id,content_id,inclusion_method,inclusion_version,status,rationale,metadata)
           VALUES (:'collection',:'content','OFFICIAL_CASE_LAW','dp313-v1',
                   'INCLUDED','Anonymized original for private research',
                   '{"capture_authorized":true,"private_only":true}'::jsonb)
           ON CONFLICT (collection_id,content_id) DO NOTHING;""",
        collection=COLLECTION, content=CONTENT_ID,
    )
    snapshot = store.run(
        """SELECT json_build_object('url',c.canonical_url,'source',c.source_id,
                    'rights',c.rights_status,'collection',r.status,
                    'member',m.status,'permission',m.metadata->'capture_authorized')::text
           FROM content_item c
           JOIN research_collection_content m ON m.content_id=c.id
           JOIN research_collection r ON r.id=m.collection_id
           WHERE c.id=:'content' AND r.id=:'collection';""",
        content=CONTENT_ID, collection=COLLECTION,
    )
    value = json.loads(snapshot or "null")
    if not isinstance(value, dict) or any((
        value.get("url") != SOURCE_URL,
        value.get("source") != SOURCE_ID,
        value.get("collection") != "ACTIVE",
        value.get("member") != "INCLUDED",
        value.get("permission") is not True,
    )):
        raise RuntimeError("DP313_SOURCE_IDENTITY_CONFLICT")
    if value["rights"] not in {"UNKNOWN", "CLEARED"}:
        raise RuntimeError("DP313_SOURCE_RIGHTS_CONFLICT")


def _rights(store: CapturePipelineStore):
    """Current narrowly scoped copyright permission; no public or privacy grant."""
    subject = RightsSubject(source_family=FAMILY, locator_kind="URL",
                            locator_value=SOURCE_URL, content_id=CONTENT_ID)
    registry = PrivateRightsRegistryStore(database_url=store.database_url)
    current = registry.read_current(subject)
    previous_unusable_record = (
        current is not None
        and current.policy_version == POLICY
        and current.rights_status == "CLEARED"
        and current.rights_receipt_ref == RIGHTS_RECEIPT
        and current.reviewer_ref == "machine:dp313-curia-official-copyright-review"
        and set(current.permitted_uses) == set(USES) - {"RESEARCH_CAPTURE_PRIVATE"}
    )
    if current is None or previous_unusable_record:
        now = datetime.now(timezone.utc)
        current = registry.record_rights(
            subject=subject, policy_version=POLICY, rights_status="CLEARED",
            rights_receipt_ref=RIGHTS_RECEIPT, permitted_uses=USES,
            attribution_requirements=("ATTRIBUTION_REQUIRED", "NO_PUBLIC_QUOTE",
                                      "EXCLUDE_THIRD_PARTY_WORKS", "PRIVACY_HOLD"),
            reviewed_at=now.isoformat(), expires_at=(now + timedelta(days=7)).isoformat(),
            reviewer_ref="machine:dp313-curia-official-copyright-review",
            supersedes_record_id=current.id if previous_unusable_record else None,
        )
    if (current.rights_status != "CLEARED" or current.version_state != "CURRENT"
            or current.policy_version != POLICY or current.rights_receipt_ref != RIGHTS_RECEIPT
            or set(current.permitted_uses) != set(USES)):
        raise RuntimeError("DP313_RIGHTS_NOT_CURRENT")
    changed = store.run(
        """UPDATE content_item SET rights_status='CLEARED'
           WHERE id=:'content' AND source_id=:'source' AND canonical_url=:'url'
             AND rights_status IN ('UNKNOWN','CLEARED') RETURNING id;""",
        content=CONTENT_ID, source=SOURCE_ID, url=SOURCE_URL,
    )
    if changed != CONTENT_ID:
        raise RuntimeError("DP313_CONTENT_RIGHTS_CONFLICT")
    relevance = replay_current_ingestion_relevance(
        store.run, content_ref=CONTENT_ID, canonical_url=SOURCE_URL,
    )
    if not relevance.allowed:
        if relevance.blocker != "INGESTION_RELEVANCE_MISSING":
            raise RuntimeError("DP313_INGESTION_RELEVANCE_CONFLICT")
        append_ingestion_relevance_authority(
            store.run, content_ref=CONTENT_ID, canonical_url=SOURCE_URL,
            relevance_reason="OFFICIAL_RECORD", reviewer_ref="machine:dp313-curia-official",
            audit_ref="dp313:" + SOURCE_SHA256,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )
    return registry, subject, current
