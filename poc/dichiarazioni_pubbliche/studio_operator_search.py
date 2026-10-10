"""Read-only private operator corpus search; never a public HTTP/asset endpoint.

The lookup reuses DP-116's persisted PostgreSQL search. Only bounded identifiers
and source references are returned. Snippets, private passages and search terms
are never placed into stdout or error receipts. The operator runs this locally
with the existing private database access, not through Astro's static pages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol

from dichiarazioni_pubbliche.corpus_search import (
    CorpusSearchRequest,
    CorpusSearchResult,
    CorpusSearchStore,
    SEARCH_RESULT_KINDS,
)


STUDIO_OPERATOR_SEARCH_VERSION = "studio-operator-search-v1"
_SAFE_REF = re.compile(r"^[A-Za-z0-9_:/.-]{1,180}$")


class _SearchBackend(Protocol):
    def search(self, request: CorpusSearchRequest) -> list[CorpusSearchResult]: ...


def _ref(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_REF.fullmatch(value):
        raise ValueError("STUDIO_SEARCH_RESULT_REFERENCE_INVALID")
    return value


@dataclass(frozen=True)
class StudioOperatorSearchReceipt:
    query_sha256: str
    result_count: int
    results: tuple[dict[str, str | None], ...]
    contract_version: str = STUDIO_OPERATOR_SEARCH_VERSION
    private_only: bool = True
    publication_authority: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "private_only": self.private_only,
            "publication_authority": self.publication_authority,
            "query_sha256": self.query_sha256,
            "result_count": self.result_count,
            "results": list(self.results),
        }


def search_private_corpus(
    backend: _SearchBackend,
    *,
    query: str,
    kinds: tuple[str, ...] = (),
    collection_id: str | None = None,
    source_id: str | None = None,
    person_id: str | None = None,
    topic_id: str | None = None,
    event_id: str | None = None,
    status: str | None = None,
    claim_type: str | None = None,
    check_worthy: bool | None = None,
    from_at: str | None = None,
    to_at: str | None = None,
    limit: int = 20,
) -> StudioOperatorSearchReceipt:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 128:
        raise ValueError("STUDIO_QUERY_LENGTH_INVALID")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("STUDIO_SEARCH_LIMIT_INVALID")
    if any(kind not in SEARCH_RESULT_KINDS for kind in kinds):
        raise ValueError("STUDIO_SEARCH_KIND_INVALID")
    for value in (collection_id, source_id, person_id, topic_id, event_id, status, claim_type):
        if value is not None:
            _ref(value)
    if check_worthy is not None and not isinstance(check_worthy, bool):
        raise ValueError("STUDIO_SEARCH_CHECK_WORTHY_INVALID")
    if from_at is not None and not isinstance(from_at, str):
        raise ValueError("STUDIO_SEARCH_FROM_AT_INVALID")
    if to_at is not None and not isinstance(to_at, str):
        raise ValueError("STUDIO_SEARCH_TO_AT_INVALID")
    if from_at is not None and len(from_at) > 40 or to_at is not None and len(to_at) > 40:
        raise ValueError("STUDIO_SEARCH_DATE_LIMIT")
    request = CorpusSearchRequest(
        query=query.strip(),
        kinds=kinds,
        collection_id=collection_id,
        source_id=source_id,
        person_id=person_id,
        topic_id=topic_id,
        event_id=event_id,
        status=status,
        claim_type=claim_type,
        check_worthy=check_worthy,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
    )
    try:
        raw_results = backend.search(request)
    except Exception:
        # No raw DB errors, search terms, snippets or credentials in logs.
        raise RuntimeError("STUDIO_PRIVATE_SEARCH_UNAVAILABLE") from None
    if len(raw_results) > limit:
        raise ValueError("STUDIO_SEARCH_BACKEND_LIMIT_BROKEN")
    results: list[dict[str, str | None]] = []
    for row in raw_results:
        if row.kind not in SEARCH_RESULT_KINDS:
            raise ValueError("STUDIO_SEARCH_RESULT_KIND_INVALID")
        results.append({
            "id": _ref(row.id),
            "kind": row.kind,
            "source_id": _ref(row.source_id) if row.source_id else None,
            "content_id": _ref(row.content_id) if row.content_id else None,
            "passage_id": _ref(row.passage_id) if row.passage_id else None,
        })
    return StudioOperatorSearchReceipt(
        query_sha256=hashlib.sha256(query.strip().encode("utf-8")).hexdigest(),
        result_count=len(results),
        results=tuple(results),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator-local, metadata-only private corpus search. No HTTP server."
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--kind", action="append", choices=sorted(SEARCH_RESULT_KINDS), default=[])
    parser.add_argument("--source-id")
    parser.add_argument("--collection-id")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        receipt = search_private_corpus(
            CorpusSearchStore(),
            query=args.query,
            kinds=tuple(args.kind),
            source_id=args.source_id,
            collection_id=args.collection_id,
            limit=args.limit,
        )
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
