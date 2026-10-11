"""DP-439: precomputed, opt-in Person × Topic original-opinion intersection.

Consumes only a previously governed public Statement v3 release, approved
first-class PublicPerson read model and a separately attested topic-membership
decision manifest. No text/LLM matching, HTTP route, rights grant or writer.
The caller must obtain *all three* current fingerprints from an independently
authenticated release authority. Rehashing untrusted inputs proves nothing.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from dichiarazioni_pubbliche.public_api import list_public_statements_v3
from dichiarazioni_pubbliche.public_person_v3 import PUBLIC_PERSON_SCHEMA_VERSION
from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_STATEMENT_SCHEMA_VERSION, _public_route_slug, validate_public_bundle,
)

PERSON_TOPIC_SCHEMA_VERSION = "public-person-topic-v3-opt-in"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


@dataclass(frozen=True)
class ReviewedTopicMembership:
    """External private membership decision; never serialized to a public card.

    A new immutable revision replaces an earlier decision for exactly one
    (Statement, Statement version, Topic) key. Its independently adjudicated
    topic identity and public original/content hashes must match the release.
    """

    membership_id: str
    revision: int
    status: str  # APPROVED, HELD, REVOKED
    review_event_id: str
    statement_id: str
    version_id: str
    person_id: str
    topic_id: str
    topic_entity_version: str
    content_id: str
    quote_sha256: str
    source_sha256: str
    public_dataset_sha256: str
    reviewed_at: str
    valid_until: str


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _sha(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OverflowError, TypeError, ValueError):
        return None


def _decision_material(decisions: tuple[ReviewedTopicMembership, ...]) -> list[dict]:
    if not isinstance(decisions, tuple) or any(
        not isinstance(item, ReviewedTopicMembership) for item in decisions
    ):
        raise ValueError("DP439_EXTERNAL_MEMBERSHIP_CONTRACT_INVALID")
    material = [asdict(item) for item in decisions]
    return sorted(material, key=lambda item: (
        item["statement_id"], item["version_id"], item["topic_id"], item["revision"],
    ))


def membership_manifest_sha256(decisions: tuple[ReviewedTopicMembership, ...]) -> str:
    """Deterministic bytes for an upstream *private* authorization manifest.

    A caller-calculated hash is NOT an authorization. The separately supplied
    expected current hash must be authenticated out of band by a release owner.
    Never include the private manifest hash in public output: a change in an
    unapproved private membership must not alter public observable content.
    """
    return _digest(_decision_material(decisions))


def _public_material(model: Mapping[str, Any]) -> dict:
    return {
        key: model[key] for key in (
            "schema_version", "source_dataset_sha256", "person_dataset_sha256",
            "generated_at", "coverage_note", "status", "result_count", "data",
        )
    }


def build_public_person_topic_v3(
    *,
    public_bundle: dict[str, Any],
    public_people: dict[str, Any],
    membership_decisions: tuple[ReviewedTopicMembership, ...],
    current_public_dataset_sha256: str,
    current_people_dataset_sha256: str,
    current_membership_manifest_sha256: str,
    now: datetime,
    coverage_note: str,
    allow_person_topic_v3: bool = False,
) -> dict[str, Any]:
    """Materialize source-bound approved original OPINION intersections offline.

    Historic approved-but-now-withdrawn Statements, privately held memberships,
    unavailable identities and stale Topic versions all omit their intersections.
    The only visible count is that of published intersections.
    """
    if allow_person_topic_v3 is not True:
        raise ValueError("DP439_EXPLICIT_V3_OPT_IN_REQUIRED")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("DP439_AWARE_NOW_REQUIRED")
    if (not isinstance(coverage_note, str) or coverage_note != coverage_note.strip()
        or not 1 <= len(coverage_note) <= 400 or any(ord(c) < 32 for c in coverage_note)):
        raise ValueError("DP439_SCOPE_DISCLOSURE_REQUIRED")
    if not all(map(_sha, (current_public_dataset_sha256,
                          current_people_dataset_sha256,
                          current_membership_manifest_sha256))):
        raise ValueError("DP439_CURRENT_RELEASE_AUTHORITY_MISSING")
    if not isinstance(public_bundle, dict) or not isinstance(public_people, dict):
        raise ValueError("DP439_INPUT_INVALID")

    # Snapshot before inspecting potentially mutable callers' collections.
    snapshot = copy.deepcopy(public_bundle)
    people_snapshot = copy.deepcopy(public_people)
    events = _decision_material(membership_decisions)
    if _digest(events) != current_membership_manifest_sha256:
        raise ValueError("DP439_STALE_MEMBERSHIP_MANIFEST")
    if snapshot.get("schema_version") != PUBLIC_STATEMENT_SCHEMA_VERSION:
        raise ValueError("DP439_REQUIRES_PUBLIC_ORIGINAL_V3")
    validate_public_bundle(snapshot, allow_statement_v3=True)
    if snapshot["dataset_sha256"] != current_public_dataset_sha256:
        raise ValueError("DP439_STALE_STATEMENT_RELEASE")
    snapshot_at = _instant(snapshot.get("generated_at"))
    now_utc = now.astimezone(timezone.utc)
    if snapshot_at is None or snapshot_at > now_utc:
        raise ValueError("DP439_SNAPSHOT_TIMESTAMP_INVALID")

    if (people_snapshot.get("schema_version") != PUBLIC_PERSON_SCHEMA_VERSION
        or not isinstance(people_snapshot.get("people"), list)
        or not _sha(people_snapshot.get("dataset_sha256"))
        or _digest(people_snapshot["people"]) != people_snapshot["dataset_sha256"]
        or people_snapshot["dataset_sha256"] != current_people_dataset_sha256):
        raise ValueError("DP439_STALE_OR_UNAUTHORIZED_PUBLIC_PERSON_RELEASE")
    people: dict[str, dict] = {}
    person_routes: set[str] = set()
    for person in people_snapshot["people"]:
        if (not isinstance(person, dict)
            or not _id(person.get("person_id"))
            or not isinstance(person.get("slug"), str)
            or not _SLUG.fullmatch(person["slug"])
            or person.get("route") != f"/persone/{person['slug']}/"
            or person.get("status") != "PUBLISHED"
            or not isinstance(person.get("statements"), list)
            or person["person_id"] in people or person["route"] in person_routes):
            raise ValueError("DP439_PUBLIC_PERSON_IDENTITY_INVALID")
        people[person["person_id"]] = person
        person_routes.add(person["route"])
    topics = {
        row["topic_id"]: row for row in snapshot["topics"]
    }  # Already schema-validated first-class public Topic identities.
    statement_rows = {
        (row["statement_id"], row["version_id"]): row
        for row in list_public_statements_v3(snapshot, allow_statement_v3=True)["data"]
    }
    # Membership needs its own independent review decision. Reusing a
    # previously accepted source/rights/identity/Topic event does not give
    # that event a second, unreviewed topic-classification meaning.
    preexisting_review_ids = {
        review_id for topic in snapshot["topics"]
        for review_id in topic["review_event_ids"]
    } | {
        review_id for statement in snapshot["statements"]
        for review_id in statement["review_provenance"].values()
    }
    # Refuse duplicated or recycled review IDs, conflicting revisions and
    # reused membership ID subjects instead of picking approval by row order.
    revision_sets: dict[tuple[str, str, str], list[dict]] = {}
    review_ids: set[str] = set()
    membership_owners: dict[str, tuple[str, str, str]] = {}
    for item in events:
        key = (item["statement_id"], item["version_id"], item["topic_id"])
        values = (
            item["membership_id"], item["review_event_id"],
            item["statement_id"], item["version_id"], item["person_id"],
            item["topic_id"], item["topic_entity_version"], item["content_id"],
        )
        if (not all(map(_id, values))
            or not all(map(_sha, (item["quote_sha256"], item["source_sha256"],
                                  item["public_dataset_sha256"])))
            or type(item["revision"]) is not int or item["revision"] < 1
            or item["status"] not in {"APPROVED", "HELD", "REVOKED"}
            or _instant(item["reviewed_at"]) is None
            or _instant(item["valid_until"]) is None
            or item["review_event_id"] in preexisting_review_ids
            or item["review_event_id"] in review_ids
            or (item["membership_id"] in membership_owners
                and membership_owners[item["membership_id"]] != key)):
            raise ValueError("DP439_AMBIGUOUS_OR_INVALID_TOPIC_MEMBERSHIP_REVIEW")
        review_ids.add(item["review_event_id"])
        membership_owners[item["membership_id"]] = key
        revision_sets.setdefault(key, []).append(item)

    approved: list[dict] = []
    for key, history in revision_sets.items():
        if len({entry["revision"] for entry in history}) != len(history):
            raise ValueError("DP439_AMBIGUOUS_TOPIC_REVISION")
        decision = max(history, key=lambda entry: entry["revision"])
        if decision["status"] != "APPROVED":
            continue
        attested_at, valid_until = (_instant(decision["reviewed_at"]),
                                    _instant(decision["valid_until"]))
        if (attested_at is None or valid_until is None or not
            (snapshot_at <= attested_at <= now_utc < valid_until)):
            continue
        statement = statement_rows.get((decision["statement_id"], decision["version_id"]))
        person = people.get(decision["person_id"])
        topic = topics.get(decision["topic_id"])
        if (statement is None or person is None or topic is None
            or decision["public_dataset_sha256"] != snapshot["dataset_sha256"]
            or decision["topic_entity_version"] != topic["entity_version"]
            or statement["person"]["id"] != decision["person_id"]
            or statement["source"]["content_id"] != decision["content_id"]
            or statement["source"]["sha256"] != decision["source_sha256"]
            or statement["original"]["quote_sha256"] != decision["quote_sha256"]
            or statement["speech_act"] != "OPINION"
            or statement["endorsed"] is not True):
            continue
        # Identity was independently approved by the Person v3 pipeline. Its
        # current published membership must also agree with the exact source,
        # preventing alias/name lookup and stale version cross-joins.
        members = [
            row for row in person["statements"]
            if isinstance(row, dict)
            and row.get("statement_id") == decision["statement_id"]
            and row.get("version_id") == decision["version_id"]
            and row.get("content_id") == decision["content_id"]
            and row.get("source_sha256") == decision["source_sha256"]
            and row.get("quote_sha256") == decision["quote_sha256"]
            and row.get("source_version") == statement["source"]["version_id"]
            and row.get("locator") == statement["original"]["locator"]
            and row.get("statement_route") == (
                f"/dichiarazioni/{_public_route_slug(decision['statement_id'], field='statement_id')}/"
            )
        ]
        if len(members) != 1:
            continue
        approved.append({
            "statement_id": decision["statement_id"],
            "version_id": decision["version_id"],
            "statement_route": members[0]["statement_route"],
            "statement_date": statement["statement_date"],
            "person_id": person["person_id"],
            "person_route": person["route"],
            "topic_id": topic["topic_id"],
            "topic_route": f"/temi/{topic['slug']}/",
            "statement": statement,
        })
    approved.sort(key=lambda row: (
        row["statement_date"], row["statement_id"], row["version_id"],
        row["person_id"], row["topic_id"],
    ), reverse=True)
    status = ("READY" if approved else
              "EMPTY_PUBLIC_CORPUS" if not statement_rows else
              "EMPTY_PUBLIC_INTERSECTION")
    material = {
        "schema_version": PERSON_TOPIC_SCHEMA_VERSION,
        "source_dataset_sha256": snapshot["dataset_sha256"],
        "person_dataset_sha256": people_snapshot["dataset_sha256"],
        "generated_at": snapshot["generated_at"],
        "coverage_note": coverage_note,
        "status": status,
        "result_count": len(approved),
        "data": approved,
    }
    return {
        **material, "dataset_sha256": _digest(material),
        "provider_calls": 0,
    }


def filter_public_person_topic_v3(
    read_model: Mapping[str, Any], *, expected_dataset_sha256: str,
    person_id: str | None = None, topic_id: str | None = None,
) -> dict[str, Any]:
    """Filter only pinned precomputed public rows; no private data query."""
    if not _sha(expected_dataset_sha256) or not isinstance(read_model, Mapping):
        raise ValueError("DP439_CURRENT_READ_MODEL_REQUIRED")
    for value in (person_id, topic_id):
        if value is not None and not _id(value):
            raise ValueError("DP439_FILTER_ID_INVALID")
    try:
        if (read_model["schema_version"] != PERSON_TOPIC_SCHEMA_VERSION
            or read_model["dataset_sha256"] != expected_dataset_sha256
            or _digest(_public_material(read_model)) != expected_dataset_sha256
            or read_model["result_count"] != len(read_model["data"])
            or read_model["status"] not in {
                "READY", "EMPTY_PUBLIC_CORPUS", "EMPTY_PUBLIC_INTERSECTION",
            }
            or (bool(read_model["data"]) != (read_model["status"] == "READY"))
            or type(read_model["provider_calls"]) is not int
            or read_model["provider_calls"] != 0):
            raise ValueError("DP439_STALE_OR_TAMPERED_READ_MODEL")
    except (KeyError, TypeError) as exc:
        raise ValueError("DP439_STALE_OR_TAMPERED_READ_MODEL") from exc
    data = [
        copy.deepcopy(row) for row in read_model["data"]
        if (person_id is None or row["person_id"] == person_id)
        and (topic_id is None or row["topic_id"] == topic_id)
    ]
    return {
        "schema_version": PERSON_TOPIC_SCHEMA_VERSION,
        "dataset_sha256": expected_dataset_sha256,
        "source_dataset_sha256": read_model["source_dataset_sha256"],
        "generated_at": read_model["generated_at"],
        "coverage_note": read_model["coverage_note"],
        "status": ("READY" if data else
                   read_model["status"] if not read_model["data"] else "NO_MATCH"),
        "result_count": len(data), "data": data, "provider_calls": 0,
    }


__all__ = [
    "PERSON_TOPIC_SCHEMA_VERSION", "ReviewedTopicMembership",
    "build_public_person_topic_v3", "filter_public_person_topic_v3",
    "membership_manifest_sha256",
]
