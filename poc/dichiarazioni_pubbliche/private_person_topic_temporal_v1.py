"""Private source-date facets for a separately pinned DP-439 public join.

No route, search index mutation, publication permission or evidence inference.
Month buckets refer exclusively to dates printed on the *original Statement*;
they are not ingestion, archive-added, legal-currentness or rights timestamps.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping

from .public_person_topic_v3 import filter_public_person_topic_v3

VERSION = "dp439-private-person-topic-temporal-v1"
_MONTH = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _month(value: object, *, as_of: date) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not _MONTH.fullmatch(value):
        raise ValueError("TEMPORAL_MONTH_INVALID")
    if value > as_of.strftime("%Y-%m"):
        raise ValueError("TEMPORAL_MONTH_INVALID")
    return value


def prepare_temporal_preview(
    *,
    read_model: Mapping[str, Any],
    expected_join_sha256: str,
    expected_statement_sha256: str,
    expected_people_sha256: str,
    as_of: date,
    allow_offline_preview: bool = False,
    person_id: str | None = None,
    topic_id: str | None = None,
    first_month: str | None = None,
    last_month: str | None = None,
) -> dict[str, Any]:
    """Return bounded count-only temporal facets, never the original text.

    All three SHA pins must come from an authenticated *external* release
    owner. This cannot renew membership or guarantee current source rights.
    """
    if allow_offline_preview is not True:
        raise ValueError("TEMPORAL_EXPLICIT_OPT_IN_REQUIRED")
    if type(as_of) is not date or not 2000 <= as_of.year <= 2200:
        raise ValueError("TEMPORAL_DATE_INVALID")
    if (
        any(
            type(value) is not str or _HASH.fullmatch(value) is None
            for value in (
                expected_join_sha256,
                expected_statement_sha256,
                expected_people_sha256,
            )
        )
        or not isinstance(read_model, Mapping)
        or read_model.get("dataset_sha256") != expected_join_sha256
        or read_model.get("source_dataset_sha256") != expected_statement_sha256
        or read_model.get("person_dataset_sha256") != expected_people_sha256
    ):
        raise ValueError("TEMPORAL_PIN_MISMATCH")
    low, high = _month(first_month, as_of=as_of), _month(last_month, as_of=as_of)
    if low is not None and high is not None and low > high:
        raise ValueError("TEMPORAL_MONTH_INVALID")
    try:
        validated = filter_public_person_topic_v3(
            read_model,
            expected_dataset_sha256=expected_join_sha256,
            person_id=person_id,
            topic_id=topic_id,
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("TEMPORAL_STALE_OR_TAMPERED") from exc

    # A source-date timeline assembled tomorrow cannot be backdated as a
    # historically *available* view today. Its independently pinned UTC
    # projection snapshot must already have existed on the requested as-of day.
    try:
        instant = datetime.fromisoformat(
            validated["generated_at"].replace("Z", "+00:00")
        )
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError
        snapshot_day = instant.astimezone(timezone.utc).date()
    except (TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("TEMPORAL_SNAPSHOT_INVALID") from exc
    if snapshot_day > as_of:
        raise ValueError("TEMPORAL_SNAPSHOT_IN_FUTURE")

    grouped: dict[str, dict[str, Any]] = {}
    unique_keys: set[tuple[str, str]] = set()
    count = 0
    for row in validated["data"]:
        # The source join already verified exact public membership. We still
        # reject a malformed date rather than making up a month or freshness.
        statement_date = row.get("statement_date")
        try:
            if (
                type(statement_date) is not str
                or date.fromisoformat(statement_date).isoformat() != statement_date
                or date.fromisoformat(statement_date) > as_of
            ):
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("TEMPORAL_SOURCE_DATE_INVALID") from exc
        month = statement_date[:7]
        if (low is not None and month < low) or (high is not None and month > high):
            continue
        key = (row["statement_id"], row["version_id"])
        unique_keys.add(key)
        counts = grouped.setdefault(
            month,
            {
                "statement_versions": set(),
                "people": set(),
                "topics": set(),
                "record_count": 0,
            },
        )
        counts["record_count"] += 1
        counts["statement_versions"].add(key)
        counts["people"].add(row["person_id"])
        counts["topics"].add(row["topic_id"])
        count += 1
    periods = [
        {
            "month": month,
            "record_count": data["record_count"],
            "unique_statement_count": len(data["statement_versions"]),
            "public_person_count": len(data["people"]),
            "public_topic_count": len(data["topics"]),
        }
        for month, data in sorted(grouped.items(), reverse=True)
    ]
    if len(periods) > 120:
        raise ValueError("TEMPORAL_WINDOW_TOO_LARGE")
    return {
        "schema_version": VERSION,
        "status": "READY_PRIVATE_PREVIEW" if periods else "NO_MATCH",
        "join_dataset_sha256": expected_join_sha256,
        "source_dataset_sha256": expected_statement_sha256,
        "source_date_meaning": "ORIGINAL_STATEMENT_DATE_NOT_INGESTION_OR_ARCHIVE",
        "record_count": count,
        "unique_statement_count": len(unique_keys),
        "periods": periods,
        "absence_of_statements_established": False,
        "publication_authority": False,
        "rights_authority": False,
        "provider_calls": 0,
    }
