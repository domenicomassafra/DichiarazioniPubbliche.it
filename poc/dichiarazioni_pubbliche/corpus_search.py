from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


SEARCH_CONTRACT_VERSION = "corpus-search-v1"
SEARCH_RESULT_KINDS = frozenset(
    {
        "CONTENT",
        "PASSAGE",
        "STATEMENT_CANDIDATE",
        "CLAIM_CANDIDATE",
        "ATOMIC_CLAIM",
        "PERSON",
        "ORGANIZATION",
        "TOPIC",
        "EVENT",
        "COLLECTION",
    }
)
CANDIDATE_STATUSES = frozenset(
    {"CANDIDATE", "APPROVED", "REJECTED", "HELD", "SUPERSEDED", "DUPLICATE", "PROMOTED"}
)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _aware_iso(value: str | None, field_name: str) -> str | None:
    value = _clean_optional(value)
    if value is None:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"SEARCH_{field_name.upper()}_INVALID_DATETIME") from exc
    if dt.tzinfo is None:
        raise ValueError(f"SEARCH_{field_name.upper()}_TIMEZONE_REQUIRED")
    return value


@dataclass(frozen=True)
class CorpusSearchRequest:
    query: str
    kinds: tuple[str, ...] = ()
    collection_id: str | None = None
    person_id: str | None = None
    topic_id: str | None = None
    event_id: str | None = None
    source_id: str | None = None
    content_id: str | None = None
    status: str | None = None
    claim_type: str | None = None
    check_worthy: bool | None = None
    from_at: str | None = None
    to_at: str | None = None
    limit: int = 20
    contract_version: str = SEARCH_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("SEARCH_QUERY_REQUIRED")
        if self.contract_version != SEARCH_CONTRACT_VERSION:
            raise ValueError("SEARCH_CONTRACT_VERSION_MISMATCH")
        if not 1 <= int(self.limit) <= 100:
            raise ValueError("SEARCH_LIMIT_OUT_OF_RANGE")
        unknown = set(self.kinds) - SEARCH_RESULT_KINDS
        if unknown:
            raise ValueError(f"SEARCH_KIND_INVALID:{sorted(unknown)}")
        _aware_iso(self.from_at, "from_at")
        _aware_iso(self.to_at, "to_at")
        if self.check_worthy is not None and not isinstance(self.check_worthy, bool):
            raise ValueError("SEARCH_CHECK_WORTHY_INVALID")

    def variables(self) -> dict[str, object]:
        return {
            "query": self.query.strip(),
            "kinds": json.dumps(list(self.kinds), separators=(",", ":")),
            "collection_id": _clean_optional(self.collection_id) or "",
            "person_id": _clean_optional(self.person_id) or "",
            "topic_id": _clean_optional(self.topic_id) or "",
            "event_id": _clean_optional(self.event_id) or "",
            "source_id": _clean_optional(self.source_id) or "",
            "content_id": _clean_optional(self.content_id) or "",
            "status": _clean_optional(self.status) or "",
            "claim_type": _clean_optional(self.claim_type) or "",
            "check_worthy": "" if self.check_worthy is None else ("true" if self.check_worthy else "false"),
            "from_at": _aware_iso(self.from_at, "from_at") or "",
            "to_at": _aware_iso(self.to_at, "to_at") or "",
            "limit": int(self.limit),
        }


@dataclass(frozen=True)
class CorpusSearchResult:
    kind: str
    id: str
    label: str
    snippet: str | None
    content_id: str | None
    passage_id: str | None
    source_id: str | None
    person_id: str | None
    topic_id: str | None
    event_id: str | None
    event_at: str | None
    status: str | None
    claim_type: str | None
    check_worthy: bool | None
    lexical_score: float
    trigram_score: float

    @property
    def score(self) -> float:
        return self.lexical_score + (0.65 * self.trigram_score)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CorpusSearchResult":
        if raw.get("kind") not in SEARCH_RESULT_KINDS:
            raise ValueError("SEARCH_RESULT_KIND_INVALID")
        return cls(
            kind=str(raw["kind"]),
            id=str(raw["id"]),
            label=str(raw.get("label") or ""),
            snippet=None if raw.get("snippet") is None else str(raw["snippet"]),
            content_id=None if raw.get("content_id") is None else str(raw["content_id"]),
            passage_id=None if raw.get("passage_id") is None else str(raw["passage_id"]),
            source_id=None if raw.get("source_id") is None else str(raw["source_id"]),
            person_id=None if raw.get("person_id") is None else str(raw["person_id"]),
            topic_id=None if raw.get("topic_id") is None else str(raw["topic_id"]),
            event_id=None if raw.get("event_id") is None else str(raw["event_id"]),
            event_at=None if raw.get("event_at") is None else str(raw["event_at"]),
            status=None if raw.get("status") is None else str(raw["status"]),
            claim_type=None if raw.get("claim_type") is None else str(raw["claim_type"]),
            check_worthy=None if raw.get("check_worthy") is None else bool(raw["check_worthy"]),
            lexical_score=float(raw.get("lexical_score") or 0),
            trigram_score=float(raw.get("trigram_score") or 0),
        )


