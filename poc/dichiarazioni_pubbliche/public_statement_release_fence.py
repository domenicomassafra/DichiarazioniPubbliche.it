"""#704: decide whether a v3 release may be served while a challenge is open.

The challenge ledger is append-only and keeps every historical target, so the
inventory is read as bounded, resumable pages. A release is clear only when
none of the versions it serves carries an open challenge; history that the
release no longer serves can never turn a public read into an outage.
"""
from __future__ import annotations

import json
from typing import Callable, Iterable

_INVENTORY_PAGE = 500
_MAX_INVENTORY_PAGES = 100_000


def _page_size(limit: object) -> int:
    if type(limit) is not int or not 1 <= limit <= _INVENTORY_PAGE:
        raise ValueError("DP468_CHALLENGE_INVENTORY_LIMIT_INVALID")
    return limit


def _valid_target(target: object) -> bool:
    return (type(target) is tuple and len(target) == 2
            and all(isinstance(value, str) and value for value in target))


def public_release_clear(
    store: object, published: object,
    *, page_size: int = _INVENTORY_PAGE,
    may_serve_cleared: Callable[[tuple[str, str]], bool] | None = None,
) -> bool | None:
    """True when no challenged version of this exact release is still open.

    Only targets that are part of the release under evaluation are opened for
    their hold chain; the rest of the append-only history is skipped page by
    page, so lifetime growth cannot block a public read.

    A version whose chain is clear may still be unreservable here: when the
    caller passes ``may_serve_cleared``, a challenged version of this release
    must also be provably newer than the challenge that named it. Otherwise a
    release that predates the challenge (a rotated or stale pointer) would be
    served as if its version had been cleared.
    """
    if (not isinstance(published, frozenset)
            or any(not _valid_target(target) for target in published)):
        return None
    try:
        after = None
        for _ in range(_MAX_INVENTORY_PAGES):
            # The page itself must be bounded: an oversized page would be
            # rejected as corrupt instead of being paginated through.
            limit = _page_size(page_size)  # bounded page, never the raw argument
            page = store.challenged_statements(after=after, limit=limit)
            served = [target for target in page if target in published]
            for target in served:
                if store.current_hold(*target) is not False:
                    return False
                if (may_serve_cleared is not None
                        and may_serve_cleared(target) is not True):
                    return False
            if len(page) < limit:
                return True
            after = page[-1]
        return None
    except Exception:
        return None


def challenge_opened_at(store: object, statement_id: str, version_id: str) -> str | None:
    """Most recent challenge instant for an exact target, or None."""
    raw = store.run(
        """
        SELECT COALESCE(row_to_json(opened_row)::text, '')
        FROM (
            SELECT MAX(r.created_at) AS opened_at
            FROM public_statement_challenge_request r
            WHERE r.statement_id = :'statement_id'
              AND r.version_id = :'version_id'
        ) opened_row;
        """,
        statement_id=statement_id, version_id=version_id,
    )
    if not raw:
        return None
    parsed = json.loads(raw)
    # The aggregate may arrive wrapped in its JSON array or as one row.
    if isinstance(parsed, list):
        if len(parsed) != 1:
            return None
        parsed = parsed[0]
    opened = parsed.get("opened_at") if isinstance(parsed, dict) else None
    return opened if isinstance(opened, str) and opened else None
