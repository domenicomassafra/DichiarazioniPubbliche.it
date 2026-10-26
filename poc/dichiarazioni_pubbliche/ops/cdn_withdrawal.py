"""DP-518C: durable, fail-closed Cloudflare purge/HTTP readback for withdrawn releases.

The caller MUST provide a verified immutable revocation event, a release fence
backed by the active origin, and the complete affected URL/cache-key inventory.
This module cannot independently authenticate #481/#482 release authority.
Until those production adapters exist, it is a callable operational component,
not a publication permission or a standalone live withdrawal daemon.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import stat
import statistics
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib import error, request

_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ACK = re.compile(r"[a-fA-F0-9]{32}\Z")
_MAX_PROBES = 240
_MAX_BODY = 524288


@dataclass(frozen=True, slots=True)
class Probe:
    """A concrete cache-key URL path; a safe 200 requires an exact pinned hash."""

    path: str
    safe_sha256: str | None  # None means absent: only 404/410 is accepted


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: int
    body: bytes
    cache_status: str = ""


@dataclass(frozen=True, slots=True)
class WithdrawalEvent:
    event_id: str
    source_id: str
    reason_class: str
    committed_at: str
    previous_manifest_sha256: str
    safe_manifest_sha256: str
    generation_sha256: str
    probes: tuple[Probe, ...]


@dataclass(frozen=True, slots=True)
class WithdrawalResult:
    status: str
    reason: str
    provider_ack: str | None
    safe_count: int
    commit_to_safe_ms: int | None


def _validate_event(event: WithdrawalEvent) -> datetime:
    if not isinstance(event, WithdrawalEvent):
        raise TypeError("EVENT_INVALID")
    if any(not isinstance(value, str) or not _REF.fullmatch(value) for value in
           (event.event_id, event.source_id, event.reason_class)):
        raise ValueError("EVENT_IDENTITY_INVALID")
    if any(not isinstance(value, str) or not _SHA.fullmatch(value) for value in
           (event.previous_manifest_sha256, event.safe_manifest_sha256,
            event.generation_sha256)):
        raise ValueError("EVENT_RELEASE_PIN_INVALID")
    if event.previous_manifest_sha256 == event.safe_manifest_sha256:
        raise ValueError("EVENT_UNCHANGED_RELEASE")
    try:
        instant = datetime.fromisoformat(event.committed_at)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("time must include an offset")
        instant = instant.astimezone(UTC)
        if instant > datetime.now(UTC):
            raise ValueError("future time")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("EVENT_TIME_INVALID") from exc
    if not isinstance(event.probes, tuple) or not 1 <= len(event.probes) <= _MAX_PROBES:
        raise ValueError("EVENT_PROBES_INVALID")
    keys = set()
    for probe in event.probes:
        if (not isinstance(probe, Probe) or not isinstance(probe.path, str)
                or not probe.path.startswith("/") or probe.path.startswith("//")
                or len(probe.path) > 400 or "#" in probe.path
                or any(ord(ch) < 33 or ord(ch) > 126 for ch in probe.path)
                or probe.path in keys
                or (probe.safe_sha256 is not None and not _SHA.fullmatch(probe.safe_sha256))):
            raise ValueError("EVENT_PROBES_INVALID")
        keys.add(probe.path)
    return instant


def _safe(probe: Probe, response: ProbeResult) -> bool:
    if (not isinstance(response, ProbeResult) or type(response.status) is not int
            or not isinstance(response.body, bytes) or len(response.body) > _MAX_BODY):
        return False
    if probe.safe_sha256 is None:
        return response.status in (404, 410)
    return (response.status == 200 and
            hashlib.sha256(response.body).hexdigest() == probe.safe_sha256)


@contextmanager
def _db(path: Path) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("WITHDRAWAL_LEDGER_PATH_INVALID")
    if not path.exists():
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass  # another retry worker initialized the same private ledger
        else:
            os.close(fd)
    if not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("WITHDRAWAL_LEDGER_PERMISSIONS_UNSAFE")
    with closing(sqlite3.connect(path, timeout=10)) as db, db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS event (
            event_id TEXT PRIMARY KEY, event_json TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS attempt (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
            observed_at TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
            provider_ack TEXT, safe_count INTEGER NOT NULL, commit_to_safe_ms INTEGER,
            observations_json TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES event(event_id))""")
        for command in (
            ("CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON event "
             "BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END"),
            ("CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON event "
             "BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END"),
            ("CREATE TRIGGER IF NOT EXISTS attempt_no_update BEFORE UPDATE ON attempt "
             "BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END"),
            ("CREATE TRIGGER IF NOT EXISTS attempt_no_delete BEFORE DELETE ON attempt "
             "BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END"),
        ):
            db.execute(command)
        yield db