# Each branch keeps the indexed search expression syntactically aligned with the index.
# Trigram `<%` is a candidate-generation operator only; result ranking never approves
# identity, proposition equivalence, evidence, or publication.
CORPUS_SEARCH_SQL_V1 = r"""
SET pg_trgm.word_similarity_threshold = 0.35;
WITH params AS (
    SELECT
        websearch_to_tsquery('italian', :'query') AS tsq,
        :'query'::text AS raw_query
), hits AS (
    SELECT
        'CONTENT'::text AS kind,
        c.id,
        coalesce(c.title, c.canonical_url) AS label,
        left(coalesce(c.description, ''), 500) AS snippet,
        c.id AS content_id,
        NULL::text AS passage_id,
        c.source_id,
        NULL::text AS person_id,
        NULL::text AS topic_id,
        NULL::text AS event_id,
        c.published_at AS event_at,
        c.processing_status AS status,
        NULL::text AS claim_type,
        NULL::boolean AS check_worthy,
        ts_rank_cd(
            to_tsvector('italian', coalesce(c.title, '') || ' ' || coalesce(c.description, '')),
            params.tsq
        )::double precision AS lexical_score,
        greatest(word_similarity(params.raw_query, coalesce(c.title, '')), 0)::double precision AS trigram_score
    FROM content_item c CROSS JOIN params
    WHERE
        to_tsvector('italian', coalesce(c.title, '') || ' ' || coalesce(c.description, '')) @@ params.tsq
        OR params.raw_query <% coalesce(c.title, '')

    UNION ALL
    SELECT
        'PASSAGE', p.id, left(coalesce(p.private_text, '[passage]'), 220),
        left(coalesce(p.private_text, ''), 500), p.content_id, p.id, c.source_id,
        NULL, NULL, NULL, c.published_at, NULL, NULL, NULL,
        ts_rank_cd(to_tsvector('italian', coalesce(p.private_text, '')), params.tsq)::double precision,
        greatest(word_similarity(params.raw_query, coalesce(p.private_text, '')), 0)::double precision
    FROM passage p JOIN content_item c ON c.id=p.content_id CROSS JOIN params
    WHERE to_tsvector('italian', coalesce(p.private_text, '')) @@ params.tsq
       OR params.raw_query <% coalesce(p.private_text, '')

    UNION ALL
    SELECT
        'STATEMENT_CANDIDATE', s.id, s.normalized_statement, s.normalized_statement,
        s.content_id, sp.passage_id, c.source_id, s.speaker_person_id, NULL, NULL,
        coalesce(s.statement_at, c.published_at), s.status, NULL, NULL,
        ts_rank_cd(to_tsvector('italian', s.normalized_statement), params.tsq)::double precision,
        word_similarity(params.raw_query, s.normalized_statement)::double precision
    FROM statement_candidate s
    JOIN content_item c ON c.id=s.content_id
    LEFT JOIN LATERAL (
        SELECT passage_id FROM statement_candidate_passage
        WHERE statement_candidate_id=s.id ORDER BY passage_id LIMIT 1
    ) sp ON true
    CROSS JOIN params
    WHERE to_tsvector('italian', s.normalized_statement) @@ params.tsq
       OR params.raw_query <% s.normalized_statement

    UNION ALL
    SELECT
        'CLAIM_CANDIDATE', cc.id, cc.normalized_claim, cc.normalized_claim,
        cc.content_id, sp.passage_id, c.source_id, sc.speaker_person_id, NULL, NULL,
        coalesce(sc.statement_at, c.published_at), cc.status, cc.proposed_claim_type, cc.check_worthy,
        ts_rank_cd(to_tsvector('italian', cc.normalized_claim), params.tsq)::double precision,
        word_similarity(params.raw_query, cc.normalized_claim)::double precision
    FROM claim_candidate cc
    JOIN statement_candidate sc ON sc.id=cc.statement_candidate_id
    JOIN content_item c ON c.id=cc.content_id
    LEFT JOIN LATERAL (
        SELECT passage_id FROM statement_candidate_passage
        WHERE statement_candidate_id=sc.id ORDER BY passage_id LIMIT 1
    ) sp ON true
    CROSS JOIN params
    WHERE to_tsvector('italian', cc.normalized_claim) @@ params.tsq
       OR params.raw_query <% cc.normalized_claim

    UNION ALL
    SELECT
        'ATOMIC_CLAIM', ac.id, ac.normalized_claim, ac.normalized_claim,
        ac.content_id, cs.canonical_segment_id, c.source_id, ac.speaker_person_id, NULL, NULL,
        c.published_at, 'ATOMIC', ac.claim_type, ac.check_worthy,
        ts_rank_cd(to_tsvector('italian', ac.normalized_claim), params.tsq)::double precision,
        word_similarity(params.raw_query, ac.normalized_claim)::double precision
    FROM atomic_claim ac
    JOIN content_item c ON c.id=ac.content_id
    LEFT JOIN LATERAL (
        SELECT segment_id AS canonical_segment_id FROM claim_segment
        WHERE claim_id=ac.id ORDER BY segment_id LIMIT 1
    ) cs ON true
    CROSS JOIN params
    WHERE to_tsvector('italian', ac.normalized_claim) @@ params.tsq
       OR params.raw_query <% ac.normalized_claim

    UNION ALL
    SELECT
        'PERSON', p.id, p.canonical_name, p.public_role, NULL, NULL, NULL, p.id, NULL, NULL,
        NULL, 'ACTIVE', NULL, NULL, 0::double precision,
        greatest(
            word_similarity(params.raw_query, p.canonical_name),
            coalesce((SELECT max(word_similarity(params.raw_query, pa.alias)) FROM person_alias pa WHERE pa.person_id=p.id), 0)
        )::double precision
    FROM person p CROSS JOIN params
    WHERE params.raw_query <% p.canonical_name
       OR EXISTS (SELECT 1 FROM person_alias pa WHERE pa.person_id=p.id AND params.raw_query <% pa.alias)

    UNION ALL
    SELECT
        'ORGANIZATION', o.id, o.canonical_name, o.organization_type, NULL, NULL, NULL, NULL, NULL, NULL,
        NULL, 'ACTIVE', NULL, NULL, 0::double precision,
        greatest(
            word_similarity(params.raw_query, o.canonical_name),
            coalesce((SELECT max(word_similarity(params.raw_query, oa.alias)) FROM organization_alias oa WHERE oa.organization_id=o.id), 0)
        )::double precision
    FROM organization o CROSS JOIN params
    WHERE params.raw_query <% o.canonical_name
       OR EXISTS (SELECT 1 FROM organization_alias oa WHERE oa.organization_id=o.id AND params.raw_query <% oa.alias)

    UNION ALL
    SELECT
        'TOPIC', t.id, t.canonical_name, t.scope_text, NULL, NULL, NULL, NULL, t.id, NULL,
        NULL, t.status, NULL, NULL,
        ts_rank_cd(to_tsvector('italian', t.canonical_name || ' ' || t.scope_text), params.tsq)::double precision,
        greatest(
            word_similarity(params.raw_query, t.canonical_name),
            coalesce((SELECT max(word_similarity(params.raw_query, ta.alias)) FROM topic_alias ta WHERE ta.topic_id=t.id), 0)
        )::double precision
    FROM topic t CROSS JOIN params
    WHERE t.status='ACTIVE' AND (
        to_tsvector('italian', t.canonical_name || ' ' || t.scope_text) @@ params.tsq
        OR params.raw_query <% t.canonical_name
        OR EXISTS (SELECT 1 FROM topic_alias ta WHERE ta.topic_id=t.id AND params.raw_query <% ta.alias)
    )

    UNION ALL
    SELECT
        'EVENT', e.id, e.canonical_name, e.scope_text, NULL, NULL, NULL, NULL, NULL, e.id,
        e.start_at, e.status, NULL, NULL,
        ts_rank_cd(to_tsvector('italian', e.canonical_name || ' ' || e.scope_text), params.tsq)::double precision,
        greatest(
            word_similarity(params.raw_query, e.canonical_name),
            coalesce((SELECT max(word_similarity(params.raw_query, ea.alias)) FROM event_alias ea WHERE ea.event_id=e.id), 0)
        )::double precision
    FROM event e CROSS JOIN params
    WHERE e.status='ACTIVE' AND (
        to_tsvector('italian', e.canonical_name || ' ' || e.scope_text) @@ params.tsq
        OR params.raw_query <% e.canonical_name
        OR EXISTS (SELECT 1 FROM event_alias ea WHERE ea.event_id=e.id AND params.raw_query <% ea.alias)
    )

    UNION ALL
    SELECT
        'COLLECTION', rc.id, rc.name, rc.scope_text, NULL, NULL, NULL, NULL, NULL, NULL,
        rc.updated_at, rc.status, NULL, NULL,
        ts_rank_cd(to_tsvector('italian', rc.name || ' ' || rc.scope_text), params.tsq)::double precision,
        word_similarity(params.raw_query, rc.name)::double precision
    FROM research_collection rc CROSS JOIN params
    WHERE to_tsvector('italian', rc.name || ' ' || rc.scope_text) @@ params.tsq
       OR params.raw_query <% rc.name
), filtered AS (
    SELECT h.*
    FROM hits h
    WHERE
        (:'kinds'::jsonb = '[]'::jsonb OR h.kind IN (SELECT jsonb_array_elements_text(:'kinds'::jsonb)))
        AND (NULLIF(:'content_id','') IS NULL OR h.content_id=:'content_id')
        AND (NULLIF(:'source_id','') IS NULL OR h.source_id=:'source_id')
        AND (NULLIF(:'status','') IS NULL OR h.status=:'status')
        AND (NULLIF(:'claim_type','') IS NULL OR h.claim_type=:'claim_type')
        AND (NULLIF(:'check_worthy','') IS NULL OR h.check_worthy=NULLIF(:'check_worthy','')::boolean)
        AND (NULLIF(:'from_at','') IS NULL OR h.event_at >= NULLIF(:'from_at','')::timestamptz)
        AND (NULLIF(:'to_at','') IS NULL OR h.event_at <= NULLIF(:'to_at','')::timestamptz)
        AND (
            NULLIF(:'collection_id','') IS NULL
            OR (h.content_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM research_collection_content rcc
                WHERE rcc.collection_id=:'collection_id' AND rcc.content_id=h.content_id AND rcc.status='INCLUDED'
            ))
        )
        AND (
            NULLIF(:'person_id','') IS NULL
            OR h.person_id=:'person_id'
            OR (h.content_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM entity_resolution_candidate erc
                WHERE erc.content_id=h.content_id AND erc.status='APPROVED' AND erc.target_person_id=:'person_id'
            ))
        )
        AND (
            NULLIF(:'topic_id','') IS NULL
            OR h.topic_id=:'topic_id'
            OR (h.content_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM entity_resolution_candidate erc
                WHERE erc.content_id=h.content_id AND erc.status='APPROVED' AND erc.target_topic_id=:'topic_id'
            ))
        )
        AND (
            NULLIF(:'event_id','') IS NULL
            OR h.event_id=:'event_id'
            OR (h.content_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM entity_resolution_candidate erc
                WHERE erc.content_id=h.content_id AND erc.status='APPROVED' AND erc.target_event_id=:'event_id'
            ))
        )
)
SELECT json_build_object(
    'kind', kind,
    'id', id,
    'label', label,
    'snippet', NULLIF(snippet, ''),
    'content_id', content_id,
    'passage_id', passage_id,
    'source_id', source_id,
    'person_id', person_id,
    'topic_id', topic_id,
    'event_id', event_id,
    'event_at', event_at,
    'status', status,
    'claim_type', claim_type,
    'check_worthy', check_worthy,
    'lexical_score', lexical_score,
    'trigram_score', trigram_score
)::text
FROM filtered
ORDER BY (lexical_score + (0.65 * trigram_score)) DESC, event_at DESC NULLS LAST, kind, id
LIMIT :'limit'::integer;
""".strip()


