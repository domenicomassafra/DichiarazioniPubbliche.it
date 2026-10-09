from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from dichiarazioni_pubbliche.proposition_clustering import (
    INSERT_CLUSTER_MEMBER_SQL_V1,
    INSERT_PROPOSITION_CLUSTER_SQL_V1,
    PropositionInput,
    PropositionMatch,
    classify_proposition_pair,
    make_cluster,
    make_cluster_member,
    record_to_params,
)
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


MATCHING_VERSION = "candidate-matching-v1"
# A changed disposition rule must create a new run fingerprint so an existing
# persisted proposal cannot be replayed as if it had passed the stricter gate.
DISPOSITION_POLICY_VERSION = "structured-scope-conflict-hold-v2"
DEFAULT_TARGET_LIMIT = 200


class CandidateMatchingError(RuntimeError):
    pass


@dataclass(frozen=True)
class MatchingInput:
    proposition: PropositionInput
    claim_type: str | None = None
    temporal_scope: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResult:
    target: MatchingInput
    match: PropositionMatch
    rank: int
    disposition: str
    cluster_id: str | None
    supporting_features: tuple[dict[str, Any], ...]
    contradicting_features: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class MatchRunReceipt:
    run_id: str
    claim_candidate_id: str
    input_fingerprint: str
    result_count: int
    results: tuple[MatchResult, ...]
    replayed: bool = False


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: object) -> str:
    material = "\x1f".join(str(part) for part in parts)
    return prefix + ":" + hashlib.sha256(material.encode()).hexdigest()


