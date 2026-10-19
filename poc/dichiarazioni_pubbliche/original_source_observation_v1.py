"""Private immutable readback of independently observed DP-241 lookup metadata.

Evidence is caller-supplied and therefore never conveys rights, review or
publication authority. The bounded journal intentionally excludes source bodies.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit


VERSION = "dp241-observed-source-recovery-v1"
_CASE = re.compile(r"[a-z0-9][a-z0-9-]{2,79}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PLAN = re.compile(r"original-source-plan:[a-f0-9]{64}\Z")
_RESULTS = {"CONTEXT_LOCATED_HELD", "METADATA_ONLY", "NOT_FOUND", "OUTAGE", "RIGHTS_BLOCKED"}
_FIELDS = {
    "contract_version", "case_id", "plan_id", "timeline_snapshot_id",
    "private_only", "review_authority", "rights_clearance", "publication_authority",
    "external_receipts_independently_verified", "case_question", "exception_question",
    "target", "attempt_cap", "cost_cap_usd", "spent_usd", "attempts", "status",
    "reason_code", "next_action", "reanalysis_required", "root_lineage",
}
_ATTEMPT_FIELDS = {
    "attempt_id", "method_family", "source_family", "lookup_uri", "observed_at",
    "final_uri", "http_status", "source_version_sha256", "selector_type",
    "selector_start", "selector_end", "selector_sha256", "result", "reason_code",
    "rights_basis_uri", "spent_usd", "next_trigger",
}


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode("ascii")).hexdigest()


def _safe_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 512:
        return False
    url = urlsplit(value)
    return (url.scheme == "https" and bool(url.hostname) and url.username is None
            and url.password is None and not url.fragment and url.port is None
            and all(ord(char) >= 32 for char in value))


def _validate(record: object) -> dict[str, object]:
    if not isinstance(record, dict) or set(record) != _FIELDS:
        raise ValueError("DP241_OBSERVATION_FIELDS_INVALID")
    if (record["contract_version"] != VERSION
            or not isinstance(record["case_id"], str)
            or not _CASE.fullmatch(record["case_id"])
            or not isinstance(record["plan_id"], str)
            or not _PLAN.fullmatch(record["plan_id"])
            or not isinstance(record["timeline_snapshot_id"], str)
            or not re.fullmatch(r"original-source-timeline:[a-f0-9]{64}", record["timeline_snapshot_id"])
            or any(record[field] is not False for field in (
                "review_authority", "rights_clearance", "publication_authority",
                "external_receipts_independently_verified"))
            or record["private_only"] is not True):
        raise ValueError("DP241_OBSERVATION_AUTHORITY_INVALID")
    if (not isinstance(record["case_question"], str)
            or not 12 <= len(record["case_question"]) <= 1024
            or not record["case_question"].endswith("?")
            or not isinstance(record["exception_question"], str)
            or not 12 <= len(record["exception_question"]) <= 1024
            or not record["exception_question"].endswith("?")):
        raise ValueError("DP241_OBSERVATION_QUESTION_INVALID")
    target = record["target"]
    target_fields = {"content_id", "capture_id", "passage_id", "uri",
                     "version_sha256", "selector_type", "selector_start",
                     "selector_end", "selector_sha256"}
    media_fields = {"media_uri", "media_http_status", "media_content_length"}
    if (not isinstance(target, dict)
            or set(target) not in (target_fields, target_fields | media_fields)
            or not _safe_url(target["uri"])
            or not isinstance(target["version_sha256"], str)
            or not _SHA.fullmatch(target["version_sha256"])):
        raise ValueError("DP241_OBSERVATION_TARGET_INVALID")
    if media_fields <= target.keys() and (
            not _safe_url(target["media_uri"])
            or target["media_http_status"] != 200
            or type(target["media_content_length"]) is not int
            or not 0 < target["media_content_length"] <= 10_000_000):
        raise ValueError("DP241_OBSERVATION_MEDIA_INVALID")
    if not isinstance(record["attempts"], list):
        raise ValueError("DP241_OBSERVATION_ATTEMPTS_INVALID")
    for row in [target, *record["attempts"]]:
        if not isinstance(row, dict):
            raise ValueError("DP241_OBSERVATION_SELECTOR_INVALID")
        if (row.get("selector_type") != "TEXT_POSITION"
                or type(row.get("selector_start")) is not int
                or type(row.get("selector_end")) is not int
                or not 0 <= row["selector_start"] < row["selector_end"] <= 2_000_000
                or not isinstance(row.get("selector_sha256"), str)
                or not _SHA.fullmatch(row["selector_sha256"])):
            raise ValueError("DP241_OBSERVATION_SELECTOR_INVALID")
    attempts = record["attempts"]
    if (type(record["attempt_cap"]) is not int or not 2 <= record["attempt_cap"] <= 8
            or not isinstance(attempts, list)
            or len(attempts) != 2 or len(attempts) > record["attempt_cap"]
            or record["cost_cap_usd"] != "0" or record["spent_usd"] != "0"
            or record["status"] not in {"HELD_FOR_REVIEW", "SOURCE_STALE"}
            or record["reason_code"] not in {"RECOVERY_INDEPENDENT_LINEAGE_REVIEW_REQUIRED",
                                              "RECOVERY_TARGET_VERSION_CHANGED"}
            or record["next_action"] not in {"REVIEW_SOURCE_AND_DP511", "DP511_SOURCE_REVALIDATION"}
            or record["reanalysis_required"] is not True
            or record["root_lineage"] != "NASA_APOLLO_11_SINGLE_ROOT"):
        raise ValueError("DP241_OBSERVATION_BOUNDS_INVALID")
    ids: set[str] = set()
    families: set[str] = set()
    for row in attempts:
        if (not isinstance(row, dict) or set(row) != _ATTEMPT_FIELDS
                or not isinstance(row["attempt_id"], str)
                or not re.fullmatch(r"original-source-attempt:[a-f0-9]{64}", row["attempt_id"])
                or row["method_family"] not in {"ORIGINAL_PUBLISHER", "OFFICIAL_RECORD"}
                or row["source_family"] != "NASA_APOLLO_11_SINGLE_ROOT"
                or not _safe_url(row["lookup_uri"]) or not _safe_url(row["final_uri"])
                or not _safe_url(row["rights_basis_uri"])
                or not isinstance(row["observed_at"], str)
                or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", row["observed_at"])
                or row["http_status"] != 200
                or not isinstance(row["source_version_sha256"], str)
                or not _SHA.fullmatch(row["source_version_sha256"])
                or row["result"] not in _RESULTS or row["spent_usd"] != "0"
                or not isinstance(row["reason_code"], str) or not 3 <= len(row["reason_code"]) <= 120
                or not isinstance(row["next_trigger"], str) or not 3 <= len(row["next_trigger"]) <= 120):
            raise ValueError("DP241_OBSERVATION_ATTEMPT_INVALID")
        ids.add(row["attempt_id"])
        families.add(row["method_family"])
    if len(ids) != 2 or families != {"ORIGINAL_PUBLISHER", "OFFICIAL_RECORD"}:
        raise ValueError("DP241_OBSERVATION_LINEAGE_OR_METHOD_INVALID")
    return record


class LocalObservedRecoveryJournal:
    """Owner-only append-only snapshots. Replay never performs another fetch."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ValueError("DP241_OBSERVATION_ROOT_UNSAFE")
        try:
            details = self.root.stat()
        except OSError:
            raise ValueError("DP241_OBSERVATION_ROOT_UNSAFE") from None
        if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid()
                or stat.S_IMODE(details.st_mode) & 0o077):
            raise ValueError("DP241_OBSERVATION_ROOT_UNSAFE")

    def _directory(self, case_id: str, create: bool) -> Path | None:
        if not isinstance(case_id, str) or not _CASE.fullmatch(case_id):
            raise ValueError("DP241_OBSERVATION_CASE_INVALID")
        path = self.root / case_id
        if create:
            path.mkdir(mode=0o700, exist_ok=True)
        if not path.exists():
            return None
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("DP241_OBSERVATION_CASE_UNSAFE")
        return path

    def history(self, case_id: str) -> tuple[dict[str, object], ...]:
        directory = self._directory(case_id, create=False)
        if directory is None:
            return ()
        paths = list(directory.iterdir())
        if len(paths) > 16:
            raise ValueError("DP241_OBSERVATION_HISTORY_UNBOUNDED")
        results = []
        for path in paths:
            if not re.fullmatch(r"[a-f0-9]{64}\.json", path.name):
                raise ValueError("DP241_OBSERVATION_FILE_UNSAFE")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                info = os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 16384):
                    raise ValueError("DP241_OBSERVATION_FILE_UNSAFE")
                payload = os.read(fd, 16385)
            finally:
                os.close(fd)
            try:
                record = _validate(json.loads(payload))
            except (ValueError, UnicodeError, TypeError):
                raise ValueError("DP241_OBSERVATION_FILE_TAMPERED") from None
            if _hash(record) != path.stem or record["case_id"] != case_id:
                raise ValueError("DP241_OBSERVATION_FILE_TAMPERED")
            results.append({"snapshot_id": path.stem, "recorded_local_at": info.st_mtime,
                            "record": record})
        return tuple(sorted(results, key=lambda row: (row["recorded_local_at"], row["snapshot_id"])))

    def append(self, record: dict[str, object]) -> dict[str, object]:
        _validate(record)
        directory = self._directory(record["case_id"], create=True)
        snapshot_id = _hash(record)
        path = directory / (snapshot_id + ".json")
        if path.exists() or path.is_symlink():
            return next(row for row in self.history(record["case_id"])
                        if row["snapshot_id"] == snapshot_id)
        if len(self.history(record["case_id"])) >= 16:
            raise ValueError("DP241_OBSERVATION_HISTORY_FULL")
        payload = json.dumps(record, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":")).encode("ascii")
        if len(payload) > 16384:
            raise ValueError("DP241_OBSERVATION_RECORD_UNBOUNDED")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        return next(row for row in self.history(record["case_id"])
                    if row["snapshot_id"] == snapshot_id)

    def read(self, case_id: str) -> dict[str, object]:
        entries = self.history(case_id)
        if not entries:
            raise ValueError("DP241_OBSERVATION_CASE_NOT_FOUND")
        latest = entries[-1]
        return {"contract_version": VERSION, "private_only": True, "read_only": True,
                "publication_authority": False, "case_id": case_id,
                "history_count": len(entries), "snapshot_id": latest["snapshot_id"],
                "record": latest["record"]}
