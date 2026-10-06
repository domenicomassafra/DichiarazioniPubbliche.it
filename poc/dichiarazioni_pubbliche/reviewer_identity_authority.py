from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from dichiarazioni_pubbliche.publication_review_control import (
    PublicationReviewEvent,
    review_event_integrity_valid,
)
from dichiarazioni_pubbliche.publication_review_persistence import (
    PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION,
    ReviewerIdentityAttestation,
    build_identity_attestation,
)


LOCAL_REVIEWER_CREDENTIAL_VERSION = "local-reviewer-credential-v1"
LOCAL_REVIEWER_RECEIPT_VERSION = "local-reviewer-receipt-v1"
LOCAL_REVIEWER_AUTHORITY_VERSION = "local-reviewer-identity-authority-v1"

_CREDENTIAL_KEYS = {
    "contract_version",
    "credential_id",
    "actor_ref",
    "key_version",
    "status",
    "secret_hex",
}
_RECEIPT_KEYS = {
    "contract_version",
    "credential_id",
    "attestation",
    "mac_sha256",
}
_ATTESTATION_KEYS = set(ReviewerIdentityAttestation.__dataclass_fields__)
_STATUSES = {"ACTIVE", "REVOKED"}


@dataclass(frozen=True)
class LocalReviewerIdentity:
    credential_id: str
    actor_ref: str
    credential_fingerprint: str
    key_version: str
    status: str


def _required(value: object, code: str, *, limit: int = 256) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError(code)
    return text


def _safe_id(value: object, code: str) -> str:
    text = _required(value, code, limit=128)
    if any(not (char.isalnum() or char in "._-") for char in text):
        raise ValueError(code)
    return text


def _hex_secret(value: object) -> str:
    text = _required(value, "REVIEWER_CREDENTIAL_SECRET_INVALID", limit=128).lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError("REVIEWER_CREDENTIAL_SECRET_INVALID")
    return text


def _private_mode(path: Path, *, directory: bool) -> None:
    info = path.stat()
    expected_kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not expected_kind:
        raise ValueError("REVIEWER_IDENTITY_AUTHORITY_PATH_TYPE_INVALID")
    if info.st_uid != os.geteuid():
        raise ValueError("REVIEWER_IDENTITY_AUTHORITY_OWNER_INVALID")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("REVIEWER_IDENTITY_AUTHORITY_PERMISSIONS_UNSAFE")


