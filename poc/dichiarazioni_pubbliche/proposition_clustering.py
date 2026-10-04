from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


CLUSTER_VERSION = "proposition-cluster-v1"
DERIVATION_VERSION = "content-derivation-v1"

MATCH_CLASSES = frozenset(
    {"DUPLICATE_EXTRACTION", "SAME_PROPOSITION", "RELATED", "DIFFERENT", "UNCERTAIN"}
)
CLUSTER_METHODS = frozenset(
    {"EXACT_NORMALIZED", "SOURCE_SELECTOR_OVERLAP", "LEXICAL_TRIGRAM", "MANUAL_REVIEW", "MODEL_SUGGESTION"}
)
REVIEW_STATUSES = frozenset({"CANDIDATE", "APPROVED", "REJECTED", "SUPERSEDED"})
DERIVATION_RELATIONS = frozenset(
    {"REPUBLICATION", "SYNDICATION", "QUOTATION", "PRESS_RELEASE_DERIVED", "UNKNOWN_DERIVATION"}
)
DERIVATION_METHODS = frozenset(
    {"EXACT_BODY_HASH", "EXPLICIT_SOURCE_CREDIT", "LEXICAL_OVERLAP", "MANUAL_REVIEW", "MODEL_SUGGESTION"}
)

_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", re.UNICODE)


def _required(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"CLUSTER_{field_name.upper()}_REQUIRED")
    return value.strip()


def _features(value: Sequence[Mapping[str, Any]] | None, field_name: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"CLUSTER_{field_name.upper()}_INVALID")
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping) or not str(item.get("code") or "").strip():
            raise ValueError(f"CLUSTER_{field_name.upper()}_ITEM_INVALID")
        out.append(dict(item))
    return tuple(out)


def normalize_proposition(text: str) -> str:
    text = unicodedata.normalize("NFKC", _required(text, "proposition")).casefold()
    return " ".join(_TOKEN.findall(text))


def token_jaccard(left: str, right: str) -> float:
    a = set(normalize_proposition(left).split())
    b = set(normalize_proposition(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def deterministic_id(prefix: str, *parts: str) -> str:
    material = "\x1f".join(_required(part, "id_part") for part in parts)
    return _required(prefix, "id_prefix") + ":" + hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True)
class PropositionInput:
    member_type: str
    member_id: str
    content_id: str
    normalized_text: str
    provenance_key: str | None = None
    entity_keys: tuple[str, ...] = ()
    topic_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.member_type not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}:
            raise ValueError("CLUSTER_MEMBER_TYPE_INVALID")
        for name in ("member_id", "content_id", "normalized_text"):
            _required(getattr(self, name), name)


@dataclass(frozen=True)
class PropositionMatch:
    match_class: str
    method: str
    lexical_score: float
    supporting_features: tuple[dict[str, Any], ...]
    contradicting_features: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.match_class not in MATCH_CLASSES:
            raise ValueError("CLUSTER_MATCH_CLASS_INVALID")
        if self.method not in CLUSTER_METHODS:
            raise ValueError("CLUSTER_METHOD_INVALID")
        if not 0 <= self.lexical_score <= 1:
            raise ValueError("CLUSTER_LEXICAL_SCORE_INVALID")


