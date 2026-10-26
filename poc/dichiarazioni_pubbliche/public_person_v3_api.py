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
import stat
from urllib.parse import urlsplit
from xml.etree import ElementTree
from xml.etree import ElementTree
from urllib.parse import urlsplit
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HASH = re.compile(r"^[a-f0-9]{64}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_STATEMENT_ROUTE = re.compile(r"^/dichiarazioni/[a-z0-9]+(?:-[a-z0-9]+)*/$")
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


def _pin_sha(pins: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        pins, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf8")).hexdigest()


@lru_cache(maxsize=8)
def _validated_asset(path: str, signature: tuple[int, int, int, int], expected: str,
                     pins_sha: str) -> list[dict[str, Any]]:
    asset = _read(path)
    if not isinstance(asset, dict) or set(asset) != {
        "schema_version", "dataset_sha256", "people", "release_pins_sha256"
    }:
        raise PublicPersonReleaseUnavailable
    people = asset["people"]
    if (asset["schema_version"] != _SCHEMA or asset["dataset_sha256"] != expected
            or asset["release_pins_sha256"] != pins_sha
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
        for statement in person["statements"]:
            route = statement.get("statement_route") if isinstance(statement, dict) else None
            if not isinstance(route, str) or not _STATEMENT_ROUTE.fullmatch(route):
                raise PublicPersonReleaseUnavailable
        ids.add(person["person_id"])
        slugs.add(person["slug"])
    return people


def load_current_public_people_v3() -> tuple[list[dict[str, Any]], str]:
    """Return published identities only when the current release authority agrees."""
    if os.environ.get(ENABLE) != "1":
        raise PublicPersonReleaseUnavailable
    asset_path, pins_path = os.environ.get(API_ASSET), os.environ.get(PINS)
    if not asset_path or not pins_path or asset_path == pins_path:
        raise PublicPersonReleaseUnavailable
    try:
        pins = _read(pins_path)
        if not isinstance(pins, dict) or pins.get("publicationAuthorized") is not True:
            raise PublicPersonReleaseUnavailable
        if pins.get("allowPrivatePersonPreview") is not True:
            raise PublicPersonReleaseUnavailable
        expected = pins.get("personSha256")
        if not isinstance(expected, str) or not _HASH.fullmatch(expected):
            raise PublicPersonReleaseUnavailable
        _expiry(pins.get("validUntil"))
        info = os.stat(asset_path, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
            raise PublicPersonReleaseUnavailable
        signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        people = _validated_asset(asset_path, signature, expected, _pin_sha(pins))
        # Revocation may rotate the authority while asset validation is in progress.
        _expiry(pins.get("validUntil"))
        if _read(pins_path) != pins:
            raise PublicPersonReleaseUnavailable
        return people, expected
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise PublicPersonReleaseUnavailable from exc


def require_v3_compatible_projection(index: Any) -> Any:
    """A current v3 Person release never coexists with v2 published records."""
    if os.environ.get(ENABLE) == "1" and (index.entries or index.records or index.topics):
        from . import public_api as api
        raise api._unavailable()
    return index


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
    if os.environ.get(ENABLE) == "1":
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


def _read_static(root_fd: int, name: str) -> bytes:
    file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root_fd)
    with os.fdopen(file_fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
            raise PublicPersonReleaseUnavailable
        return stream.read(16 * 1024 * 1024 + 1)


def _static_catalog_current(root_fd: int, name: str, people: list[dict[str, Any]]) -> bool:
    """Reject stale search/sitemap after partial identity rotation or withdrawal."""
    expected: dict[tuple[str, str], str] = {}
    for person in people:
        expected[("person", person["route"])] = person["display_name"]
        for statement in person["statements"]:
            expected[("statement", statement["statement_route"])] = (
                f'Dichiarazione di {person["display_name"]}'
            )
    try:
        data = _read_static(root_fd, name)
        if name == "search-index.v1.json":
            records = json.loads(data)
            if not isinstance(records, dict) or not isinstance(records.get("records"), list):
                return False
            found: dict[tuple[str, str], str] = {}
            for record in records["records"]:
                if not isinstance(record, dict) or record.get("kind") not in {"person", "statement"}:
                    return False
                key = (record["kind"], record.get("route"))
                if key in found or not isinstance(key[1], str):
                    return False
                found[key] = record.get("title")
            return found == expected
        if name == "sitemap.xml":
            document = ElementTree.fromstring(data)
            routes = [urlsplit(element.text or "").path for element in document.iter()
                      if element.tag.rsplit("}", 1)[-1] == "loc"]
            relevant = [route for route in routes if route.startswith(("/persone/", "/dichiarazioni/"))]
            return (len(relevant) == len(set(relevant)) and
                    set(relevant) == {route for _, route in expected})
        return True
    except (OSError, ValueError, TypeError, KeyError, IndexError, UnicodeError, ElementTree.ParseError):
        return False


def _static_public_surface_current(parts: tuple[str, ...], root_fd: int,
                                   people: list[dict[str, Any]]) -> bool:
    """Deny stale identity URLs embedded in a rotated search index or sitemap."""
    if parts not in (("search-index.v1.json",), ("sitemap.xml",)):
        return True
    name = parts[0]
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root_fd)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 16 * 1024 * 1024:
            return False
        contents = stream.read(16 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
        if (len(contents) > 16 * 1024 * 1024 or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            return False
    approved = {person["route"]: person for person in people}
    statements = {statement["statement_route"]
                  for person in people for statement in person["statements"]}
    if name == "search-index.v1.json":
        index = json.loads(contents)
        rows = index.get("records") if isinstance(index, dict) else None
        if not isinstance(rows, list):
            return False
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("route"), str):
                return False
            route = row["route"]
            if route in seen:
                return False
            seen.add(route)
            if row.get("kind") == "person":
                subject = approved.get(route)
                if subject is None or row.get("title") != subject["display_name"]:
                    return False
            elif row.get("kind") != "statement" or route not in statements:
                return False
        return True
    xml = ElementTree.fromstring(contents)
    if xml.tag not in ("urlset", "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset"):
        return False
    fixed = {"/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/"}
    allowed = fixed | set(approved) | statements
    for loc in xml.iter():
        if loc.tag.rsplit("}", 1)[-1] != "loc":
            continue
        value = (loc.text or "").strip()
        target = urlsplit(value)
        if (target.scheme or target.netloc) and (
                target.scheme != "https" or target.netloc != "dichiarazionipubbliche.it"):
            return False
        if target.query or target.fragment or target.path not in allowed:
            return False
    return True


_root_marker_cache: dict[tuple[Any, ...], bool] = {}


def static_person_release_current(parts: tuple[str, ...], root_fd: int) -> bool:
    """Bind the pinned static root to current release authority on every request."""
    enabled = os.environ.get(ENABLE) == "1"
    try:
        info = os.stat("public-people.v3.json", dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return not enabled
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
        return False
    if not enabled:
        return False  # A v3 build cannot silently downgrade to an unguarded v2 runtime.
    # Legacy Person aliases are intentionally absent from a v3 build. A stale
    # file at an old path must never reveal a now withheld public identity.
    if len(parts) >= 2 and parts[:2] == ("record", "person"):
        return False
    try:
        people, person_sha = load_current_public_people_v3()
        if len(parts) >= 2 and parts[0] == "persone":
            if parts[1] not in {person["slug"] for person in people}:
                return False
        if len(parts) >= 2 and parts[0] == "dichiarazioni":
            approved_routes = {item["statement_route"].split("/")[2]
                               for person in people for item in person["statements"]}
            if parts[1] not in approved_routes:
                return False
        if not _static_public_surface_current(parts, root_fd, people):
            return False
        pins = _read(os.environ[PINS])
        root = os.fstat(root_fd)
        key = (root.st_dev, root.st_ino, info.st_dev, info.st_ino,
               info.st_size, info.st_mtime_ns, _pin_sha(pins), person_sha)
        cached = _root_marker_cache.get(key)
        if cached is not None:
            return cached and (len(parts) != 1 or
                               _static_catalog_current(root_fd, parts[0], people))
        fd = os.open("public-people.v3.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=root_fd)
        with os.fdopen(fd, "rb") as stream:
            marker = json.load(stream)
            final = os.fstat(stream.fileno())
        result = ((final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) ==
                  (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                  and isinstance(marker, dict)
                  and marker.get("release_pins_sha256") == key[-2]
                  and marker.get("dataset_sha256") == person_sha)
        if len(_root_marker_cache) > 16:
            _root_marker_cache.clear()
        _root_marker_cache[key] = result
        return result and (len(parts) != 1 or _static_catalog_current(root_fd, parts[0], people))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, ElementTree.ParseError, PublicPersonReleaseUnavailable):
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
