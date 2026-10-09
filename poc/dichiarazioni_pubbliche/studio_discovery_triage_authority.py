"""DP-417 off-database reviewer attestations for *private* Discovery triage.

An attestation identifies the active holder of a local reviewer credential for
one exact, validated Discovery intent. It is NOT a grant to reject content,
approve evidence, extract claims, merge identities, or publish anything.
No HTTP route, SQL mutation, or external service is exposed here.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
from pathlib import Path
from typing import Mapping

from dichiarazioni_pubbliche.reviewer_identity_authority import (
    LOCAL_REVIEWER_CREDENTIAL_VERSION,
    LocalFileReviewerIdentityAuthority,
)
from dichiarazioni_pubbliche.studio_discovery_triage_contract import (
    StudioDiscoveryTriageRequest,
    make_triage_request,
)


TRIAGE_ATTESTATION_DOMAIN = "DP417_TRIAGE_V1"
_DIRECTORY = "triage-receipts"
_ID = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z", re.ASCII)
_RECEIPT_ID = re.compile(r"triage-receipt-[0-9a-f]{64}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-fA-F]{64}\Z", re.ASCII)
_CREDENTIAL_KEYS = frozenset({
    "contract_version", "credential_id", "actor_ref", "key_version",
    "status", "secret_hex",
})
_RECEIPT_KEYS = frozenset({
    "domain", "receipt_id", "credential_id", "credential_fingerprint",
    "key_version", "collection_id", "hit_id", "request_key", "decision",
    "expected_revision", "actor_ref", "payload_sha256", "mac_sha256",
})
_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _validate_request(request: StudioDiscoveryTriageRequest) -> StudioDiscoveryTriageRequest:
    if type(request) is not StudioDiscoveryTriageRequest:
        raise ValueError("DP417_TRIAGE_REQUEST_INVALID")
    try:
        validated = make_triage_request(
            collection_id=request.collection_id, hit_id=request.hit_id,
            request_key=request.request_key, decision=request.decision,
            expected_revision=request.expected_revision, actor_ref=request.actor_ref,
        )
    except (ValueError, TypeError, AttributeError):
        raise ValueError("DP417_TRIAGE_REQUEST_INVALID") from None
    if not hmac.compare_digest(validated.payload_sha256, request.payload_sha256):
        raise ValueError("DP417_TRIAGE_REQUEST_FINGERPRINT_INVALID")
    return validated


def _valid_credential_id(credential_id: object) -> str:
    if not isinstance(credential_id, str) or not _ID.fullmatch(credential_id):
        raise ValueError("DP417_TRIAGE_CREDENTIAL_ID_INVALID")
    return credential_id


def _valid_receipt_id(receipt_id: object) -> str:
    if not isinstance(receipt_id, str) or not _RECEIPT_ID.fullmatch(receipt_id):
        raise ValueError("DP417_TRIAGE_RECEIPT_ID_INVALID")
    return receipt_id


def _private_stat(info: os.stat_result, *, directory: bool) -> None:
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    mode = 0o700 if directory else 0o600
    if (
        not kind or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != mode
        or (not directory and info.st_nlink != 1)
    ):
        raise ValueError("DP417_TRIAGE_PRIVATE_PATH_UNSAFE")


def _open_private_dir(path: Path) -> int:
    try:
        before = path.lstat()  # lstat rejects symlink directories.
        _private_stat(before, directory=True)
        fd = os.open(path, _DIR_FLAGS)
        try:
            after = os.fstat(fd)
            _private_stat(after, directory=True)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise ValueError("DP417_TRIAGE_PRIVATE_PATH_CHANGED")
            return fd
        except BaseException:
            os.close(fd)
            raise
    except OSError:
        raise ValueError("DP417_TRIAGE_PRIVATE_PATH_UNAVAILABLE") from None


def _open_private_child_dir(parent_fd: int, name: str) -> int:
    """Resolve the child against the checked parent inode, not its path."""
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        _private_stat(before, directory=True)
        fd = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
        try:
            after = os.fstat(fd)
            _private_stat(after, directory=True)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise ValueError("DP417_TRIAGE_PRIVATE_PATH_CHANGED")
            return fd
        except BaseException:
            os.close(fd)
            raise
    except OSError:
        raise ValueError("DP417_TRIAGE_PRIVATE_PATH_UNAVAILABLE") from None


def _read_private_json(dir_fd: int, name: str, *, maximum: int = 8192) -> dict[str, object]:
    fd: int | None = None
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=dir_fd)
        with os.fdopen(fd, "rb") as handle:
            fd = None
            _private_stat(os.fstat(handle.fileno()), directory=False)
            blob = handle.read(maximum + 1)
            if len(blob) > maximum:
                raise ValueError("DP417_TRIAGE_RECEIPT_TOO_LARGE")
        # Reject duplicate JSON keys (including key-shadowing MAC/domain).
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            if len(pairs) != len({key for key, _ in pairs}):
                raise ValueError("DP417_TRIAGE_JSON_DUPLICATE_KEY")
            return dict(pairs)
        parsed = json.loads(blob.decode("utf-8"), object_pairs_hook=unique)
        if not isinstance(parsed, dict):
            raise ValueError("DP417_TRIAGE_JSON_OBJECT_REQUIRED")
        return parsed
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("DP417_TRIAGE_PRIVATE_FILE_INVALID") from None
    finally:
        if fd is not None:
            os.close(fd)


def _credential(authority: LocalFileReviewerIdentityAuthority, credential_id: str) -> tuple[str, str, str, bytes]:
    if not isinstance(authority, LocalFileReviewerIdentityAuthority):
        raise ValueError("DP417_TRIAGE_AUTHORITY_INVALID")
    credential_id = _valid_credential_id(credential_id)
    root_fd = _open_private_dir(authority.root)
    try:
        cred_fd = _open_private_child_dir(root_fd, "credentials")
        try:
            # Legacy authority identity() enforces active status and rejects
            # fingerprint reuse across different actors. This snapshot adds
            # no-follow fd reads, exact permissions, and matching key material.
            for item in os.listdir(cred_fd):
                if item.endswith(".json"):
                    file_fd = os.open(item, _FILE_FLAGS, dir_fd=cred_fd)
                    try:
                        _private_stat(os.fstat(file_fd), directory=False)
                    finally:
                        os.close(file_fd)
            identity = authority.identity(credential_id, require_active=True)
            payload = _read_private_json(cred_fd, f"{credential_id}.json")
            if set(payload) != _CREDENTIAL_KEYS:
                raise ValueError("DP417_TRIAGE_CREDENTIAL_INVALID")
            secret_hex = payload.get("secret_hex")
            if not isinstance(secret_hex, str) or not _HEX.fullmatch(secret_hex):
                raise ValueError("DP417_TRIAGE_CREDENTIAL_INVALID")
            secret = bytes.fromhex(secret_hex)
            fingerprint = hashlib.sha256(secret).hexdigest()
            if (
                payload["contract_version"] != LOCAL_REVIEWER_CREDENTIAL_VERSION
                or payload["credential_id"] != identity.credential_id
                or payload["actor_ref"] != identity.actor_ref
                or payload["key_version"] != identity.key_version
                or payload["status"] != "ACTIVE"
                or not hmac.compare_digest(fingerprint, identity.credential_fingerprint)
            ):
                raise ValueError("DP417_TRIAGE_CREDENTIAL_INVALID")
            return identity.actor_ref, identity.key_version, fingerprint, secret
        finally:
            os.close(cred_fd)
    except (OSError, TypeError, AttributeError):
        raise ValueError("DP417_TRIAGE_CREDENTIAL_INVALID") from None
    finally:
        os.close(root_fd)


def _receipt_material(
    request: StudioDiscoveryTriageRequest,
    *, credential_id: str, key_version: str, credential_fingerprint: str,
) -> dict[str, object]:
    identity_digest = hashlib.sha256(_canonical({
        "domain": TRIAGE_ATTESTATION_DOMAIN,
        "credential_id": credential_id,
        "key_version": key_version,
        "credential_fingerprint": credential_fingerprint,
        "payload_sha256": request.payload_sha256,
    })).hexdigest()
    return {
        "domain": TRIAGE_ATTESTATION_DOMAIN,
        "receipt_id": f"triage-receipt-{identity_digest}",
        "credential_id": credential_id,
        "credential_fingerprint": credential_fingerprint,
        "key_version": key_version,
        "collection_id": request.collection_id,
        "hit_id": request.hit_id,
        "request_key": request.request_key,
        "decision": request.decision,
        "expected_revision": request.expected_revision,
        "actor_ref": request.actor_ref,
        "payload_sha256": request.payload_sha256,
    }


def _signed_material(material: dict[str, object], secret: bytes) -> dict[str, object]:
    mac = hmac.new(secret, _canonical(material), hashlib.sha256).hexdigest()
    return material | {"mac_sha256": mac}


def _check_signed(
    stored: dict[str, object], expected: dict[str, object], secret: bytes,
) -> None:
    if set(stored) != _RECEIPT_KEYS:
        raise ValueError("DP417_TRIAGE_RECEIPT_INVALID")
    supplied = stored.get("mac_sha256")
    if not isinstance(supplied, str) or not _HEX.fullmatch(supplied):
        raise ValueError("DP417_TRIAGE_RECEIPT_INVALID")
    # Compare MAC in constant time even when an attacker has altered one field.
    signed = {key: stored[key] for key in expected}
    try:
        actual_mac = hmac.new(secret, _canonical(signed), hashlib.sha256).hexdigest()
    except (TypeError, ValueError, UnicodeError):
        raise ValueError("DP417_TRIAGE_RECEIPT_INVALID") from None
    if not hmac.compare_digest(supplied, actual_mac):
        raise ValueError("DP417_TRIAGE_RECEIPT_INVALID")
    if signed != expected:
        raise ValueError("DP417_TRIAGE_RECEIPT_BINDING_MISMATCH")


def _receipt_dir(authority: LocalFileReviewerIdentityAuthority, *, create: bool) -> int:
    root_fd = _open_private_dir(authority.root)
    try:
        if create:
            try:
                os.mkdir(_DIRECTORY, 0o700, dir_fd=root_fd)
                os.fsync(root_fd)
            except FileExistsError:
                pass
        return _open_private_child_dir(root_fd, _DIRECTORY)
    except OSError:
        raise ValueError("DP417_TRIAGE_RECEIPT_DIRECTORY_INVALID") from None
    finally:
        os.close(root_fd)


def _write_once(dir_fd: int, name: str, payload: dict[str, object]) -> None:
    temporary = f".{name}.{secrets.token_hex(16)}.tmp"
    try:
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600, dir_fd=dir_fd,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(_canonical(payload) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            raise
        # Link then unlink: atomic *no replacement*, including concurrent issue.
        try:
            os.link(temporary, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)
            # Finish publishing promptly: the final file must have exactly
            # one hardlink for independent verification to accept it.
            os.unlink(temporary, dir_fd=dir_fd)
            os.fsync(dir_fd)
        except FileExistsError:
            existing = _read_private_json(dir_fd, name)
            if existing != payload:
                raise ValueError("DP417_TRIAGE_RECEIPT_CONFLICT")
    finally:
        try:
            os.unlink(temporary, dir_fd=dir_fd)
            os.fsync(dir_fd)
        except FileNotFoundError:
            pass


def issue_triage_attestation(
    authority: LocalFileReviewerIdentityAuthority,
    request: StudioDiscoveryTriageRequest,
    credential_id: str,
) -> dict[str, str]:
    """Bind one exact non-authoritative triage intent to an active local actor."""
    req = _validate_request(request)
    clean_id = _valid_credential_id(credential_id)
    actor_ref, key_version, fingerprint, secret = _credential(authority, clean_id)
    if req.actor_ref != actor_ref:
        raise ValueError("DP417_TRIAGE_ACTOR_MISMATCH")
    material = _receipt_material(
        req, credential_id=clean_id, key_version=key_version,
        credential_fingerprint=fingerprint,
    )
    signed = _signed_material(material, secret)
    receipt_id = str(material["receipt_id"])
    dir_fd = _receipt_dir(authority, create=True)
    try:
        _write_once(dir_fd, f"{receipt_id}.json", signed)
        stored = _read_private_json(dir_fd, f"{receipt_id}.json")
        _check_signed(stored, material, secret)
    except OSError:
        raise ValueError("DP417_TRIAGE_RECEIPT_WRITE_FAILED") from None
    finally:
        os.close(dir_fd)
    # If administrative revocation/rotation raced issuance, refuse to return
    # a usable receipt. Future use must always call verify again.
    last_actor, last_key_version, last_fingerprint, _ = _credential(authority, clean_id)
    if (
        last_actor != actor_ref or last_key_version != key_version
        or not hmac.compare_digest(last_fingerprint, fingerprint)
    ):
        raise ValueError("DP417_TRIAGE_CREDENTIAL_CHANGED")
    return {"receipt_id": receipt_id, "payload_sha256": req.payload_sha256}


def verify_triage_attestation(
    authority: LocalFileReviewerIdentityAuthority,
    request: StudioDiscoveryTriageRequest,
    receipt_id: str,
) -> dict[str, str]:
    """Fail closed after revocation or any signed-binding / file-permission drift."""
    req = _validate_request(request)
    receipt_id = _valid_receipt_id(receipt_id)
    dir_fd = _receipt_dir(authority, create=False)
    try:
        stored = _read_private_json(dir_fd, f"{receipt_id}.json")
    finally:
        os.close(dir_fd)
    credential_id = _valid_credential_id(stored.get("credential_id"))
    actor_ref, key_version, fingerprint, secret = _credential(authority, credential_id)
    if req.actor_ref != actor_ref:
        raise ValueError("DP417_TRIAGE_ACTOR_MISMATCH")
    expected = _receipt_material(
        req, credential_id=credential_id, key_version=key_version,
        credential_fingerprint=fingerprint,
    )
    if receipt_id != expected["receipt_id"]:
        raise ValueError("DP417_TRIAGE_RECEIPT_BINDING_MISMATCH")
    _check_signed(stored, expected, secret)
    # Authentication is invalid if the receipt changes while credentials are
    # resolved or the credential is revoked while its MAC is checked. This
    # second snapshot narrows both TOCTOU windows at the verification seam.
    dir_fd = _receipt_dir(authority, create=False)
    try:
        latest_receipt = _read_private_json(dir_fd, f"{receipt_id}.json")
    finally:
        os.close(dir_fd)
    _check_signed(latest_receipt, expected, secret)
    last_actor, last_key_version, last_fingerprint, _ = _credential(authority, credential_id)
    if (
        last_actor != actor_ref or last_key_version != key_version
        or not hmac.compare_digest(last_fingerprint, fingerprint)
    ):
        raise ValueError("DP417_TRIAGE_CREDENTIAL_CHANGED")
    return {"receipt_id": receipt_id, "payload_sha256": req.payload_sha256}


__all__ = [
    "TRIAGE_ATTESTATION_DOMAIN",
    "issue_triage_attestation",
    "verify_triage_attestation",
]