def _event_json(event: WithdrawalEvent) -> str:
    return json.dumps(asdict(event), sort_keys=True, separators=(",", ":"))


class WithdrawalRunner:
    """Callbacks are trust boundaries: the caller must verify active immutable state.

    `verify_current_release` must fail closed if the *actual* MiniPC origin
    pointer, DP-320 revocation epoch or held state differs. It is rechecked
    after CDN reads to catch rollback and concurrent publication races.
    """

    def __init__(self, ledger: Path, *,
                 verify_current_release: Callable[[WithdrawalEvent], bool],
                 read_origin: Callable[[Probe], ProbeResult],
                 read_edge: Callable[[Probe], ProbeResult],
                 purge_cloudflare: Callable[[], str]):
        self.ledger = ledger
        self.verify_current_release = verify_current_release
        self.read_origin = read_origin
        self.read_edge = read_edge
        self.purge_cloudflare = purge_cloudflare

    def run(self, event: WithdrawalEvent) -> WithdrawalResult:
        committed = _validate_event(event)
        with _db(self.ledger) as db:
            payload = _event_json(event)
            db.execute("INSERT OR IGNORE INTO event(event_id,event_json) VALUES (?,?)",
                       (event.event_id, payload))
            previous = db.execute("SELECT event_json FROM event WHERE event_id=?",
                                  (event.event_id,)).fetchone()[0]
            if previous != payload:
                raise ValueError("EVENT_REPLAY_CONFLICT")
            last = db.execute("""SELECT status,reason,provider_ack,safe_count,
                                      commit_to_safe_ms FROM attempt
                                      WHERE event_id=? ORDER BY seq DESC LIMIT 1""",
                              (event.event_id,)).fetchone()
            if last and last[0] == "SAFE_READBACK":
                # A prior success is NOT proof that a later rollback stayed safe.
                valid = False
                try:
                    if (self.verify_current_release(event) is True and all(
                        _safe(probe, self.read_origin(probe)) for probe in event.probes
                    ) and all(
                        _safe(probe, self.read_edge(probe)) for probe in event.probes
                    ) and self.verify_current_release(event) is True):
                        valid = True
                except Exception:  # noqa: BLE001 - fail closed on any untrusted adapter error
                    valid = False
                if valid:
                    return WithdrawalResult(*last)

        ack = None
        count = 0
        reason = "RELEASE_FENCE_UNVERIFIED"
        observations: list[dict[str, str | int]] = []

        def observed(location: str, probe: Probe, response: ProbeResult) -> ProbeResult:
            if (isinstance(response, ProbeResult) and type(response.status) is int
                    and isinstance(response.body, bytes) and len(response.body) <= _MAX_BODY):
                observations.append({
                    "location": location, "path": probe.path, "status": response.status,
                    "body_sha256": hashlib.sha256(response.body).hexdigest(),
                })
            return response

        try:
            if self.verify_current_release(event) is not True:
                raise _Held(reason)
            for probe in event.probes:
                if not _safe(probe, observed("origin", probe, self.read_origin(probe))):
                    raise _Held("ORIGIN_UNSAFE_OR_UNAVAILABLE")
            if self.verify_current_release(event) is not True:
                raise _Held("RELEASE_FENCE_CHANGED")
            try:
                ack = self.purge_cloudflare()
            except Exception as exc:
                raise _Held("PURGE_FAILED_OR_TIMED_OUT") from exc
            if not isinstance(ack, str) or not _ACK.fullmatch(ack):
                ack = None
                raise _Held("PURGE_ACK_MISSING")
            for probe in event.probes:
                if not _safe(probe, observed("edge", probe, self.read_edge(probe))):
                    raise _Held("EDGE_UNSAFE_OR_UNAVAILABLE")
                count += 1
            if self.verify_current_release(event) is not True:
                raise _Held("RELEASE_FENCE_CHANGED")
            reason = "SAFE_BYTES_READ_BACK"
            status = "SAFE_READBACK"
        except _Held as exc:
            reason, status = str(exc), "HOLD"
        except Exception:  # noqa: BLE001 - fail closed and never expose private adapter errors
            # Provider/reader details may contain credentials, URLs or private text.
            reason, status = "READBACK_OR_FENCE_UNAVAILABLE", "HOLD"
        elapsed = (max(0, int((datetime.now(UTC) - committed).total_seconds()
                              * 1000)) if status == "SAFE_READBACK" else None)
        result = WithdrawalResult(status, reason, ack, count, elapsed)
        with _db(self.ledger) as db:
            db.execute("""INSERT INTO attempt(event_id,observed_at,status,reason,
                        provider_ack,safe_count,commit_to_safe_ms,observations_json)
                        VALUES (?,?,?,?,?,?,?,?)""", (
                event.event_id, datetime.now(UTC).isoformat(),
                result.status, result.reason, result.provider_ack,
                result.safe_count, result.commit_to_safe_ms,
                json.dumps(observations, sort_keys=True, separators=(",", ":"))))
        return result