def _canonical_bytes(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fingerprint(secret_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(secret_hex)).hexdigest()


def _authority_version(key_version: str) -> str:
    return f"{LOCAL_REVIEWER_AUTHORITY_VERSION}:{key_version}"


def _attestation_binding(attestation: ReviewerIdentityAttestation) -> str:
    material = {
        "contract_version": PUBLICATION_REVIEW_IDENTITY_AUTHORITY_CONTRACT_VERSION,
        "receipt_id": attestation.receipt_id,
        "actor_ref": attestation.actor_ref,
        "credential_fingerprint": attestation.credential_fingerprint,
        "review_event_integrity_sha256": attestation.review_event_integrity_sha256,
        "record_id": attestation.record_id,
        "record_version": attestation.record_version,
        "policy_version": attestation.policy_version,
        "authority_version": attestation.authority_version,
        "issued_at": attestation.issued_at,
    }
    return hashlib.sha256(_canonical_bytes(material)).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def initialize_authority_root(root: str | Path) -> Path:
    base = Path(root)
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    for name in ("credentials", "receipts"):
        child = base / name
        child.mkdir(mode=0o700, exist_ok=True)
        os.chmod(child, 0o700)
    _private_mode(base, directory=True)
    _private_mode(base / "credentials", directory=True)
    _private_mode(base / "receipts", directory=True)
    return base


def provision_reviewer_credential(
    root: str | Path,
    *,
    credential_id: str,
    actor_ref: str,
    key_version: str,
    secret_hex: str | None = None,
) -> LocalReviewerIdentity:
    base = initialize_authority_root(root)
    clean_id = _safe_id(credential_id, "REVIEWER_CREDENTIAL_ID_INVALID")
    clean_actor = _required(actor_ref, "REVIEWER_CREDENTIAL_ACTOR_INVALID")
    clean_key_version = _safe_id(key_version, "REVIEWER_CREDENTIAL_KEY_VERSION_INVALID")
    secret = _hex_secret(secret_hex or secrets.token_hex(32))
    path = base / "credentials" / f"{clean_id}.json"
    if path.exists():
        raise ValueError("REVIEWER_CREDENTIAL_ALREADY_EXISTS")
    payload = {
        "contract_version": LOCAL_REVIEWER_CREDENTIAL_VERSION,
        "credential_id": clean_id,
        "actor_ref": clean_actor,
        "key_version": clean_key_version,
        "status": "ACTIVE",
        "secret_hex": secret,
    }
    _atomic_json(path, payload)
    return LocalReviewerIdentity(
        credential_id=clean_id,
        actor_ref=clean_actor,
        credential_fingerprint=_fingerprint(secret),
        key_version=clean_key_version,
        status="ACTIVE",
    )


class LocalFileReviewerIdentityAuthority:
    """Local/off-DB reviewer authority for the current operator-only architecture.

    Credential and receipt files are deliberately outside PostgreSQL. The database stores
    only the opaque receipt id and binding from DP-310. This class does not create remote
    authentication or claim to protect against compromise of both the DB and authority root.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        _private_mode(self.root, directory=True)
        _private_mode(self.root / "credentials", directory=True)
        _private_mode(self.root / "receipts", directory=True)

    def _credential_payload(self, credential_id: str) -> dict[str, str]:
        clean_id = _safe_id(credential_id, "REVIEWER_CREDENTIAL_ID_INVALID")
        path = self.root / "credentials" / f"{clean_id}.json"
        _private_mode(path, directory=False)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("REVIEWER_CREDENTIAL_UNREADABLE") from exc
        if not isinstance(payload, dict) or set(payload) != _CREDENTIAL_KEYS:
            raise ValueError("REVIEWER_CREDENTIAL_SCHEMA_INVALID")
        if payload.get("contract_version") != LOCAL_REVIEWER_CREDENTIAL_VERSION:
            raise ValueError("REVIEWER_CREDENTIAL_VERSION_INVALID")
        if _safe_id(payload.get("credential_id"), "REVIEWER_CREDENTIAL_ID_INVALID") != clean_id:
            raise ValueError("REVIEWER_CREDENTIAL_ID_MISMATCH")
        clean = {
            "contract_version": LOCAL_REVIEWER_CREDENTIAL_VERSION,
            "credential_id": clean_id,
            "actor_ref": _required(payload.get("actor_ref"), "REVIEWER_CREDENTIAL_ACTOR_INVALID"),
            "key_version": _safe_id(
                payload.get("key_version"), "REVIEWER_CREDENTIAL_KEY_VERSION_INVALID"
            ),
            "status": _required(payload.get("status"), "REVIEWER_CREDENTIAL_STATUS_INVALID"),
            "secret_hex": _hex_secret(payload.get("secret_hex")),
        }
        if clean["status"] not in _STATUSES:
            raise ValueError("REVIEWER_CREDENTIAL_STATUS_INVALID")
        return clean

    def _identities(self) -> dict[str, LocalReviewerIdentity]:
        identities: dict[str, LocalReviewerIdentity] = {}
        by_fingerprint: dict[str, str] = {}
        for path in sorted((self.root / "credentials").glob("*.json")):
            payload = self._credential_payload(path.stem)
            identity = LocalReviewerIdentity(
                credential_id=payload["credential_id"],
                actor_ref=payload["actor_ref"],
                credential_fingerprint=_fingerprint(payload["secret_hex"]),
                key_version=payload["key_version"],
                status=payload["status"],
            )
            prior_actor = by_fingerprint.get(identity.credential_fingerprint)
            if prior_actor is not None and prior_actor != identity.actor_ref:
                raise ValueError("REVIEWER_CREDENTIAL_FINGERPRINT_SHARED_ACROSS_ACTORS")
            by_fingerprint[identity.credential_fingerprint] = identity.actor_ref
            identities[identity.credential_id] = identity
        return identities

    def identity(self, credential_id: str, *, require_active: bool = True) -> LocalReviewerIdentity:
        clean_id = _safe_id(credential_id, "REVIEWER_CREDENTIAL_ID_INVALID")
        identity = self._identities().get(clean_id)
        if identity is None:
            raise ValueError("REVIEWER_CREDENTIAL_UNKNOWN")
        if require_active and identity.status != "ACTIVE":
            raise ValueError("REVIEWER_CREDENTIAL_REVOKED")
        return identity

    def issue(
        self,
        event: PublicationReviewEvent,
        *,
        credential_id: str,
        issued_at: str,
    ) -> ReviewerIdentityAttestation:
        if not review_event_integrity_valid(event):
            raise ValueError("REVIEWER_IDENTITY_EVENT_TAMPERED")
        identity = self.identity(credential_id, require_active=True)
        if event.actor_ref != identity.actor_ref:
            raise ValueError("REVIEWER_IDENTITY_EVENT_ACTOR_MISMATCH")
        if event.credential_fingerprint != identity.credential_fingerprint:
            raise ValueError("REVIEWER_IDENTITY_EVENT_CREDENTIAL_MISMATCH")
        credential = self._credential_payload(identity.credential_id)
        receipt_digest = hashlib.sha256(
            _canonical_bytes(
                {
                    "credential_id": identity.credential_id,
                    "event_integrity_sha256": event.integrity_sha256,
                    "issued_at": _required(issued_at, "REVIEWER_IDENTITY_ISSUED_AT_REQUIRED", limit=64),
                    "key_version": identity.key_version,
                }
            )
        ).hexdigest()
        receipt_id = f"review-receipt-{receipt_digest}"
        attestation = build_identity_attestation(
            event,
            receipt_id=receipt_id,
            authority_version=_authority_version(identity.key_version),
            issued_at=issued_at,
        )
        receipt_payload: dict[str, object] = {
            "contract_version": LOCAL_REVIEWER_RECEIPT_VERSION,
            "credential_id": identity.credential_id,
            "attestation": asdict(attestation),
        }
        mac = hmac.new(
            bytes.fromhex(credential["secret_hex"]),
            _canonical_bytes(receipt_payload),
            hashlib.sha256,
        ).hexdigest()
        encoded = receipt_payload | {"mac_sha256": mac}
        path = self.root / "receipts" / f"{receipt_id}.json"
        if path.exists():
            _private_mode(path, directory=False)
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("REVIEWER_IDENTITY_RECEIPT_UNREADABLE") from exc
            if existing != encoded:
                raise ValueError("REVIEWER_IDENTITY_RECEIPT_CONFLICT")
        else:
            _atomic_json(path, encoded)
        return attestation

    def resolve(self, receipt_id: str) -> ReviewerIdentityAttestation | None:
        try:
            clean_id = _safe_id(receipt_id, "REVIEWER_IDENTITY_RECEIPT_ID_INVALID")
            path = self.root / "receipts" / f"{clean_id}.json"
            _private_mode(path, directory=False)
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != _RECEIPT_KEYS:
                return None
            if payload.get("contract_version") != LOCAL_REVIEWER_RECEIPT_VERSION:
                return None
            credential_id = _safe_id(
                payload.get("credential_id"), "REVIEWER_CREDENTIAL_ID_INVALID"
            )
            credential = self._credential_payload(credential_id)
            identity = self.identity(credential_id, require_active=False)
            attestation_payload = payload.get("attestation")
            if not isinstance(attestation_payload, dict) or set(attestation_payload) != _ATTESTATION_KEYS:
                return None
            attestation = ReviewerIdentityAttestation(**attestation_payload)
            if attestation.receipt_id != clean_id:
                return None
            if attestation.actor_ref != identity.actor_ref:
                return None
            if attestation.credential_fingerprint != identity.credential_fingerprint:
                return None
            if attestation.authority_version != _authority_version(identity.key_version):
                return None
            if not hmac.compare_digest(attestation.binding_sha256, _attestation_binding(attestation)):
                return None
            signed = {
                "contract_version": LOCAL_REVIEWER_RECEIPT_VERSION,
                "credential_id": credential_id,
                "attestation": attestation_payload,
            }
            expected_mac = hmac.new(
                bytes.fromhex(credential["secret_hex"]),
                _canonical_bytes(signed),
                hashlib.sha256,
            ).hexdigest()
            supplied_mac = str(payload.get("mac_sha256") or "")
            if not hmac.compare_digest(supplied_mac, expected_mac):
                return None
            return attestation
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            return None

    def revoke(self, credential_id: str) -> LocalReviewerIdentity:
        identity = self.identity(credential_id, require_active=False)
        if identity.status == "REVOKED":
            return identity
        payload = self._credential_payload(identity.credential_id)
        payload["status"] = "REVOKED"
        _atomic_json(
            self.root / "credentials" / f"{identity.credential_id}.json",
            payload,
        )
        return self.identity(identity.credential_id, require_active=False)


__all__ = [
    "LOCAL_REVIEWER_AUTHORITY_VERSION",
    "LOCAL_REVIEWER_CREDENTIAL_VERSION",
    "LOCAL_REVIEWER_RECEIPT_VERSION",
    "LocalFileReviewerIdentityAuthority",
    "LocalReviewerIdentity",
    "initialize_authority_root",
    "provision_reviewer_credential",
]
