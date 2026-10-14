"""DP-438: isolated, opt-in first-class public Person read model.

The caller supplies private Person/role snapshots and *separate*, current reviewed
decisions. Neither a private roster entry nor an attributable Statement is enough
to publish an identity. The only join source is a validated, published v3 bundle.
There is deliberately no database reader, HTTP route or v2 integration here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.public_schema import (
    PUBLIC_STATEMENT_SCHEMA_VERSION,
    _public_route_slug,
    validate_public_bundle,
)


PUBLIC_PERSON_SCHEMA_VERSION = "dichiarazioni-pubbliche-public-v3-person-opt-in"

_PERSON_FIELDS = frozenset({
    "person_id", "slug", "display_name", "disambiguator", "entity_version",
    "profile_scope", "privacy_policy_ref", "sensitive_policy_ref",
})
_IDENTITY_DECISION_FIELDS = frozenset({
    "person_id", "revision", "status", "person_sha256", "identity_review_id",
    "publication_review_id", "privacy_review_status", "sensitive_review_status",
    "privacy_policy_ref", "sensitive_policy_ref",
})
_ROLE_FIELDS = frozenset({
    "role_id", "person_id", "role_version", "label", "organization",
    "valid_from", "valid_to", "source_ref", "source_url",
})
_ROLE_DECISION_FIELDS = frozenset({
    "role_id", "person_id", "revision", "status", "role_sha256", "review_event_id",
})
_STABLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def person_snapshot_sha256(person: Mapping[str, Any]) -> str:
    """Canonical decision binding; callers must hash the *whole* reviewed snapshot."""
    return _fingerprint(_valid_person(person))


def role_snapshot_sha256(role: Mapping[str, Any]) -> str:
    return _fingerprint(_valid_role(role))


def _fields(value: Any, expected: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError("unexpected or missing private projection fields")
    return dict(value)


def _string(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > limit:
        raise ValueError("invalid public text")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("invalid control character")
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise ValueError("invalid stable identifier")
    return value


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("invalid date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must be canonical ISO")
    return parsed


def _valid_person(value: Any) -> dict[str, Any]:
    row = _fields(value, _PERSON_FIELDS)
    _id(row["person_id"])
    if not isinstance(row["slug"], str) or len(row["slug"]) > 120 or not _SLUG.fullmatch(row["slug"]):
        raise ValueError("invalid public slug")
    _string(row["display_name"])
    if row["disambiguator"] is not None:
        _string(row["disambiguator"])
    _id(row["entity_version"])
    if row["profile_scope"] not in ("PUBLIC_ROLE", "PUBLIC_INTEREST"):
        raise ValueError("private profile scope")
    _string(row["privacy_policy_ref"], limit=100)
    _string(row["sensitive_policy_ref"], limit=100)
    return row


def _valid_role(value: Any) -> dict[str, Any]:
    row = _fields(value, _ROLE_FIELDS)
    for field in ("role_id", "person_id", "role_version", "source_ref"):
        _id(row[field])
    _string(row["label"])
    if row["organization"] is not None:
        _string(row["organization"])
    start = _date(row["valid_from"])
    if row["valid_to"] is not None and _date(row["valid_to"]) < start:
        raise ValueError("role ends before it starts")
    url = row["source_url"]
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("invalid role source URL")
    split = urlsplit(url)
    if split.scheme != "https" or not split.hostname or split.username or split.password:
        raise ValueError("role source must be public HTTPS")
    return row


def _current_decisions(
    rows: Iterable[Mapping[str, Any]], *, key: str, fields: frozenset[str],
) -> dict[str, dict[str, Any]]:
    """A corrupt/ambiguous history holds the subject; last revision can revoke."""
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get(key), str):
            continue
        grouped[row[key]].append(row)
    result: dict[str, dict[str, Any]] = {}
    for identifier, candidates in grouped.items():
        try:
            parsed = [_fields(candidate, fields) for candidate in candidates]
            for decision in parsed:
                _id(decision[key])
                if type(decision["revision"]) is not int or decision["revision"] < 1:
                    raise ValueError("invalid decision revision")
                if decision["status"] not in ("APPROVED", "HELD", "REVOKED"):
                    raise ValueError("invalid decision status")
                for field in fields:
                    if field.endswith("_sha256") and (
                        not isinstance(decision[field], str) or not _SHA.fullmatch(decision[field])
                    ):
                        raise ValueError("invalid decision binding")
                for field in fields & {"identity_review_id", "publication_review_id", "review_event_id"}:
                    _id(decision[field])
            revisions = [item["revision"] for item in parsed]
            if len(set(revisions)) != len(revisions):
                raise ValueError("duplicate decision revision")
            for review_field in ("identity_review_id", "publication_review_id", "review_event_id"):
                if review_field in fields and len({item[review_field] for item in parsed}) != len(parsed):
                    raise ValueError("review event reused after decision revision")
            result[identifier] = max(parsed, key=lambda item: item["revision"])
        except (TypeError, ValueError, StopIteration):
            # A malformed revocation must not expose an earlier approval.
            continue
    return result


def _without_reused_review_events(
    decisions: dict[str, dict[str, Any]], *, review_fields: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """One review event must not authorize two independently reviewed subjects."""
    owners: dict[str, set[str]] = defaultdict(set)
    for identifier, decision in decisions.items():
        for field in review_fields:
            owners[decision[field]].add(identifier)
    conflicted = {identifier for identifiers in owners.values() if len(identifiers) > 1
                  for identifier in identifiers}
    return {identifier: decision for identifier, decision in decisions.items()
            if identifier not in conflicted}


def _identity_approved(row: dict[str, Any], decision: dict[str, Any] | None) -> bool:
    return bool(
        decision and decision["status"] == "APPROVED"
        and decision["privacy_review_status"] == "APPROVED"
        and decision["sensitive_review_status"] == "APPROVED"
        and decision["privacy_policy_ref"] == row["privacy_policy_ref"]
        and decision["sensitive_policy_ref"] == row["sensitive_policy_ref"]
        and decision["identity_review_id"] != decision["publication_review_id"]
        and isinstance(decision["person_sha256"], str)
        and _SHA.fullmatch(decision["person_sha256"])
        and decision["person_sha256"] == person_snapshot_sha256(row)
    )


def _approved_roles(
    person_id: str,
    roles: Mapping[str, list[Mapping[str, Any]]],
    decisions: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for candidates in roles.values():
        if len(candidates) != 1:
            continue
        try:
            role = _valid_role(candidates[0])
            if role["person_id"] != person_id:
                continue
            decision = decisions.get(role["role_id"])
            if not decision or decision["person_id"] != person_id or decision["status"] != "APPROVED":
                continue
            if not isinstance(decision["role_sha256"], str) or not _SHA.fullmatch(decision["role_sha256"]):
                continue
            if decision["role_sha256"] != role_snapshot_sha256(role):
                continue
            public.append({
                "role_id": role["role_id"], "label": role["label"],
                "organization": role["organization"], "valid_from": role["valid_from"],
                "valid_to": role["valid_to"], "source_ref": role["source_ref"],
                "source_url": role["source_url"],
            })
        except (KeyError, TypeError, ValueError):
            continue
    public.sort(key=lambda item: (item["valid_from"], item["role_id"]))
    return public


def _role_at(roles: list[dict[str, Any]], when: str) -> dict[str, Any] | None:
    # Two independently approved overlapping roles are still ambiguous as the
    # *one* source-time label. Never guess which title the source implies.
    matches = [role for role in roles if role["valid_from"] <= when and (
        role["valid_to"] is None or when <= role["valid_to"]
    )]
    return dict(matches[0]) if len(matches) == 1 else None


def build_public_people_v3(
    private_people: Iterable[Mapping[str, Any]],
    identity_decisions: Iterable[Mapping[str, Any]],
    private_roles: Iterable[Mapping[str, Any]],
    role_decisions: Iterable[Mapping[str, Any]],
    *,
    public_bundle: dict[str, Any],
    current_public_dataset_sha256: str,
    allow_public_person_v3: bool = False,
) -> dict[str, Any]:
    """Create only approved public identities from the independently current v3 snapshot.

    The current fingerprint MUST be supplied by a separate public release
    authority, never calculated by this function from its own input bundle.
    Valid historical v3 snapshots are not proof that source rights persist.
    """
    if allow_public_person_v3 is not True:
        raise ValueError("PublicPerson v3 requires explicit opt-in")
    # Keep an independent candidate before validation; private roster/role
    # inputs can be lazy iterables whose callbacks mutate their shared source.
    # Validation and the subsequent Person join must use the same snapshot.
    public_bundle = copy.deepcopy(public_bundle)
    if public_bundle.get("schema_version") != PUBLIC_STATEMENT_SCHEMA_VERSION:
        raise ValueError("PublicPerson v3 requires a published Statement v3 bundle")
    validate_public_bundle(public_bundle, allow_statement_v3=True)
    if (not isinstance(current_public_dataset_sha256, str)
            or not _SHA.fullmatch(current_public_dataset_sha256)
            or public_bundle["dataset_sha256"] != current_public_dataset_sha256):
        raise ValueError("PublicPerson v3 requires current published Statement fingerprint")

    identities = _without_reused_review_events(
        _current_decisions(identity_decisions, key="person_id", fields=_IDENTITY_DECISION_FIELDS),
        review_fields=("identity_review_id", "publication_review_id"),
    )
    role_reviews = _without_reused_review_events(
        _current_decisions(role_decisions, key="role_id", fields=_ROLE_DECISION_FIELDS),
        review_fields=("review_event_id",),
    )
    identity_events = {
        decision[field] for decision in identities.values()
        for field in ("identity_review_id", "publication_review_id")
    }
    role_reviews = {
        role_id: decision for role_id, decision in role_reviews.items()
        if decision["review_event_id"] not in identity_events
    }
    roster: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in private_people:
        if isinstance(row, Mapping) and isinstance(row.get("person_id"), str):
            roster[row["person_id"]].append(row)
    all_roles: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for role in private_roles:
        if isinstance(role, Mapping) and isinstance(role.get("role_id"), str):
            all_roles[role["role_id"]].append(role)

    approved: list[dict[str, Any]] = []
    for person_id, candidates in roster.items():
        if len(candidates) != 1:
            continue
        try:
            person = _valid_person(candidates[0])
            if not _identity_approved(person, identities.get(person_id)):
                continue
            roles = _approved_roles(person_id, all_roles, role_reviews)
            memberships = []
            for statement in public_bundle["statements"]:
                if statement["person_id"] != person_id:
                    continue
                # Reported/criticized quotation and irony are not independently
                # established expressions of the recorded Person's position.
                if not statement["endorsed"] or statement["speech_act"] not in ("DIRECT_ASSERTION", "OPINION"):
                    continue
                memberships.append({
                    "statement_id": statement["statement_id"],
                    # Use the same slug grammar as the validated v3 bundle's
                    # canonical Statement route, never a Person-local guess.
                    "statement_route": (
                        f"/dichiarazioni/{_public_route_slug(statement['statement_id'], field='statement_id')}/"
                    ),
                    "version_id": statement["version_id"],
                    "statement_date": statement["statement_date"],
                    "content_id": statement["content_id"],
                    "source_title": statement["source_title"],
                    "source_url": statement["source_url"],
                    "source_version": statement["source_version"],
                    "source_kind": statement["source_kind"],
                    # Copy the public-only locator: this Person read model's
                    # fingerprint must bind the exact approved source span,
                    # even if a caller later mutates the input bundle.
                    "locator": dict(statement["locator"]),
                    "original_text": statement["original_text"],
                    "language": statement["language"],
                    "quote_sha256": statement["quote_sha256"],
                    "source_sha256": statement["source_sha256"],
                    "speech_act": statement["speech_act"],
                    "finding_id": statement["finding_id"],
                    "role_at_statement": _role_at(roles, statement["statement_date"]),
                })
            memberships.sort(key=lambda item: (item["statement_date"], item["statement_id"]), reverse=True)
            approved.append({
                "person_id": person_id, "slug": person["slug"],
                "route": f"/persone/{person['slug']}/",
                "display_name": person["display_name"],
                "disambiguator": person["disambiguator"],
                "entity_version": person["entity_version"],
                "profile_scope": person["profile_scope"],
                "status": "PUBLISHED", "roles": roles, "statements": memberships,
            })
        except (KeyError, TypeError, ValueError):
            continue

    # IDs and slugs share the public lookup namespace. A slug that equals a
    # *different* Person's ID is as ambiguous as two identical public slugs;
    # withhold all affected subjects instead of resolving by iteration order.
    identifier_owners: dict[str, set[str]] = defaultdict(set)
    for person in approved:
        identifier_owners[person["person_id"]].add(person["person_id"])
        identifier_owners[person["slug"]].add(person["person_id"])
    conflicted_person_ids = {
        person_id for owners in identifier_owners.values() if len(owners) > 1
        for person_id in owners
    }
    # Only identities still eligible for publication participate in the
    # homonym check. An already-withheld alias collision must not hide an
    # unrelated approved, zero-Statement Person with the same display name.
    unambiguous_ids = [person for person in approved
                       if person["person_id"] not in conflicted_person_ids]
    name_counts: dict[str, int] = defaultdict(int)
    for person in unambiguous_ids:
        name_counts[person["display_name"].casefold()] += 1
    ambiguous_names = {
        name for name, count in name_counts.items() if count > 1 and any(
            person["display_name"].casefold() == name and person["disambiguator"] is None
            for person in unambiguous_ids
        )
    }
    visible = [person for person in unambiguous_ids
               if person["display_name"].casefold() not in ambiguous_names]
    visible.sort(key=lambda item: (item["display_name"].casefold(), item["person_id"]))
    return {
        "schema_version": PUBLIC_PERSON_SCHEMA_VERSION,
        "people": visible,
        "dataset_sha256": _fingerprint(visible),
    }


def get_public_person_v3(collection: Mapping[str, Any], identifier: str) -> dict[str, Any] | None:
    """Private, revoked and unknown IDs share the same generic unavailable result."""
    if collection.get("schema_version") != PUBLIC_PERSON_SCHEMA_VERSION:
        raise ValueError("unrecognized public Person collection")
    return next((person for person in collection["people"] if identifier in (
        person["person_id"], person["slug"]
    )), None)


__all__ = [
    "PUBLIC_PERSON_SCHEMA_VERSION", "person_snapshot_sha256", "role_snapshot_sha256",
    "build_public_people_v3", "get_public_person_v3",
]