def classify_proposition_pair(left: PropositionInput, right: PropositionInput) -> PropositionMatch:
    if left.member_type == right.member_type and left.member_id == right.member_id:
        raise ValueError("CLUSTER_SELF_MATCH_REFUSED")

    left_norm = normalize_proposition(left.normalized_text)
    right_norm = normalize_proposition(right.normalized_text)
    score = token_jaccard(left.normalized_text, right.normalized_text)
    same_selector = bool(
        left.content_id == right.content_id
        and left.provenance_key
        and right.provenance_key
        and left.provenance_key == right.provenance_key
    )
    shared_entities = sorted(set(left.entity_keys) & set(right.entity_keys))
    shared_topics = sorted(set(left.topic_keys) & set(right.topic_keys))

    if same_selector and left_norm == right_norm:
        return PropositionMatch(
            "DUPLICATE_EXTRACTION",
            "SOURCE_SELECTOR_OVERLAP",
            1.0,
            ({"code": "SAME_CONTENT_SELECTOR"}, {"code": "EXACT_NORMALIZED_TEXT"}),
        )
    if left_norm == right_norm:
        return PropositionMatch(
            "SAME_PROPOSITION", "EXACT_NORMALIZED", 1.0,
            ({"code": "EXACT_NORMALIZED_TEXT"},),
        )
    if score >= 0.82 and (shared_entities or shared_topics):
        features = [{"code": "HIGH_LEXICAL_OVERLAP", "score": round(score, 6)}]
        if shared_entities:
            features.append({"code": "SHARED_ENTITIES", "values": shared_entities})
        if shared_topics:
            features.append({"code": "SHARED_TOPICS", "values": shared_topics})
        return PropositionMatch("SAME_PROPOSITION", "LEXICAL_TRIGRAM", score, tuple(features))
    if score >= 0.45 or shared_entities or shared_topics:
        features = [{"code": "RELATED_LEXICAL_OR_ENTITY_CONTEXT", "score": round(score, 6)}]
        return PropositionMatch("RELATED", "LEXICAL_TRIGRAM", score, tuple(features))
    if score <= 0.2 and not shared_entities and not shared_topics:
        return PropositionMatch(
            "DIFFERENT", "LEXICAL_TRIGRAM", score, (),
            ({"code": "LOW_LEXICAL_NO_SHARED_CONTEXT", "score": round(score, 6)},),
        )
    return PropositionMatch(
        "UNCERTAIN", "LEXICAL_TRIGRAM", score,
        ({"code": "AMBIGUOUS_LEXICAL_OVERLAP", "score": round(score, 6)},),
    )


@dataclass(frozen=True)
class PropositionClusterRecord:
    id: str
    representative_text: str
    cluster_method: str
    status: str = "CANDIDATE"
    cluster_version: str = CLUSTER_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.id, "cluster_id")
        _required(self.representative_text, "representative_text")
        if self.cluster_method not in CLUSTER_METHODS:
            raise ValueError("CLUSTER_METHOD_INVALID")
        if self.cluster_version != CLUSTER_VERSION:
            raise ValueError("CLUSTER_VERSION_MISMATCH")
        if self.status not in REVIEW_STATUSES:
            raise ValueError("CLUSTER_STATUS_INVALID")

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class PropositionClusterMemberRecord:
    id: str
    cluster_id: str
    member_type: str
    member_id: str
    match_class: str
    membership_method: str
    lexical_score: float | None = None
    supporting_features: tuple[dict[str, Any], ...] = ()
    contradicting_features: tuple[dict[str, Any], ...] = ()
    status: str = "CANDIDATE"
    membership_version: str = CLUSTER_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "cluster_id", "member_id"):
            _required(getattr(self, name), name)
        if self.member_type not in {"CLAIM_CANDIDATE", "ATOMIC_CLAIM"}:
            raise ValueError("CLUSTER_MEMBER_TYPE_INVALID")
        if self.match_class not in MATCH_CLASSES:
            raise ValueError("CLUSTER_MATCH_CLASS_INVALID")
        if self.membership_method not in CLUSTER_METHODS:
            raise ValueError("CLUSTER_METHOD_INVALID")
        if self.membership_version != CLUSTER_VERSION:
            raise ValueError("CLUSTER_VERSION_MISMATCH")
        if self.status not in REVIEW_STATUSES:
            raise ValueError("CLUSTER_STATUS_INVALID")
        if self.lexical_score is not None and not 0 <= self.lexical_score <= 1:
            raise ValueError("CLUSTER_LEXICAL_SCORE_INVALID")
        _features(self.supporting_features, "supporting_features")
        _features(self.contradicting_features, "contradicting_features")

    def target_columns(self) -> dict[str, str | None]:
        return {
            "claim_candidate_id": self.member_id if self.member_type == "CLAIM_CANDIDATE" else None,
            "atomic_claim_id": self.member_id if self.member_type == "ATOMIC_CLAIM" else None,
        }

    def to_dict(self) -> dict[str, Any]:
        data=asdict(self); data["supporting_features"]=list(self.supporting_features); data["contradicting_features"]=list(self.contradicting_features)
        data.update(self.target_columns()); data.pop("member_id"); return data


