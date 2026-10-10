"""Bounded read-only candidate import for Senato's official Akoma Ntoso bulk data.

The Senate's AkomaNtosoBulkData repository publishes ``resaula`` XML under
CC BY 4.0.  This parser consumes caller-fetched, commit-pinned XML and emits
*private, unreviewed* speech candidates.  It never resolves a public Person,
promotes a statement, grants excerpt rights, fetches URLs, or publishes data.

The XML speaker ``by`` attribute is bound to an explicit ``TLCPerson`` entry.
Unresolvable speaker turns are returned as holds rather than guessed from the
``from`` presentation label or a video/platform account.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET


ADAPTER_VERSION = "senato-akoma-stenographic-candidates-v1"
LICENSE_ID = "CC-BY-4.0"
LICENSE_URL = "https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData/blob/master/LICENSE.MD"
SOURCE_REPOSITORY = "https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData"
MAX_XML_BYTES = 3_000_000
MAX_SPEECHES = 1500
MAX_REVIEW_TEXT_CHARS = 20_000

NAMESPACE = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"
_RAW_URL = re.compile(
    r"https://raw\.githubusercontent\.com/SenatoDellaRepubblica/"
    r"AkomaNtosoBulkData/([a-fA-F0-9]{40})/Leg(\d{1,2})/"
    r"Atto(\d{8})/resaula/(\d{8})-ra\.akn\.xml\Z"
)
_WORK_URI = re.compile(
    r"http://dati\.senato\.it/osr/RESAULA/(\d{4}-\d{2}-\d{2})/(\d{1,6})\Z"
)
_PERSON_ID = re.compile(r"p([1-9][0-9]{0,11})\Z")
_PERSON_URI = re.compile(r"http://dati\.senato\.it/osr/Persona/([1-9][0-9]{0,11})\Z")


class SenatoAkomaError(ValueError):
    """Fail closed on an unsupported XML, identity, or source assertion."""


@dataclass(frozen=True)
class SenatoAkomaSpeechCandidate:
    ordinal: int
    source_speaker_ref: str
    official_person_uri: str
    official_display_name: str
    presentation_label: str
    review_text: str
    review_text_sha256: str
    speech_id: str
    quote_or_person_approved: bool = False


@dataclass(frozen=True)
class SenatoAkomaHeldSpeech:
    ordinal: int
    reason: str
    source_speaker_ref: str | None


@dataclass(frozen=True)
class SenatoAkomaCandidateImport:
    sitting_id: str
    sitting_date: str
    legislature: int
    sitting_number: int
    source_raw_url: str
    source_commit_sha: str
    source_blob_sha1: str
    source_sha256: str
    source_license_id: str
    source_license_url: str
    speeches: tuple[SenatoAkomaSpeechCandidate, ...]
    held_speeches: tuple[SenatoAkomaHeldSpeech, ...]
    source_rights_decision: str = "PENDING_OPERATOR_SCOPE_REVIEW"
    publication_authorized: bool = False
    adapter_version: str = ADAPTER_VERSION


def _literal(element: ET.Element | None, attr: str, reason: str) -> str:
    if element is None:
        raise SenatoAkomaError(reason)
    value = element.get(attr)
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise SenatoAkomaError(reason)
    return value.strip()


def _paragraph_text(element: ET.Element) -> str:
    # Reconstruction is a private review hint; it is never an approved quote.
    chunks = []
    for child in element:
        if child.tag == NAMESPACE + "from":
            continue
        if child.tag not in {NAMESPACE + "p", NAMESPACE + "block", NAMESPACE + "tblock"}:
            continue
        value = " ".join("".join(child.itertext()).split())
        if value:
            chunks.append(value)
    return "\n".join(chunks)


def import_senato_akoma_stenographic(
    xml_bytes: bytes, *, source_raw_url: str, expected_blob_sha1: str
) -> SenatoAkomaCandidateImport:
    """Import official Senate sitting speech candidates from an immutable raw blob.

    The operator must independently verify that the supplied commit really
    belongs to the official Senate repository.  The Git blob digest is checked
    over the *actual* bytes; a caller-supplied URL alone has no authority.
    """
    match = _RAW_URL.fullmatch(source_raw_url) if isinstance(source_raw_url, str) else None
    if match is None:
        raise SenatoAkomaError("SENATO_AKN_PINNED_OFFICIAL_REPOSITORY_URL_REQUIRED")
    commit, legislature, act_id, document_id = match.groups()
    if not isinstance(xml_bytes, bytes) or not xml_bytes or len(xml_bytes) > MAX_XML_BYTES:
        raise SenatoAkomaError("SENATO_AKN_XML_SIZE_INVALID")
    blob_hash = hashlib.sha1(b"blob " + str(len(xml_bytes)).encode() + b"\x00" + xml_bytes).hexdigest()
    if not isinstance(expected_blob_sha1, str) or expected_blob_sha1.lower() != blob_hash:
        raise SenatoAkomaError("SENATO_AKN_BLOB_MISMATCH")
    if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        raise SenatoAkomaError("SENATO_AKN_DTD_FORBIDDEN")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SenatoAkomaError("SENATO_AKN_XML_INVALID") from exc
    if root.tag != NAMESPACE + "akomaNtoso" or len(root) != 1 or root[0].tag != NAMESPACE + "debate":
        raise SenatoAkomaError("SENATO_AKN_DOCUMENT_UNSUPPORTED")
    debate = root[0]
    base = debate.find(f"{NAMESPACE}meta/{NAMESPACE}identification/{NAMESPACE}FRBRWork")
    uri = _literal(base.find(NAMESPACE + "FRBRuri") if base is not None else None,
                   "value", "SENATO_AKN_WORK_URI_MISSING")
    work_match = _WORK_URI.fullmatch(uri)
    if work_match is None:
        raise SenatoAkomaError("SENATO_AKN_WORK_URI_INVALID")
    sitting_date, sitting_num = work_match.groups()
    try:
        from datetime import date
        if date.fromisoformat(sitting_date).isoformat() != sitting_date:
            raise ValueError
    except ValueError:
        raise SenatoAkomaError("SENATO_AKN_DATE_INVALID") from None
    work_date = _literal(base.find(NAMESPACE + "FRBRdate"), "date", "SENATO_AKN_DATE_MISSING")
    if sitting_date != work_date:
        raise SenatoAkomaError("SENATO_AKN_WORK_DATE_MISMATCH")
    body = debate.find(NAMESPACE + "debateBody")
    if body is None:
        raise SenatoAkomaError("SENATO_AKN_BODY_MISSING")
    title = body.get("title", "")
    title_match = re.fullmatch(r"Resoconto n\.(\d+) della legislatura (\d+)", title)
    if title_match is None or (int(title_match[1]), int(title_match[2])) != (int(sitting_num), int(legislature)):
        raise SenatoAkomaError("SENATO_AKN_SITTING_MISMATCH")
    if len(debate.findall(f"{NAMESPACE}meta/{NAMESPACE}references")) != 1:
        raise SenatoAkomaError("SENATO_AKN_REFERENCES_MISSING")
    references = debate.find(f"{NAMESPACE}meta/{NAMESPACE}references")
    assert references is not None
    people: dict[str, tuple[str, str]] = {}
    for person in references.findall(NAMESPACE + "TLCPerson"):
        person_id, href, show_as = (person.get("id", ""), person.get("href", ""), person.get("showAs", ""))
        person_match = _PERSON_ID.fullmatch(person_id)
        href_match = _PERSON_URI.fullmatch(href)
        if person_match is None or href_match is None or person_match[1] != href_match[1]:
            raise SenatoAkomaError("SENATO_AKN_PERSON_REFERENCE_INVALID")
        if not show_as.strip() or len(show_as) > 200 or person_id in people:
            raise SenatoAkomaError("SENATO_AKN_PERSON_LABEL_OR_DUPLICATE_INVALID")
        people[person_id] = (href, show_as.strip())
    candidates: list[SenatoAkomaSpeechCandidate] = []
    held: list[SenatoAkomaHeldSpeech] = []
    speeches = list(body.iter(NAMESPACE + "speech"))
    if not speeches or len(speeches) > MAX_SPEECHES:
        raise SenatoAkomaError("SENATO_AKN_SPEECH_COUNT_INVALID")
    source_hash = hashlib.sha256(xml_bytes).hexdigest()
    for ordinal, speech in enumerate(speeches):
        speaker_ref = speech.get("by")
        origin = speech.find(NAMESPACE + "from")
        if (not isinstance(speaker_ref, str) or not speaker_ref.startswith("#")
                or speaker_ref[1:] not in people or origin is None
                or origin.get("refersTo") != speaker_ref):
            held.append(SenatoAkomaHeldSpeech(ordinal, "OFFICIAL_SPEAKER_REFERENCE_UNRESOLVED", speaker_ref))
            continue
        label = " ".join("".join(origin.itertext()).split())
        if not label or len(label) > 200:
            held.append(SenatoAkomaHeldSpeech(ordinal, "OFFICIAL_PRESENTATION_LABEL_MISSING", speaker_ref))
            continue
        text = _paragraph_text(speech)
        if not text or len(text) > MAX_REVIEW_TEXT_CHARS:
            held.append(SenatoAkomaHeldSpeech(ordinal, "SPEECH_REVIEW_TEXT_MISSING_OR_TOO_LONG", speaker_ref))
            continue
        official_uri, display = people[speaker_ref[1:]]
        candidates.append(SenatoAkomaSpeechCandidate(
            ordinal=ordinal, source_speaker_ref=speaker_ref,
            official_person_uri=official_uri, official_display_name=display,
            presentation_label=label, review_text=text,
            review_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            speech_id=(f"senato:akn:{legislature}:{sitting_date}:{sitting_num}:"
                       f"atto:{act_id}:document:{document_id}:speech:{ordinal}"),
        ))
    return SenatoAkomaCandidateImport(
        sitting_id=f"senato:akn:{legislature}:{sitting_date}:{sitting_num}",
        sitting_date=sitting_date, legislature=int(legislature),
        sitting_number=int(sitting_num), source_raw_url=source_raw_url,
        source_commit_sha=commit.lower(), source_blob_sha1=blob_hash,
        source_sha256=source_hash, source_license_id=LICENSE_ID,
        source_license_url=LICENSE_URL,
        speeches=tuple(candidates), held_speeches=tuple(held),
    )
