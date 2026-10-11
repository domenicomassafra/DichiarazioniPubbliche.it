"""DP-235 source-only private pilot manifest gate.

This module does not ingest sources or grant rights. It freezes a proposed
private pilot shape and fails closed when authorization/provenance inputs are
missing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

VERSION = "bounded-private-pilot-manifest-v1"


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class PrivatePilotSample:
    sample_id: str
    content_id: str
    source_family: str
    language: str
    medium: str
    rights_reference: str | None
    capture_permission: str

    def __post_init__(self) -> None:
        if not all((self.sample_id, self.content_id, self.source_family, self.language, self.medium)):
            raise ValueError("PILOT_SAMPLE_FIELDS_REQUIRED")
        if self.capture_permission != "APPROVED_EXTERNAL_REQUIRED":
            raise ValueError("PILOT_NEVER_INVENTS_PERMISSION")


@dataclass(frozen=True)
class PrivatePilotManifest:
    samples: tuple[PrivatePilotSample, ...]
    manifest_sha256: str
    dispatch_authorized: bool = False


def freeze_private_pilot_manifest(samples: Sequence[PrivatePilotSample]) -> PrivatePilotManifest:
    rows = tuple(sorted(samples, key=lambda item: item.sample_id))
    if not rows:
        raise ValueError("PILOT_EMPTY_MANIFEST")
    if len({item.sample_id for item in rows}) != len(rows):
        raise ValueError("PILOT_DUPLICATE_SAMPLE")
    material = {"version": VERSION, "samples": [item.__dict__ for item in rows]}
    return PrivatePilotManifest(rows, _hash(material), False)


def validate_private_pilot_manifest(manifest: PrivatePilotManifest) -> None:
    if not isinstance(manifest, PrivatePilotManifest) or manifest.dispatch_authorized:
        raise ValueError("PILOT_DISPATCH_NOT_LOCAL")
    expected = _hash({"version": VERSION, "samples": [item.__dict__ for item in manifest.samples]})
    if expected != manifest.manifest_sha256:
        raise ValueError("PILOT_MANIFEST_TAMPERED")