def _temporal_key(scope: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    allowed = ("statement_date", "valid_from", "valid_until", "reference_period")
    return tuple(
        (key, str(scope[key]).strip())
        for key in allowed
        if scope.get(key) is not None and str(scope.get(key)).strip()
    )


def _augment_features(
    candidate: MatchingInput,
    target: MatchingInput,
    match: PropositionMatch,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    supporting = list(match.supporting_features)
    contradicting = list(match.contradicting_features)
    if candidate.claim_type and target.claim_type:
        if candidate.claim_type == target.claim_type:
            supporting.append({"code": "SAME_CLAIM_TYPE", "value": candidate.claim_type})
        else:
            contradicting.append(
                {
                    "code": "CLAIM_TYPE_MISMATCH",
                    "candidate": candidate.claim_type,
                    "target": target.claim_type,
                }
            )
    left_temporal = _temporal_key(candidate.temporal_scope)
    right_temporal = _temporal_key(target.temporal_scope)
    if left_temporal and right_temporal:
        if left_temporal == right_temporal:
            supporting.append(
                {"code": "SAME_TEMPORAL_SCOPE", "values": dict(left_temporal)}
            )
        else:
            contradicting.append(
                {
                    "code": "TEMPORAL_SCOPE_DIFFERS",
                    "candidate": dict(left_temporal),
                    "target": dict(right_temporal),
                }
            )
    return tuple(supporting), tuple(contradicting)


def _disposition(match_class: str, contradicting_features: Sequence[Mapping[str, Any]]) -> str:
    # The lexical classifier does not know ClaimType or the reference period.
    # An exact string match alone cannot propose semantic equivalence when
    # those typed inputs explicitly disagree. Preserve the match for review.
    if any(feature.get("code") in {"CLAIM_TYPE_MISMATCH", "TEMPORAL_SCOPE_DIFFERS"}
           for feature in contradicting_features):
        return "HOLD"
    if match_class in {"DUPLICATE_EXTRACTION", "SAME_PROPOSITION"}:
        return "PROPOSE_CLUSTER"
    if match_class == "UNCERTAIN":
        return "HOLD"
    return "NO_CLUSTER"


_CLASS_ORDER = {
    "DUPLICATE_EXTRACTION": 0,
    "SAME_PROPOSITION": 1,
    "UNCERTAIN": 2,
    "RELATED": 3,
    "DIFFERENT": 4,
}


def rank_candidate_matches(
    candidate: MatchingInput,
    targets: Iterable[MatchingInput],
) -> tuple[MatchResult, ...]:
    provisional: list[tuple[MatchingInput, PropositionMatch, tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]] = []
    for target in targets:
        if (
            candidate.proposition.member_type == target.proposition.member_type
            and candidate.proposition.member_id == target.proposition.member_id
        ):
            continue
        match = classify_proposition_pair(candidate.proposition, target.proposition)
        supporting, contradicting = _augment_features(candidate, target, match)
        provisional.append((target, match, supporting, contradicting))
    provisional.sort(
        key=lambda row: (
            _CLASS_ORDER[row[1].match_class],
            -row[1].lexical_score,
            row[0].proposition.member_type,
            row[0].proposition.member_id,
        )
    )
    output: list[MatchResult] = []
    for index, (target, match, supporting, contradicting) in enumerate(provisional, start=1):
        disposition = _disposition(match.match_class, contradicting)
        cluster_id = (
            make_cluster(candidate.proposition.normalized_text, match.method).id
            if disposition == "PROPOSE_CLUSTER"
            else None
        )
        output.append(
            MatchResult(
                target=target,
                match=match,
                rank=index,
                disposition=disposition,
                cluster_id=cluster_id,
                supporting_features=supporting,
                contradicting_features=contradicting,
            )
        )
    return tuple(output)


def matching_input_fingerprint(
    candidate: MatchingInput,
    targets: Sequence[MatchingInput],
) -> str:
    payload = {
        "matching_version": MATCHING_VERSION,
        "disposition_policy_version": DISPOSITION_POLICY_VERSION,
        "candidate": asdict(candidate),
        "targets": [
            asdict(item)
            for item in sorted(
                targets,
                key=lambda item: (
                    item.proposition.member_type,
                    item.proposition.member_id,
                ),
            )
        ],
    }
    return hashlib.sha256(_stable_json(payload).encode()).hexdigest()


def deterministic_match_run_id(claim_candidate_id: str, fingerprint: str) -> str:
    return _stable_id("candidate-match-run", MATCHING_VERSION, claim_candidate_id, fingerprint)


def deterministic_match_result_id(
    run_id: str,
    target_type: str,
    target_id: str,
) -> str:
    return _stable_id("candidate-match-result", run_id, target_type, target_id)


class CandidateMatchingStore(PsqlRuntime):
    def load_candidate(self, claim_candidate_id: str) -> MatchingInput | None:
        raw = self.run(
            r"""
            SELECT COALESCE(json_build_object(
                'member_type', 'CLAIM_CANDIDATE',
                'member_id', candidate.id,
                'content_id', candidate.content_id,
                'normalized_text', candidate.normalized_claim,
                'provenance_key', COALESCE(candidate.metadata->>'parent_passage_id', statement.id),
                'claim_type', candidate.proposed_claim_type,
                'temporal_scope', candidate.temporal_scope,
                'entity_keys', COALESCE((
                    SELECT json_agg(DISTINCT COALESCE(
                        resolution.target_person_id,
                        resolution.target_organization_id,
                        resolution.target_topic_id,
                        resolution.target_event_id
                    ) ORDER BY COALESCE(
                        resolution.target_person_id,
                        resolution.target_organization_id,
                        resolution.target_topic_id,
                        resolution.target_event_id
                    ))
                    FROM entity_resolution_candidate resolution
                    WHERE resolution.passage_id = NULLIF(
                        candidate.metadata->>'parent_passage_id', ''
                    )
                      AND resolution.status IN ('CANDIDATE', 'APPROVED')
                ), '[]'::json)
            )::text, '')
            FROM claim_candidate candidate
            JOIN statement_candidate statement ON statement.id=candidate.statement_candidate_id
            WHERE candidate.id=:'claim_candidate_id';
            """,
            claim_candidate_id=claim_candidate_id,
        )
        if not raw:
            return None
        return _matching_input_from_dict(json.loads(raw))

    def load_targets(
        self,
        claim_candidate_id: str,
        *,
        limit: int = DEFAULT_TARGET_LIMIT,
    ) -> tuple[MatchingInput, ...]:
        if not 1 <= int(limit) <= 1000:
            raise CandidateMatchingError("CANDIDATE_MATCH_LIMIT_INVALID")
        raw = self.run(
            r"""
            WITH candidate AS (
                SELECT id, normalized_claim
                FROM claim_candidate
                WHERE id=:'claim_candidate_id'
            ), pool AS (
                SELECT
                    'ATOMIC_CLAIM'::text AS member_type,
                    claim.id AS member_id,
                    claim.content_id,
                    claim.normalized_claim AS normalized_text,
                    COALESCE(
                        (SELECT min(link.segment_id) FROM claim_segment link WHERE link.claim_id=claim.id),
                        (SELECT min(provenance.id) FROM claim_text_provenance provenance WHERE provenance.claim_id=claim.id),
                        claim.id
                    ) AS provenance_key,
                    claim.claim_type,
                    claim.temporal_scope,
                    CASE
                        WHEN lower(claim.normalized_claim) = lower(candidate.normalized_claim) THEN 1.0
                        ELSE word_similarity(candidate.normalized_claim, claim.normalized_claim)
                    END AS candidate_score
                FROM atomic_claim claim CROSS JOIN candidate
                UNION ALL
                SELECT
                    'CLAIM_CANDIDATE', other.id, other.content_id, other.normalized_claim,
                    COALESCE(other.metadata->>'parent_passage_id', other.statement_candidate_id),
                    other.proposed_claim_type, other.temporal_scope,
                    CASE
                        WHEN lower(other.normalized_claim) = lower(candidate.normalized_claim) THEN 1.0
                        ELSE word_similarity(candidate.normalized_claim, other.normalized_claim)
                    END
                FROM claim_candidate other CROSS JOIN candidate
                WHERE other.id <> :'claim_candidate_id'
            )
            SELECT json_build_object(
                'member_type', member_type,
                'member_id', member_id,
                'content_id', content_id,
                'normalized_text', normalized_text,
                'provenance_key', provenance_key,
                'claim_type', claim_type,
                'temporal_scope', temporal_scope,
                'entity_keys', '[]'::json
            )::text
            FROM pool
            ORDER BY candidate_score DESC, member_type, member_id
            LIMIT :'limit'::integer;
            """,
            claim_candidate_id=claim_candidate_id,
            limit=limit,
        )
        return tuple(
            _matching_input_from_dict(json.loads(line))
            for line in raw.splitlines()
            if line.strip()
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        raw = self.run(
            """
            SELECT COALESCE(json_build_object(
              'id', id, 'claim_candidate_id', claim_candidate_id,
              'input_fingerprint', input_fingerprint, 'status', status,
              'result_count', result_count
            )::text, '')
            FROM candidate_match_run WHERE id=:'run_id';
            """,
            run_id=run_id,
        )
        return json.loads(raw) if raw else None

    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]:
        raw = self.run(
            """
            SELECT json_build_object(
              'id', result.id, 'rank', result.rank, 'target_type', result.target_type,
              'target_id', COALESCE(result.target_claim_candidate_id, result.target_atomic_claim_id),
              'match_class', result.match_class, 'method', result.method,
              'lexical_score', result.lexical_score, 'disposition', result.disposition,
              'proposition_cluster_id', result.proposition_cluster_id,
              'supporting_features', result.supporting_features,
              'contradicting_features', result.contradicting_features
            )::text
            FROM candidate_match_result result
            WHERE result.run_id=:'run_id'
            ORDER BY result.rank, result.id;
            """,
            run_id=run_id,
        )
        return tuple(json.loads(line) for line in raw.splitlines() if line.strip())

    def insert_cluster_proposal(
        self,
        *,
        candidate: MatchingInput,
        result: MatchResult,
    ) -> None:
        if result.cluster_id is None:
            return
        cluster = make_cluster(candidate.proposition.normalized_text, result.match.method)
        state = self.run(INSERT_PROPOSITION_CLUSTER_SQL_V1, **record_to_params(cluster))
        if state not in {"INSERTED", "EXISTING"}:
            raise CandidateMatchingError("CANDIDATE_MATCH_CLUSTER_CONFLICT")
        seed_match = PropositionMatch(
            match_class="SAME_PROPOSITION",
            method=result.match.method,
            lexical_score=1.0,
            supporting_features=({"code": "MATCH_RUN_SEED"},),
        )
        for member, match in (
            (candidate.proposition, seed_match),
            (result.target.proposition, result.match),
        ):
            row = make_cluster_member(cluster, member, match)
            member_state = self.run(INSERT_CLUSTER_MEMBER_SQL_V1, **record_to_params(row))
            if member_state not in {"INSERTED", "EXISTING"}:
                raise CandidateMatchingError("CANDIDATE_MATCH_CLUSTER_MEMBER_CONFLICT")

    def persist_run(
        self,
        *,
        run_id: str,
        claim_candidate_id: str,
        fingerprint: str,
        results: Sequence[MatchResult],
    ) -> None:
        raw = self.run(
            """
            WITH inserted AS (
              INSERT INTO candidate_match_run(
                id, claim_candidate_id, matching_version, input_fingerprint,
                status, result_count, metadata
              ) VALUES (
                :'run_id', :'claim_candidate_id', 'candidate-matching-v1',
                :'input_fingerprint', 'COMPLETED', :'result_count'::integer, '{}'::jsonb
              ) ON CONFLICT (id) DO NOTHING RETURNING id
            ), existing AS (
              SELECT id FROM candidate_match_run
              WHERE id=:'run_id' AND claim_candidate_id=:'claim_candidate_id'
                AND matching_version='candidate-matching-v1'
                AND input_fingerprint=:'input_fingerprint'
                AND status='COMPLETED' AND result_count=:'result_count'::integer
            )
            SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
                        WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
                        ELSE 'CONFLICT' END;
            """,
            run_id=run_id,
            claim_candidate_id=claim_candidate_id,
            input_fingerprint=fingerprint,
            result_count=len(results),
        )
        if raw not in {"INSERTED", "EXISTING"}:
            raise CandidateMatchingError("CANDIDATE_MATCH_RUN_CONFLICT")
        for result in results:
            target = result.target.proposition
            result_id = deterministic_match_result_id(run_id, target.member_type, target.member_id)
            target_candidate_id = target.member_id if target.member_type == "CLAIM_CANDIDATE" else ""
            target_atomic_id = target.member_id if target.member_type == "ATOMIC_CLAIM" else ""
            state = self.run(
                """
                WITH inserted AS (
                  INSERT INTO candidate_match_result(
                    id, run_id, target_type, target_claim_candidate_id,
                    target_atomic_claim_id, rank, match_class, method, lexical_score,
                    supporting_features, contradicting_features, disposition,
                    proposition_cluster_id, matching_version, status, metadata
                  ) VALUES (
                    :'id', :'run_id', :'target_type', NULLIF(:'target_candidate_id',''),
                    NULLIF(:'target_atomic_id',''), :'rank'::integer, :'match_class', :'method',
                    :'lexical_score'::numeric, :'supporting_features'::jsonb,
                    :'contradicting_features'::jsonb, :'disposition', NULLIF(:'cluster_id',''),
                    'candidate-matching-v1', 'CANDIDATE', '{}'::jsonb
                  ) ON CONFLICT (id) DO NOTHING RETURNING id
                ), existing AS (
                  SELECT id FROM candidate_match_result
                  WHERE id=:'id' AND run_id=:'run_id' AND target_type=:'target_type'
                    AND target_claim_candidate_id IS NOT DISTINCT FROM NULLIF(:'target_candidate_id','')
                    AND target_atomic_claim_id IS NOT DISTINCT FROM NULLIF(:'target_atomic_id','')
                    AND rank=:'rank'::integer AND match_class=:'match_class' AND method=:'method'
                    AND lexical_score=:'lexical_score'::numeric
                    AND supporting_features=:'supporting_features'::jsonb
                    AND contradicting_features=:'contradicting_features'::jsonb
                    AND disposition=:'disposition'
                    AND proposition_cluster_id IS NOT DISTINCT FROM NULLIF(:'cluster_id','')
                    AND matching_version='candidate-matching-v1' AND status='CANDIDATE'
                )
                SELECT CASE WHEN EXISTS(SELECT 1 FROM inserted) THEN 'INSERTED'
                            WHEN EXISTS(SELECT 1 FROM existing) THEN 'EXISTING'
                            ELSE 'CONFLICT' END;
                """,
                id=result_id,
                run_id=run_id,
                target_type=target.member_type,
                target_candidate_id=target_candidate_id,
                target_atomic_id=target_atomic_id,
                rank=result.rank,
                match_class=result.match.match_class,
                method=result.match.method,
                lexical_score=f"{result.match.lexical_score:.6f}",
                supporting_features=_stable_json(list(result.supporting_features)),
                contradicting_features=_stable_json(list(result.contradicting_features)),
                disposition=result.disposition,
                cluster_id=result.cluster_id or "",
            )
            if state not in {"INSERTED", "EXISTING"}:
                raise CandidateMatchingError("CANDIDATE_MATCH_RESULT_CONFLICT")


def _matching_input_from_dict(raw: Mapping[str, Any]) -> MatchingInput:
    proposition = PropositionInput(
        member_type=str(raw["member_type"]),
        member_id=str(raw["member_id"]),
        content_id=str(raw["content_id"]),
        normalized_text=str(raw["normalized_text"]),
        provenance_key=str(raw.get("provenance_key") or "").strip() or None,
        entity_keys=tuple(sorted(str(item) for item in (raw.get("entity_keys") or []) if item)),
        topic_keys=tuple(sorted(str(item) for item in (raw.get("topic_keys") or []) if item)),
    )
    temporal = raw.get("temporal_scope") or {}
    if not isinstance(temporal, Mapping):
        raise CandidateMatchingError("CANDIDATE_MATCH_TEMPORAL_SCOPE_INVALID")
    return MatchingInput(
        proposition=proposition,
        claim_type=str(raw.get("claim_type") or "").strip() or None,
        temporal_scope=dict(temporal),
    )


def match_claim_candidate(
    *,
    claim_candidate_id: str,
    store: CandidateMatchingStore,
    target_limit: int = DEFAULT_TARGET_LIMIT,
) -> MatchRunReceipt:
    candidate = store.load_candidate(claim_candidate_id)
    if candidate is None:
        raise CandidateMatchingError("CANDIDATE_MATCH_INPUT_NOT_FOUND")
    targets = store.load_targets(claim_candidate_id, limit=target_limit)
    fingerprint = matching_input_fingerprint(candidate, targets)
    run_id = deterministic_match_run_id(claim_candidate_id, fingerprint)
    existing = store.get_run(run_id)
    if existing is not None:
        if (existing.get("status") != "COMPLETED"
                or existing.get("claim_candidate_id") != claim_candidate_id
                or existing.get("input_fingerprint") != fingerprint):
            raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_AUTHORITY_MISMATCH")
        rows = store.load_results(run_id)
        if int(existing.get("result_count") or 0) != len(rows):
            raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_INCOMPLETE")
        expected_targets = {
            (target.proposition.member_type, target.proposition.member_id)
            for target in targets
            if (target.proposition.member_type, target.proposition.member_id) !=
               (candidate.proposition.member_type, candidate.proposition.member_id)
        }
        actual_targets = {
            (row.get("target_type"), row.get("target_id")) for row in rows
        }
        if (len(actual_targets) != len(rows) or actual_targets != expected_targets
                or {row.get("rank") for row in rows} != set(range(1, len(rows) + 1))):
            raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_RESULTS_MISMATCH")
        # Fingerprints bind the inputs, but the persisted result rows have
        # independent mutable fields. Recompute the deterministic decisions
        # so a stale/tampered disposition or cluster cannot pass as replay.
        expected_results = rank_candidate_matches(candidate, targets)
        for row, expected in zip(sorted(rows, key=lambda value: value["rank"]), expected_results):
            if (row.get("rank") != expected.rank
                    or row.get("target_type") != expected.target.proposition.member_type
                    or row.get("target_id") != expected.target.proposition.member_id
                    or row.get("match_class") != expected.match.match_class
                    or row.get("method") != expected.match.method
                    or row.get("disposition") != expected.disposition
                    or row.get("proposition_cluster_id") != expected.cluster_id
                    or row.get("supporting_features") != list(expected.supporting_features)
                    or row.get("contradicting_features") != list(expected.contradicting_features)):
                raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_SEMANTICS_MISMATCH")
            try:
                score = float(row["lexical_score"])
            except (KeyError, ValueError, TypeError):
                raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_SCORE_INVALID") from None
            if abs(score - expected.match.lexical_score) > 0.000001:
                raise CandidateMatchingError("CANDIDATE_MATCH_REPLAY_SCORE_INVALID")
        return MatchRunReceipt(
            run_id=run_id,
            claim_candidate_id=claim_candidate_id,
            input_fingerprint=fingerprint,
            result_count=len(rows),
            results=(),
            replayed=True,
        )
    results = rank_candidate_matches(candidate, targets)
    for result in results:
        if result.disposition == "PROPOSE_CLUSTER":
            store.insert_cluster_proposal(candidate=candidate, result=result)
    store.persist_run(
        run_id=run_id,
        claim_candidate_id=claim_candidate_id,
        fingerprint=fingerprint,
        results=results,
    )
    return MatchRunReceipt(
        run_id=run_id,
        claim_candidate_id=claim_candidate_id,
        input_fingerprint=fingerprint,
        result_count=len(results),
        results=results,
        replayed=False,
    )


__all__ = [
    "CandidateMatchingError",
    "CandidateMatchingStore",
    "DEFAULT_TARGET_LIMIT",
    "MATCHING_VERSION",
    "MatchResult",
    "MatchRunReceipt",
    "MatchingInput",
    "deterministic_match_result_id",
    "deterministic_match_run_id",
    "match_claim_candidate",
    "matching_input_fingerprint",
    "rank_candidate_matches",
]