@dataclass(frozen=True)
class ContentDerivationFamilyRecord:
    id: str
    root_content_id: str
    status: str = "CANDIDATE"
    family_version: str = DERIVATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.id, "family_id"); _required(self.root_content_id, "root_content_id")
        if self.family_version != DERIVATION_VERSION: raise ValueError("DERIVATION_VERSION_MISMATCH")
        if self.status not in REVIEW_STATUSES: raise ValueError("DERIVATION_STATUS_INVALID")

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class ContentDerivationCandidateRecord:
    id: str
    family_id: str
    derived_content_id: str
    origin_content_id: str
    relation_type: str
    derivation_method: str
    supporting_features: tuple[dict[str, Any], ...] = ()
    contradicting_features: tuple[dict[str, Any], ...] = ()
    lexical_score: float | None = None
    status: str = "CANDIDATE"
    derivation_version: str = DERIVATION_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "family_id", "derived_content_id", "origin_content_id"):
            _required(getattr(self,name), name)
        if self.derived_content_id == self.origin_content_id: raise ValueError("DERIVATION_SELF_REFUSED")
        if self.relation_type not in DERIVATION_RELATIONS: raise ValueError("DERIVATION_RELATION_INVALID")
        if self.derivation_method not in DERIVATION_METHODS: raise ValueError("DERIVATION_METHOD_INVALID")
        if self.derivation_version != DERIVATION_VERSION: raise ValueError("DERIVATION_VERSION_MISMATCH")
        if self.status not in REVIEW_STATUSES: raise ValueError("DERIVATION_STATUS_INVALID")
        if self.lexical_score is not None and not 0 <= self.lexical_score <= 1: raise ValueError("DERIVATION_SCORE_INVALID")
        _features(self.supporting_features,"supporting_features"); _features(self.contradicting_features,"contradicting_features")

    def to_dict(self) -> dict[str, Any]:
        data=asdict(self); data["supporting_features"]=list(self.supporting_features); data["contradicting_features"]=list(self.contradicting_features); return data


@dataclass(frozen=True)
class IndependenceGroupProposal:
    family_id: str
    proposed_group: str
    content_ids: tuple[str, ...]
    rationale: str = "APPROVED_DERIVATION_FAMILY"


def make_cluster(representative_text: str, method: str) -> PropositionClusterRecord:
    norm=normalize_proposition(representative_text)
    return PropositionClusterRecord(
        id=deterministic_id("proposition-cluster", CLUSTER_VERSION, norm),
        representative_text=representative_text.strip(), cluster_method=method,
    )


def make_cluster_member(cluster: PropositionClusterRecord, member: PropositionInput, match: PropositionMatch) -> PropositionClusterMemberRecord:
    return PropositionClusterMemberRecord(
        id=deterministic_id("cluster-member", cluster.id, member.member_type, member.member_id, CLUSTER_VERSION),
        cluster_id=cluster.id, member_type=member.member_type, member_id=member.member_id,
        match_class=match.match_class, membership_method=match.method, lexical_score=match.lexical_score,
        supporting_features=match.supporting_features, contradicting_features=match.contradicting_features,
    )


def make_derivation_family(root_content_id: str) -> ContentDerivationFamilyRecord:
    return ContentDerivationFamilyRecord(
        id=deterministic_id("derivation-family", DERIVATION_VERSION, root_content_id), root_content_id=root_content_id
    )


def make_derivation_candidate(*, family: ContentDerivationFamilyRecord, derived_content_id: str, origin_content_id: str,
                              relation_type: str, method: str, supporting_features: Sequence[Mapping[str,Any]]=(),
                              contradicting_features: Sequence[Mapping[str,Any]]=(), lexical_score: float | None=None) -> ContentDerivationCandidateRecord:
    return ContentDerivationCandidateRecord(
        id=deterministic_id("derivation-candidate", family.id, derived_content_id, origin_content_id, relation_type, DERIVATION_VERSION),
        family_id=family.id, derived_content_id=derived_content_id, origin_content_id=origin_content_id,
        relation_type=relation_type, derivation_method=method,
        supporting_features=_features(supporting_features,"supporting_features"),
        contradicting_features=_features(contradicting_features,"contradicting_features"), lexical_score=lexical_score,
    )


