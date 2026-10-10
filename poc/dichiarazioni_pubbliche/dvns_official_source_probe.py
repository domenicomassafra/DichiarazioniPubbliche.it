"""Bounded, read-only *technical* ingestion of official Senato metadata into DP-234.

The repository's DVNS-style importer is provider-neutral; this deliberately small
probe exercises one real, public, source-owned RDF dataset through that importer
and the DP-215 suitability bridge. It does NOT authorize a DVNS partner API,
approve reuse rights, persist Evidence or enable publication.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from dichiarazioni_pubbliche.dvns_source_suitability import (
    HELD,
    derive_dvns_candidate_suitability,
)
from dichiarazioni_pubbliche.senato_open_data_sedute import (
    DATASET_URL,
    MAX_ARCHIVE_BYTES,
    PROVIDER_ID,
    SenatoOpenDataCandidateImport,
    import_senato_open_data_sittings,
)
from dichiarazioni_pubbliche.source_intelligence import load_source_intelligence_contract


class DvnsOfficialProbeError(ValueError):
    """Unavailable, changed or unapproved source: zero accepted evidence."""


class _DenyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_REDIRECT_REFUSED")


@dataclass(frozen=True)
class SenatoTechnicalReceipt:
    dataset_url: str
    source_sha256: str
    source_bytes: int
    observed_at_utc: str
    provider_id: str
    source_version: str
    dvns_replay_id: str
    imported_records: int
    candidate_state: str
    blocking_reasons: tuple[str, ...]
    rights_gate: str
    first_source_record_id: str
    last_source_record_id: str


def _live_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fetch_official_archive(*, opener=None) -> bytes:
    # Fixed official URL: no arbitrary URL, redirect, credentials, query or retry.
    transport = opener or urllib.request.build_opener(_DenyRedirect())
    request = urllib.request.Request(
        DATASET_URL,
        headers={"Accept": "application/zip", "User-Agent": "DichiarazioniPubbliche-DVNS-technical-canary/1"},
    )
    try:
        with transport.open(request, timeout=15) as response:
            if response.geturl() != DATASET_URL or response.status != 200:
                raise DvnsOfficialProbeError("DVNS_OFFICIAL_RESPONSE_UNEXPECTED")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    parsed_length = int(length)
                except ValueError as exc:
                    raise DvnsOfficialProbeError("DVNS_OFFICIAL_LENGTH_INVALID") from exc
                if parsed_length <= 0 or parsed_length > MAX_ARCHIVE_BYTES:
                    raise DvnsOfficialProbeError("DVNS_OFFICIAL_LENGTH_INVALID")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
            if content_type not in {"application/zip", "application/octet-stream"}:
                raise DvnsOfficialProbeError("DVNS_OFFICIAL_CONTENT_TYPE_INVALID")
            blob = response.read(MAX_ARCHIVE_BYTES + 1)
            if not blob or len(blob) > MAX_ARCHIVE_BYTES:
                raise DvnsOfficialProbeError("DVNS_OFFICIAL_SIZE_INVALID")
            if length is not None and len(blob) != parsed_length:
                raise DvnsOfficialProbeError("DVNS_OFFICIAL_LENGTH_MISMATCH")
            return blob
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_UNAVAILABLE") from exc


def read_back_senato_official_candidate(
    source_archive_bytes: bytes, *, observed_at_utc: str,
) -> SenatoTechnicalReceipt:
    """Independently recompute a rights-held receipt from archived source bytes.

    `observed_at_utc` must be the timestamp recorded by the original acquisition.
    A separate cross-host verifier reads original bytes and recomputes hashes,
    values and suitability; supplying the timestamp does not claim fresh acquisition.
    """
    imported: SenatoOpenDataCandidateImport = import_senato_open_data_sittings(
        source_archive_bytes, observed_at_utc=observed_at_utc,
    )
    contract = load_source_intelligence_contract()
    profile = contract.evidence_profiles_by_registry_id["senato-linked-data"]
    scope = profile.authority_scopes[0]
    suitability = derive_dvns_candidate_suitability(
        imported.imported,
        target_id="technical-canary:senato-open-data-sittings",
        statement_date=observed_at_utc[:10],
        claim_requirements={"metric": "senato_assemblea_numero_seduta"},
        source_profile=profile,
        evidence_role="OFFICIAL_PROCEDURAL_RECORD",
        authority_scope=scope,
    )
    if suitability.candidate_state != HELD or "DVNS_RIGHTS_BLOCKED" not in suitability.blocking_reasons:
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_RIGHTS_GATE_NOT_HELD")
    rows = imported.imported.normalized_batch.values
    if not rows or len(suitability.records) != len(rows):
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_INCOMPLETE_CANDIDATE_BATCH")
    source_ids = sorted(row.source_record_id for row in rows)
    return SenatoTechnicalReceipt(
        dataset_url=DATASET_URL,
        source_sha256=hashlib.sha256(source_archive_bytes).hexdigest(),
        source_bytes=len(source_archive_bytes),
        observed_at_utc=observed_at_utc,
        provider_id=PROVIDER_ID,
        source_version=imported.imported.source_version,
        dvns_replay_id=imported.imported.replay_id,
        imported_records=imported.rows_imported,
        candidate_state=suitability.candidate_state,
        blocking_reasons=suitability.blocking_reasons,
        rights_gate=imported.rights_gate,
        first_source_record_id=source_ids[0],
        last_source_record_id=source_ids[-1],
    )


def verify_senato_official_readback(
    source_archive_bytes: bytes, *, expected: SenatoTechnicalReceipt,
) -> SenatoTechnicalReceipt:
    """Fail closed if a separate host cannot reconstruct the exact original receipt."""
    if not isinstance(expected, SenatoTechnicalReceipt):
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_RECEIPT_TYPE_INVALID")
    result = read_back_senato_official_candidate(
        source_archive_bytes, observed_at_utc=expected.observed_at_utc,
    )
    if result != expected:
        raise DvnsOfficialProbeError("DVNS_OFFICIAL_RECEIPT_MISMATCH")
    return result


def acquire_senato_official_candidate(*, opener=None) -> SenatoTechnicalReceipt:
    """Actual bounded HTTPS fetch; only receipt returned, no raw body persisted."""
    blob = _fetch_official_archive(opener=opener)
    return read_back_senato_official_candidate(blob, observed_at_utc=_live_utc())
