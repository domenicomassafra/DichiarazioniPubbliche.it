"""Explicitly started, operator-local, authenticated read-only Studio API.

There is no public route, remote bind option, cookie/session scheme, CORS
permission, HTTP mutation, static-asset delivery or automatic service startup.
An operator with existing local DB permission must deliberately start it and
provide a protected token file.  The API has no review/promotion authority.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Protocol

from dichiarazioni_pubbliche.candidate_matching import CandidateMatchingStore
from dichiarazioni_pubbliche.capture_pipeline import CapturePipelineStore
from dichiarazioni_pubbliche.corpus_search import CorpusSearchStore
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime, _clean
from dichiarazioni_pubbliche.studio_candidate_review import inspect_candidate_match_run
from dichiarazioni_pubbliche.studio_capture_inspector import (
    inspect_capture_versions, inspect_capture_passage_selectors,
)
from dichiarazioni_pubbliche.studio_media_selector import inspect_candidate_media_selector
from dichiarazioni_pubbliche.studio_operator_search import search_private_corpus
from dichiarazioni_pubbliche.studio_operator_queues import StudioOperatorQueues
from dichiarazioni_pubbliche.studio_discovery_inbox_workflow import DiscoveryInboxWorkflow
from dichiarazioni_pubbliche.studio_local_page import render_studio_login_page

STUDIO_LOCAL_API_VERSION = "studio-local-readonly-api-v1"
STUDIO_LOCAL_MAX_BODY_BYTES = 4096
_TOKEN_HEX = re.compile(r"^[0-9a-f]{64,128}$")
_STUDIO_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")
_CAPTURE_SHA = re.compile(r"^[0-9a-f]{64}$")
_CAPTURE_STATES = frozenset({"CAPTURED", "QUARANTINED", "PURGE_PENDING", "PURGED_BODY"})
_ARCHIVE_STATES = frozenset({"NOT_REQUESTED", "REQUESTED", "PENDING", "SUCCEEDED", "FAILED"})
_ALLOWED_PATHS = frozenset({
    "/v1/corpus/search", "/v1/capture/compare", "/v1/capture/passages",
    "/v1/media/segment", "/v1/candidate/matches",
    "/v1/collections/list", "/v1/collections/members",
    "/v1/collections/member", "/v1/collections/claim-provenance",
    "/v1/collections/captures",
    "/v1/collections/passage-candidates",
    "/v1/discovery/list", "/v1/discovery/inspect", "/v1/discovery/triage-history",
    "/v1/discovery/inbox",
})

class _StudioReadOnlyDb(PsqlRuntime):
    """Guard even a mistakenly invoked write at the PostgreSQL session layer."""

    def run(self, sql: str, **variables: object) -> str:
        args = self._args()
        for key, value in variables.items():
            args.extend(["-v", f"{key}={_clean(value)}"])
        environment = os.environ.copy()
        environment["PGOPTIONS"] = (
            environment.get("PGOPTIONS", "")
            + " -c default_transaction_read_only=on"
            + " -c statement_timeout=3000"
            + " -c lock_timeout=1000"
        ).strip()
        environment["PGCONNECT_TIMEOUT"] = "3"
        try:
            process = subprocess.run(
                args, input=sql, text=True, capture_output=True, check=False,
                env=environment, timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("STUDIO_LOCAL_DB_TIMEOUT_OR_UNAVAILABLE") from None
        if process.returncode != 0:
            raise RuntimeError("STUDIO_LOCAL_DB_QUERY_REFUSED")
        if len(process.stdout) > 128_000:
            raise RuntimeError("STUDIO_LOCAL_DB_RESULT_TOO_LARGE")
        return process.stdout.strip()


class _StudioCorpusReader(_StudioReadOnlyDb, CorpusSearchStore):
    pass


class _StudioCaptureReader(_StudioReadOnlyDb, CapturePipelineStore):
    def list_collection_passage_candidates(
        self, *, collection_id: str, content_id: str, passage_id: str,
        limit: int = 20, after_id: str | None = None,
    ) -> dict[str, Any]:
        """Persisted included Content→Passage→Statement→Claim IDs, never texts.

        An exact Content/Passage binding is required even when no candidate
        exists; one wrong or missing foreign key must not become an empty
        successful fake edge. Claim candidate children are capped per row.
        """
        for ref in (collection_id, content_id, passage_id):
            if not isinstance(ref, str) or not _STUDIO_REF.fullmatch(ref):
                raise ValueError("STUDIO_PASSAGE_CANDIDATE_REF_INVALID")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError("STUDIO_PASSAGE_CANDIDATE_LIMIT_INVALID")
        if after_id is not None and (not isinstance(after_id, str) or not _STUDIO_REF.fullmatch(after_id)):
            raise ValueError("STUDIO_PASSAGE_CANDIDATE_CURSOR_INVALID")
        raw = self.run("""
            SELECT json_build_object(
                'collection_id', member.collection_id,
                'content_id', item.id, 'source_id', item.source_id,
                'source_exists', source.id IS NOT NULL,
                'rights_status', item.rights_status,
                'passage_id', passage.id, 'selector_type', passage.selector_type,
                'candidates', (
                    SELECT coalesce(json_agg(row_to_json(selected) ORDER BY selected.id), '[]'::json)
                    FROM (
                        SELECT candidate.id, candidate.status,
                            (SELECT coalesce(json_agg(row_to_json(child) ORDER BY child.id), '[]'::json)
                             FROM (SELECT claim.id, claim.status, claim.promoted_claim_id
                                   FROM claim_candidate claim
                                   WHERE claim.statement_candidate_id=candidate.id
                                     AND claim.content_id=item.id
                                   ORDER BY claim.id LIMIT 20) child
                            ) AS claims
                        FROM statement_candidate_passage link
                        JOIN statement_candidate candidate
                          ON candidate.id=link.statement_candidate_id
                         AND candidate.content_id=link.content_id
                        WHERE link.passage_id=passage.id
                          AND link.content_id=item.id
                          AND candidate.id > :'after_id'
                        ORDER BY candidate.id LIMIT :'row_limit'::integer
                    ) selected
                )
            )::text
            FROM research_collection_content member
            JOIN content_item item ON item.id=member.content_id
            JOIN passage ON passage.id=:'passage_id' AND passage.content_id=item.id
            LEFT JOIN source source ON source.id=item.source_id
            WHERE member.collection_id=:'collection_id'
              AND member.content_id=:'content_id' AND member.status='INCLUDED';
        """, collection_id=collection_id, content_id=content_id,
            passage_id=passage_id, after_id=after_id or "", row_limit=limit + 1)
        if not raw:
            raise ValueError("STUDIO_PASSAGE_NOT_IN_INCLUDED_COLLECTION")
        try:
            record = json.loads(raw)
        except (TypeError, ValueError):
            raise ValueError("STUDIO_PASSAGE_CANDIDATE_RESULT_INVALID") from None
        if (not isinstance(record, dict)
                or record.get("collection_id") != collection_id
                or record.get("content_id") != content_id
                or record.get("passage_id") != passage_id
                or record.get("selector_type") not in {"TEXT_POSITION", "PAGE_RANGE", "MEDIA_SEGMENT_REF"}
                or record.get("source_exists") is not True
                or not isinstance(record.get("source_id"), str)
                or not _STUDIO_REF.fullmatch(record["source_id"])
                or not isinstance(record.get("rights_status"), str)
                or not isinstance(record.get("candidates"), list)):
            raise ValueError("STUDIO_PASSAGE_CANDIDATE_SCOPE_INVALID")
        rows = record["candidates"]
        if len(rows) > limit + 1:
            raise ValueError("STUDIO_PASSAGE_CANDIDATE_PAGE_INVALID")
        next_id = after_id or ""
        result = []
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"id", "status", "claims"}
                    or not isinstance(row["id"], str) or not _STUDIO_REF.fullmatch(row["id"])
                    or row["id"] <= next_id
                    or row["status"] not in {"CANDIDATE", "APPROVED", "REJECTED", "HELD", "SUPERSEDED"}
                    or not isinstance(row["claims"], list) or len(row["claims"]) > 20):
                raise ValueError("STUDIO_PASSAGE_CANDIDATE_ROW_INVALID")
            next_id = row["id"]
            claims = []
            prev_claim = ""
            for child in row["claims"]:
                if (not isinstance(child, dict) or set(child) != {"id", "status", "promoted_claim_id"}
                        or not isinstance(child["id"], str)
                        or not _STUDIO_REF.fullmatch(child["id"])
                        or child["id"] <= prev_claim
                        or child["status"] not in {"CANDIDATE", "DUPLICATE", "PROMOTED", "REJECTED", "HELD"}
                        or (child["promoted_claim_id"] is not None
                            and (not isinstance(child["promoted_claim_id"], str)
                                 or not _STUDIO_REF.fullmatch(child["promoted_claim_id"])))):
                    raise ValueError("STUDIO_PASSAGE_CLAIM_ROW_INVALID")
                prev_claim = child["id"]
                claims.append({"id": child["id"], "status": child["status"],
                               "promoted_claim_id": child["promoted_claim_id"]})
            if len(result) < limit:
                result.append({"statement_candidate_id": row["id"], "status": row["status"],
                               "claim_candidates": claims})
        more = len(rows) > limit
        return {"contract_version": "studio-passage-candidates-v1",
                "private_only": True, "publication_authority": False,
                "rights_clearance": False, "review_authority": False,
                "collection_id": collection_id, "content_id": content_id,
                "source_id": record["source_id"], "rights_status": record["rights_status"],
                "passage_id": passage_id, "selector_type": record["selector_type"],
                "candidates": result, "has_more": more,
                "next_after_id": result[-1]["statement_candidate_id"] if more else None}

    def list_collection_captures(
        self, *, collection_id: str, content_id: str,
        limit: int = 20, after_id: str | None = None,
    ) -> dict[str, Any]:
        """Collection membership-bound, paginated Capture navigation; hashes only.

        The query selects no Capture body, title, URL, provider headers,
        private metadata or archive/purge receipts. The source existence flag
        is a DB reference check, not rights or reviewer authority.
        """
        if any(not isinstance(ref, str) or not _STUDIO_REF.fullmatch(ref)
               for ref in (collection_id, content_id)):
            raise ValueError("STUDIO_CAPTURE_COLLECTION_REF_INVALID")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            raise ValueError("STUDIO_CAPTURE_COLLECTION_LIMIT_INVALID")
        if after_id is not None and (not isinstance(after_id, str) or not _STUDIO_REF.fullmatch(after_id)):
            raise ValueError("STUDIO_CAPTURE_COLLECTION_CURSOR_INVALID")
        raw = self.run("""
            SELECT json_build_object(
                'collection_id', member.collection_id,
                'content_id', content.id, 'source_id', content.source_id,
                'source_exists', source.id IS NOT NULL,
                'collection_state', collection.status,
                'rights_status', content.rights_status,
                'processing_status', content.processing_status,
                'captures', (
                    SELECT coalesce(json_agg(row_to_json(item) ORDER BY item.id), '[]'::json)
                    FROM (
                        SELECT capture.id, capture.content_sha256,
                               capture.observed_at, capture.status,
                               capture.archive_status
                        FROM content_capture capture
                        WHERE capture.content_id=content.id
                          AND capture.id > :'after_id'
                        ORDER BY capture.id
                        LIMIT :'row_limit'::integer
                    ) item
                )
            )::text
            FROM research_collection_content member
            JOIN research_collection collection ON collection.id=member.collection_id
            JOIN content_item content ON content.id=member.content_id
            LEFT JOIN source source ON source.id=content.source_id
            WHERE member.collection_id=:'collection_id'
              AND member.content_id=:'content_id'
              AND member.status='INCLUDED';
        """, collection_id=collection_id, content_id=content_id,
            after_id=after_id or "", row_limit=limit + 1)
        if not raw:
            raise ValueError("STUDIO_CAPTURE_COLLECTION_MEMBER_NOT_FOUND")
        try:
            record = json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError("STUDIO_CAPTURE_COLLECTION_RESULT_INVALID") from None
        if (not isinstance(record, dict)
                or record.get("collection_id") != collection_id
                or record.get("content_id") != content_id
                or record.get("collection_state") not in {"PAUSED", "ACTIVE", "ARCHIVED"}
                or not isinstance(record.get("source_exists"), bool)
                or not isinstance(record.get("rights_status"), str)
                or not isinstance(record.get("processing_status"), str)
                or not isinstance(record.get("captures"), list)):
            raise ValueError("STUDIO_CAPTURE_COLLECTION_SCOPE_INVALID")
        source_id = record.get("source_id")
        if (source_id is not None and
                (not isinstance(source_id, str) or not _STUDIO_REF.fullmatch(source_id))):
            raise ValueError("STUDIO_CAPTURE_COLLECTION_SOURCE_INVALID")
        if bool(source_id) != record["source_exists"]:
            raise ValueError("STUDIO_CAPTURE_COLLECTION_SOURCE_INVALID")
        rows = record["captures"]
        if len(rows) > limit + 1:
            raise ValueError("STUDIO_CAPTURE_COLLECTION_PAGE_INVALID")
        selected: list[dict[str, str]] = []
        previous_id = after_id or ""
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "id", "content_sha256", "observed_at", "status", "archive_status",
            }:
                raise ValueError("STUDIO_CAPTURE_COLLECTION_ROW_INVALID")
            capture_id, digest = row["id"], row["content_sha256"]
            if (not isinstance(capture_id, str) or not _STUDIO_REF.fullmatch(capture_id)
                    or capture_id <= previous_id or not isinstance(digest, str)
                    or not _CAPTURE_SHA.fullmatch(digest)
                    or row["status"] not in _CAPTURE_STATES
                    or row["archive_status"] not in _ARCHIVE_STATES):
                raise ValueError("STUDIO_CAPTURE_COLLECTION_ROW_INVALID")
            observed = row["observed_at"]
            try:
                when = datetime.fromisoformat(observed)
            except (TypeError, ValueError):
                raise ValueError("STUDIO_CAPTURE_COLLECTION_TIME_INVALID") from None
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("STUDIO_CAPTURE_COLLECTION_TIME_INVALID")
            previous_id = capture_id
            if len(selected) < limit:
                selected.append({
                    "id": capture_id, "content_sha256": digest,
                    "observed_at": observed, "status": row["status"],
                    "archive_status": row["archive_status"],
                })
        has_more = len(rows) > limit
        return {
            "contract_version": "studio-collection-captures-v1",
            "private_only": True, "publication_authority": False,
            "rights_clearance": False, "capture_authorized": False,
            "collection_id": collection_id, "content_id": content_id,
            "source_id": source_id, "source_exists": record["source_exists"],
            "collection_state": record["collection_state"],
            "rights_status": record["rights_status"],
            "processing_status": record["processing_status"],
            "captures": selected, "has_more": has_more,
            "next_after_id": selected[-1]["id"] if has_more else None,
        }

    def list_passage_selectors(self, capture_id: str, *, limit: int, after_id: str | None) -> list[dict[str, Any]]:
        """Select only locator metadata; never transfer private passage text to the API."""
        raw = self.run(
            """
            SELECT json_build_object(
                'id', id, 'content_id', content_id, 'capture_id', capture_id,
                'canonical_segment_id', canonical_segment_id,
                'selector_type', selector_type, 'text_sha256', text_sha256,
                'start_char', start_char, 'end_char', end_char,
                'page_start', page_start, 'page_end', page_end
            )::text
            FROM passage
            WHERE capture_id=:'capture_id' AND id > :'after_id'
            ORDER BY id
            LIMIT :'row_limit'::integer;
            """,
            capture_id=capture_id,
            after_id=after_id or "",
            row_limit=limit + 1,
        )
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def read_candidate_media_selector(
        self, *, content_id: str, statement_candidate_id: str, passage_id: str,
    ) -> dict[str, Any] | None:
        """Require a persisted Candidate→Passage→canonical Segment join, no raw words."""
        raw = self.run(
            """
            SELECT json_build_object(
                'statement_candidate_id', candidate.id,
                'candidate_content_id', candidate.content_id,
                'candidate_status', candidate.status,
                'passage_id', passage.id,
                'passage_content_id', passage.content_id,
                'passage_capture_id', passage.capture_id,
                'selector_type', passage.selector_type,
                'text_sha256', passage.text_sha256,
                'passage_segment_id', passage.canonical_segment_id,
                'segment_id', segment.id,
                'segment_content_id', segment.content_id,
                'segment_index', segment.segment_index,
                'start_ms', segment.start_ms,
                'end_ms', segment.end_ms,
                'transcript_status', segment.transcript_status,
                'publication_blocked', segment.publication_blocked
            )::text
            FROM statement_candidate candidate
            JOIN statement_candidate_passage link
              ON link.statement_candidate_id=candidate.id
             AND link.content_id=candidate.content_id
            JOIN passage ON passage.id=link.passage_id
                        AND passage.content_id=link.content_id
            JOIN canonical_transcript_segment segment
              ON segment.id=passage.canonical_segment_id
             AND segment.content_id=passage.content_id
            WHERE candidate.id=:'statement_candidate_id'
              AND candidate.content_id=:'content_id'
              AND passage.id=:'passage_id'
              AND passage.selector_type='MEDIA_SEGMENT_REF'
              AND passage.capture_id IS NULL
            LIMIT 1;
            """,
            content_id=content_id, statement_candidate_id=statement_candidate_id,
            passage_id=passage_id,
        )
        return json.loads(raw) if raw else None


class _StudioCandidateReader(_StudioReadOnlyDb, CandidateMatchingStore):
    pass


class _StudioQueueReader(_StudioReadOnlyDb, StudioOperatorQueues):
    def list_discovery_inbox(
        self, *, collection_id: str, limit: int = 20, after_id: str | None = None,
    ) -> dict[str, object]:
        """Render only current, collection-scoped persisted Discovery metadata.

        This is deliberately a read operation. The local bearer token confers
        no review identity, capture permission, triage write or publication role.
        """
        return DiscoveryInboxWorkflow(self).list_rows(
            collection_id=collection_id, limit=limit, after_id=after_id,
        )


class _CorpusReader(Protocol):
    def search(self, request: Any) -> list[Any]: ...


class _CaptureReader(Protocol):
    def find_capture(self, content_id: str, content_sha256: str) -> dict[str, Any] | None: ...
    def list_passage_selectors(self, capture_id: str, *, limit: int, after_id: str | None) -> list[dict[str, Any]]: ...
    def read_candidate_media_selector(self, *, content_id: str, statement_candidate_id: str, passage_id: str) -> dict[str, Any] | None: ...
    def list_collection_captures(self, *, collection_id: str, content_id: str, limit: int, after_id: str | None) -> dict[str, Any]: ...
    def list_collection_passage_candidates(self, *, collection_id: str, content_id: str, passage_id: str, limit: int, after_id: str | None) -> dict[str, Any]: ...


class _CandidateReader(Protocol):
    def get_run(self, run_id: str) -> dict[str, Any] | None: ...
    def load_results(self, run_id: str) -> tuple[dict[str, Any], ...]: ...

class _QueueReader(Protocol):
    def list_collections(self, *, limit: int, after_id: str | None) -> dict[str, object]: ...
    def list_discovery(self, *, limit: int, after_id: str | None) -> dict[str, object]: ...
    def list_discovery_inbox(self, *, collection_id: str, limit: int, after_id: str | None) -> dict[str, object]: ...
    def inspect_discovery(self, *, collection_id: str, hit_id: str) -> dict[str, object]: ...
    def inspect_discovery_triage(self, *, collection_id: str, hit_id: str, limit: int, after_revision: int) -> dict[str, object]: ...
    def list_collection_members(self, *, collection_id: str, limit: int, after_id: str | None) -> dict[str, object]: ...
    def inspect_collection_member(self, *, collection_id: str, content_id: str, limit: int, after_claim_id: str | None) -> dict[str, object]: ...
    def inspect_claim_provenance(self, *, collection_id: str, content_id: str, claim_id: str, limit: int, after_id: str | None) -> dict[str, object]: ...


@dataclass(frozen=True)
class StudioLocalReaders:
    corpus: _CorpusReader
    captures: _CaptureReader
    candidates: _CandidateReader
    queues: _QueueReader | None = None


def _fields(body: dict[str, Any], *, required: set[str], optional: set[str] | None = None) -> None:
    allowed = required | (optional or set())
    if body.keys() & required != required or body.keys() - allowed:
        raise ValueError("STUDIO_LOCAL_REQUEST_FIELDS_INVALID")


def _dispatch(readers: StudioLocalReaders, path: str, body: dict[str, Any]) -> dict[str, object]:
    if path == "/v1/corpus/search":
        _fields(body, required={"query"}, optional={
            "kinds", "source_id", "collection_id", "person_id", "topic_id", "event_id",
            "status", "claim_type", "check_worthy", "from_at", "to_at", "limit",
        })
        kinds = body.get("kinds", [])
        if not isinstance(kinds, list) or len(kinds) > 10 or any(not isinstance(k, str) for k in kinds):
            raise ValueError("STUDIO_LOCAL_KINDS_INVALID")
        receipt = search_private_corpus(
            readers.corpus,
            query=body["query"],
            kinds=tuple(kinds),
            source_id=body.get("source_id"),
            collection_id=body.get("collection_id"),
            person_id=body.get("person_id"),
            topic_id=body.get("topic_id"),
            event_id=body.get("event_id"),
            status=body.get("status"),
            claim_type=body.get("claim_type"),
            check_worthy=body.get("check_worthy"),
            from_at=body.get("from_at"),
            to_at=body.get("to_at"),
            limit=body.get("limit", 20),
        )
        return receipt.to_dict()
    if path == "/v1/capture/compare":
        _fields(body, required={"content_id", "earlier_hash", "later_hash"})
        return inspect_capture_versions(readers.captures, **body, include_selector_diff=True)
    if path == "/v1/capture/passages":
        _fields(body, required={"content_id", "capture_hash"}, optional={"limit", "after_id"})
        return inspect_capture_passage_selectors(readers.captures, **body)
    if path == "/v1/collections/captures":
        _fields(body, required={"collection_id", "content_id"}, optional={"limit", "after_id"})
        return readers.captures.list_collection_captures(**body)
    if path == "/v1/collections/passage-candidates":
        _fields(body, required={"collection_id", "content_id", "passage_id"}, optional={"limit", "after_id"})
        return readers.captures.list_collection_passage_candidates(**body)
    if path == "/v1/media/segment":
        _fields(body, required={"content_id", "statement_candidate_id", "passage_id"})
        return inspect_candidate_media_selector(readers.captures, **body)
    if path == "/v1/candidate/matches":
        _fields(body, required={"run_id", "claim_candidate_id"})
        return inspect_candidate_match_run(readers.candidates, **body)
    if path in {"/v1/collections/list", "/v1/discovery/list"}:
        _fields(body, required=set(), optional={"limit", "after_id"})
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        if path == "/v1/collections/list":
            return readers.queues.list_collections(**body)
        return readers.queues.list_discovery(**body)
    if path == "/v1/discovery/inspect":
        _fields(body, required={"collection_id", "hit_id"})
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        return readers.queues.inspect_discovery(**body)
    if path == "/v1/discovery/triage-history":
        _fields(body, required={"collection_id", "hit_id"}, optional={"limit", "after_revision"})
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        return readers.queues.inspect_discovery_triage(**body)
    if path == "/v1/discovery/inbox":
        _fields(body, required={"collection_id"}, optional={"limit", "after_id"})
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        return readers.queues.list_discovery_inbox(**body)
    if path in {"/v1/collections/members", "/v1/collections/member", "/v1/collections/claim-provenance"}:
        if readers.queues is None:
            raise RuntimeError("STUDIO_LOCAL_QUEUES_UNAVAILABLE")
        if path == "/v1/collections/members":
            _fields(body, required={"collection_id"}, optional={"limit", "after_id"})
            return readers.queues.list_collection_members(**body)
        if path == "/v1/collections/claim-provenance":
            _fields(
                body, required={"collection_id", "content_id", "claim_id"},
                optional={"limit", "after_id"},
            )
            return readers.queues.inspect_claim_provenance(**body)
        _fields(
            body, required={"collection_id", "content_id"},
            optional={"limit", "after_claim_id"},
        )
        return readers.queues.inspect_collection_member(**body)
    raise ValueError("STUDIO_LOCAL_PATH_NOT_ALLOWED")


def load_private_token(path: Path) -> str:
    """Refuse absent, symlinked, non-owner, group-readable or invalid token files."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    if path.is_symlink():
        raise ValueError("STUDIO_LOCAL_TOKEN_SYMLINK_FORBIDDEN")
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or not 64 <= info.st_size <= 129
        ):
            raise ValueError("STUDIO_LOCAL_TOKEN_FILE_UNSAFE")
        token = os.read(fd, 130).decode("ascii").strip()
        if not _TOKEN_HEX.fullmatch(token):
            raise ValueError("STUDIO_LOCAL_TOKEN_INVALID")
        return token
    finally:
        os.close(fd)