def detect_exact_body_derivation(*, family: ContentDerivationFamilyRecord, derived_content_id: str,
                                 origin_content_id: str, derived_sha256: str | None, origin_sha256: str | None) -> ContentDerivationCandidateRecord | None:
    if not derived_sha256 or not origin_sha256 or derived_sha256 != origin_sha256:
        return None
    return make_derivation_candidate(
        family=family, derived_content_id=derived_content_id, origin_content_id=origin_content_id,
        relation_type="REPUBLICATION", method="EXACT_BODY_HASH",
        supporting_features=({"code":"EXACT_BODY_SHA256","sha256":derived_sha256},), lexical_score=1.0,
    )


def propose_evidence_independence_group(family: ContentDerivationFamilyRecord,
                                        edges: Sequence[ContentDerivationCandidateRecord]) -> IndependenceGroupProposal | None:
    if family.status != "APPROVED":
        return None
    approved=[e for e in edges if e.family_id == family.id and e.status == "APPROVED"]
    if not approved:
        return None
    ids={family.root_content_id}
    for edge in approved:
        ids.add(edge.origin_content_id); ids.add(edge.derived_content_id)
    return IndependenceGroupProposal(
        family_id=family.id, proposed_group="derivation:"+family.id, content_ids=tuple(sorted(ids))
    )


INSERT_PROPOSITION_CLUSTER_SQL_V1 = """
WITH inserted AS (
 INSERT INTO proposition_cluster (id,representative_text,cluster_method,cluster_version,status,metadata)
 VALUES (:'id',:'representative_text',:'cluster_method',:'cluster_version',:'status',:'metadata'::jsonb)
 ON CONFLICT (id) DO NOTHING RETURNING id
), existing AS (
 SELECT id FROM proposition_cluster WHERE id=:'id' AND representative_text=:'representative_text'
  AND cluster_method=:'cluster_method' AND cluster_version=:'cluster_version' AND status=:'status' AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED' WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_CLUSTER_MEMBER_SQL_V1 = """
