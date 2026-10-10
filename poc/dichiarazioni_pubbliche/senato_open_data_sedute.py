"""Read-only Senato *open-data metadata* import for DP-234.

The Senato OpenData repository publishes its RDF datasets under CC BY 3.0.
This module imports *assembly sitting numbers and dates only*; it does not
import/rescope parliamentary speeches, assert who spoke, or license media.
All imported candidates remain rights-BLOCKED until independent source review.
No network, operational DB, publication or upstream provider client is present.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from xml.etree import ElementTree as ET

from dichiarazioni_pubbliche.dvns_structured_evidence import (
    DVNS_SOURCE_SCHEMA_VERSION,
    DvnsStructuredEvidenceImport,
    import_dvns_structured_evidence,
)

ADAPTER_VERSION = "senato-open-data-assembly-sittings-v1"
PROVIDER_ID = "senato-open-data-assembly-sittings"
DATASET_URL = "https://raw.githubusercontent.com/SenatoDellaRepubblica/OpenData/main/Leg19/dump-sedute-19.zip"
LICENSE_URL = "https://dati.senato.it/sito/faq?testo_generico=16"
DATASET_LICENSE = "CC-BY-3.0 (official OpenData datasets only)"
ZIP_MEMBER = "dump-sedute_assemblea-19.rdf"
MAX_ARCHIVE_BYTES = 512_000
MAX_XML_BYTES = 5_000_000
MAX_RECORDS = 500
RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
OSR = "{http://dati.senato.it/osr/}"
XSD = "http://www.w3.org/2001/XMLSchema#"
ASSEMBLY_TYPE = "http://dati.senato.it/osr/SedutaAssemblea"
COMMISSION_TYPE = "http://dati.senato.it/osr/SedutaCommissione"
URI = re.compile(r"http://dati\.senato\.it/sedutaassemblea/[0-9]{1,12}\Z")


class SenatoOpenDataError(ValueError):
    """Rejected or unverified official RDF archive; nothing was imported."""


@dataclass(frozen=True)
class SenatoOpenDataCandidateImport:
    source_archive_sha256: str
    source_dataset_url: str
    source_license_notice_url: str
    observed_license_scope: str
    rows_imported: int
    rights_gate: str
    imported: DvnsStructuredEvidenceImport
    adapter_version: str = ADAPTER_VERSION


def _observed_utc(raw: str) -> str:
    if not isinstance(raw, str) or not raw.endswith("Z"):
        raise SenatoOpenDataError("OBSERVATION_UTC_REQUIRED")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SenatoOpenDataError("OBSERVATION_TIMESTAMP_INVALID") from None
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise SenatoOpenDataError("OBSERVATION_UTC_REQUIRED")
    return raw


def _read_archive(raw: bytes) -> bytes:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_ARCHIVE_BYTES:
        raise SenatoOpenDataError("SENATO_ARCHIVE_SIZE_INVALID")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != ZIP_MEMBER:
                raise SenatoOpenDataError("SENATO_ARCHIVE_MEMBERS_UNEXPECTED")
            entry = entries[0]
            if (entry.file_size > MAX_XML_BYTES or entry.file_size == 0
                    or entry.flag_bits & 1 or entry.is_dir()):
                raise SenatoOpenDataError("SENATO_RDF_SIZE_OR_ENCRYPTION_INVALID")
            with archive.open(entry) as source:
                xml = source.read(MAX_XML_BYTES + 1)
            if len(xml) != entry.file_size or len(xml) > MAX_XML_BYTES:
                raise SenatoOpenDataError("SENATO_RDF_SIZE_MISMATCH")
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as error:
        raise SenatoOpenDataError("SENATO_ARCHIVE_INVALID") from error
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise SenatoOpenDataError("SENATO_RDF_ENTITY_FORBIDDEN")
    return xml


def _literal(row: ET.Element, field: str, datatype: str) -> str:
    nodes = row.findall(OSR + field)
    if len(nodes) != 1:
        raise SenatoOpenDataError(f"SENATO_{field.upper()}_MISSING_OR_DUPLICATE")
    node = nodes[0]
    if node.attrib != {RDF + "datatype": XSD + datatype} or not node.text:
        raise SenatoOpenDataError(f"SENATO_{field.upper()}_TYPE_INVALID")
    return node.text.strip()


def _parse(xml: bytes) -> list[dict[str, object]]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise SenatoOpenDataError("SENATO_RDF_XML_INVALID") from error
    if root.tag != RDF + "RDF":
        raise SenatoOpenDataError("SENATO_RDF_ROOT_INVALID")
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    for item in root:
        if item.tag != RDF + "Description":
            raise SenatoOpenDataError("SENATO_RDF_DESCRIPTION_INVALID")
        types = item.findall(RDF + "type")
        if len(types) != 1 or set(types[0].attrib) != {RDF + "resource"}:
            raise SenatoOpenDataError("SENATO_RDF_TYPE_INVALID")
        kind = types[0].attrib[RDF + "resource"]
        if kind == COMMISSION_TYPE:
            continue  # Has no numeroSeduta; cannot be silently converted.
        if kind != ASSEMBLY_TYPE:
            raise SenatoOpenDataError("SENATO_RDF_UNKNOWN_CLASS")
        if len(item) != 4 or {node.tag for node in item} != {
            RDF + "type", OSR + "legislatura", OSR + "dataSeduta", OSR + "numeroSeduta"
        }:
            raise SenatoOpenDataError("SENATO_ASSEMBLY_FIELDS_UNEXPECTED")
        uri = item.attrib.get(RDF + "about")
        if len(item.attrib) != 1 or not isinstance(uri, str) or not URI.fullmatch(uri):
            raise SenatoOpenDataError("SENATO_ASSEMBLY_ID_INVALID")
        if uri in seen:
            raise SenatoOpenDataError("SENATO_ASSEMBLY_DUPLICATE_ID")
        seen.add(uri)
        legislature = _literal(item, "legislatura", "integer")
        if legislature != "19":
            raise SenatoOpenDataError("SENATO_LEGISLATURE_MISMATCH")
        sitting_date = _literal(item, "dataSeduta", "date")
        try:
            if date.fromisoformat(sitting_date).isoformat() != sitting_date:
                raise ValueError
        except ValueError:
            raise SenatoOpenDataError("SENATO_DATE_INVALID") from None
        number = _literal(item, "numeroSeduta", "integer")
        if not re.fullmatch(r"0|[1-9][0-9]{0,7}", number):
            raise SenatoOpenDataError("SENATO_NUMBER_INVALID")
        selector = f'rdf:Description[@rdf:about="{uri}"]'
        records.append({
            "external_id": uri,
            "source_url": DATASET_URL,
            "metric": "senato_assemblea_numero_seduta",
            "value_state": "PRESENT",
            "value_numeric": int(number),
            "value_text": None,
            "unit": "ordinal",
            "reference_period": sitting_date,
            "publication_date": None,  # Dataset metadata does not supply an issue date.
            "observed_at": None,  # Set from the actual caller's observation below.
            "effective_from": None,
            "effective_to": None,
            "dimensions": {"legislatura": "19"},
            "source_roles": [],  # Self-declared source roles never authorize evidence.
            "field_provenance": {
                "external_id": f"{selector}/@rdf:about",
                "source_version": "sha256(source_archive_bytes)",
                "source_url": "verified_git_repository_dataset_path",
                "metric": "adapter:sitting_number_field_mapping",
                "value_state": f"{selector}/osr:numeroSeduta/presence",
                "value_numeric": f"{selector}/osr:numeroSeduta",
                "unit": "adapter:integer_ordinal",
                "reference_period": f"{selector}/osr:dataSeduta",
                "observed_at": "operator:observed_at_utc",
                "dimensions.legislatura": f"{selector}/osr:legislatura",
            },
        })
    if not records or len(records) > MAX_RECORDS:
        raise SenatoOpenDataError("SENATO_ASSEMBLY_ROW_COUNT_INVALID")
    return records


def import_senato_open_data_sittings(
    archive_bytes: bytes, *, observed_at_utc: str
) -> SenatoOpenDataCandidateImport:
    """Normalize a caller-observed ZIP into existing candidate-only DP-234 seam.

    This function never fetches the source or approves its suitability. The
    observed license CC BY 3.0 only applies to Senato *open data*, not speech,
    parliamentary speaker IDs, media, publication, or operator permissions.
    """
    observed = _observed_utc(observed_at_utc)
    digest = hashlib.sha256(archive_bytes).hexdigest()
    rows = _parse(_read_archive(archive_bytes))
    for row in rows:
        row["observed_at"] = observed
    imported = import_dvns_structured_evidence({
        "schema_version": DVNS_SOURCE_SCHEMA_VERSION,
        "provider_id": PROVIDER_ID,
        "source_version": "sha256:" + digest,
        "rights_status": "BLOCKED",  # Needs a project-specific rights/profile decision.
        "availability_status": "AVAILABLE",
        "fetch_state": "SUCCEEDED",
        "blocker": None,
        "records": rows,
    }, expected_provider_id=PROVIDER_ID, max_records=MAX_RECORDS)
    return SenatoOpenDataCandidateImport(
        source_archive_sha256=digest,
        source_dataset_url=DATASET_URL,
        source_license_notice_url=LICENSE_URL,
        observed_license_scope=DATASET_LICENSE,
        rows_imported=len(imported.normalized_batch.values),
        rights_gate="BLOCKED_PENDING_PROJECT_SOURCE_PROFILE_REVIEW",
        imported=imported,
    )
