from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping


CORRECTION_PROPAGATION_VERSION = "correction-propagation-v1"
ROUTE_STATIC_MANIFEST_VERSION = "public-route-static-manifest-v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ENTITY_KINDS = ("finding", "content", "person", "topic")


@dataclass(frozen=True)
class ProjectionState:
    fingerprint: str
    findings: Mapping[str, Mapping[str, Any]]
    contents: Mapping[str, Mapping[str, Any]]
    people: Mapping[str, Mapping[str, Any]]
    topics: Mapping[str, Mapping[str, Any]]
    titles: Mapping[tuple[str, str], str]
    entity_sha256: Mapping[tuple[str, str], str]
    has_first_class_contents: bool


@dataclass(frozen=True)
class CorrectionPropagationReceipt:
    status: str
    old_projection_fingerprint: str
    new_projection_fingerprint: str
    observed_projection_fingerprints: tuple[str, ...]
    affected_finding_ids: tuple[str, ...]
    affected_content_ids: tuple[str, ...]
    affected_person_ids: tuple[str, ...]
    affected_topic_ids: tuple[str, ...]
    current_finding_ids: tuple[str, ...]
    historical_finding_ids: tuple[str, ...]
    stale_artifacts: tuple[str, ...]
    orphan_artifacts: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    blockers: tuple[str, ...]
    receipt_sha256: str = ""
    checker_version: str = CORRECTION_PROPAGATION_VERSION

    @property
    def consistent(self) -> bool:
        return self.status == "CONSISTENT"


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _required_text(value: Any, code: str, *, limit: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError(code)
    return text


def _projection_fingerprint(value: Any, code: str) -> str:
    fingerprint = _required_text(value, code, limit=64).lower()
    if not _SHA256_RE.fullmatch(fingerprint):
        raise ValueError(code)
    return fingerprint


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _rows(value: Any, code: str) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(code)
    output: list[Mapping[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            raise ValueError(code)
        output.append(row)
    return tuple(output)


def _index_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    key: str,
    missing_code: str,
    duplicate_code: str,
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identifier = _required_text(row.get(key), missing_code)
        if identifier in output:
            raise ValueError(f"{duplicate_code}:{identifier}")
        output[identifier] = row
    return output


def _projection_state(payload: Mapping[str, Any]) -> ProjectionState:
    fingerprint = _projection_fingerprint(
        payload.get("dataset_sha256"),
        "CORRECTION_PROPAGATION_PROJECTION_FINGERPRINT_INVALID",
    )
    dossiers = _rows(payload.get("dossiers"), "CORRECTION_PROPAGATION_DOSSIERS_INVALID")
    contents_rows = _rows(
        payload.get("contents"),
        "CORRECTION_PROPAGATION_CONTENTS_INVALID",
    )
    topics_rows = _rows(payload.get("topics"), "CORRECTION_PROPAGATION_TOPICS_INVALID")

    findings = _index_rows(
        dossiers,
        key="finding_id",
        missing_code="CORRECTION_PROPAGATION_FINDING_ID_REQUIRED",
        duplicate_code="CORRECTION_PROPAGATION_FINDING_DUPLICATE",
    )
    explicit_contents = _index_rows(
        contents_rows,
        key="content_id",
        missing_code="CORRECTION_PROPAGATION_CONTENT_ID_REQUIRED",
        duplicate_code="CORRECTION_PROPAGATION_CONTENT_DUPLICATE",
    )
    topics = _index_rows(
        topics_rows,
        key="topic_id",
        missing_code="CORRECTION_PROPAGATION_TOPIC_ID_REQUIRED",
        duplicate_code="CORRECTION_PROPAGATION_TOPIC_DUPLICATE",
    )

    people_parts: dict[str, dict[str, Any]] = {}
    content_parts: dict[str, dict[str, Any]] = {}
    titles: dict[tuple[str, str], str] = {}

    for finding_id, dossier in findings.items():
        titles[("finding", finding_id)] = _required_text(
            dossier.get("claim"),
            "CORRECTION_PROPAGATION_FINDING_TITLE_REQUIRED",
            limit=10_000,
        )
        speaker = _mapping(
            dossier.get("speaker"),
            "CORRECTION_PROPAGATION_SPEAKER_INVALID",
        )
        person_id = _required_text(
            speaker.get("id"),
            "CORRECTION_PROPAGATION_PERSON_ID_REQUIRED",
        )
        person = people_parts.setdefault(
            person_id,
            {"speaker_variants": {}, "finding_ids": []},
        )
        person["speaker_variants"][_digest(speaker)] = dict(speaker)
        person["finding_ids"].append(finding_id)
        titles[("person", person_id)] = _required_text(
            speaker.get("name") or person_id,
            "CORRECTION_PROPAGATION_PERSON_TITLE_REQUIRED",
            limit=10_000,
        )

        source = _mapping(
            dossier.get("source"),
            "CORRECTION_PROPAGATION_SOURCE_INVALID",
        )
        content_id = _required_text(
            source.get("content_id"),
            "CORRECTION_PROPAGATION_SOURCE_CONTENT_ID_REQUIRED",
        )
        content = content_parts.setdefault(
            content_id,
            {"source_variants": {}, "finding_ids": []},
        )
        content["source_variants"][_digest(source)] = dict(source)
        content["finding_ids"].append(finding_id)
        if ("content", content_id) not in titles:
            titles[("content", content_id)] = _required_text(
                source.get("title") or content_id,
                "CORRECTION_PROPAGATION_CONTENT_TITLE_REQUIRED",
                limit=10_000,
            )

    people: dict[str, Mapping[str, Any]] = {}
    for person_id, raw in people_parts.items():
        people[person_id] = {
            "speaker_variants": [
                raw["speaker_variants"][key]
                for key in sorted(raw["speaker_variants"])
            ],
            "finding_ids": sorted(raw["finding_ids"]),
        }

    contents: dict[str, Mapping[str, Any]] = {}
    for content_id in sorted(set(explicit_contents) | set(content_parts)):
        raw = content_parts.get(content_id, {"source_variants": {}, "finding_ids": []})
        explicit = explicit_contents.get(content_id)
        if explicit is not None:
            titles[("content", content_id)] = _required_text(
                explicit.get("title") or content_id,
                "CORRECTION_PROPAGATION_CONTENT_TITLE_REQUIRED",
                limit=10_000,
            )
        contents[content_id] = {
            "public_content": dict(explicit) if explicit is not None else None,
            "source_variants": [
                raw["source_variants"][key]
                for key in sorted(raw["source_variants"])
            ],
            "finding_ids_from_dossiers": sorted(raw["finding_ids"]),
        }

    for topic_id, topic in topics.items():
        titles[("topic", topic_id)] = _required_text(
            topic.get("canonical_name") or topic_id,
            "CORRECTION_PROPAGATION_TOPIC_TITLE_REQUIRED",
            limit=10_000,
        )

    entity_sha256: dict[tuple[str, str], str] = {}
    for kind, rows_by_id in (
        ("finding", findings),
        ("content", contents),
        ("person", people),
        ("topic", topics),
    ):
        for identifier, row in rows_by_id.items():
            entity_sha256[(kind, identifier)] = _digest(row)

    return ProjectionState(
        fingerprint=fingerprint,
        findings=findings,
        contents=contents,
        people=people,
        topics=topics,
        titles=titles,
        entity_sha256=entity_sha256,
        has_first_class_contents=payload.get("contents") is not None,
    )


def _changed_ids(
    old_rows: Mapping[str, Mapping[str, Any]],
    new_rows: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    output: set[str] = set()
    for identifier in set(old_rows) | set(new_rows):
        old = old_rows.get(identifier)
        new = new_rows.get(identifier)
        if old is None or new is None or _digest(old) != _digest(new):
            output.add(identifier)
    return output


def _finding_related_ids(
    state: ProjectionState,
    finding_ids: set[str],
) -> tuple[set[str], set[str], set[str]]:
    people: set[str] = set()
    contents: set[str] = set()
    topics: set[str] = set()
    claim_ids: set[str] = set()
    for finding_id in finding_ids:
        dossier = state.findings.get(finding_id)
        if dossier is None:
            continue
        speaker = dossier.get("speaker") or {}
        source = dossier.get("source") or {}
        if isinstance(speaker, Mapping) and speaker.get("id"):
            people.add(str(speaker["id"]))
        if isinstance(source, Mapping) and source.get("content_id"):
            contents.add(str(source["content_id"]))
        if dossier.get("claim_id"):
            claim_ids.add(str(dossier["claim_id"]))

    for topic_id, topic in state.topics.items():
        memberships = topic.get("memberships") or []
        if not isinstance(memberships, list):
            raise ValueError("CORRECTION_PROPAGATION_TOPIC_MEMBERSHIPS_INVALID")
        for membership in memberships:
            if not isinstance(membership, Mapping):
                raise ValueError("CORRECTION_PROPAGATION_TOPIC_MEMBERSHIP_INVALID")
            membership_findings = {str(value) for value in membership.get("finding_ids") or []}
            claim_id = str(membership.get("claim_id") or "")
            if membership_findings & finding_ids or (claim_id and claim_id in claim_ids):
                topics.add(topic_id)
                break
    return people, contents, topics


def _current_identity_sets(state: ProjectionState) -> dict[str, set[str]]:
    return {
        "finding": set(state.findings),
        "content": set(state.contents),
        "person": set(state.people),
        "topic": set(state.topics),
    }


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _artifact_fingerprint(
    value: Any,
    *,
    artifact: str,
    blockers: list[str],
    stale_artifacts: list[str],
) -> str | None:
    try:
        return _projection_fingerprint(
            value,
            f"CORRECTION_PROPAGATION_{artifact.upper()}_FINGERPRINT_INVALID",
        )
    except ValueError:
        _add_once(blockers, f"INVALID_ARTIFACT_FINGERPRINT:{artifact}")
        _add_once(stale_artifacts, artifact)
        return None


def _search_terms(values: Iterable[Any]) -> list[str]:
    """Mirror web/src/lib/searchIndex.ts::compactTerms exactly for public strings."""
    terms: list[str] = []
    for raw in values:
        term = str(raw).strip() if raw is not None else ""
        if term and term not in terms:
            terms.append(term)
    return terms


def _public_search_slug(identifier: str) -> str:
    """Mirror format.ts::publicIdSlug (lower, NFKD, remove marks, ASCII slug)."""
    normalized = unicodedata.normalize("NFKD", identifier.lower())
    without_marks = "".join(
        char for char in normalized if not unicodedata.category(char).startswith("M")
    )
    return re.sub(r"[^a-z0-9]+", "-", without_marks).strip("-")


def _search_record(
    kind: str,
    identifier: str,
    title: str,
    subtitle: str,
    published_at: str | None,
    assessment: str | None,
    route: str,
    primary: Iterable[Any],
    secondary: Iterable[Any],
    *,
    corrections: bool = False,
    replies: bool = False,
    wording: str | None = None,
    source_wording: str | None = None,
    **facets: Any,
) -> dict[str, Any]:
    """The full PublicSearchRecord v1 allowlist; no omitted or extra metadata."""
    return {
        "id": identifier, "kind": kind, "title": title, "subtitle": subtitle,
        "published_at": published_at, "assessment": assessment, "route": route,
        "has_corrections": corrections, "has_rights_of_reply": replies,
        "wording_type": wording, "source_wording_type": source_wording,
        "direct_quote_eligible": False,
        "primary_terms": _search_terms(primary), "secondary_terms": _search_terms(secondary),
        **facets,
    }


def _expected_search_records(current: ProjectionState) -> dict[tuple[str, str], dict[str, Any]]:
    """Recreate all four approved v1 search kinds from the CURRENT projection.

    Mirrors findingRecord and buildSearchIndexMaterial in searchIndex.ts:
    never trust a copied title or self-claimed SHA to authorize hidden terms,
    route rebinding, wrong facets, or even missing/extra record fields.
    """
    result: dict[tuple[str, str], dict[str, Any]] = {}
    topic_memberships: dict[str, set[str]] = {}
    for topic_id, topic in current.topics.items():
        for membership in topic["memberships"]:
            for finding_id in membership["finding_ids"]:
                topic_memberships.setdefault(finding_id, set()).add(topic_id)

    for finding_id, dossier in current.findings.items():
        speaker = dossier["speaker"]
        source = dossier["source"]
        finding = dossier["finding"]
        roles: list[Any] = []
        for role in speaker.get("public_roles") or []:
            if not isinstance(role, Mapping):
                raise ValueError("CORRECTION_PROPAGATION_PUBLIC_ROLE_INVALID")
            roles.extend((role["role"], role.get("organization_name")))
        finding_date = finding.get("published_at")
        original_wording = dossier.get("wording")
        source_wording = (
            original_wording["source_occurrence"]["wording_type"]
            if original_wording is not None else None
        )
        result[("finding", finding_id)] = _search_record(
            "finding", finding_id, dossier["claim"],
            " · ".join(str(value) for value in (speaker["name"], source["title"]) if value),
            finding_date if finding_date is not None else source.get("published_at"),
            finding["assessment"],
            f"/dichiarazioni/{_public_search_slug(finding_id)}/",
            (dossier["claim"],),
            (speaker["name"], source["title"], dossier["claim_type"], finding["assessment"], *roles),
            corrections=bool(dossier.get("corrections")),
            replies=bool(dossier.get("rights_of_reply")),
            wording="PARAPHRASE", source_wording=source_wording,
            person_id=speaker["id"],
            topic_ids=sorted(topic_memberships.get(finding_id, ())),
        )
        person_id = speaker["id"]
        if ("person", person_id) not in result:
            result[("person", person_id)] = _search_record(
                "person", person_id, speaker["name"],
                " · ".join(_search_terms(roles)), None, None,
                f"/persone/{_public_search_slug(person_id)}/",
                (speaker["name"],), roles,
            )
        if not current.has_first_class_contents:
            content_id = source["content_id"]
            if ("content", content_id) not in result:
                result[("content", content_id)] = _search_record(
                    "content", content_id, source["title"], "Fonte pubblica",
                    source.get("published_at"), None,
                    f"/contenuti/{_public_search_slug(content_id)}/",
                    (source["title"],), (),
                )

    for topic_id, topic in current.topics.items():
        result[("topic", topic_id)] = _search_record(
            "topic", topic_id, topic["canonical_name"],
            topic["scope_text"] if topic.get("scope_text") is not None
            else "Tema pubblico revisionato",
            None, None, f"/temi/{topic['slug']}/",
            (topic["canonical_name"],), (topic.get("scope_text"),),
        )
    if current.has_first_class_contents:
        for content_id, content in current.contents.items():
            explicit = content["public_content"]
            if explicit is None:
                continue
            result[("content", content_id)] = _search_record(
                "content", content_id, explicit["title"],
                explicit["content_kind"].lower(), explicit.get("published_at"),
                None, f"/contenuti/{explicit['slug']}/",
                (explicit["title"],), (explicit["content_kind"],),
            )
    return result


def _check_search_index(
    search_index: Mapping[str, Any],
    *,
    current: ProjectionState,
    blockers: list[str],
    stale_artifacts: list[str],
    orphan_artifacts: list[str],
    missing_artifacts: list[str],
) -> str | None:
    fingerprint = _artifact_fingerprint(
        search_index.get("projection_sha256"),
        artifact="search-index",
        blockers=blockers,
        stale_artifacts=stale_artifacts,
    )
    canonical_records = _expected_search_records(current)
    seen: set[tuple[str, str]] = set()
    records = search_index.get("records")
    if not isinstance(records, list):
        _add_once(blockers, "SEARCH_INDEX_RECORDS_INVALID")
        _add_once(stale_artifacts, "search-index")
        records = []
    for row in records:
        if not isinstance(row, Mapping):
            _add_once(blockers, "SEARCH_INDEX_RECORD_INVALID")
            continue
        kind = str(row.get("kind") or "")
        identifier = str(row.get("id") or "")
        identity = (kind, identifier)
        label = f"search:{kind}:{identifier}"
        if kind not in _ENTITY_KINDS or not identifier:
            _add_once(blockers, "SEARCH_INDEX_RECORD_INVALID")
            _add_once(orphan_artifacts, label)
            continue
        if identity in seen:
            _add_once(blockers, "SEARCH_INDEX_DUPLICATE_ENTRY")
            _add_once(stale_artifacts, label)
            continue
        seen.add(identity)
        expected_record = canonical_records.get(identity)
        if expected_record is None:
            _add_once(blockers, "SEARCH_INDEX_ORPHAN_ENTRY")
            _add_once(orphan_artifacts, label)
            continue
        expected_title = expected_record["title"]
        if expected_title is not None and str(row.get("title") or "") != expected_title:
            _add_once(blockers, "SEARCH_INDEX_STALE_ENTRY")
            _add_once(stale_artifacts, label)
        # Strict complete-record parity. A missing field is NOT an optional
        # omission, even if searchIndex.ts's client parser tolerates old v1
        # assets. All current Finding/Person/Topic/Content representations
        # must originate from the same approved correction/revocation state.
        if row != expected_record:
            _add_once(blockers, "SEARCH_INDEX_STALE_METADATA")
            _add_once(stale_artifacts, label)

    # Search record eligibility differs from historical source lineage:
    # `contents=[]` is a first-class empty catalog, not a request for legacy
    # per-dossier Content fallback rows. Static route/history tracking still
    # uses all source Content identities in `_current_identity_sets`.
    for kind, identifier in sorted(canonical_records):
        if (kind, identifier) not in seen:
            _add_once(blockers, "SEARCH_INDEX_PARTIAL")
            _add_once(missing_artifacts, f"search:{kind}:{identifier}")
    return fingerprint


def _check_route_static_manifest(
    manifest: Mapping[str, Any],
    *,
    old: ProjectionState,
    current: ProjectionState,
    historical_finding_ids: set[str],
    blockers: list[str],
    stale_artifacts: list[str],
    orphan_artifacts: list[str],
    missing_artifacts: list[str],
    observed_fingerprints: set[str],
) -> str | None:
    if manifest.get("manifest_version") != ROUTE_STATIC_MANIFEST_VERSION:
        _add_once(blockers, "ROUTE_STATIC_MANIFEST_VERSION_INVALID")
    fingerprint = _artifact_fingerprint(
        manifest.get("projection_fingerprint"),
        artifact="route-static",
        blockers=blockers,
        stale_artifacts=stale_artifacts,
    )
    expected = _current_identity_sets(current)
    current_seen: set[tuple[str, str]] = set()
    historical_seen: set[str] = set()
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        _add_once(blockers, "ROUTE_STATIC_ENTRIES_INVALID")
        _add_once(stale_artifacts, "route-static")
        entries = []
    artifact_ids: set[str] = set()
    for row in entries:
        if not isinstance(row, Mapping):
            _add_once(blockers, "ROUTE_STATIC_ENTRY_INVALID")
            continue
        artifact_id = str(row.get("artifact_id") or "")
        if not artifact_id:
            _add_once(blockers, "ROUTE_STATIC_ARTIFACT_ID_REQUIRED")
            continue
        if artifact_id in artifact_ids:
            _add_once(blockers, "ROUTE_STATIC_DUPLICATE_ARTIFACT")
            _add_once(stale_artifacts, f"route:{artifact_id}")
            continue
        artifact_ids.add(artifact_id)
        entry_fp = _artifact_fingerprint(
            row.get("projection_fingerprint"),
            artifact=f"route:{artifact_id}",
            blockers=blockers,
            stale_artifacts=stale_artifacts,
        )
        if entry_fp is not None:
            observed_fingerprints.add(entry_fp)

        kind = str(row.get("entity_kind") or "")
        identifier = str(row.get("entity_id") or "")
        view = str(row.get("view") or "")
        if not kind and not identifier:
            continue
        if kind not in _ENTITY_KINDS or not identifier or view not in {"CURRENT", "HISTORICAL"}:
            _add_once(blockers, "ROUTE_STATIC_ENTRY_INVALID")
            _add_once(orphan_artifacts, f"route:{artifact_id}")
            continue
        identity = (kind, identifier)
        claimed_entity_sha = str(row.get("entity_sha256") or "")
        if view == "CURRENT":
            if identifier not in expected[kind]:
                _add_once(blockers, "ROUTE_STATIC_ORPHAN_CURRENT_ENTRY")
                _add_once(orphan_artifacts, f"route:{artifact_id}")
                continue
            current_seen.add(identity)
            expected_sha = current.entity_sha256[identity]
            if claimed_entity_sha != expected_sha:
                _add_once(blockers, "ROUTE_STATIC_STALE_ENTITY")
                _add_once(stale_artifacts, f"route:{artifact_id}")
        else:
            if kind != "finding" or identifier not in historical_finding_ids:
                _add_once(blockers, "ROUTE_STATIC_ORPHAN_HISTORICAL_ENTRY")
                _add_once(orphan_artifacts, f"route:{artifact_id}")
                continue
            historical_seen.add(identifier)
            old_row = old.findings.get(identifier)
            if old_row is None or claimed_entity_sha != _digest(old_row):
                _add_once(blockers, "ROUTE_STATIC_STALE_HISTORICAL_ENTITY")
                _add_once(stale_artifacts, f"route:{artifact_id}")

    for kind in _ENTITY_KINDS:
        for identifier in sorted(expected[kind]):
            if (kind, identifier) not in current_seen:
                _add_once(blockers, "ROUTE_STATIC_PARTIAL")
                _add_once(missing_artifacts, f"route:{kind}:{identifier}")
    return fingerprint


def _receipt_digest(receipt: CorrectionPropagationReceipt) -> str:
    payload = asdict(replace(receipt, receipt_sha256=""))
    return _digest(payload)


def check_correction_propagation(
    *,
    old_projection: Mapping[str, Any],
    new_projection: Mapping[str, Any],
    search_index: Mapping[str, Any] | None,
    linked_data_receipt: Mapping[str, Any] | None,
    route_static_manifest: Mapping[str, Any] | None,
) -> CorrectionPropagationReceipt:
    """Check whether derived public artifacts consistently reflect one new projection.

    The checker is pure and creates no publication authority. Removed finding-version IDs
    are retained in the receipt as historical identifiers, while search/current route
    entries may reference only the new projection's current identifiers. Historical route
    entries are optional, but when present they must be explicitly marked HISTORICAL and be
    regenerated under the same new projection fingerprint.
    """

    old = _projection_state(_mapping(old_projection, "OLD_PUBLIC_PROJECTION_INVALID"))
    current = _projection_state(_mapping(new_projection, "NEW_PUBLIC_PROJECTION_INVALID"))

    affected_findings = _changed_ids(old.findings, current.findings)
    affected_contents = _changed_ids(old.contents, current.contents)
    affected_people = _changed_ids(old.people, current.people)
    affected_topics = _changed_ids(old.topics, current.topics)

    old_related = _finding_related_ids(old, affected_findings)
    new_related = _finding_related_ids(current, affected_findings)
    affected_people.update(old_related[0] | new_related[0])
    affected_contents.update(old_related[1] | new_related[1])
    affected_topics.update(old_related[2] | new_related[2])

    current_finding_ids = set(current.findings)
    explicit_superseded_ids = {
        str((dossier.get("finding") or {}).get("supersedes_id"))
        for dossier in current.findings.values()
        if isinstance(dossier.get("finding"), Mapping)
        and (dossier.get("finding") or {}).get("supersedes_id")
    }
    historical_finding_ids = (
        (set(old.findings) - current_finding_ids) | explicit_superseded_ids
    ) - current_finding_ids

    blockers: list[str] = []
    stale_artifacts: list[str] = []
    orphan_artifacts: list[str] = []
    missing_artifacts: list[str] = []
    observed_fingerprints: set[str] = set()

    for finding_id in sorted(set(old.findings) & set(current.findings)):
        if _digest(old.findings[finding_id]) != _digest(current.findings[finding_id]):
            _add_once(blockers, "FINDING_VERSION_MUTATED_IN_PLACE")
            _add_once(stale_artifacts, f"finding-version:{finding_id}")
    for finding_id in sorted(explicit_superseded_ids & current_finding_ids):
        _add_once(blockers, "SUPERSEDED_FINDING_STILL_CURRENT")
        _add_once(stale_artifacts, f"finding-current:{finding_id}")

    if (affected_findings or affected_contents or affected_people or affected_topics) and (
        old.fingerprint == current.fingerprint
    ):
        _add_once(blockers, "CHANGED_PROJECTION_REUSED_FINGERPRINT")

    if search_index is None:
        _add_once(blockers, "DERIVED_ARTIFACT_MISSING:search-index")
        _add_once(missing_artifacts, "search-index")
    else:
        search_fp = _check_search_index(
            _mapping(search_index, "CORRECTION_PROPAGATION_SEARCH_INDEX_INVALID"),
            current=current,
            blockers=blockers,
            stale_artifacts=stale_artifacts,
            orphan_artifacts=orphan_artifacts,
            missing_artifacts=missing_artifacts,
        )
        if search_fp is not None:
            observed_fingerprints.add(search_fp)

    if linked_data_receipt is None:
        _add_once(blockers, "DERIVED_ARTIFACT_MISSING:linked-data")
        _add_once(missing_artifacts, "linked-data")
    else:
        linked = _mapping(
            linked_data_receipt,
            "CORRECTION_PROPAGATION_LINKED_DATA_RECEIPT_INVALID",
        )
        linked_fp = _artifact_fingerprint(
            linked.get("projection_fingerprint"),
            artifact="linked-data",
            blockers=blockers,
            stale_artifacts=stale_artifacts,
        )
        if linked_fp is not None:
            observed_fingerprints.add(linked_fp)

    if route_static_manifest is None:
        _add_once(blockers, "DERIVED_ARTIFACT_MISSING:route-static")
        _add_once(missing_artifacts, "route-static")
    else:
        route_fp = _check_route_static_manifest(
            _mapping(
                route_static_manifest,
                "CORRECTION_PROPAGATION_ROUTE_STATIC_MANIFEST_INVALID",
            ),
            old=old,
            current=current,
            historical_finding_ids=historical_finding_ids,
            blockers=blockers,
            stale_artifacts=stale_artifacts,
            orphan_artifacts=orphan_artifacts,
            missing_artifacts=missing_artifacts,
            observed_fingerprints=observed_fingerprints,
        )
        if route_fp is not None:
            observed_fingerprints.add(route_fp)

    if observed_fingerprints != {current.fingerprint}:
        _add_once(blockers, "MIXED_OR_STALE_PROJECTION_FINGERPRINT")
    if len(observed_fingerprints) > 1:
        _add_once(blockers, "MULTIPLE_DERIVED_PROJECTION_FINGERPRINTS")

    receipt = CorrectionPropagationReceipt(
        status="CONSISTENT" if not blockers else "HOLD",
        old_projection_fingerprint=old.fingerprint,
        new_projection_fingerprint=current.fingerprint,
        observed_projection_fingerprints=tuple(sorted(observed_fingerprints)),
        affected_finding_ids=tuple(sorted(affected_findings)),
        affected_content_ids=tuple(sorted(affected_contents)),
        affected_person_ids=tuple(sorted(affected_people)),
        affected_topic_ids=tuple(sorted(affected_topics)),
        current_finding_ids=tuple(sorted(current_finding_ids)),
        historical_finding_ids=tuple(sorted(historical_finding_ids)),
        stale_artifacts=tuple(sorted(stale_artifacts)),
        orphan_artifacts=tuple(sorted(orphan_artifacts)),
        missing_artifacts=tuple(sorted(missing_artifacts)),
        blockers=tuple(blockers),
    )
    return replace(receipt, receipt_sha256=_receipt_digest(receipt))


__all__ = [
    "CORRECTION_PROPAGATION_VERSION",
    "ROUTE_STATIC_MANIFEST_VERSION",
    "CorrectionPropagationReceipt",
    "ProjectionState",
    "check_correction_propagation",
]
