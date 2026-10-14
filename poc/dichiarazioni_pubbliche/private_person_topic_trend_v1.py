"""Private DP-439 month-to-month visibility changes across two pinned releases.

Count only *approved public* Person × Topic intersections already materialized
by the canonical join. Changes compare two historical read-model inventories;
they do not assert a publication, rights-revocation or opinion-change *event*
on the printed original's month, nor grant current publication permission.
No public v3 route, raw text, names, URLs, or private roster are emitted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

from .private_person_topic_temporal_v1 import _month, prepare_temporal_preview
from .public_person_topic_v3 import filter_public_person_topic_v3

VERSION = "dp439-private-person-topic-monthly-change-v1"
MAX_SNAPSHOT_BYTES = 4_000_000
MAX_WINDOW_MONTHS = 120


def _detached_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    """Freeze untrusted Mapping exactly once before any pin/read-model access."""
    if not isinstance(value, Mapping):
        raise ValueError("TREND_SNAPSHOT_INVALID")
    try:
        material = json.dumps(value, ensure_ascii=True, allow_nan=False)
        if len(material) > MAX_SNAPSHOT_BYTES:
            raise ValueError("TREND_SNAPSHOT_TOO_LARGE")
        frozen = json.loads(material)
        if type(frozen) is not dict:
            raise ValueError("TREND_SNAPSHOT_INVALID")
        return frozen
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("TREND_SNAPSHOT_INVALID") from exc


def _month_serial(month: str) -> int:
    year, number = (int(part) for part in month.split("-"))
    return year * 12 + number - 1


def _months(start: int, stop: int) -> list[str]:
    if stop - start >= MAX_WINDOW_MONTHS:
        raise ValueError("TREND_WINDOW_TOO_LARGE")
    return [
        f"{index // 12:04d}-{index % 12 + 1:02d}"
        for index in range(stop, start - 1, -1)
    ]


def _pinned_rows(
    *,
    snapshot: dict[str, Any],
    expected_join: str,
    expected_statement: str,
    expected_people: str,
    as_of: date,
    person_id: str | None,
    topic_id: str | None,
) -> tuple[
    dict[tuple[str, str, str, str], str],
    dict[tuple[str, str], tuple[str, str, str, str, str]],
]:
    # Crucially, the temporal preview checks every joined row for original
    # source-date validity, SHA pins and UTC creation before the requested day,
    # even when the caller's Person/Topic filters would hide an invalid row.
    prepare_temporal_preview(
        read_model=snapshot,
        expected_join_sha256=expected_join,
        expected_statement_sha256=expected_statement,
        expected_people_sha256=expected_people,
        as_of=as_of,
        allow_offline_preview=True,
    )
    all_rows = filter_public_person_topic_v3(
        snapshot,
        expected_dataset_sha256=expected_join,
    )
    selected = filter_public_person_topic_v3(
        snapshot,
        expected_dataset_sha256=expected_join,
        person_id=person_id,
        topic_id=topic_id,
    )
    all_entries: dict[tuple[str, str, str, str], str] = {}
    originals: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
    try:
        # Check immutable identity even for a row excluded by the query facet;
        # a changed Person ID cannot evade version-coherence checks merely
        # because the caller selected the old or new Person ID.
        for row in all_rows["data"]:
            statement = row["statement"]
            original_key = (row["statement_id"], row["version_id"])
            fingerprint = (
                row["statement_date"],
                row["person_id"],
                statement["source"]["content_id"],
                statement["source"]["sha256"],
                statement["original"]["quote_sha256"],
            )
            if (
                not all(
                    type(part) is str and part for part in (*original_key, *fingerprint)
                )
                or statement["person"]["id"] != row["person_id"]
                or statement["statement_date"] != row["statement_date"]
                or (
                    original_key in originals and originals[original_key] != fingerprint
                )
            ):
                raise ValueError("TREND_ORIGINAL_IDENTITY_DRIFT")
            originals[original_key] = fingerprint
            intersection = (*original_key, row["person_id"], row["topic_id"])
            if intersection in all_entries:
                raise ValueError("TREND_DUPLICATE_INTERSECTION")
            all_entries[intersection] = row["statement_date"][:7]
        selected_keys = {
            (row["statement_id"], row["version_id"], row["person_id"], row["topic_id"])
            for row in selected["data"]
        }
        if not selected_keys <= all_entries.keys():
            raise ValueError("TREND_SNAPSHOT_INVALID")
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("TREND_SNAPSHOT_INVALID") from exc
    return {key: all_entries[key] for key in selected_keys}, originals


def _snapshot_instant(snapshot: Mapping[str, Any]) -> datetime:
    # The join inherits the source projection's generated_at: a lower bound,
    # not proof of the actual Person × Topic JOIN creation time.
    try:
        instant = datetime.fromisoformat(
            snapshot["generated_at"].replace("Z", "+00:00")
        )
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError
        return instant.astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise ValueError("TREND_SNAPSHOT_INVALID") from exc


def _created_at_receipt(value: str, *, as_of: date) -> datetime:
    """Require separately authenticated creation time for the JOIN release."""
    try:
        if type(value) is not str or len(value) > 40:
            raise ValueError
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError
        utc = instant.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("TREND_CREATION_RECEIPT_INVALID") from exc
    if utc.date() > as_of:
        raise ValueError("TREND_SNAPSHOT_IN_FUTURE")
    return utc


def inspect_private_person_topic_monthly_changes(
    *,
    earlier_read_model: Mapping[str, Any],
    later_read_model: Mapping[str, Any],
    expected_earlier_join_sha256: str,
    expected_earlier_statement_sha256: str,
    expected_earlier_people_sha256: str,
    expected_later_join_sha256: str,
    expected_later_statement_sha256: str,
    expected_later_people_sha256: str,
    earlier_as_of: date,
    later_as_of: date,
    earlier_snapshot_created_at: str,
    later_snapshot_created_at: str,
    allow_offline_review: bool = False,
    person_id: str | None = None,
    topic_id: str | None = None,
    first_month: str | None = None,
    last_month: str | None = None,
) -> dict[str, Any]:
    """Compare dated snapshot visibility using six external release SHA pins.

    `as_of` values mean end of UTC day. An original's source month is *not*
    the time a membership was approved, removed, or published. An absent
    intersection in either snapshot proves neither absent private records nor
    that the source was historically unspoken. The caller must independently
    authenticate both release SHA triplets, each actual JOIN creation receipt,
    and source rights/currentness. The embedded `generated_at` alone is the
    Statement source creation time, which may predate the JOIN materialization.
    """
    if allow_offline_review is not True:
        raise ValueError("TREND_EXPLICIT_OPT_IN_REQUIRED")
    if (
        type(earlier_as_of) is not date
        or type(later_as_of) is not date
        or not 2000 <= earlier_as_of.year <= 2200
        or not 2000 <= later_as_of.year <= 2200
        or earlier_as_of > later_as_of
    ):
        raise ValueError("TREND_DATE_ORDER_INVALID")

    # Never reuse the caller's (potentially mutable or noncooperative)
    # Mapping after freezing. In particular, separate digest verification and
    # comparison reads must see identical detached source bytes.
    before = _detached_snapshot(earlier_read_model)
    after = _detached_snapshot(later_read_model)
    low = _month(first_month, as_of=later_as_of)
    high = _month(last_month, as_of=later_as_of)
    if low is not None and high is not None and low > high:
        raise ValueError("TREND_WINDOW_INVALID")
    if low is not None and high is not None:
        _months(_month_serial(low), _month_serial(high))

    before_rows, before_originals = _pinned_rows(
        snapshot=before,
        expected_join=expected_earlier_join_sha256,
        expected_statement=expected_earlier_statement_sha256,
        expected_people=expected_earlier_people_sha256,
        as_of=earlier_as_of,
        person_id=person_id,
        topic_id=topic_id,
    )
    after_rows, after_originals = _pinned_rows(
        snapshot=after,
        expected_join=expected_later_join_sha256,
        expected_statement=expected_later_statement_sha256,
        expected_people=expected_later_people_sha256,
        as_of=later_as_of,
        person_id=person_id,
        topic_id=topic_id,
    )
    earlier_created = _created_at_receipt(
        earlier_snapshot_created_at, as_of=earlier_as_of
    )
    later_created = _created_at_receipt(later_snapshot_created_at, as_of=later_as_of)
    if earlier_created < _snapshot_instant(before) or later_created < _snapshot_instant(
        after
    ):
        raise ValueError("TREND_CREATION_PROVENANCE_INVALID")
    if earlier_created > later_created:
        raise ValueError("TREND_SNAPSHOT_ORDER_INVALID")

    # A stable Statement ID+version cannot silently change person, original
    # date, source or quote between two independently pinned releases.
    for key in before_originals.keys() & after_originals.keys():
        if before_originals[key] != after_originals[key]:
            raise ValueError("TREND_ORIGINAL_IDENTITY_DRIFT")

    def in_window(items: dict[tuple[str, str, str, str], str]):
        return {
            key: month
            for key, month in items.items()
            if (low is None or month >= low) and (high is None or month <= high)
        }

    before_rows = in_window(before_rows)
    after_rows = in_window(after_rows)
    before_keys = set(before_rows)
    after_keys = set(after_rows)
    new_keys = after_keys - before_keys
    retired_keys = before_keys - after_keys
    before_original_keys = {key[:2] for key in before_keys}
    after_original_keys = {key[:2] for key in after_keys}
    new_originals = after_original_keys - before_original_keys
    retired_originals = before_original_keys - after_original_keys

    available_months = sorted(set(before_rows.values()) | set(after_rows.values()))
    if available_months:
        start = _month_serial(low or available_months[0])
        stop = _month_serial(high or available_months[-1])
        months = _months(start, stop)
    else:
        months = []
    periods: list[dict[str, int | str]] = []
    for month in months:
        baseline = {key for key, value in before_rows.items() if value == month}
        comparison = {key for key, value in after_rows.items() if value == month}
        acquired = comparison - baseline
        removed = baseline - comparison
        baseline_originals = {key[:2] for key in baseline}
        comparison_originals = {key[:2] for key in comparison}
        periods.append(
            {
                "month": month,
                "earlier_record_count": len(baseline),
                "later_record_count": len(comparison),
                "earlier_unique_statement_count": len(baseline_originals),
                "later_unique_statement_count": len(comparison_originals),
                "net_intersection_change": len(comparison) - len(baseline),
                "newly_visible_intersection_count": len(acquired),
                "no_longer_visible_intersection_count": len(removed),
                "newly_visible_unique_statement_count": len(
                    comparison_originals - baseline_originals
                ),
                "no_longer_visible_unique_statement_count": len(
                    baseline_originals - comparison_originals
                ),
            }
        )
    return {
        "schema_version": VERSION,
        "status": (
            "NO_MATCH"
            if not (before_keys or after_keys)
            else "CHANGED"
            if new_keys or retired_keys
            else "UNCHANGED"
        ),
        "earlier_as_of": earlier_as_of.isoformat(),
        "later_as_of": later_as_of.isoformat(),
        "earlier_join_dataset_sha256": expected_earlier_join_sha256,
        "later_join_dataset_sha256": expected_later_join_sha256,
        "source_date_meaning": "ORIGINAL_STATEMENT_DATE_NOT_INGESTION_OR_ARCHIVE",
        "change_time_meaning": "VISIBILITY_DIFFERENCE_BETWEEN_SNAPSHOTS_NOT_EVENT_DATE",
        "earlier_record_count": len(before_keys),
        "later_record_count": len(after_keys),
        "earlier_unique_statement_count": len(before_original_keys),
        "later_unique_statement_count": len(after_original_keys),
        "newly_visible_intersection_count": len(new_keys),
        "no_longer_visible_intersection_count": len(retired_keys),
        "newly_visible_unique_statement_count": len(new_originals),
        "no_longer_visible_unique_statement_count": len(retired_originals),
        "periods": periods,
        "absence_of_statements_established": False,
        "publication_authority": False,
        "rights_authority": False,
        "provider_calls": 0,
    }


__all__ = ["inspect_private_person_topic_monthly_changes"]
