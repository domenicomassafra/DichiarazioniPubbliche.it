from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence


KNOWLEDGE_ENTITY_VERSION = "knowledge-entity-v1"
ENTITY_IDENTIFIER_VERSION = "entity-identifier-v1"
ENTITY_RESOLUTION_VERSION = "entity-resolution-v1"

ENTITY_TYPES = frozenset({"PERSON", "ORGANIZATION", "TOPIC", "EVENT"})
RESOLUTION_METHODS = frozenset(
    {"EXACT_IDENTIFIER", "KNOWN_ALIAS", "CONTEXT_MATCH", "MODEL_SUGGESTION", "MANUAL_REVIEW"}
)
RESOLUTION_STATUSES = frozenset({"CANDIDATE", "APPROVED", "REJECTED", "SUPERSEDED"})
ENTITY_STATUSES = frozenset({"ACTIVE", "SUPERSEDED"})
ALIAS_TYPES = frozenset({"NAME", "ACRONYM", "HISTORICAL_NAME", "SEARCH"})


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"KNOWLEDGE_{field_name.upper()}_REQUIRED")
    return value.strip()


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"KNOWLEDGE_{field_name.upper()}_INVALID")
    value = value.strip()
    return value or None


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"KNOWLEDGE_{field_name.upper()}_INVALID")
    return dict(value)


def _feature_tuple(value: Any, field_name: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"KNOWLEDGE_{field_name.upper()}_INVALID")
    out: list[dict[str, Any]] = []
    for feature in value:
        if not isinstance(feature, Mapping):
            raise ValueError(f"KNOWLEDGE_{field_name.upper()}_ITEM_INVALID")
        item = dict(feature)
        code = item.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"KNOWLEDGE_{field_name.upper()}_CODE_REQUIRED")
        out.append(item)
    return tuple(out)


def _sha256(value: Any, field_name: str) -> str:
    value = _required_str(value, field_name).lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"KNOWLEDGE_{field_name.upper()}_INVALID_SHA256")
    return value


