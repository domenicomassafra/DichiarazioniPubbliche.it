"""One public DVNS MCP aggregate, source-owned licence and private candidate Evidence.

The upstream API is read-only. The code uses the project's own DVNS/DP-215 and
private rights/Evidence stores; no upstream application code or raw corpus is copied.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any

from dichiarazioni_pubbliche.dvns_source_suitability import (
    READY_FOR_DP215_ASSESSMENT, derive_dvns_candidate_suitability,
)
from dichiarazioni_pubbliche.dvns_structured_evidence import (
    DvnsStructuredEvidenceImport, import_dvns_structured_evidence,
    DVNS_SOURCE_SCHEMA_VERSION,
)
from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.rights_registry import RightsSubject
from dichiarazioni_pubbliche.source_intelligence import load_source_intelligence_contract

MCP_URL = "https://www.dovevannoinostrisoldi.com/api/mcp"
LICENSE_URL = "https://opencoesione.gov.it/it/licenza/"
SOURCE_URL = "https://opencoesione.gov.it/it/api/aggregati/temi/ricerca-e-innovazione"
DATASET = "opencoesione_progetti"
PROVIDER = "dvns-opencoesione-mcp"
SOURCE_FAMILY = "DVNS_OPENCOESIONE_AGGREGATES"
POLICY_VERSION = "dp329-dvns-opencoesione-private-v1"
METRIC = "opencoesione_projects_count"
ADAPTER_VERSION = "dp329-dvns-mcp-opencoesione-v1"
MAX_RESPONSE = 150_000


class DvnsMcpError(ValueError):
    """A changed API, source or rights contract cannot create private Evidence."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DvnsMcpError("DVNS_MCP_REDIRECT_REFUSED")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError) as exc:
        raise DvnsMcpError("DVNS_MCP_TIMESTAMP_INVALID") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise DvnsMcpError("DVNS_MCP_TIMESTAMP_UNZONED")
    return result.astimezone(timezone.utc)


def _open_fixed(url: str, *, body: bytes | None = None, opener=None) -> bytes:
    if url not in {MCP_URL, LICENSE_URL, SOURCE_URL} or (body is not None and url != MCP_URL):
        raise DvnsMcpError("DVNS_MCP_NETWORK_TARGET_INVALID")
    transport = opener or urllib.request.build_opener(_NoRedirect())
    headers = {"User-Agent": "DichiarazioniPubbliche-DVNS-private-read/1"}
    if body is not None:
        headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    request = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST" if body is not None else "GET")
    try:
        with transport.open(request, timeout=15) as response:
            if response.status != 200 or response.geturl() != url:
                raise DvnsMcpError("DVNS_MCP_HTTP_RESPONSE_INVALID")
            media = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            expected_media = ({"text/event-stream", "application/json"} if body is not None
                              else {"application/json"} if url == SOURCE_URL else {"text/html"})
            if media not in expected_media:
                raise DvnsMcpError("DVNS_MCP_MEDIA_TYPE_INVALID")
            data = response.read(MAX_RESPONSE + 1)
            if not data or len(data) > MAX_RESPONSE:
                raise DvnsMcpError("DVNS_MCP_RESPONSE_SIZE_INVALID")
            return data
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DvnsMcpError("DVNS_MCP_NETWORK_UNAVAILABLE") from exc


def official_licence_receipt(*, opener=None) -> str:
    """Hash the official notice actually observed, and require its scoped CC BY grant."""
    body = _open_fixed(LICENSE_URL, opener=opener)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.decode("utf-8")))
    if (not re.search(r"CC-BY\s*4\.0", text, re.I)
            or "OpenCoesione" not in text
            or "ove non diversamente specificato" not in text
            or "indicata la fonte" not in text):
        raise DvnsMcpError("DVNS_MCP_OFFICIAL_LICENCE_NOT_VERIFIED")
    return "sha256:" + hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class OfficialReferenceReceipt:
    """Current primary endpoint receipt, independent of the DVNS snapshot."""
    source_version: str
    reference_period: str
    projects: int


