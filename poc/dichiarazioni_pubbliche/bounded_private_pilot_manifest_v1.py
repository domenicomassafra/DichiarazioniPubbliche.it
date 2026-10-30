"""DP-235 source-only private pilot proposal, not a permit or dispatcher.

The digest detects accidental/unsanctioned edits to a frozen local proposal; it
is not a signature and does not attest to the real source bytes, rights record,
human attribution, source availability, or provider pricing. Every downstream
operation must independently re-check those conditions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import hmac
import ipaddress
import json
import re
from typing import Sequence
from urllib.parse import urlsplit

VERSION = "bounded-private-pilot-manifest-v1"
MAX_SAMPLES = 8
MAX_SOURCE_FAMILIES = 4
MAX_BUDGET_EUR_CENTS = 10_000

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_./-]{0,199}$")
_FAMILY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_LANG = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_RIGHTS_REF = re.compile(r"^rights:[A-Za-z0-9][A-Za-z0-9:_./-]{0,199}$")
_MEDIA = {
    "written": frozenset({"text/plain", "text/html", "application/pdf"}),
    "audio": frozenset({"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg"}),
    "video": frozenset({"video/mp4", "video/webm"}),
}
_ROLES = frozenset({"AUTHOR", "SPEAKER", "REPORTED", "UNKNOWN"})


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"PILOT_{label}_INVALID")


def _digest(value: object, label: str) -> None:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError(f"PILOT_{label}_INVALID")


def _cents(value: object, label: str, maximum: int) -> None:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"PILOT_{label}_INVALID")


def _locator(value: object) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 2048
        or not value.isascii()
        or "\\" in value
        or any(char.isspace() or ord(char) < 32 for char in value)
    ):
        raise ValueError("PILOT_SOURCE_LOCATOR_INVALID")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or port is not None
            or host == "localhost"
            or host.endswith((".local", ".internal"))
        ):
            raise ValueError("PILOT_SOURCE_LOCATOR_INVALID")
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError("PILOT_SOURCE_LOCATOR_INVALID")
        except ValueError as exc:
            if str(exc) == "PILOT_SOURCE_LOCATOR_INVALID":
                raise
            if "." not in host:
                raise ValueError("PILOT_SOURCE_LOCATOR_INVALID") from None
    except (ValueError, UnicodeError) as exc:
        raise ValueError("PILOT_SOURCE_LOCATOR_INVALID") from exc


@dataclass(frozen=True)
class PrivatePilotSample:
    # Original 7-argument constructor remains valid for existing callers.
    # The new fields are required by freeze/validate, not by construction.
    sample_id: str
    content_id: str
    source_family: str
    language: str
    medium: str
    rights_reference: str | None
    capture_permission: str
    source_locator: str | None = None
    source_version: str | None = None
    source_version_sha256: str | None = None
    person_id: str | None = None
    attribution_role: str | None = None
    media_type: str | None = None
    estimated_cost_eur_cents: int = 0
    rights_source_family: str | None = None
    rights_content_id: str | None = None
    rights_version_sha256: str | None = None
    rights_source_locator: str | None = None

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                self.sample_id,
                self.content_id,
                self.source_family,
                self.language,
                self.medium,
            )
        ):
            raise ValueError("PILOT_SAMPLE_FIELDS_REQUIRED")
        if self.capture_permission != "APPROVED_EXTERNAL_REQUIRED":
            raise ValueError("PILOT_NEVER_INVENTS_PERMISSION")


@dataclass(frozen=True)
class PrivatePilotManifest:
    samples: tuple[PrivatePilotSample, ...]
    manifest_sha256: str
    dispatch_authorized: bool = False
    review_status: str = "HELD"
    hold_reasons: tuple[str, ...] = ()
    max_samples: int = MAX_SAMPLES
    budget_eur_cents: int = 0
    estimated_cost_eur_cents: int = 0


def _validate_sample(sample: PrivatePilotSample) -> tuple[str, ...]:
    for label, field in (
        ("SAMPLE_ID", sample.sample_id),
        ("CONTENT_ID", sample.content_id),
        ("SOURCE_VERSION", sample.source_version),
    ):
        _identifier(field, label)
    if (
        not isinstance(sample.source_family, str)
        or len(sample.source_family) > 80
        or _FAMILY.fullmatch(sample.source_family) is None
        or sample.source_family in {"source", "unknown"}
    ):
        raise ValueError("PILOT_SOURCE_FAMILY_INVALID")
    _locator(sample.source_locator)
    _digest(sample.source_version_sha256, "SOURCE_VERSION_SHA256")
    if (
        not isinstance(sample.language, str)
        or _LANG.fullmatch(sample.language) is None
        or sample.language == "und"
    ):
        raise ValueError("PILOT_LANGUAGE_INVALID")
    if (
        not isinstance(sample.medium, str)
        or sample.medium not in _MEDIA
        or not isinstance(sample.media_type, str)
        or sample.media_type not in _MEDIA[sample.medium]
    ):
        raise ValueError("PILOT_MEDIA_FORMAT_INVALID")
    if (
        not isinstance(sample.attribution_role, str)
        or sample.attribution_role not in _ROLES
    ):
        raise ValueError("PILOT_ATTRIBUTION_ROLE_INVALID")
    if sample.attribution_role == "UNKNOWN":
        if sample.person_id is not None:
            raise ValueError("PILOT_UNKNOWN_PERSON_CONFLICT")
    else:
        _identifier(sample.person_id, "PERSON_ID")
    if sample.medium != "written" and sample.attribution_role == "AUTHOR":
        raise ValueError("PILOT_MEDIA_AUTHOR_ROLE_INVALID")
    if sample.capture_permission != "APPROVED_EXTERNAL_REQUIRED":
        raise ValueError("PILOT_NEVER_INVENTS_PERMISSION")
    _cents(sample.estimated_cost_eur_cents, "SAMPLE_ESTIMATE", MAX_BUDGET_EUR_CENTS)

    holds = []
    if sample.attribution_role in {"UNKNOWN", "REPORTED"}:
        holds.append(f"{sample.sample_id}:PILOT_ATTRIBUTION_UNRESOLVED")
    if sample.rights_reference is None:
        if any(
            (
                sample.rights_source_family,
                sample.rights_content_id,
                sample.rights_version_sha256,
                sample.rights_source_locator,
            )
        ):
            raise ValueError("PILOT_RIGHTS_SCOPE_MISMATCH")
        holds.append(f"{sample.sample_id}:PILOT_RIGHTS_REFERENCE_MISSING")
    else:
        if (
            not isinstance(sample.rights_reference, str)
            or _RIGHTS_REF.fullmatch(sample.rights_reference) is None
            or sample.rights_source_family != sample.source_family
            or sample.rights_content_id != sample.content_id
            or sample.rights_version_sha256 != sample.source_version_sha256
            or sample.rights_source_locator != sample.source_locator
        ):
            raise ValueError("PILOT_RIGHTS_SCOPE_MISMATCH")
    return tuple(holds)


def _inspect(
    samples: tuple[PrivatePilotSample, ...],
    max_samples: int,
    budget_eur_cents: int,
) -> tuple[str, tuple[str, ...], int]:
    if type(max_samples) is not int or not 1 <= max_samples <= MAX_SAMPLES:
        raise ValueError("PILOT_SAMPLE_CAP_INVALID")
    _cents(budget_eur_cents, "BUDGET", MAX_BUDGET_EUR_CENTS)
    if not samples:
        raise ValueError("PILOT_EMPTY_MANIFEST")
    if len(samples) > max_samples:
        raise ValueError("PILOT_SAMPLE_CAP_EXCEEDED")
    if any(type(sample) is not PrivatePilotSample for sample in samples):
        raise ValueError("PILOT_SAMPLE_TYPE_INVALID")
    if tuple(sorted(samples, key=lambda sample: sample.sample_id)) != samples:
        raise ValueError("PILOT_SAMPLE_ORDER_INVALID")

    reasons: list[str] = []
    content_ids: set[str] = set()
    sample_ids: set[str] = set()
    source_versions: set[tuple[str, str, str]] = set()
    version_hashes: set[str] = set()
    families: set[str] = set()
    total = 0
    for sample in samples:
        reasons.extend(_validate_sample(sample))
        if (
            sample.sample_id in sample_ids
            or sample.content_id in content_ids
            or (sample.source_family, sample.source_locator, sample.source_version)
            in source_versions
            or sample.source_version_sha256 in version_hashes
        ):
            raise ValueError("PILOT_DUPLICATE_SAMPLE_OR_CONTENT")
        sample_ids.add(sample.sample_id)
        content_ids.add(sample.content_id)
        source_versions.add(
            (sample.source_family, sample.source_locator, sample.source_version)
        )
        version_hashes.add(sample.source_version_sha256)
        families.add(sample.source_family)
        total += sample.estimated_cost_eur_cents
    if len(families) > MAX_SOURCE_FAMILIES:
        raise ValueError("PILOT_SOURCE_FAMILY_CAP_EXCEEDED")
    if total > budget_eur_cents:
        raise ValueError("PILOT_BUDGET_EXCEEDED")
    return ("HELD" if reasons else "PROPOSED", tuple(sorted(reasons)), total)


def _material(manifest: PrivatePilotManifest) -> dict[str, object]:
    return {
        "version": VERSION,
        "samples": [asdict(sample) for sample in manifest.samples],
        "review_status": manifest.review_status,
        "hold_reasons": manifest.hold_reasons,
        "max_samples": manifest.max_samples,
        "budget_eur_cents": manifest.budget_eur_cents,
        "estimated_cost_eur_cents": manifest.estimated_cost_eur_cents,
    }


def freeze_private_pilot_manifest(
    samples: Sequence[PrivatePilotSample],
    *,
    max_samples: int = MAX_SAMPLES,
    budget_eur_cents: int = 0,
) -> PrivatePilotManifest:
    if not isinstance(samples, (list, tuple)) or len(samples) > MAX_SAMPLES:
        raise ValueError("PILOT_SAMPLE_CAP_INVALID")
    if any(type(sample) is not PrivatePilotSample for sample in samples):
        raise ValueError("PILOT_SAMPLE_TYPE_INVALID")
    rows = tuple(sorted(samples, key=lambda item: item.sample_id))
    status, reasons, estimated = _inspect(rows, max_samples, budget_eur_cents)
    proposed = PrivatePilotManifest(
        rows,
        "",
        False,
        status,
        reasons,
        max_samples,
        budget_eur_cents,
        estimated,
    )
    return replace(proposed, manifest_sha256=_hash(_material(proposed)))


def validate_private_pilot_manifest(manifest: PrivatePilotManifest) -> None:
    if (
        type(manifest) is not PrivatePilotManifest
        or manifest.dispatch_authorized is not False
    ):
        raise ValueError("PILOT_DISPATCH_NOT_LOCAL")
    if type(manifest.samples) is not tuple:
        raise ValueError("PILOT_SAMPLE_TYPE_INVALID")
    status, reasons, estimated = _inspect(
        manifest.samples,
        manifest.max_samples,
        manifest.budget_eur_cents,
    )
    if (
        manifest.review_status != status
        or type(manifest.hold_reasons) is not tuple
        or manifest.hold_reasons != reasons
        or manifest.estimated_cost_eur_cents != estimated
        or type(manifest.estimated_cost_eur_cents) is not int
    ):
        raise ValueError("PILOT_MANIFEST_STATE_TAMPERED")
    if (
        not isinstance(manifest.manifest_sha256, str)
        or _SHA.fullmatch(manifest.manifest_sha256) is None
        or not hmac.compare_digest(_hash(_material(manifest)), manifest.manifest_sha256)
    ):
        raise ValueError("PILOT_MANIFEST_TAMPERED")