TRIGRAM_PLAN_PROBE_SQL_V1 = r"""
SET enable_seqscan=off;
SET pg_trgm.word_similarity_threshold = 0.35;
EXPLAIN (COSTS OFF)
SELECT id
FROM atomic_claim
WHERE :'query' <% normalized_claim
ORDER BY word_similarity(:'query', normalized_claim) DESC
LIMIT 5;
RESET enable_seqscan;
""".strip()


class CorpusSearchStore(PsqlRuntime):
    def search(self, request: CorpusSearchRequest) -> list[CorpusSearchResult]:
        raw = self.run(CORPUS_SEARCH_SQL_V1, **request.variables())
        if not raw:
            return []
        results: list[CorpusSearchResult] = []
        for line in raw.splitlines():
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise RuntimeError("SEARCH_RESULT_NOT_OBJECT")
            results.append(CorpusSearchResult.from_dict(parsed))
        return results

    def trigram_plan_probe(self, query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("SEARCH_QUERY_REQUIRED")
        return self.run(TRIGRAM_PLAN_PROBE_SQL_V1, query=query.strip())


def result_ids(results: Iterable[CorpusSearchResult]) -> tuple[str, ...]:
    return tuple(item.id for item in results)


__all__ = [
    "CORPUS_SEARCH_SQL_V1",
    "CorpusSearchRequest",
    "CorpusSearchResult",
    "CorpusSearchStore",
    "SEARCH_CONTRACT_VERSION",
    "SEARCH_RESULT_KINDS",
    "TRIGRAM_PLAN_PROBE_SQL_V1",
    "result_ids",
]