def observe_official_reference(*, opener=None) -> OfficialReferenceReceipt:
    raw = _open_fixed(SOURCE_URL, opener=opener)
    try:
        payload = json.loads(raw)
        raw_date = payload["data_aggiornamento"]
        raw_projects = payload["aggregati"]["totali"]["progetti"]
        if (not isinstance(raw_date, str) or not re.fullmatch(r"[0-9]{8}", raw_date)
                or not isinstance(raw_projects, str) or not re.fullmatch(r"[0-9]+", raw_projects)):
            raise DvnsMcpError("DVNS_MCP_OFFICIAL_SOURCE_SHAPE_INVALID")
        period = datetime.strptime(raw_date, "%Y%m%d").date().isoformat()
        projects = int(raw_projects)
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise DvnsMcpError("DVNS_MCP_OFFICIAL_SOURCE_SHAPE_INVALID") from exc
    return OfficialReferenceReceipt("sha256:" + hashlib.sha256(raw).hexdigest(),
                                    period, projects)


def fetch_public_mcp_snapshot(*, opener=None) -> dict[str, Any]:
    """One fixed query, no credentials, user URLs, pagination or bulk fetch."""
    envelope = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "query_dataset", "arguments": {"dataset": DATASET}}}
    raw = _open_fixed(MCP_URL, body=json.dumps(envelope).encode(), opener=opener)
    try:
        message = raw.decode("utf-8")
        if message.startswith("event:") or message.startswith("data:"):
            events = [line[6:] for line in message.splitlines() if line.startswith("data: ")]
            if len(events) != 1:
                raise DvnsMcpError("DVNS_MCP_EVENT_COUNT_INVALID")
            message = events[0]
        outer = json.loads(message)
        if outer.get("id") != 1 or outer.get("error") or outer.get("result", {}).get("isError"):
            raise DvnsMcpError("DVNS_MCP_RPC_FAILED")
        content = outer["result"]["content"]
        if len(content) != 1 or content[0]["type"] != "text":
            raise DvnsMcpError("DVNS_MCP_CONTENT_INVALID")
        return json.loads(content[0]["text"])
    except (AttributeError, KeyError, IndexError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise DvnsMcpError("DVNS_MCP_PROTOCOL_INVALID") from exc


def import_opencoesione_snapshot(
    payload: dict[str, Any], *, observed_at: str,
) -> DvnsStructuredEvidenceImport:
    observed = _datetime(observed_at)
    if not isinstance(payload, dict) or payload.get("ok") is not True or payload.get("dataset") != DATASET:
        raise DvnsMcpError("DVNS_MCP_DATASET_MISMATCH")
    data = payload.get("data")
    if not isinstance(data, dict) or type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1:
        raise DvnsMcpError("DVNS_MCP_SCHEMA_VERSION_UNSUPPORTED")
    generated = _datetime(data.get("generatedAt"))
    try:
        reference = date.fromisoformat(data["referenceDate"])
    except (TypeError, ValueError, KeyError) as exc:
        raise DvnsMcpError("DVNS_MCP_REFERENCE_DATE_INVALID") from exc
    if generated > observed or reference > generated.date() or data.get("scope") != "national-overview":
        raise DvnsMcpError("DVNS_MCP_SNAPSHOT_TEMPORAL_OR_SCOPE_INVALID")
    source = data.get("source")
    if (not isinstance(source, dict) or source.get("owner") != "Dipartimento per le Politiche di Coesione"
            or source.get("endpoint") != "https://opencoesione.gov.it/it/api/aggregati/"
            or source.get("license") != "CC BY 4.0"):
        raise DvnsMcpError("DVNS_MCP_SOURCE_LICENCE_MISMATCH")
    themes = data.get("themes")
    if not isinstance(themes, list):
        raise DvnsMcpError("DVNS_MCP_THEMES_INVALID")
    found = [(index, item) for index, item in enumerate(themes)
             if isinstance(item, dict) and item.get("slug") == "ricerca-e-innovazione"]
    if len(found) != 1:
        raise DvnsMcpError("DVNS_MCP_SOURCE_IDENTITY_INVALID")
    index, item = found[0]
    value = item.get("projects")
    if item.get("sourceUrl") != SOURCE_URL or type(value) is not int or value < 0:
        raise DvnsMcpError("DVNS_MCP_SOURCE_VALUE_INVALID")
    source_version = "sha256:" + _digest(data)
    fields = {
        "external_id": f"$.data.themes[{index}].slug",
        "source_version": "$.data (canonical JSON SHA-256)",
        "source_url": f"$.data.themes[{index}].sourceUrl",
        "metric": f"$.data.themes[{index}].projects",
        "value_state": f"$.data.themes[{index}].projects (present)",
        "value_numeric": f"$.data.themes[{index}].projects",
        "unit": f"$.data.themes[{index}].projects (count)",
        "reference_period": "$.data.referenceDate",
        "publication_date": "$.data.generatedAt (downstream snapshot generation)",
        "observed_at": "HTTP MCP response receipt timestamp",
        "source_roles": "$.data.source.owner (secondary DVNS aggregation)",
    }
    return import_dvns_structured_evidence({
        "schema_version": DVNS_SOURCE_SCHEMA_VERSION, "provider_id": PROVIDER,
        "source_version": source_version, "rights_status": "UNRESOLVED",
        "availability_status": "AVAILABLE", "fetch_state": "SUCCEEDED",
        "records": [{"external_id": f"{DATASET}:themes:ricerca-e-innovazione",
                     "source_url": SOURCE_URL, "metric": METRIC,
                     "value_state": "PRESENT", "value_numeric": value, "unit": "projects",
                     "reference_period": reference.isoformat(),
                     "publication_date": generated.date().isoformat(),
                     "observed_at": observed.isoformat(),
                     "source_roles": ["SECONDARY_REFERENCE"],
                     "field_provenance": fields}],
    }, expected_provider_id=PROVIDER, max_records=1)


def rights_subject() -> RightsSubject:
    return RightsSubject(source_family=SOURCE_FAMILY, locator_kind="URL", locator_value=SOURCE_URL)


@dataclass(frozen=True)
class PrivateEvidenceReceipt:
    evidence_id: str
    observation_id: str
    source_version: str
    source_record_id: str
    rights_record_id: str
    licence_sha256: str
    suitability_state: str
    observation_status: str = "CANDIDATE"
    publication_authorized: bool = False


def persist_private_candidate(imported, *, store, rights, licence_receipt: str,
                              observed_at: str,
                              official_reference: OfficialReferenceReceipt) -> PrivateEvidenceReceipt:
    """Enforce a current source-specific grant; persist only typed candidate rows."""
    subject = rights_subject()
    current = rights.read_current(subject)
    if current is None or current.rights_receipt_ref != licence_receipt:
        raise DvnsMcpError("DVNS_MCP_RIGHTS_OR_LICENCE_NOT_CURRENT")
    now = _datetime(observed_at)
    for use in ("FETCH", "STORE_BODY"):
        verdict = evaluate_source_use(current, subject=subject, rights_record_id=current.id,
                                      policy_version=POLICY_VERSION, use=use, now=now)
        if not verdict.permitted:
            raise DvnsMcpError(verdict.reason_code)
    if (imported.provider_id != PROVIDER or imported.rights_status != "UNRESOLVED"
            or len(imported.normalized_batch.values) != 1):
        raise DvnsMcpError("DVNS_MCP_IMPORT_CONTRACT_INVALID")
    row = imported.normalized_batch.values[0]
    if (not isinstance(official_reference, OfficialReferenceReceipt)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", official_reference.source_version)
            or official_reference.projects < 0):
        raise DvnsMcpError("DVNS_MCP_OFFICIAL_RECEIPT_REQUIRED")
    try:
        official_date = date.fromisoformat(official_reference.reference_period)
        historical_date = date.fromisoformat(row.reference_period)
    except (TypeError, ValueError) as exc:
        raise DvnsMcpError("DVNS_MCP_REFERENCE_PERIOD_INVALID") from exc
    if official_date < historical_date:
        raise DvnsMcpError("DVNS_MCP_OFFICIAL_SOURCE_REGRESSED")
    if official_date == historical_date and official_reference.projects != int(row.value_numeric):
        raise DvnsMcpError("DVNS_MCP_OFFICIAL_VALUE_CONFLICT")
    superseded = official_date > historical_date
    profile = load_source_intelligence_contract().evidence_profiles_by_registry_id[PROVIDER]
    profile = replace(profile, rights_status="CLEARED")
    scope = profile.authority_scopes[0]
    suitability = derive_dvns_candidate_suitability(
        replace(imported, rights_status="CLEARED"),
        target_id="source-candidate:dvns-opencoesione-projects", statement_date=now.date().isoformat(),
        claim_requirements={"metric": METRIC, "unit": "projects",
                            "reference_period": row.reference_period, "jurisdiction": "IT",
                            "dataset_class": "OPENCOESIONE_PROJECTS"},
        source_profile=profile, evidence_role="SECONDARY_REFERENCE", authority_scope=scope,
    )
    if suitability.candidate_state != READY_FOR_DP215_ASSESSMENT:
        raise DvnsMcpError("DVNS_MCP_DP215_HELD:" + ",".join(suitability.records[0].reason_codes))
    # Evidence's canonical URL points to the primary official endpoint. Its
    # content hash must therefore identify those *actual response bytes*, not
    # the secondary DVNS JSON normalization. Version both snapshots in the ID.
    evidence_id = "evidence:" + _digest([
        PROVIDER, row.source_record_id, row.source_version,
        official_reference.source_version,
    ])
    observation_id = "observation:" + _digest([evidence_id, row.record_id, METRIC])
    # Rights are read again at the write boundary: revocations supersede old receipts.
    if rights.read_current(subject) != current:
        raise DvnsMcpError("DVNS_MCP_RIGHTS_CHANGED")
    store.upsert_evidence(
        evidence_id=evidence_id, canonical_url=SOURCE_URL, publisher=source_owner(),
        source_type="SECONDARY_OFFICIAL_DATA_AGGREGATE", fetched_at=observed_at,
        publication_date=row.publication_date,
        record_status="SUPERSEDED" if superseded else "ACTIVE",
        content_sha256=official_reference.source_version[7:],
        reference_period=row.reference_period,
        rights_status="CLEARED", metadata={
            "provider": PROVIDER, "dataset": DATASET, "source_version": row.source_version,
            "external_id": row.source_record_id, "adapter_version": ADAPTER_VERSION,
            "source_schema_version": imported.source_schema_version,
            "dvns_replay_id": imported.replay_id, "rights_record_id": current.id,
            "licence_notice": LICENSE_URL, "licence_sha256": licence_receipt,
            "licence": "CC-BY-4.0", "attribution": source_owner(),
            "publication_date_is_downstream_snapshot_generation": True,
            "candidate_only": True,
            "official_current_source_version": official_reference.source_version,
            "official_current_reference_period": official_reference.reference_period,
            "official_current_projects": official_reference.projects,
            "dvns_snapshot_superseded": superseded,
        })
    # The two store operations are separate existing PostgreSQL calls. Recheck
    # the append-only current head before writing the typed observation too.
    if rights.read_current(subject) != current:
        raise DvnsMcpError("DVNS_MCP_RIGHTS_CHANGED_BEFORE_OBSERVATION")
    store.insert_evidence_observation(
        observation_id=observation_id, evidence_id=evidence_id, observation_type="STRUCTURED_NUMERIC",
        metric=METRIC, value_numeric=float(row.value_numeric), value_text=None,
        unit=row.unit, reference_period=row.reference_period, dimensions={},
        extraction_method="DVNS_MCP_QUERY_DATASET", extraction_version=ADAPTER_VERSION,
        source_pointer={"canonical_url": SOURCE_URL, "source_version": row.source_version,
                        "external_id": row.source_record_id,
                        "official_current_source_version": official_reference.source_version,
                        "official_current_reference_period": official_reference.reference_period,
                        "field_provenance": dict(imported.provenance[0].fields)},
        status="CANDIDATE", metadata={"rights_record_id": current.id,
                                      "dp215_fingerprint": suitability.input_fingerprint,
                                      "dvns_snapshot_superseded": superseded,
                                      "candidate_only": True},
    )
    return PrivateEvidenceReceipt(evidence_id, observation_id, row.source_version,
                                  row.source_record_id, current.id, licence_receipt,
                                  suitability.candidate_state)


def source_owner() -> str:
    return "Dipartimento per le Politiche di Coesione / OpenCoesione"