def normalized_alias(value: str) -> str:
    text = _required_str(value, "alias")
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def deterministic_knowledge_id(prefix: str, *parts: str) -> str:
    prefix = _required_str(prefix, "id_prefix")
    material = "\x1f".join(_required_str(part, "id_part") for part in parts)
    return f"{prefix}:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TopicRecord:
    id: str
    slug: str
    canonical_name: str
    scope_text: str
    entity_version: str = KNOWLEDGE_ENTITY_VERSION
    status: str = "ACTIVE"
    supersedes_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "slug", "canonical_name", "scope_text"):
            _required_str(getattr(self, name), name)
        if self.entity_version != KNOWLEDGE_ENTITY_VERSION:
            raise ValueError("KNOWLEDGE_ENTITY_VERSION_MISMATCH")
        if self.status not in ENTITY_STATUSES:
            raise ValueError("KNOWLEDGE_ENTITY_STATUS_INVALID")
        if self.supersedes_id == self.id:
            raise ValueError("KNOWLEDGE_SELF_SUPERSESSION_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("KNOWLEDGE_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventRecord:
    id: str
    slug: str
    canonical_name: str
    scope_text: str
    start_at: str | None = None
    end_at: str | None = None
    entity_version: str = KNOWLEDGE_ENTITY_VERSION
    status: str = "ACTIVE"
    supersedes_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "slug", "canonical_name", "scope_text"):
            _required_str(getattr(self, name), name)
        if self.entity_version != KNOWLEDGE_ENTITY_VERSION:
            raise ValueError("KNOWLEDGE_ENTITY_VERSION_MISMATCH")
        if self.status not in ENTITY_STATUSES:
            raise ValueError("KNOWLEDGE_ENTITY_STATUS_INVALID")
        if self.supersedes_id == self.id:
            raise ValueError("KNOWLEDGE_SELF_SUPERSESSION_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("KNOWLEDGE_METADATA_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityIdentifierRecord:
    id: str
    entity_type: str
    entity_id: str
    identifier_kind: str
    identifier_value: str
    authority: str
    source_ref: dict[str, Any]
    identifier_version: str = ENTITY_IDENTIFIER_VERSION
    status: str = "ACTIVE"
    supersedes_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "entity_id", "identifier_kind", "identifier_value", "authority"):
            _required_str(getattr(self, name), name)
        if self.entity_type not in ENTITY_TYPES:
            raise ValueError("KNOWLEDGE_ENTITY_TYPE_INVALID")
        if self.identifier_version != ENTITY_IDENTIFIER_VERSION:
            raise ValueError("KNOWLEDGE_IDENTIFIER_VERSION_MISMATCH")
        if self.status not in ENTITY_STATUSES:
            raise ValueError("KNOWLEDGE_IDENTIFIER_STATUS_INVALID")
        if self.supersedes_id == self.id:
            raise ValueError("KNOWLEDGE_SELF_SUPERSESSION_INVALID")
        if not isinstance(self.source_ref, Mapping) or not self.source_ref:
            raise ValueError("KNOWLEDGE_IDENTIFIER_SOURCE_REF_REQUIRED")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("KNOWLEDGE_METADATA_INVALID")

    def target_columns(self) -> dict[str, str | None]:
        return {
            "person_id": self.entity_id if self.entity_type == "PERSON" else None,
            "organization_id": self.entity_id if self.entity_type == "ORGANIZATION" else None,
            "topic_id": self.entity_id if self.entity_type == "TOPIC" else None,
            "event_id": self.entity_id if self.entity_type == "EVENT" else None,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.update(self.target_columns())
        data.pop("entity_id")
        return data


@dataclass(frozen=True)
class EntityResolutionCandidateRecord:
    id: str
    content_id: str
    mention_text: str
    mention_text_sha256: str
    entity_type: str
    target_id: str
    resolution_method: str
    supporting_features: tuple[dict[str, Any], ...] = ()
    contradicting_features: tuple[dict[str, Any], ...] = ()
    passage_id: str | None = None
    retrieval_score: float | None = None
    resolution_version: str = ENTITY_RESOLUTION_VERSION
    status: str = "CANDIDATE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "content_id", "mention_text", "target_id"):
            _required_str(getattr(self, name), name)
        _sha256(self.mention_text_sha256, "mention_text_sha256")
        if self.entity_type not in ENTITY_TYPES:
            raise ValueError("KNOWLEDGE_ENTITY_TYPE_INVALID")
        if self.resolution_method not in RESOLUTION_METHODS:
            raise ValueError("KNOWLEDGE_RESOLUTION_METHOD_INVALID")
        if self.resolution_version != ENTITY_RESOLUTION_VERSION:
            raise ValueError("KNOWLEDGE_RESOLUTION_VERSION_MISMATCH")
        if self.status not in RESOLUTION_STATUSES:
            raise ValueError("KNOWLEDGE_RESOLUTION_STATUS_INVALID")
        _feature_tuple(self.supporting_features, "supporting_features")
        _feature_tuple(self.contradicting_features, "contradicting_features")
        if self.retrieval_score is not None and not 0 <= float(self.retrieval_score) <= 1:
            raise ValueError("KNOWLEDGE_RETRIEVAL_SCORE_INVALID")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("KNOWLEDGE_METADATA_INVALID")

    def target_columns(self) -> dict[str, str | None]:
        return {
            "target_person_id": self.target_id if self.entity_type == "PERSON" else None,
            "target_organization_id": self.target_id if self.entity_type == "ORGANIZATION" else None,
            "target_topic_id": self.target_id if self.entity_type == "TOPIC" else None,
            "target_event_id": self.target_id if self.entity_type == "EVENT" else None,
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["supporting_features"] = list(self.supporting_features)
        data["contradicting_features"] = list(self.contradicting_features)
        data.update(self.target_columns())
        data.pop("target_id")
        return data


@dataclass(frozen=True)
class ResolutionDecision:
    decision: str
    entity_type: str | None = None
    entity_id: str | None = None
    matched_identifier_ids: tuple[str, ...] = ()
    reason: str = ""


def make_resolution_candidate(
    *,
    content_id: str,
    mention_text: str,
    entity_type: str,
    target_id: str,
    resolution_method: str,
    passage_id: str | None = None,
    supporting_features: Sequence[Mapping[str, Any]] = (),
    contradicting_features: Sequence[Mapping[str, Any]] = (),
    retrieval_score: float | None = None,
    metadata: Mapping[str, Any] | None = None,
    resolution_version: str = ENTITY_RESOLUTION_VERSION,
) -> EntityResolutionCandidateRecord:
    clean_mention = _required_str(mention_text, "mention_text")
    if entity_type not in ENTITY_TYPES:
        raise ValueError("KNOWLEDGE_ENTITY_TYPE_INVALID")
    if resolution_method not in RESOLUTION_METHODS:
        raise ValueError("KNOWLEDGE_RESOLUTION_METHOD_INVALID")
    if resolution_version != ENTITY_RESOLUTION_VERSION:
        raise ValueError("KNOWLEDGE_RESOLUTION_VERSION_MISMATCH")
    mention_hash = hashlib.sha256(clean_mention.encode("utf-8")).hexdigest()
    candidate_id = deterministic_knowledge_id(
        "entity-resolution",
        content_id,
        passage_id or "NO_PASSAGE",
        mention_hash,
        entity_type,
        target_id,
        resolution_method,
        resolution_version,
    )
    return EntityResolutionCandidateRecord(
        id=candidate_id,
        content_id=content_id,
        passage_id=passage_id,
        mention_text=clean_mention,
        mention_text_sha256=mention_hash,
        entity_type=entity_type,
        target_id=target_id,
        resolution_method=resolution_method,
        supporting_features=_feature_tuple(supporting_features, "supporting_features"),
        contradicting_features=_feature_tuple(contradicting_features, "contradicting_features"),
        retrieval_score=retrieval_score,
        resolution_version=resolution_version,
        metadata=_mapping(metadata, "metadata"),
    )


def resolve_exact_identifier(
    *,
    entity_type: str,
    authority: str,
    identifier_kind: str,
    identifier_value: str,
    identifiers: Iterable[EntityIdentifierRecord],
) -> ResolutionDecision:
    if entity_type not in ENTITY_TYPES:
        raise ValueError("KNOWLEDGE_ENTITY_TYPE_INVALID")
    authority = _required_str(authority, "authority")
    identifier_kind = _required_str(identifier_kind, "identifier_kind")
    identifier_value = _required_str(identifier_value, "identifier_value")
    matches = [
        row
        for row in identifiers
        if row.status == "ACTIVE"
        and row.entity_type == entity_type
        and row.authority == authority
        and row.identifier_kind == identifier_kind
        and row.identifier_value == identifier_value
        and row.identifier_version == ENTITY_IDENTIFIER_VERSION
    ]
    if not matches:
        return ResolutionDecision(decision="NO_MATCH", reason="NO_ACTIVE_EXACT_IDENTIFIER")
    entity_ids = {row.entity_id for row in matches}
    if len(matches) != 1 or len(entity_ids) != 1:
        return ResolutionDecision(
            decision="AMBIGUOUS",
            matched_identifier_ids=tuple(sorted(row.id for row in matches)),
            reason="EXACT_IDENTIFIER_NOT_UNIQUE",
        )
    row = matches[0]
    return ResolutionDecision(
        decision="AUTO_LINK",
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        matched_identifier_ids=(row.id,),
        reason="ACTIVE_EXACT_IDENTIFIER_V1",
    )


def propose_alias_matches(
    *,
    mention_text: str,
    entity_type: str,
    entities: Sequence[Mapping[str, Any]],
) -> tuple[ResolutionDecision, ...]:
    """Return review candidates only. Alias/name matches never auto-link."""
    if entity_type not in ENTITY_TYPES:
        raise ValueError("KNOWLEDGE_ENTITY_TYPE_INVALID")
    needle = normalized_alias(mention_text)
    decisions: list[ResolutionDecision] = []
    for entity in entities:
        if str(entity.get("entity_type") or "") != entity_type:
            continue
        entity_id = str(entity.get("entity_id") or "").strip()
        canonical_name = str(entity.get("canonical_name") or "").strip()
        aliases = entity.get("aliases") or []
        if not entity_id or not isinstance(aliases, (list, tuple)):
            continue
        names = [canonical_name, *[str(a) for a in aliases]]
        if any(name.strip() and normalized_alias(name) == needle for name in names):
            decisions.append(
                ResolutionDecision(
                    decision="CANDIDATE",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    reason="KNOWN_ALIAS_REQUIRES_REVIEW",
                )
            )
    return tuple(sorted(decisions, key=lambda d: d.entity_id or ""))


def _strict_record(data: Any, cls: type):
    if isinstance(data, cls):
        return data
    if hasattr(data, "__dataclass_fields__") and not isinstance(data, type):
        data = asdict(data)
    if not isinstance(data, Mapping):
        raise ValueError(f"KNOWLEDGE_RECORD_INVALID_TYPE:{cls.__name__}")
    allowed = set(cls.__dataclass_fields__)
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"KNOWLEDGE_RECORD_UNKNOWN_FIELDS:{sorted(unknown)}")
    try:
        return cls(**dict(data))
    except TypeError as exc:
        raise ValueError(f"KNOWLEDGE_RECORD_MISSING_FIELDS:{exc}") from exc


def normalize_topic(data: Any) -> TopicRecord:
    return _strict_record(data, TopicRecord)


def normalize_event(data: Any) -> EventRecord:
    return _strict_record(data, EventRecord)


def normalize_identifier(data: Any) -> EntityIdentifierRecord:
    return _strict_record(data, EntityIdentifierRecord)


def normalize_resolution_candidate(data: Any) -> EntityResolutionCandidateRecord:
    if isinstance(data, Mapping):
        data = dict(data)
        for key in ("supporting_features", "contradicting_features"):
            if isinstance(data.get(key), list):
                data[key] = tuple(data[key])
    return _strict_record(data, EntityResolutionCandidateRecord)


INSERT_TOPIC_SQL_V1 = """
WITH inserted AS (
    INSERT INTO topic (id, slug, canonical_name, scope_text, entity_version, status, supersedes_id, metadata)
    VALUES (:'id', :'slug', :'canonical_name', :'scope_text', :'entity_version', :'status', NULLIF(:'supersedes_id',''), :'metadata'::jsonb)
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM topic
    WHERE id=:'id' AND slug=:'slug' AND canonical_name=:'canonical_name'
      AND scope_text=:'scope_text' AND entity_version=:'entity_version' AND status=:'status'
      AND supersedes_id IS NOT DISTINCT FROM NULLIF(:'supersedes_id','')
      AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_EVENT_SQL_V1 = """
WITH inserted AS (
    INSERT INTO event (id, slug, canonical_name, scope_text, start_at, end_at, entity_version, status, supersedes_id, metadata)
    VALUES (:'id', :'slug', :'canonical_name', :'scope_text', NULLIF(:'start_at','')::timestamptz,
            NULLIF(:'end_at','')::timestamptz, :'entity_version', :'status', NULLIF(:'supersedes_id',''), :'metadata'::jsonb)
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM event
    WHERE id=:'id' AND slug=:'slug' AND canonical_name=:'canonical_name'
      AND scope_text=:'scope_text' AND start_at IS NOT DISTINCT FROM NULLIF(:'start_at','')::timestamptz
      AND end_at IS NOT DISTINCT FROM NULLIF(:'end_at','')::timestamptz
      AND entity_version=:'entity_version' AND status=:'status'
      AND supersedes_id IS NOT DISTINCT FROM NULLIF(:'supersedes_id','') AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_ENTITY_IDENTIFIER_SQL_V1 = """
WITH inserted AS (
    INSERT INTO entity_identifier (
        id, entity_type, person_id, organization_id, topic_id, event_id,
        identifier_kind, identifier_value, authority, identifier_version,
        source_ref, status, supersedes_id, metadata
    ) VALUES (
        :'id', :'entity_type', NULLIF(:'person_id',''), NULLIF(:'organization_id',''),
        NULLIF(:'topic_id',''), NULLIF(:'event_id',''), :'identifier_kind', :'identifier_value',
        :'authority', :'identifier_version', :'source_ref'::jsonb, :'status',
        NULLIF(:'supersedes_id',''), :'metadata'::jsonb
    )
    ON CONFLICT DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM entity_identifier
    WHERE id=:'id' AND entity_type=:'entity_type'
      AND person_id IS NOT DISTINCT FROM NULLIF(:'person_id','')
      AND organization_id IS NOT DISTINCT FROM NULLIF(:'organization_id','')
      AND topic_id IS NOT DISTINCT FROM NULLIF(:'topic_id','')
      AND event_id IS NOT DISTINCT FROM NULLIF(:'event_id','')
      AND identifier_kind=:'identifier_kind' AND identifier_value=:'identifier_value'
      AND authority=:'authority' AND identifier_version=:'identifier_version'
      AND source_ref=:'source_ref'::jsonb AND status=:'status'
      AND supersedes_id IS NOT DISTINCT FROM NULLIF(:'supersedes_id','')
      AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_ENTITY_RESOLUTION_CANDIDATE_SQL_V1 = """
WITH inserted AS (
    INSERT INTO entity_resolution_candidate (
        id, content_id, passage_id, mention_text, mention_text_sha256, entity_type,
        target_person_id, target_organization_id, target_topic_id, target_event_id,
        resolution_method, resolution_version, supporting_features, contradicting_features,
        retrieval_score, status, metadata
    ) VALUES (
        :'id', :'content_id', NULLIF(:'passage_id',''), :'mention_text', :'mention_text_sha256', :'entity_type',
        NULLIF(:'target_person_id',''), NULLIF(:'target_organization_id',''), NULLIF(:'target_topic_id',''), NULLIF(:'target_event_id',''),
        :'resolution_method', :'resolution_version', :'supporting_features'::jsonb, :'contradicting_features'::jsonb,
        NULLIF(:'retrieval_score','')::numeric, :'status', :'metadata'::jsonb
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), existing AS (
    SELECT id FROM entity_resolution_candidate
    WHERE id=:'id' AND content_id=:'content_id'
      AND passage_id IS NOT DISTINCT FROM NULLIF(:'passage_id','')
      AND mention_text=:'mention_text' AND mention_text_sha256=:'mention_text_sha256'
      AND entity_type=:'entity_type'
      AND target_person_id IS NOT DISTINCT FROM NULLIF(:'target_person_id','')
      AND target_organization_id IS NOT DISTINCT FROM NULLIF(:'target_organization_id','')
      AND target_topic_id IS NOT DISTINCT FROM NULLIF(:'target_topic_id','')
      AND target_event_id IS NOT DISTINCT FROM NULLIF(:'target_event_id','')
      AND resolution_method=:'resolution_method' AND resolution_version=:'resolution_version'
      AND supporting_features=:'supporting_features'::jsonb
      AND contradicting_features=:'contradicting_features'::jsonb
      AND retrieval_score IS NOT DISTINCT FROM NULLIF(:'retrieval_score','')::numeric
      AND status=:'status' AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
            WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

EXACT_IDENTIFIER_LOOKUP_SQL_V1 = """
SELECT json_build_object(
    'id', id,
    'entity_type', entity_type,
    'entity_id', CASE entity_type
        WHEN 'PERSON' THEN person_id
        WHEN 'ORGANIZATION' THEN organization_id
        WHEN 'TOPIC' THEN topic_id
        WHEN 'EVENT' THEN event_id
    END,
    'identifier_version', identifier_version
)::text
FROM entity_identifier
WHERE status='ACTIVE'
  AND entity_type=:'entity_type'
  AND authority=:'authority'
  AND identifier_kind=:'identifier_kind'
  AND identifier_value=:'identifier_value'
ORDER BY id;
""".strip()

KNOWN_ALIAS_LOOKUP_SQL_V1 = """
WITH candidates AS (
    SELECT 'PERSON'::text AS entity_type, p.id AS entity_id, p.canonical_name AS canonical_name
      FROM person p WHERE lower(p.canonical_name)=lower(:'mention')
    UNION ALL
    SELECT 'PERSON', p.id, p.canonical_name FROM person p
      JOIN person_alias a ON a.person_id=p.id WHERE lower(a.alias)=lower(:'mention')
    UNION ALL
    SELECT 'ORGANIZATION', o.id, o.canonical_name FROM organization o WHERE lower(o.canonical_name)=lower(:'mention')
    UNION ALL
    SELECT 'ORGANIZATION', o.id, o.canonical_name FROM organization o
      JOIN organization_alias a ON a.organization_id=o.id WHERE lower(a.alias)=lower(:'mention')
    UNION ALL
    SELECT 'TOPIC', t.id, t.canonical_name FROM topic t WHERE t.status='ACTIVE' AND lower(t.canonical_name)=lower(:'mention')
    UNION ALL
    SELECT 'TOPIC', t.id, t.canonical_name FROM topic t
      JOIN topic_alias a ON a.topic_id=t.id WHERE t.status='ACTIVE' AND lower(a.alias)=lower(:'mention')
    UNION ALL
    SELECT 'EVENT', e.id, e.canonical_name FROM event e WHERE e.status='ACTIVE' AND lower(e.canonical_name)=lower(:'mention')
    UNION ALL
    SELECT 'EVENT', e.id, e.canonical_name FROM event e
      JOIN event_alias a ON a.event_id=e.id WHERE e.status='ACTIVE' AND lower(a.alias)=lower(:'mention')
)
SELECT DISTINCT entity_type, entity_id, canonical_name
FROM candidates
WHERE entity_type=:'entity_type'
ORDER BY entity_id;
""".strip()

APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1 = """
WITH candidate AS (
    SELECT id, status FROM entity_resolution_candidate WHERE id=:'candidate_id' FOR UPDATE
), review_insert AS (
    INSERT INTO review_event (id, entity_type, entity_id, action, actor_ref, reason, metadata)
    SELECT :'event_id', 'ENTITY_RESOLUTION_CANDIDATE', candidate.id, 'APPROVED', :'actor_ref', NULLIF(:'reason',''), :'review_metadata'::jsonb
    FROM candidate
    WHERE candidate.status IN ('CANDIDATE', 'APPROVED')
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), review_ok AS (
    SELECT id FROM review_insert
    UNION ALL
    SELECT review.id FROM review_event review
    WHERE review.id=:'event_id'
      AND review.entity_type='ENTITY_RESOLUTION_CANDIDATE'
      AND review.entity_id=:'candidate_id'
      AND review.action='APPROVED'
), updated AS (
    UPDATE entity_resolution_candidate target
    SET status='APPROVED'
    WHERE target.id=:'candidate_id'
      AND target.status IN ('CANDIDATE','APPROVED')
      AND EXISTS (SELECT 1 FROM review_ok)
    RETURNING target.id
)
SELECT CASE
    WHEN NOT EXISTS (SELECT 1 FROM candidate) THEN 'NOT_FOUND'
    WHEN EXISTS (SELECT 1 FROM updated) THEN 'APPROVED'
    ELSE 'CONFLICT'
END;
""".strip()

SUPERSEDE_TOPIC_SQL_V1 = """
WITH old AS (
    SELECT id FROM topic WHERE id=:'old_id' AND status='ACTIVE' FOR UPDATE
), inserted AS (
    INSERT INTO topic (id, slug, canonical_name, scope_text, entity_version, status, supersedes_id, metadata)
    SELECT :'new_id', :'slug', :'canonical_name', :'scope_text', :'entity_version', 'ACTIVE', old.id, :'metadata'::jsonb
    FROM old
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), marked AS (
    UPDATE topic SET status='SUPERSEDED', updated_at=now()
    WHERE id IN (SELECT id FROM old) AND EXISTS (SELECT 1 FROM inserted)
    RETURNING id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) AND EXISTS(SELECT 1 FROM marked)
            THEN 'SUPERSEDED' ELSE 'CONFLICT' END;
""".strip()

SUPERSEDE_EVENT_SQL_V1 = """
WITH old AS (
    SELECT id FROM event WHERE id=:'old_id' AND status='ACTIVE' FOR UPDATE
), inserted AS (
    INSERT INTO event (id, slug, canonical_name, scope_text, start_at, end_at, entity_version, status, supersedes_id, metadata)
    SELECT :'new_id', :'slug', :'canonical_name', :'scope_text', NULLIF(:'start_at','')::timestamptz,
           NULLIF(:'end_at','')::timestamptz, :'entity_version', 'ACTIVE', old.id, :'metadata'::jsonb
    FROM old
    ON CONFLICT (id) DO NOTHING
    RETURNING id
), marked AS (
    UPDATE event SET status='SUPERSEDED', updated_at=now()
    WHERE id IN (SELECT id FROM old) AND EXISTS (SELECT 1 FROM inserted)
    RETURNING id
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) AND EXISTS(SELECT 1 FROM marked)
            THEN 'SUPERSEDED' ELSE 'CONFLICT' END;
""".strip()


def record_to_params(record: Any) -> dict[str, str]:
    if not hasattr(record, "to_dict"):
        raise ValueError("KNOWLEDGE_RECORD_INVALID")
    data = record.to_dict()
    out: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            out[key] = ""
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        elif isinstance(value, (dict, list, tuple)):
            out[key] = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        else:
            out[key] = str(value)
    return out


__all__ = [
    "ALIAS_TYPES", "APPROVE_ENTITY_RESOLUTION_CANDIDATE_SQL_V1", "ENTITY_IDENTIFIER_VERSION",
    "ENTITY_RESOLUTION_VERSION", "ENTITY_TYPES", "EXACT_IDENTIFIER_LOOKUP_SQL_V1", "EventRecord",
    "EntityIdentifierRecord", "EntityResolutionCandidateRecord", "INSERT_ENTITY_IDENTIFIER_SQL_V1",
    "INSERT_ENTITY_RESOLUTION_CANDIDATE_SQL_V1", "INSERT_EVENT_SQL_V1", "INSERT_TOPIC_SQL_V1",
    "KNOWN_ALIAS_LOOKUP_SQL_V1", "KNOWLEDGE_ENTITY_VERSION", "RESOLUTION_METHODS", "ResolutionDecision",
    "SUPERSEDE_EVENT_SQL_V1", "SUPERSEDE_TOPIC_SQL_V1", "TopicRecord", "deterministic_knowledge_id",
    "make_resolution_candidate", "normalize_event", "normalize_identifier", "normalize_resolution_candidate",
    "normalize_topic", "normalized_alias", "propose_alias_matches", "record_to_params", "resolve_exact_identifier",
]
