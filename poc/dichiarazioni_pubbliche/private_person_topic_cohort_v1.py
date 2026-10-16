"""Private DP-439 multi-release visibility continuity audit.

Read-only, source-date count-only. Detects an intersection that disappears from
one independently pinned JOIN release and reappears in a later JOIN. Such a
reappearance is a *manual review hold*, never a finding of valid reapproval.
Original source dates are not approval, retrieval, withdrawal or event dates.
No person, topic, statement, source, quotation, URL or private ID is returned.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from .private_person_topic_temporal_v1 import _month
from .private_person_topic_trend_v1 import (
    _created_at_receipt,
    _detached_snapshot,
    _pinned_rows,
    _snapshot_instant,
)

VERSION = "dp439-private-person-topic-cohort-continuity-v1"
MIN_RELEASES = 2
MAX_RELEASES = 12
REQUIRED_FIELDS = frozenset(
    {
        "read_model",
        "expected_join_sha256",
        "expected_statement_sha256",
        "expected_people_sha256",
        "as_of",
        "snapshot_created_at",
    }
)


def _frozen_release_descriptors(
    releases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    """Freeze *every* caller-owned join before examining any pins or rows.

    Descriptor subclasses are deliberately refused, and all remaining input
    scalars are exact immutable primitive types. Noncooperative nested JOIN
    mappings are detached through the existing bounded JSON snapshot reader.
    """
    if type(releases) not in (list, tuple) or not (
        MIN_RELEASES <= len(releases) <= MAX_RELEASES
    ):
        raise ValueError("COHORT_RELEASES_INVALID")
    descriptors: list[dict[str, Any]] = []
    models: list[Mapping[str, Any]] = []
    for entry in releases:
        if type(entry) is not dict or entry.keys() != REQUIRED_FIELDS:
            raise ValueError("COHORT_RELEASE_DESCRIPTOR_INVALID")
        if (
            type(entry["as_of"]) is not date
            or not 2000 <= entry["as_of"].year <= 2200
            or any(
                type(entry[key]) is not str
                for key in (
                    "expected_join_sha256",
                    "expected_statement_sha256",
                    "expected_people_sha256",
                    "snapshot_created_at",
                )
            )
        ):
            raise ValueError("COHORT_RELEASE_DESCRIPTOR_INVALID")
        if not isinstance(entry["read_model"], Mapping):
            raise ValueError("COHORT_RELEASE_DESCRIPTOR_INVALID")
        # Freeze ALL primitive owner pins and join-created receipts BEFORE
        # inspecting ANY untrusted read-model. In particular, a malicious
        # earlier payload cannot rewrite a later caller descriptor's expected
        # hash or created-at value while its snapshot is being serialized.
        pinned = {key: entry[key] for key in REQUIRED_FIELDS if key != "read_model"}
        models.append(entry["read_model"])
        descriptors.append(pinned)
    # All snapshots are detached before validation; only these detached
    # snapshots and immutable scalar copies will be used below.
    for pinned, model in zip(descriptors, models, strict=True):
        pinned["read_model"] = _detached_snapshot(model)
    return descriptors


def audit_private_person_topic_cohort(
    *,
    releases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    allow_offline_review: bool = False,
    person_id: str | None = None,
    topic_id: str | None = None,
    first_month: str | None = None,
    last_month: str | None = None,
) -> dict[str, Any]:
    """Inspect an authenticated-owner-pinned release chain, without approval.

    SHA pins and exact UTC JOIN-creation receipts must be authenticated by an
    *external* owner; a caller rehashing mutated data cannot grant authority.
    Historical public membership and actual rights are separate requirements.
    All releases must be ordered chronologically, even for an empty query.
    """
    if allow_offline_review is not True:
        raise ValueError("COHORT_EXPLICIT_OPT_IN_REQUIRED")
    # The canonical public filter accepts isinstance(str). A hostile subclass
    # can override equality so that an actual reapproval appears NO_MATCH and
    # conceals the mandatory manual reappearance hold. Reject subclasses and
    # other non-plain identifiers *before* any expensive external reads.
    if (person_id is not None and type(person_id) is not str) or (
        topic_id is not None and type(topic_id) is not str
    ):
        raise ValueError("COHORT_FILTER_INVALID")
    frozen = _frozen_release_descriptors(releases)
    last_as_of = frozen[-1]["as_of"]
    low = _month(first_month, as_of=last_as_of)
    high = _month(last_month, as_of=last_as_of)
    if low is not None and high is not None and low > high:
        raise ValueError("COHORT_WINDOW_INVALID")

    # Existing trend validator bounds output to 120 source-date months. Here
    # keep the whole multi-release window bounded, not merely each transition.
    from .private_person_topic_trend_v1 import _month_serial

    if (
        low is not None
        and high is not None
        and _month_serial(high) - _month_serial(low) >= 120
    ):
        raise ValueError("COHORT_WINDOW_TOO_LARGE")

    inventories: list[set[tuple[str, str, str, str]]] = []
    originals_global: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
    previous_created = None
    previous_as_of = None
    previous_join = None
    historical_join_hashes: set[str] = set()

    for release in frozen:
        as_of = release["as_of"]
        if previous_as_of is not None and as_of < previous_as_of:
            raise ValueError("COHORT_DATE_ORDER_INVALID")

        # Check the *complete* frozen readmodel even for filtered, empty result
        # sets. Existing DP439 validation proves exact join/source/person SHA,
        # original dates and public membership for each independently pinned
        # release. It also refuses a future source projection.
        entries, originals = _pinned_rows(
            snapshot=release["read_model"],
            expected_join=release["expected_join_sha256"],
            expected_statement=release["expected_statement_sha256"],
            expected_people=release["expected_people_sha256"],
            as_of=as_of,
            person_id=person_id,
            topic_id=topic_id,
        )
        created = _created_at_receipt(release["snapshot_created_at"], as_of=as_of)
        if created < _snapshot_instant(release["read_model"]):
            raise ValueError("COHORT_CREATION_PROVENANCE_INVALID")
        if previous_created is not None and (
            created < previous_created
            or (
                created == previous_created
                and release["expected_join_sha256"] != previous_join
            )
        ):
            raise ValueError("COHORT_CREATION_ORDER_INVALID")

        join = release["expected_join_sha256"]
        if join in historical_join_hashes and join != previous_join:
            raise ValueError("COHORT_RELEASE_REPLAY")
        historical_join_hashes.add(join)
        previous_join = join
        previous_created = created
        previous_as_of = as_of

        for key, fingerprint in originals.items():
            existing = originals_global.setdefault(key, fingerprint)
            if existing != fingerprint:
                raise ValueError("COHORT_ORIGINAL_IDENTITY_DRIFT")
        selected = {
            key
            for key, month in entries.items()
            if (low is None or month >= low) and (high is None or month <= high)
        }
        inventories.append(selected)

    seen_removed: set[tuple[str, str, str, str]] = set()
    seen_originals_removed: set[tuple[str, str]] = set()
    reappeared_all: set[tuple[str, str, str, str]] = set()
    reappeared_originals_all: set[tuple[str, str]] = set()
    transitions: list[dict[str, int | str]] = []
    any_changes = False

    for index, (before, after) in enumerate(
        zip(inventories, inventories[1:], strict=False), start=1
    ):
        newly_visible = after - before
        no_longer_visible = before - after
        old_originals = {key[:2] for key in before}
        new_originals = {key[:2] for key in after}
        original_added = new_originals - old_originals
        original_removed = old_originals - new_originals
        reappeared = newly_visible & seen_removed
        reappeared_originals = original_added & seen_originals_removed
        reappeared_all.update(reappeared)
        reappeared_originals_all.update(reappeared_originals)
        seen_removed.update(no_longer_visible)
        seen_originals_removed.update(original_removed)
        any_changes |= bool(newly_visible or no_longer_visible)
        transitions.append(
            {
                "transition_index": index,
                "added_intersection_count": len(newly_visible),
                "removed_intersection_count": len(no_longer_visible),
                "added_original_count": len(original_added),
                "removed_original_count": len(original_removed),
                "reappeared_intersection_count": len(reappeared),
                "reappeared_original_count": len(reappeared_originals),
            }
        )

    last = inventories[-1]
    any_matches = any(inventories)
    return {
        "schema_version": VERSION,
        "status": (
            "MANUAL_VISIBILITY_RECHECK_REQUIRED"
            if reappeared_all or reappeared_originals_all
            else "NO_MATCH"
            if not any_matches
            else "CHANGED"
            if any_changes
            else "UNCHANGED"
        ),
        "release_count": len(inventories),
        "transition_count": len(transitions),
        "last_record_count": len(last),
        "last_unique_statement_count": len({key[:2] for key in last}),
        "reappeared_intersection_count": len(reappeared_all),
        "reappeared_original_count": len(reappeared_originals_all),
        "transitions": transitions,
        "change_time_meaning": "VISIBILITY_DIFFERENCE_BETWEEN_SNAPSHOTS_NOT_EVENT_DATE",
        "original_date_meaning": "ORIGINAL_STATEMENT_DATE_NOT_ARCHIVE_OR_APPROVAL",
        "external_release_owner_pins_required": True,
        "manual_review_required": bool(reappeared_all or reappeared_originals_all),
        "automatic_approval": False,
        "publication_authority": False,
        "rights_authority": False,
        "absence_of_statements_established": False,
        "provider_calls": 0,
    }


__all__ = ["audit_private_person_topic_cohort"]
