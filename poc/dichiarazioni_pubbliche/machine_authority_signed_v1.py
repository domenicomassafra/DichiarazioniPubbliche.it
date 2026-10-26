"""DP-316 opt-in verifier for off-database Ed25519 machine review receipts.

This is a private authorization seam. No public reader, release writer, legacy
review event, or production database invokes it. A genuine signature proves
which authorized key signed a bound decision, not the truth of source rights or
gold; the independent signer must verify those before issuance. Never use a
locally supplied key registry or a digest as a trust root.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.machine_authority_preflight_v1 import (
    MachineAuthorityPreflight, MachineAuthoritySnapshot,
    _material_errors, _fence_errors, _fence_covers_materials, _profile_ok, _decision_ok,
)

VERSION = "dp316-signed-authority-v1"
REGISTRY_VERSION = "dp316-registry-v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SIG = re.compile(r"[0-9a-f]{128}\Z")
_FIELDS = frozenset({
    "version", "key_id", "issuer_actor", "issuer_run", "adjudicator_actor",
    "adjudicator_run", "adjudicator_source_root", "record_id",
    "record_version", "release_ref", "snapshot_sha256", "source_root",
    "generator_run", "challenger_run", "challenger_source_root",
    "policy_version", "rights_sha256", "qualified_policy_sha256",
    "gold_sha256", "privacy_sha256", "fence_sha256", "decision", "scope",
    "rights_url", "rights_checked_at", "rights_expires_at", "permitted_uses",
    "issued_at", "expires_at",
})
_KEY_FIELDS = frozenset({
    "key_id", "actor_id", "role", "public_key_hex",
    "valid_from", "expires_at", "revoked", "source_root",
    "qualified_policy_sha256", "rights_sha256",
})


@dataclass(frozen=True)
class SignedAuthorityVerdict:
    disposition: str
    reason_codes: tuple[str, ...]
    private_signature_verified: bool = False

    @property
    def machine_signoff(self) -> bool:
        # An authentic issuer is not independent gold/qualified legal acceptance.
        return False

    @property
    def publication_authority(self) -> bool:
        # Requires separately implemented live DP-320 commit/read and release gate.
        return False

    @property
    def dispatch_authorized(self) -> bool:
        return False


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("DP316_TIMESTAMP_INVALID")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("DP316_TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)


def _hash(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _trusted_registry(path: Path, expected_sha256: str) -> dict[str, object]:
    """Read a 0600, locally owned, non-symlink registry pinned by operator config.

    Only the SHA passed from the *trusted* deployment configuration is a trust
    anchor; taking it from the receipt/DB would nullify key authentication.
    """
    if not _hash(expected_sha256) or not isinstance(path, Path):
        raise ValueError("DP316_TRUST_ANCHOR_INVALID")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_nlink != 1):
            raise ValueError("DP316_REGISTRY_PERMISSION_INVALID")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            blob = stream.read(16385)
        if len(blob) > 16384 or hashlib.sha256(blob).hexdigest() != expected_sha256:
            raise ValueError("DP316_REGISTRY_PIN_MISMATCH")
        def no_dupes(pairs):
            if len(pairs) != len({key for key, _ in pairs}):
                raise ValueError("DP316_REGISTRY_DUPLICATE_JSON_KEY")
            return dict(pairs)
        registry = json.loads(blob, object_pairs_hook=no_dupes)
        if (type(registry) is not dict
                or set(registry) != {"version", "mode", "keys"}
                or registry["version"] != REGISTRY_VERSION
                or not isinstance(registry["keys"], list)
                or len(registry["keys"]) > 64):
            raise ValueError("DP316_REGISTRY_INVALID")
        return registry
    finally:
        os.close(fd)


def verify_signed_authority(
    receipt: Mapping[str, object],
    *,
    snapshot: MachineAuthoritySnapshot,
    preflight: MachineAuthorityPreflight,
    trusted_registry_path: Path,
    pinned_registry_sha256: str,
    now: datetime,
) -> SignedAuthorityVerdict:
    """Authenticate a private decision; default and every error fail closed.

    Neither the returned verdict nor a legacy review approval authorizes a
    public write. A future release adapter must independently recheck the
    exact current rights, gold and epoch inside its persistence transaction and
    immediately before serving bytes, and version its cutover.
    """
    try:
        return _verify(
            receipt, snapshot, preflight, trusted_registry_path,
            pinned_registry_sha256, now,
        )
    except (ValueError, TypeError, OSError, KeyError, AttributeError,
            json.JSONDecodeError, UnicodeError, OverflowError) as exc:
        code = str(exc)
        if not code.startswith("DP316_"):
            code = "DP316_RECEIPT_INVALID"
        return SignedAuthorityVerdict("HOLD", (code,))


def _verify(receipt, snapshot, preflight, path, pinned_sha, now):
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise ValueError("DP316_NOW_INVALID")
    if type(receipt) is not dict or set(receipt) != (_FIELDS | {"signature_hex"}):
        raise ValueError("DP316_RECEIPT_FIELDS_INVALID")
    unsigned = {key: receipt[key] for key in _FIELDS}
    if (not all(isinstance(val, str) and val and len(val) <= 512
                for key, val in unsigned.items() if key != "permitted_uses")
            or type(unsigned["permitted_uses"]) is not list
            or unsigned["permitted_uses"] != ["PRIVATE_REVIEW"]
            or unsigned["version"] != VERSION
            or unsigned["decision"] != "ELIGIBLE"
            or unsigned["scope"] != "PRIVATE_REFERENCE"
            or not isinstance(receipt["signature_hex"], str)
            or _SIG.fullmatch(receipt["signature_hex"]) is None):
        raise ValueError("DP316_RECEIPT_INVALID")
    if not isinstance(snapshot, MachineAuthoritySnapshot) or not isinstance(
        preflight, MachineAuthorityPreflight
    ):
        raise ValueError("DP316_PREFLIGHT_INVALID")
    if (not _profile_ok(snapshot.profile) or not _decision_ok(snapshot.decision)
            or _material_errors(snapshot.materials) or _fence_errors(snapshot)
            or not _fence_covers_materials(snapshot)):
        raise ValueError("DP316_SNAPSHOT_STRUCTURE_INVALID")
    snapshot_sha = hashlib.sha256(_canonical(asdict(snapshot))).hexdigest()
    if (snapshot.profile.claim_kind != snapshot.decision.claim_kind
            or snapshot.profile.risk_class != snapshot.decision.risk_class
            or snapshot.profile.jurisdiction_ref != snapshot.decision.jurisdiction_ref
            or snapshot.profile.policy_version != snapshot.decision.policy_version):
        raise ValueError("DP316_PROFILE_DECISION_MISMATCH")
    if (preflight.disposition != "NEEDS_EXTERNAL_DECISION"
            or preflight.snapshot_sha256 != snapshot_sha
            or unsigned["snapshot_sha256"] != snapshot_sha):
        raise ValueError("DP316_PREFLIGHT_OR_SNAPSHOT_STALE")
    by_role = {item.role: item.sha256 for item in snapshot.materials}
    if (len(by_role) != len(snapshot.materials)
            or by_role.get("MACHINE_PROFILE") != hashlib.sha256(
                _canonical(asdict(snapshot.profile))
            ).hexdigest()
            or by_role.get("MACHINE_DECISION") != hashlib.sha256(
                _canonical(asdict(snapshot.decision))
            ).hexdigest()):
        raise ValueError("DP316_MATERIAL_BINDING_INVALID")
    decision = snapshot.decision
    expected = {
        "record_id": decision.record_id,
        "record_version": decision.record_version,
        "release_ref": decision.release_ref,
        "source_root": decision.generator_source_root_ref,
        "generator_run": decision.generator_run_ref,
        "challenger_run": decision.challenger_run_ref,
        "challenger_source_root": decision.challenger_source_root_ref,
        "policy_version": snapshot.profile.policy_version,
        "rights_sha256": by_role.get("SOURCE_RIGHTS"),
        "qualified_policy_sha256": by_role.get("QUALIFIED_POLICY"),
        "gold_sha256": by_role.get("GOLD_GATE"),
        "privacy_sha256": by_role.get("PRIVACY"),
        "fence_sha256": snapshot.fence.fingerprint,
    }
    if (any(unsigned[key] != value for key, value in expected.items())
            or not all(_hash(expected[key]) for key in (
                "rights_sha256", "qualified_policy_sha256", "gold_sha256",
                "privacy_sha256", "fence_sha256",
            ))
            or decision.rights_state != "CURRENT"
            or decision.correction_state != "CLEAR"
            or decision.challenger_state != "COMPLETED"
            or decision.claimed_machine_approval):
        raise ValueError("DP316_RECORD_OR_EVIDENCE_CHANGED")
    if (len({
        unsigned["generator_run"], unsigned["challenger_run"],
        unsigned["adjudicator_run"], unsigned["issuer_run"],
    }) != 4 or len({
        decision.generator_identity_ref, decision.challenger_identity_ref,
        unsigned["adjudicator_actor"], unsigned["issuer_actor"],
    }) != 4 or len({
        unsigned["source_root"], unsigned["challenger_source_root"],
        unsigned["adjudicator_source_root"],
    }) != 3):
        raise ValueError("DP316_INDEPENDENT_ACTORS_REQUIRED")
    rights_locator = urlsplit(unsigned["rights_url"])
    if (rights_locator.scheme != "https" or not rights_locator.hostname
            or rights_locator.username is not None or rights_locator.password is not None
            or rights_locator.fragment or any(c in unsigned["rights_url"] for c in (" ", "\n"))):
        raise ValueError("DP316_RIGHTS_URL_INVALID")
    at = now.astimezone(timezone.utc)
    if not (
        _timestamp(unsigned["rights_checked_at"]) <= _timestamp(unsigned["issued_at"]) <= at
        < _timestamp(unsigned["expires_at"])
        and at < _timestamp(unsigned["rights_expires_at"])
        and _timestamp(unsigned["rights_checked_at"]) <= at
    ):
        raise ValueError("DP316_RIGHTS_OR_RECEIPT_EXPIRED")
    registry = _trusted_registry(path, pinned_sha)
    if registry["mode"] != "MACHINE_V1":
        raise ValueError("DP316_MACHINE_CUTOVER_DISABLED")
    keys = registry["keys"]
    if (not all(type(item) is dict and set(item) == _KEY_FIELDS for item in keys)
            or len({item["key_id"] for item in keys}) != len(keys)):
        raise ValueError("DP316_KEY_REGISTRY_INVALID")
    approved = [item for item in keys if item["key_id"] == unsigned["key_id"]]
    if len(approved) != 1:
        raise ValueError("DP316_SIGNER_UNKNOWN")
    key = approved[0]
    if (key["actor_id"] != unsigned["issuer_actor"]
            or key["source_root"] != unsigned["source_root"]
            or key["qualified_policy_sha256"] != unsigned["qualified_policy_sha256"]
            or key["rights_sha256"] != unsigned["rights_sha256"]
            or key["role"] != "MACHINE_AUTHORITY"
            or key["revoked"] is not False
            or not (_timestamp(key["valid_from"]) <= _timestamp(unsigned["issued_at"])
                    < _timestamp(key["expires_at"]) and at < _timestamp(key["expires_at"]))
            or not isinstance(key["public_key_hex"], str)
            or not _hash(key["public_key_hex"])):
        raise ValueError("DP316_SIGNER_UNAUTHORIZED")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        raise ValueError("DP316_ED25519_BACKEND_UNAVAILABLE") from None
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key["public_key_hex"])).verify(
            bytes.fromhex(receipt["signature_hex"]), _canonical(unsigned)
        )
    except (InvalidSignature, ValueError):
        raise ValueError("DP316_SIGNATURE_INVALID") from None
    return SignedAuthorityVerdict("PRIVATE_SIGNATURE_VERIFIED", (), True)


__all__ = ["VERSION", "REGISTRY_VERSION", "SignedAuthorityVerdict", "verify_signed_authority"]
