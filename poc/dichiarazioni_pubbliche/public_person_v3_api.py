"""Current first-class public Person API readout from the validated static build.

The build verifies source, identity, index and sitemap against independent pins.
The HTTP reader never trusts the self-hash alone: current independent release
pins are mandatory on EVERY request and withdraw an old artifact immediately.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HASH = re.compile(r"^[a-f0-9]{64}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PERSON_KEYS = {
    "person_id", "slug", "route", "display_name", "disambiguator",
    "entity_version", "profile_scope", "status", "roles", "statements",
}
_SCHEMA = "dichiarazioni-pubbliche-public-v3-person-opt-in"
ENABLE = "DICHIARAZIONI_PUBBLICHE_ENABLE_PUBLIC_PERSON_V3"
API_ASSET = "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_API_PATH"
PINS = "DICHIARAZIONI_PUBBLICHE_PUBLIC_PERSON_V3_PINS_PATH"


class PublicPersonReleaseUnavailable(Exception):
    pass


def _read(path: str) -> Any:
    file = Path(path)
    before = file.stat()
    if not file.is_file() or before.st_size > 16 * 1024 * 1024:
        raise PublicPersonReleaseUnavailable
    value = json.loads(file.read_bytes())
    after = file.stat()
    if (before.st_mtime_ns, before.st_size, before.st_ino) != (
        after.st_mtime_ns, after.st_size, after.st_ino
    ):
        raise PublicPersonReleaseUnavailable
    return value


def _expiry(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise PublicPersonReleaseUnavailable
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicPersonReleaseUnavailable from exc
    if instant.tzinfo is None or instant <= datetime.now(timezone.utc):
        raise PublicPersonReleaseUnavailable
    return instant


def load_current_public_people_v3() -> tuple[list[dict[str, Any]], str]:
    """Return published identities only when the current release authority agrees."""
    if os.environ.get(ENABLE) != "1":
        raise PublicPersonReleaseUnavailable
    asset_path, pins_path = os.environ.get(API_ASSET), os.environ.get(PINS)
    if not asset_path or not pins_path or asset_path == pins_path:
        raise PublicPersonReleaseUnavailable
    try:
        pins = _read(pins_path)
        asset = _read(asset_path)
        if not isinstance(pins, dict) or pins.get("publicationAuthorized") is not True:
            raise PublicPersonReleaseUnavailable
        if pins.get("allowPrivatePersonPreview") is not True:
            raise PublicPersonReleaseUnavailable
        expected = pins.get("personSha256")
        if not isinstance(expected, str) or not _HASH.fullmatch(expected):
            raise PublicPersonReleaseUnavailable
        _expiry(pins.get("validUntil"))
        if not isinstance(asset, dict) or set(asset) != {"schema_version", "dataset_sha256", "people"}:
            raise PublicPersonReleaseUnavailable
        people = asset["people"]
        if (asset["schema_version"] != _SCHEMA or asset["dataset_sha256"] != expected
                or not isinstance(people, list) or len(people) > 10000):
            raise PublicPersonReleaseUnavailable
        digest = hashlib.sha256(json.dumps(
            people, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf8")).hexdigest()
        if digest != expected:
            raise PublicPersonReleaseUnavailable
        ids, slugs = set(), set()
        for person in people:
            if (not isinstance(person, dict) or set(person) != _PERSON_KEYS
                    or not isinstance(person["person_id"], str)
                    or not isinstance(person["slug"], str)
                    or not _SLUG.fullmatch(person["slug"])
                    or person["route"] != f'/persone/{person["slug"]}/'
                    or person["status"] != "PUBLISHED"
                    or not isinstance(person["statements"], list)
                    or not isinstance(person["roles"], list)
                    or person["person_id"] in ids or person["slug"] in slugs):
                raise PublicPersonReleaseUnavailable
            ids.add(person["person_id"])
            slugs.add(person["slug"])
        # Revocation may rotate the authority while asset validation is in progress.
        _expiry(pins.get("validUntil"))
        if _read(pins_path) != pins:
            raise PublicPersonReleaseUnavailable
        return people, expected
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise PublicPersonReleaseUnavailable from exc


def legacy_people(index: Any) -> list[dict[str, Any]]:
    """Keep the existing v2 API contract while the new release is disabled."""
    rows = [
        {
            "person_id": person_id,
            "name": person["name"],
            "finding_count": person["finding_count"],
            # Pre-DP-430 `topics` is the deprecated claim-type alias.
            "topics": person["claim_types"],
            "claim_types": person["claim_types"],
            "subject_topic_ids": person["topic_ids"],
        }
        for person_id, person in index.people.items()
    ]
    rows.sort(key=lambda row: row["person_id"])
    return rows


def people_response(index: Any, params: dict[str, str]) -> dict[str, Any]:
    from . import public_api as api
    api.validate_params(params)
    if os.environ.get(ENABLE):
        try:
            people, sha = load_current_public_people_v3()
        except PublicPersonReleaseUnavailable:
            raise api._unavailable() from None
        return api._envelope(index, people, {
            "count": len(people), "link": f"{api.API_BASE_PATH}/people",
            "person_schema_version": _SCHEMA, "person_dataset_sha256": sha,
        })
    people = legacy_people(index)
    return api._envelope(index, people, {
        "count": len(people), "link": f"{api.API_BASE_PATH}/people",
    })


def person_detail(_index: Any, slug: str) -> dict[str, Any]:
    from . import public_api as api
    if os.environ.get(ENABLE) != "1":
        raise api._not_found()
    try:
        people, _ = load_current_public_people_v3()
    except PublicPersonReleaseUnavailable:
        raise api._unavailable() from None
    for person in people:
        if person["slug"] == slug:
            return person
    raise api._not_found()


def static_person_release_current(parts: tuple[str, ...]) -> bool:
    """Deny old static Person paths immediately after independent pin withdrawal."""
    if os.environ.get(ENABLE) != "1":
        return True
    try:
        load_current_public_people_v3()
        return True
    except PublicPersonReleaseUnavailable:
        return False


def optional_person_route(path: str) -> Any:
    """Opt-in detail route while preserving the stable v1 OpenAPI table."""
    match = re.fullmatch(r"/api/v1/people/([a-z0-9]+(?:-[a-z0-9]+)*)", path)
    if match is None:
        return None
    from . import public_api as api
    return (
        api.Route(
            "person-v3", ("GET", "HEAD"), f"{api.API_BASE_PATH}/people/{{slug}}",
            detail=("slug", person_detail, f"{api.API_BASE_PATH}/people/{{value}}"),
        ),
        {"slug": match.group(1)},
    )