class StudioLoopbackServer(HTTPServer):
    allow_reuse_address = False

    def __init__(self, port: int, readers: StudioLocalReaders, token: str):
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("STUDIO_LOCAL_PORT_INVALID")
        if not isinstance(token, str) or not _TOKEN_HEX.fullmatch(token):
            raise ValueError("STUDIO_LOCAL_TOKEN_INVALID")
        self.readers = readers
        self.token = token
        super().__init__(("127.0.0.1", port), StudioLocalHandler)


class StudioLocalHandler(BaseHTTPRequestHandler):
    server: StudioLoopbackServer
    protocol_version = "HTTP/1.0"

    def setup(self) -> None:
        # A local misbehaving client must not stall the sole read-only listener.
        self.request.settimeout(4.0)
        super().setup()

    def log_message(self, fmt: str, *args: object) -> None:
        # Never log tokens, query strings, request bodies, client-controlled paths.
        return

    def _reply(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(encoded)
            except OSError:
                pass

    def _login_page(self) -> None:
        nonce = secrets.token_hex(16)
        encoded = render_studio_login_page(nonce)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(encoded)

    def _allowed_client(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        expected = f"127.0.0.1:{self.server.server_port}"
        if hosts != [expected] or self.client_address[0] != "127.0.0.1":
            return False
        origins = self.headers.get_all("Origin", [])
        if origins and origins != [f"http://{expected}"]:
            return False
        if self.headers.get("Cookie") or self.headers.get("Transfer-Encoding"):
            return False
        return True

    def _authorized(self) -> bool:
        values = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.server.token
        if len(values) != 1 or len(values[0]) > 140:
            return False
        return hmac.compare_digest(values[0], expected)

    def _process(self) -> None:
        if not self._allowed_client():
            self._reply(403, {"error": "STUDIO_LOCAL_ORIGIN_OR_HOST_REFUSED"})
            return
        if self.command == "GET" and self.path == "/":
            self._login_page()
            return
        if not self._authorized():
            self._reply(401, {"error": "STUDIO_LOCAL_AUTH_REQUIRED"})
            return
        if self.command != "POST":
            self._reply(405, {"error": "STUDIO_LOCAL_METHOD_NOT_ALLOWED"})
            return
        if self.path not in _ALLOWED_PATHS:
            self._reply(404, {"error": "STUDIO_LOCAL_PATH_NOT_ALLOWED"})
            return
        if self.headers.get_all("Content-Type", []) != ["application/json"]:
            self._reply(415, {"error": "STUDIO_LOCAL_JSON_REQUIRED"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (
            len(lengths) != 1 or len(lengths[0]) > 5
            or not lengths[0].isascii() or not lengths[0].isdigit()
        ):
            self._reply(400, {"error": "STUDIO_LOCAL_CONTENT_LENGTH_INVALID"})
            return
        length = int(lengths[0])
        if not 1 <= length <= STUDIO_LOCAL_MAX_BODY_BYTES:
            self._reply(413, {"error": "STUDIO_LOCAL_BODY_LIMIT"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("STUDIO_LOCAL_OBJECT_REQUIRED")
            response = _dispatch(self.server.readers, self.path, payload)
            self._reply(200, {"contract_version": STUDIO_LOCAL_API_VERSION, "data": response})
        except (ValueError, TypeError, UnicodeError):
            self._reply(422, {"error": "STUDIO_LOCAL_REQUEST_OR_DATA_INVALID"})
        except Exception:
            self._reply(503, {"error": "STUDIO_LOCAL_BACKEND_UNAVAILABLE"})

    do_POST = _process
    do_GET = _process
    do_HEAD = _process
    do_PUT = _process
    do_PATCH = _process
    do_DELETE = _process
    do_OPTIONS = _process


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Studio loopback API; never run behind an edge proxy")
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18777)
    args = parser.parse_args(argv)
    try:
        token = load_private_token(args.token_file)
        readers = StudioLocalReaders(
            corpus=_StudioCorpusReader(), captures=_StudioCaptureReader(),
            candidates=_StudioCandidateReader(), queues=_StudioQueueReader(),
        )
        with StudioLoopbackServer(args.port, readers, token) as server:
            print(f"Studio local API ready on 127.0.0.1:{server.server_port} (read-only)", flush=True)
            server.serve_forever(poll_interval=0.2)
    except (OSError, ValueError, UnicodeError):
        print("STUDIO_LOCAL_STARTUP_REFUSED", flush=True)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
