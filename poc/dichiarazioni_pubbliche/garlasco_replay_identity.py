"""DP-214 read-only, metadata-only replay identity comparison.

Run with two separate authoritative read-only database snapshots. This audits
equality/immutability of supplied identities; it does not attest that either
snapshot came from the MiniPC, authorize rights, or certify DP-214 completion.
The older count-only garlasco_tracer replay receipt is structural only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

COLLECTION = "research:garlasco"
SNAPSHOT_VERSION = "garlasco-replay-identity-v1"
MAX_FILE_BYTES = 262_144
MAX_CAPTURES = 5_000
_KEYS = frozenset({"collection_id", "content_ids", "claim_ids", "public_finding_ids", "captures"})
_CAPTURE_KEYS = frozenset({"id", "content_id", "content_sha256"})
_IDENTITY = re.compile(r"^[a-z][a-z0-9_.:-]{0,199}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ReplayIdentityError(ValueError):
    """Invalid/untrustworthy snapshot; no stable receipt can be issued."""


@dataclass(frozen=True)
class ReplayIdentityReceipt:
    stable: bool
    blockers: tuple[str, ...]
    before_sha256: str
    after_sha256: str
    new_capture_ids: tuple[str, ...]
    content_count: int
    claim_count: int
    public_publish_count: int
    version: str = SNAPSHOT_VERSION


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReplayIdentityError("REPLAY_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def load_replay_snapshot(path: Path) -> dict[str, object]:
    """Read only a small local export; reject duplicate keys, including nested."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ReplayIdentityError("REPLAY_FILE_TOO_LARGE")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except ReplayIdentityError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise ReplayIdentityError("REPLAY_FILE_INVALID") from None
    _validate(value)
    return value


def _ids(value: object, name: str, maximum: int, *, prefix: str = "") -> tuple[str, ...]:
    if (not isinstance(value, list)
            or any(not isinstance(x, str) or not _IDENTITY.fullmatch(x)
                   or (prefix and not x.startswith(prefix)) for x in value)):
        raise ReplayIdentityError(f"REPLAY_{name}_INVALID")
    if len(set(value)) != len(value):
        raise ReplayIdentityError(f"REPLAY_{name}_DUPLICATE")
    if len(value) > maximum:
        raise ReplayIdentityError(f"REPLAY_{name}_INVALID")
    return tuple(value)


def _validate(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ReplayIdentityError("REPLAY_SNAPSHOT_SCHEMA_INVALID")
    if value["collection_id"] != COLLECTION:
        raise ReplayIdentityError("REPLAY_COLLECTION_INVALID")
    content = _ids(value["content_ids"], "CONTENT_IDS", 100)
    _ids(value["claim_ids"], "CLAIM_IDS", 30, prefix="claim:garlasco:")
    _ids(value["public_finding_ids"], "PUBLIC_FINDING_IDS", 100_000)
    captures = value["captures"]
    if not isinstance(captures, list) or len(captures) > MAX_CAPTURES:
        raise ReplayIdentityError("REPLAY_CAPTURES_INVALID")
    capture_ids: set[str] = set()
    for row in captures:
        if not isinstance(row, dict) or set(row) != _CAPTURE_KEYS:
            raise ReplayIdentityError("REPLAY_CAPTURE_SCHEMA_INVALID")
        capture_id = row["id"]
        if not isinstance(capture_id, str) or not _IDENTITY.fullmatch(capture_id):
            raise ReplayIdentityError("REPLAY_CAPTURE_ID_INVALID")
        if capture_id in capture_ids:
            raise ReplayIdentityError("REPLAY_CAPTURE_ID_DUPLICATE")
        capture_ids.add(capture_id)
        if row["content_id"] not in content:
            raise ReplayIdentityError("REPLAY_CAPTURE_CONTENT_OUT_OF_SCOPE")
        digest = row["content_sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ReplayIdentityError("REPLAY_CAPTURE_SHA256_INVALID")


def _sha256(value: Mapping[str, object]) -> str:
    canonical = {
        "collection_id": value["collection_id"],
        "content_ids": sorted(value["content_ids"]),
        "claim_ids": sorted(value["claim_ids"]),
        "public_finding_ids": sorted(value["public_finding_ids"]),
        "captures": sorted(value["captures"], key=lambda capture: capture["id"]),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def audit_replay_snapshots(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    authorized_new_capture_ids: Sequence[str] = (),
) -> ReplayIdentityReceipt:
    """Check exact identity stability, including equal-count substitutions.

    A new Capture is permitted only by exact caller-declared ID; never infer
    authorization to capture from this check. Persisted Capture IDs cannot
    disappear, mutate content identity, or be silently rebound to other bytes.
    """
    _validate(before)
    _validate(after)
    authorizations = tuple(authorized_new_capture_ids)
    if (len(authorizations) > MAX_CAPTURES
            or any(not isinstance(x, str) or not _IDENTITY.fullmatch(x) for x in authorizations)
            or len(set(authorizations)) != len(authorizations)):
        raise ReplayIdentityError("REPLAY_AUTHORIZED_CAPTURE_IDS_INVALID")
    blockers = []
    if set(before["content_ids"]) != set(after["content_ids"]):
        blockers.append("LOGICAL_CONTENT_SET_CHANGED")
    if set(before["claim_ids"]) != set(after["claim_ids"]):
        blockers.append("BASELINE_CLAIM_SET_CHANGED")
    if set(before["public_finding_ids"]) != set(after["public_finding_ids"]):
        blockers.append("PUBLIC_PUBLISH_SET_CHANGED")
    previous = {row["id"]: row for row in before["captures"]}
    current = {row["id"]: row for row in after["captures"]}
    removed = set(previous) - set(current)
    if removed:
        blockers.append("EXISTING_CAPTURE_REMOVED")
    if any(current[key] != previous[key] for key in set(previous) & set(current)):
        blockers.append("EXISTING_CAPTURE_MUTATED")
    new_ids = set(current) - set(previous)
    if new_ids - set(authorizations):
        blockers.append("UNAUTHORIZED_NEW_CAPTURE")
    if set(authorizations) - new_ids:
        blockers.append("AUTHORIZED_CAPTURE_NOT_FOUND_OR_PREEXISTING")
    return ReplayIdentityReceipt(
        stable=not blockers,
        blockers=tuple(blockers),
        before_sha256=_sha256(before),
        after_sha256=_sha256(after),
        new_capture_ids=tuple(sorted(new_ids)),
        content_count=len(after["content_ids"]),
        claim_count=len(after["claim_ids"]),
        public_publish_count=len(after["public_finding_ids"]),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two read-only Garlasco replay identity snapshots")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--new-capture-id", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        receipt = audit_replay_snapshots(
            load_replay_snapshot(args.before),
            load_replay_snapshot(args.after),
            authorized_new_capture_ids=args.new_capture_id,
        )
        print(json.dumps(asdict(receipt), sort_keys=True))
        return 0 if receipt.stable else 2
    except ReplayIdentityError as error:
        print(json.dumps({"stable": False, "reason": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