class _Held(Exception):
    pass


def withdrawal_digest(ledger: Path) -> dict:
    """Observed event denominator and latencies, never a fabricated target SLO."""
    with _db(ledger) as db:
        events = db.execute("SELECT event_id,event_json FROM event").fetchall()
        attempts = db.execute("""SELECT event_id,status,provider_ack,
                                 commit_to_safe_ms,reason,observations_json
                                 FROM attempt ORDER BY seq""").fetchall()
    latest = {row[0]: row for row in attempts}
    latencies = sorted(row[3] for row in latest.values()
                       if row[1] == "SAFE_READBACK" and row[3] is not None)
    reasons: dict[str, int] = {}
    holds: dict[str, int] = {}
    http_statuses: dict[str, int] = {}
    surfaces = 0
    for _, raw in events:
        item = json.loads(raw)
        reasons[item["reason_class"]] = reasons.get(item["reason_class"], 0) + 1
        surfaces += len(item["probes"])
    for row in latest.values():
        if row[1] != "SAFE_READBACK":
            holds[row[4]] = holds.get(row[4], 0) + 1
    for row in attempts:
        for item in json.loads(row[5]):
            status = str(item["status"])
            http_statuses[status] = http_statuses.get(status, 0) + 1
    return {
        "event_count": len(events), "affected_surface_count": surfaces,
        "attempt_count": len(attempts), "reason_classes": reasons,
        "ack_count": len({row[0] for row in attempts if row[2] is not None}),
        "safe_count": sum(row[1] == "SAFE_READBACK" for row in latest.values()),
        "hold_count": sum(row[1] != "SAFE_READBACK" for row in latest.values()),
        "hold_reasons_requiring_response": holds,
        "observed_http_status_counts": http_statuses,
        "measured_latency_count": len(latencies),
        "commit_to_last_safe_ms": latencies,
        "observed_median_ms": int(statistics.median(latencies)) if latencies else None,
        "candidate_slo_ms": None,  # requires a representative production event sample
    }


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_probe(base: str, probe: Probe, *, timeout: float = 5) -> ProbeResult:
    """HTTP GET; origin/edge base must be trusted fixed configuration."""
    from urllib.parse import urlsplit
    url = urlsplit(base)
    if (url.scheme not in ("http", "https") or not url.netloc
            or url.path not in ("", "/") or url.query or url.fragment):
        raise ValueError("HTTP_PROBE_BASE_INVALID")
    req = request.Request(base.rstrip("/") + probe.path,
                          headers={"Accept-Encoding": "identity"})
    opener = request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(_MAX_BODY + 1)
            return ProbeResult(response.status, body, response.headers.get("CF-Cache-Status", ""))
    except error.HTTPError as exc:
        with exc:
            return ProbeResult(exc.code, exc.read(_MAX_BODY + 1),
                               exc.headers.get("CF-Cache-Status", ""))


def cloudflare_purge(zone_id: str, token: str, *, timeout: float = 8) -> str:
    """Native API adapter. ACK is *acceptance only*, never final edge proof."""
    if not re.fullmatch(r"[0-9a-fA-F]{32}", zone_id):
        raise ValueError("CLOUDFLARE_ZONE_INVALID")
    if not token or "\n" in token or "\r" in token:
        raise ValueError("CLOUDFLARE_TOKEN_INVALID")
    req = request.Request(
        "https://api.cloudflare.com/client/v4/zones/" + zone_id + "/purge_cache",
        data=b'{"purge_everything":true}', method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with request.build_opener(_NoRedirect).open(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("CLOUDFLARE_PURGE_REJECTED")
        doc = json.loads(response.read(8193))
    if (doc.get("success") is not True or not isinstance(doc.get("result"), dict)
            or not isinstance(doc["result"].get("id"), str)
            or not _ACK.fullmatch(doc["result"]["id"])):
        raise RuntimeError("CLOUDFLARE_PURGE_ACK_UNVERIFIED")
    return doc["result"]["id"]