WITH inserted AS (
 INSERT INTO proposition_cluster_member (
  id,cluster_id,member_type,claim_candidate_id,atomic_claim_id,match_class,membership_method,membership_version,
  supporting_features,contradicting_features,lexical_score,status,metadata
 ) VALUES (
  :'id',:'cluster_id',:'member_type',NULLIF(:'claim_candidate_id',''),NULLIF(:'atomic_claim_id',''),:'match_class',
  :'membership_method',:'membership_version',:'supporting_features'::jsonb,:'contradicting_features'::jsonb,
  NULLIF(:'lexical_score','')::numeric,:'status',:'metadata'::jsonb
 ) ON CONFLICT (id) DO NOTHING RETURNING id
), existing AS (
 SELECT id FROM proposition_cluster_member WHERE id=:'id' AND cluster_id=:'cluster_id' AND member_type=:'member_type'
  AND claim_candidate_id IS NOT DISTINCT FROM NULLIF(:'claim_candidate_id','')
  AND atomic_claim_id IS NOT DISTINCT FROM NULLIF(:'atomic_claim_id','')
  AND match_class=:'match_class' AND membership_method=:'membership_method' AND membership_version=:'membership_version'
  AND supporting_features=:'supporting_features'::jsonb AND contradicting_features=:'contradicting_features'::jsonb
  AND lexical_score IS NOT DISTINCT FROM NULLIF(:'lexical_score','')::numeric AND status=:'status' AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED' WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_DERIVATION_FAMILY_SQL_V1 = """
WITH inserted AS (
 INSERT INTO content_derivation_family (id,root_content_id,family_version,status,metadata)
 VALUES (:'id',:'root_content_id',:'family_version',:'status',:'metadata'::jsonb)
 ON CONFLICT (id) DO NOTHING RETURNING id
), existing AS (
 SELECT id FROM content_derivation_family WHERE id=:'id' AND root_content_id=:'root_content_id'
  AND family_version=:'family_version' AND status=:'status' AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED' WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()

INSERT_DERIVATION_CANDIDATE_SQL_V1 = """
WITH inserted AS (
 INSERT INTO content_derivation_candidate (
  id,family_id,derived_content_id,origin_content_id,relation_type,derivation_method,derivation_version,
  supporting_features,contradicting_features,lexical_score,status,metadata
 ) VALUES (
  :'id',:'family_id',:'derived_content_id',:'origin_content_id',:'relation_type',:'derivation_method',:'derivation_version',
  :'supporting_features'::jsonb,:'contradicting_features'::jsonb,NULLIF(:'lexical_score','')::numeric,:'status',:'metadata'::jsonb
 ) ON CONFLICT (id) DO NOTHING RETURNING id
), existing AS (
 SELECT id FROM content_derivation_candidate WHERE id=:'id' AND family_id=:'family_id'
  AND derived_content_id=:'derived_content_id' AND origin_content_id=:'origin_content_id'
  AND relation_type=:'relation_type' AND derivation_method=:'derivation_method' AND derivation_version=:'derivation_version'
  AND supporting_features=:'supporting_features'::jsonb AND contradicting_features=:'contradicting_features'::jsonb
  AND lexical_score IS NOT DISTINCT FROM NULLIF(:'lexical_score','')::numeric AND status=:'status' AND metadata=:'metadata'::jsonb
)
SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED' WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING' ELSE 'CONFLICT' END;
""".strip()


def _approval_sql(table: str, entity_type: str) -> str:
    return f"""
WITH current AS (SELECT id,status FROM {table} WHERE id=:'entity_id' FOR UPDATE),
review_insert AS (
 INSERT INTO review_event (id,entity_type,entity_id,action,actor_ref,reason,metadata)
 SELECT :'event_id','{entity_type}',id,'APPROVED',:'actor_ref',NULLIF(:'reason',''),:'review_metadata'::jsonb
 FROM current WHERE status IN ('CANDIDATE','APPROVED')
 ON CONFLICT (id) DO NOTHING RETURNING entity_id
), review_ok AS (
 SELECT entity_id FROM review_insert UNION ALL
 SELECT entity_id FROM review_event WHERE id=:'event_id' AND entity_type='{entity_type}' AND entity_id=:'entity_id' AND action='APPROVED'
), updated AS (
 UPDATE {table} SET status='APPROVED' WHERE id=:'entity_id' AND status IN ('CANDIDATE','APPROVED')
  AND EXISTS(SELECT 1 FROM review_ok) RETURNING id
)
SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM current) THEN 'NOT_FOUND'
 WHEN EXISTS(SELECT 1 FROM updated) THEN 'APPROVED' ELSE 'CONFLICT' END;
""".strip()

APPROVE_PROPOSITION_CLUSTER_SQL_V1=_approval_sql("proposition_cluster","PROPOSITION_CLUSTER")
APPROVE_CLUSTER_MEMBER_SQL_V1=_approval_sql("proposition_cluster_member","PROPOSITION_CLUSTER_MEMBER")
APPROVE_DERIVATION_FAMILY_SQL_V1=_approval_sql("content_derivation_family","CONTENT_DERIVATION_FAMILY")
APPROVE_DERIVATION_CANDIDATE_SQL_V1=_approval_sql("content_derivation_candidate","CONTENT_DERIVATION_CANDIDATE")


def record_to_params(record: Any) -> dict[str,str]:
    if not hasattr(record,"to_dict"): raise ValueError("CLUSTER_RECORD_INVALID")
    out={}
    for key,value in record.to_dict().items():
        if value is None: out[key]=""
        elif isinstance(value,(dict,list,tuple)): out[key]=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        else: out[key]=str(value)
    return out


__all__=[
 "APPROVE_CLUSTER_MEMBER_SQL_V1","APPROVE_DERIVATION_CANDIDATE_SQL_V1","APPROVE_DERIVATION_FAMILY_SQL_V1",
 "APPROVE_PROPOSITION_CLUSTER_SQL_V1","CLUSTER_VERSION","ContentDerivationCandidateRecord","ContentDerivationFamilyRecord",
 "DERIVATION_VERSION","INSERT_CLUSTER_MEMBER_SQL_V1","INSERT_DERIVATION_CANDIDATE_SQL_V1","INSERT_DERIVATION_FAMILY_SQL_V1",
 "INSERT_PROPOSITION_CLUSTER_SQL_V1","IndependenceGroupProposal","PropositionClusterMemberRecord","PropositionClusterRecord",
 "PropositionInput","PropositionMatch","classify_proposition_pair","detect_exact_body_derivation","make_cluster","make_cluster_member",
 "make_derivation_candidate","make_derivation_family","normalize_proposition","propose_evidence_independence_group","record_to_params","token_jaccard"
]
