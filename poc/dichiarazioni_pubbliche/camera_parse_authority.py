"""DP-319B: authenticated private Camera PARSE_TEXT on exact archived captures.

The append-only PostgreSQL receipt is only a claim until its HMAC is verified
against the active off-database local agent credential. Neither a rights_record
nor a reference string is a signature. There is no public excerpt authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from dichiarazioni_pubbliche.private_capture_rights import evaluate_source_use
from dichiarazioni_pubbliche.reviewer_identity_authority import LocalFileReviewerIdentityAuthority
from dichiarazioni_pubbliche.rights_registry import RightsSubject
from dichiarazioni_pubbliche.studio_discovery_triage_authority import _credential

CONTRACT = "dp449-camera-private-parse-attestation-v1"
ISSUER_ACTOR = "agent:private-rights-reviewer:camera"
ISSUER_ROLE = "PRIVATE_RIGHTS_AGENT"
POLICY_VERSION = "dp426-camera-article5-private-text-20261025-v1"
LEGAL_BASIS = (
    "https://def.finanze.it/DocTribFrontend/getAttoNormativoDetail.do?ACTION=getArticolo&"
    "codiceOrdinamento=0000000000000050000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000&"
    "id=%7B012E634A-9F52-4452-B7F7-980D83EDE0C6%7D"
)
# The historical SHA-256s are from actual archived PostgreSQL Capture bytes.
SOURCES: dict[str, tuple[str, str]] = {
    "content:garlasco:camera:sed0607": (
        "https://documenti.camera.it/leg19/resoconti/assemblea/html/sed0607/stenografico.htm",
        "2ab7a0739d6ffc766b45526023ab4bd878c0e996fa90aa7d6dec6a3e0cc7de6f",
    ),
    "content:garlasco:camera:sed0703": (
        "https://www.camera.it/leg19/410?idSeduta=0703&tipo=stenografico",
        "09aa5d2b696722819ca44c978b0c4000094fc60152a64fe81e4fb7e41a5df53f",
    ),
}


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _aware(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("CAMERA_PARSE_TIMESTAMP_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("CAMERA_PARSE_TIMESTAMP_INVALID") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("CAMERA_PARSE_TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT, "private_only": True,
        "publication_authority": False, "permitted": False,
        "status": "DENIED", "reason": reason,
    }


def _receipt_id(material: dict[str, Any]) -> str:
    return "camera-parse-receipt:" + hashlib.sha256(_canonical(material)).hexdigest()


class CameraParseAuthority:
    """The private operator rights-check API; reads current PG state every time."""

    def __init__(self, runtime: Any, authority: LocalFileReviewerIdentityAuthority):
        self.runtime = runtime
        self.authority = authority

    def _current(self, content_id: str, capture_sha256: str, now: datetime):
        source = SOURCES.get(content_id)
        if source is None or capture_sha256 != source[1]:
            raise ValueError("CAMERA_PARSE_SOURCE_VERSION_MISMATCH")
        subject = RightsSubject(
            source_family="camera_official_stenographic", locator_kind="URL",
            locator_value=source[0], content_id=content_id,
        )
        record = self.runtime.read_current(subject)
        if record is None:
            raise ValueError("CAMERA_PARSE_CURRENT_RIGHTS_MISSING")
        if record.policy_version != POLICY_VERSION:
            raise ValueError("CAMERA_PARSE_POLICY_VERSION_MISMATCH")
        decision = evaluate_source_use(
            record, subject=subject, rights_record_id=record.id,
            policy_version=record.policy_version, use="PARSE_TEXT", now=now,
        )
        if not decision.permitted or record.expires_at is None:
            raise ValueError("CAMERA_PARSE_CURRENT_RIGHTS_NOT_PERMITTED")
        if self.runtime.run(
            """SELECT count(*) FROM content_capture
               WHERE content_id=:'content_id' AND content_sha256=:'capture_sha256'
                 AND status='CAPTURED' AND hold_status='NONE'
                 AND rights_status='CLEARED' AND body_purged_at IS NULL AND body_ref IS NOT NULL;""",
            content_id=content_id, capture_sha256=capture_sha256,
        ) != "1":
            raise ValueError("CAMERA_PARSE_CAPTURE_VERSION_NOT_PERSISTED")
        return record, source[0]

    def _material(
        self, *, record: Any, source_url: str, content_id: str, capture_sha256: str,
        credential_id: str, key_version: str, fingerprint: str, issued_at: str,
    ) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT,
            "rights_record_id": record.id, "subject_fingerprint": record.subject_fingerprint,
            "content_id": content_id, "source_url": source_url,
            "capture_sha256": capture_sha256, "use": "PARSE_TEXT",
            "issuer_ref": ISSUER_ACTOR, "issuer_role": ISSUER_ROLE,
            "credential_id": credential_id, "key_version": key_version,
            "credential_fingerprint": fingerprint, "policy_version": record.policy_version,
            "issued_at": issued_at, "expires_at": record.expires_at,
            "jurisdiction": "IT", "legal_basis_url": LEGAL_BASIS,
            "official_source_url": source_url,
            "privacy_scope": "PRIVATE_OFFICIAL_TEXT_ONLY_NO_PUBLIC_EXCERPT",
            "publication_authority": False,
        }

    def issue(
        self, *, content_id: str, capture_sha256: str, credential_id: str, issued_at: str,
    ) -> dict[str, Any]:
        when = _aware(issued_at)
        record, source_url = self._current(content_id, capture_sha256, when)
        actor, version, fingerprint, secret = _credential(self.authority, credential_id)
        if actor != ISSUER_ACTOR:
            raise ValueError("CAMERA_PARSE_ISSUER_ROLE_NOT_AUTHORIZED")
        material = self._material(
            record=record, source_url=source_url, content_id=content_id,
            capture_sha256=capture_sha256, credential_id=credential_id,
            key_version=version, fingerprint=fingerprint, issued_at=issued_at,
        )
        rid = _receipt_id(material)
        signed = material | {"receipt_id": rid}
        signed["mac_sha256"] = hmac.new(secret, _canonical(signed), hashlib.sha256).hexdigest()
        self.runtime.run(
            """INSERT INTO private_camera_parse_attestation
               (receipt_id,rights_record_id,content_id,capture_sha256,payload)
               VALUES (:'receipt_id',:'rights_record_id',:'content_id',
                       :'capture_sha256',:'payload'::jsonb)
               ON CONFLICT (receipt_id) DO NOTHING;""",
            receipt_id=rid, rights_record_id=record.id, content_id=content_id,
            capture_sha256=capture_sha256,
            payload=json.dumps(signed, sort_keys=True, separators=(",", ":")),
        )
        result = self.inspect(
            content_id=content_id, capture_sha256=capture_sha256,
            use="PARSE_TEXT", now=when,
        )
        if not result["permitted"] or result.get("receipt_id") != rid:
            raise ValueError("CAMERA_PARSE_PERSISTED_RECEIPT_NOT_VERIFIED")
        return result

    def inspect(
        self, *, content_id: str, capture_sha256: str,
        use: str, now: datetime | None = None,
    ) -> dict[str, Any]:
        if use != "PARSE_TEXT":
            return _deny("CAMERA_PARSE_USE_NOT_AUTHORIZED")
        try:
            when = now or datetime.now(timezone.utc)
            if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
                raise ValueError("CAMERA_PARSE_CLOCK_INVALID")
            record, source_url = self._current(content_id, capture_sha256, when)
            raw = self.runtime.run(
                """SELECT payload::text FROM private_camera_parse_attestation
                   WHERE rights_record_id=:'rights_record_id'
                     AND content_id=:'content_id' AND capture_sha256=:'capture_sha256'
                   ORDER BY created_at DESC, receipt_id DESC LIMIT 1;""",
                rights_record_id=record.id, content_id=content_id,
                capture_sha256=capture_sha256,
            )
            if not raw:
                return _deny("CAMERA_PARSE_SIGNED_RECEIPT_MISSING")
            stored = json.loads(raw)
            if not isinstance(stored, dict):
                raise ValueError("CAMERA_PARSE_ATTESTATION_CONTRACT_INVALID")
            cred_id = stored.get("credential_id")
            actor, version, fingerprint, secret = _credential(self.authority, cred_id)
            if actor != ISSUER_ACTOR:
                raise ValueError("CAMERA_PARSE_ISSUER_ROLE_NOT_AUTHORIZED")
            material = self._material(
                record=record, source_url=source_url, content_id=content_id,
                capture_sha256=capture_sha256, credential_id=cred_id,
                key_version=version, fingerprint=fingerprint,
                issued_at=stored.get("issued_at"),
            )
            rid = _receipt_id(material)
            expected = material | {"receipt_id": rid}
            if set(stored) != set(expected) | {"mac_sha256"} or any(
                stored.get(key) != value for key, value in expected.items()
            ):
                raise ValueError("CAMERA_PARSE_ATTESTATION_BINDING_INVALID")
            supplied_mac = stored.get("mac_sha256")
            if not isinstance(supplied_mac, str) or len(supplied_mac) != 64:
                raise ValueError("CAMERA_PARSE_SIGNATURE_INVALID")
            computed = hmac.new(secret, _canonical(expected), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(supplied_mac, computed):
                raise ValueError("CAMERA_PARSE_SIGNATURE_INVALID")
            if not _aware(material["issued_at"]) <= when < _aware(material["expires_at"]):
                return _deny("CAMERA_PARSE_ATTESTATION_EXPIRED")
            # A revoked credential or changed permission can invalidate the check
            # between first read and MAC evaluation. Re-read both before permit.
            again, _ = self._current(content_id, capture_sha256, when)
            if again.id != record.id:
                raise ValueError("CAMERA_PARSE_RIGHTS_CHANGED")
            last_actor, last_version, last_fingerprint, _ = _credential(self.authority, cred_id)
            if (last_actor, last_version, last_fingerprint) != (actor, version, fingerprint):
                raise ValueError("CAMERA_PARSE_CREDENTIAL_CHANGED")
            return {
                "contract_version": CONTRACT, "private_only": True,
                "publication_authority": False, "permitted": True,
                "status": "PERMITTED", "reason": "CAMERA_PARSE_SIGNED_PRIVATE_USE",
                "content_id": content_id, "capture_sha256": capture_sha256,
                "rights_record_id": record.id, "receipt_id": rid,
                "issuer_ref": actor, "issuer_role": ISSUER_ROLE,
                "policy_version": record.policy_version, "jurisdiction": "IT",
                "legal_basis_url": LEGAL_BASIS, "official_source_url": source_url,
                "issued_at": material["issued_at"], "expires_at": material["expires_at"],
            }
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
            return _deny("CAMERA_PARSE_AUTHORITY_INVALID")
        except Exception:
            return _deny("CAMERA_PARSE_BACKEND_UNAVAILABLE")
