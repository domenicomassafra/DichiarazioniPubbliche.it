#!/usr/bin/env python3
"""DP-201: fail-closed, network-free preflight for an official shadow canary.

This reads only local public-provenance metadata, an immutable npm tarball, a
synthetic offline response and the canonical claim configuration. A separately
supplied SHA-256 pin must authenticate the release-gate receipt: a self-signed
receipt cannot establish official provenance. No credential is read or needed.

This script intentionally cannot send a request, install an artifact, acquire a
provider grant, authorize spend, mark a canary successful or unblock DP-202.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
import tarfile
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

from dichiarazioni_pubbliche.claim_runtime import OmniRouteClaimClient, load_claim_config


OFFICIAL_ALLOWED_VERSION = "3.8.51"
REQUIRED_MODEL = "antigravity/gemini-3.8-flash-tiered"
REQUIRED_OFFICIAL_FIX_COMMITS = frozenset({
    "22511bccb9d3ec5d869a7fa38aee1f115ad6d321",
    "03c1f7545a272b4ae255b31ce67b2bbe69b834cd",
    "7663aadea967921c468d1537a186aa4062ff6400",
})
REQUIRED_RELEASE_CHECKS = frozenset({
    "npm-stable-artifact",
    "github-stable-release",
    "stable-channel-convergence",
    "minimum-version",
    "stable-docker-artifact",
    "artifact-anchor",
    "required-fix-ancestry",
})
PROBE_MAX_OUTPUT_TOKENS = 256  # Canonical OmniRouteClaimClient.probe() value.
MAX_JOB_COST_USD = Decimal("0.25")  # Worker default; NOT the actual budget snapshot.
MAX_TARBALL_BYTES = 250 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
SAMPLE = (
    "[seg=0 0:00.000-0:03.000] "
    "Nel segmento viene affermato che il prezzo è 10 euro."
)


class PreflightBlocked(Exception):
    """Stable machine code only; never include provider bodies or local secret values."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _read_limited(path: Path, *, maximum: int = MAX_JSON_BYTES) -> bytes:
    try:
        if not path.is_file() or path.stat().st_size > maximum:
            raise PreflightBlocked("OFFLINE_INPUT_MISSING_OR_TOO_LARGE")
        raw = path.read_bytes()
        if len(raw) > maximum:
            raise PreflightBlocked("OFFLINE_INPUT_MISSING_OR_TOO_LARGE")
        return raw
    except OSError as exc:
        raise PreflightBlocked("OFFLINE_INPUT_UNREADABLE") from exc


def _parse_json(raw: bytes, *, code: str) -> dict[str, Any]:
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise PreflightBlocked(code) from exc
    if not isinstance(obj, dict):
        raise PreflightBlocked(code)
    return obj


def _sha256_pin(receipt_bytes: bytes, trusted_pin: str) -> None:
    if not isinstance(trusted_pin, str) or not re.fullmatch(r"[0-9a-f]{64}", trusted_pin):
        raise PreflightBlocked("TRUSTED_RELEASE_RECEIPT_PIN_REQUIRED")
    if hashlib.sha256(receipt_bytes).hexdigest() != trusted_pin:
        raise PreflightBlocked("RELEASE_RECEIPT_HASH_MISMATCH")


def _official_release_integrity(receipt: dict[str, Any]) -> bytes:
    if receipt.get("stable_version") != OFFICIAL_ALLOWED_VERSION:
        raise PreflightBlocked("OFFICIAL_VERSION_NOT_ALLOWED")
    if receipt.get("eligible") is not True or receipt.get("decision") != "ELIGIBLE":
        raise PreflightBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")
    if receipt.get("schema_version") != 1 or receipt.get("blockers") != []:
        raise PreflightBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")
    checks = receipt.get("checks")
    if not isinstance(checks, list) or {c.get("name") for c in checks if isinstance(c, dict)} != REQUIRED_RELEASE_CHECKS:
        raise PreflightBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")
    if len(checks) != len(REQUIRED_RELEASE_CHECKS) or any(
        not isinstance(item, dict) or item.get("passed") is not True for item in checks
    ):
        raise PreflightBlocked("OFFICIAL_RELEASE_GATE_NOT_ELIGIBLE")

    proofs = receipt.get("commit_proof")
    anchor = receipt.get("artifact_anchor")
    if (not isinstance(proofs, list) or len(proofs) != 3
            or set(receipt.get("required_commits") or ()) != REQUIRED_OFFICIAL_FIX_COMMITS
            or {p.get("required_commit") for p in proofs if isinstance(p, dict)} != REQUIRED_OFFICIAL_FIX_COMMITS
            or any(not isinstance(p, dict) or p.get("contained") is not True for p in proofs)
            or not isinstance(anchor, dict) or anchor.get("anchored_to_stable") is not True):
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")
    npm = artifacts.get("npm")
    github = artifacts.get("github_release")
    docker = artifacts.get("docker")
    if not all(isinstance(p, dict) for p in (npm, github, docker)):
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")
    if (npm.get("version") != OFFICIAL_ALLOWED_VERSION
            or npm.get("tarball") != "https://registry.npmjs.org/omniroute/-/omniroute-3.8.51.tgz"
            or github.get("tag") != f"v{OFFICIAL_ALLOWED_VERSION}"
            or github.get("draft") is not False or github.get("prerelease") is not False
            or docker.get("tag") != OFFICIAL_ALLOWED_VERSION
            or not isinstance(docker.get("digest"), str)
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", docker["digest"])):
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")
    integrity = npm.get("integrity")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")
    try:
        digest = base64.b64decode(integrity[len("sha512-"):], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE") from exc
    if len(digest) != hashlib.sha512().digest_size:
        raise PreflightBlocked("OFFICIAL_RELEASE_PROVENANCE_INCOMPLETE")
    return digest


def _verify_local_official_tarball(path: Path, expected_sha512: bytes) -> str:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_TARBALL_BYTES:
            raise PreflightBlocked("OFFICIAL_TARBALL_MISSING_OR_TOO_LARGE")
        actual = hashlib.sha512()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                actual.update(block)
            if actual.digest() != expected_sha512:
                raise PreflightBlocked("ARTIFACT_INTEGRITY_MISMATCH")
            # Keep the same already-pinned file descriptor to avoid path-swap
            # races. Never extract, execute or install archive entries.
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                members = []
                for count, member in enumerate(archive, start=1):
                    if count > 50000:
                        raise PreflightBlocked("OFFICIAL_PACKAGE_MANIFEST_INVALID")
                    if member.name == "package/package.json":
                        members.append(member)
                if len(members) != 1 or not members[0].isfile() or members[0].size > MAX_JSON_BYTES:
                    raise PreflightBlocked("OFFICIAL_PACKAGE_MANIFEST_INVALID")
                entry = archive.extractfile(members[0])
                if entry is None:
                    raise PreflightBlocked("OFFICIAL_PACKAGE_MANIFEST_INVALID")
                package = _parse_json(entry.read(MAX_JSON_BYTES + 1), code="OFFICIAL_PACKAGE_MANIFEST_INVALID")
    except (OSError, tarfile.TarError, EOFError, UnicodeError) as exc:
        raise PreflightBlocked("OFFICIAL_TARBALL_UNREADABLE") from exc
    if package.get("name") != "omniroute" or package.get("version") != OFFICIAL_ALLOWED_VERSION:
        raise PreflightBlocked("OFFICIAL_PACKAGE_MANIFEST_INVALID")
    return OFFICIAL_ALLOWED_VERSION


def build_intended_request(*, extraction: bool = False) -> dict[str, Any]:
    """Recreate canonical probe/extract requests without invoking _post()."""
    config = load_claim_config()
    if (config.get("model") != REQUIRED_MODEL
            or config.get("prompt_version") != "claim-extract-v1"
            or not isinstance(config.get("cost_policy"), dict)
            or config["cost_policy"].get("pre_dispatch_estimate_required") is not True):
        raise PreflightBlocked("CANONICAL_CLAIM_CONFIG_DRIFT")
    client = OmniRouteClaimClient(api_key="", config=config)
    if config.get("max_output_tokens") != 2048:
        raise PreflightBlocked("CANONICAL_CLAIM_CONFIG_DRIFT")
    prompt = client.build_prompt(window_text=SAMPLE, allowed_segment_indices=(0,))
    return {
        "model": client.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": client.max_output_tokens if extraction else PROBE_MAX_OUTPUT_TOKENS,
        "stream": False,
    }


def validate_intended_request(request: dict[str, Any], *, extraction: bool = False) -> None:
    """Enforce exactly the existing chat contract; no tools or hidden fallback."""
    if (not isinstance(request, dict)
            or set(request) != {"model", "messages", "temperature", "max_tokens", "stream"}
            or request.get("model") != REQUIRED_MODEL
            or request.get("temperature") != 0
            or type(request.get("max_tokens")) is not int
            or request["max_tokens"] != (2048 if extraction else PROBE_MAX_OUTPUT_TOKENS)
            or request.get("stream") is not False
            or not isinstance(request.get("messages"), list)
            or len(request["messages"]) != 1):
        raise PreflightBlocked("INTENDED_REQUEST_SCHEMA_INVALID")
    message = request["messages"][0]
    if (not isinstance(message, dict) or set(message) != {"role", "content"}
            or message["role"] != "user" or not isinstance(message["content"], str)
            or SAMPLE not in message["content"]
            or "source_segment_indices" not in message["content"]
            or len(message["content"].encode("utf-8")) > 32000):
        raise PreflightBlocked("INTENDED_REQUEST_SCHEMA_INVALID")


def _decimal_positive(raw: str) -> Decimal:
    if not isinstance(raw, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,9})?", raw):
        raise PreflightBlocked("EXPLICIT_POSITIVE_COST_REQUIRED")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise PreflightBlocked("EXPLICIT_POSITIVE_COST_REQUIRED") from exc
    if not value.is_finite() or value <= 0:
        raise PreflightBlocked("EXPLICIT_POSITIVE_COST_REQUIRED")
    return value


def _validate_offline_fixture(path: Path) -> int:
    wrapper = _parse_json(_read_limited(path), code="OFFLINE_RESPONSE_SCHEMA_INVALID")
    if wrapper.get("fixture_only") is not True or set(wrapper) != {"fixture_only", "response"}:
        raise PreflightBlocked("OFFLINE_FIXTURE_REQUIRED")
    response = wrapper.get("response")
    if not isinstance(response, dict):
        raise PreflightBlocked("OFFLINE_RESPONSE_SCHEMA_INVALID")
    try:
        client = OmniRouteClaimClient(api_key="")
        claims = client._parse_claims(response, allowed_segment_indices={0})
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError) as exc:
        raise PreflightBlocked("OFFLINE_RESPONSE_SCHEMA_INVALID") from exc
    if (len(claims) != 1 or claims[0].source_segment_indices != (0,)
            or claims[0].claim_type != "PRICE_STATISTIC"
            or claims[0].numeric_sensitive is not True
            or claims[0].check_worthy is not True
            or not re.search(r"(?<!\d)10(?!\d)", claims[0].normalized_claim)):
        raise PreflightBlocked("OFFLINE_RESPONSE_SCHEMA_INVALID")
    return len(claims)


def verify_offline_shadow_readiness(
    *,
    artifact_tarball: Path,
    official_gate_receipt: Path,
    trusted_gate_sha256: str,
    offline_fixture: Path,
    max_usd_per_1k_total_tokens: str,
    approved_max_cost_usd: str,
) -> dict[str, Any]:
    """Validate readiness metadata entirely offline and return a sanitized report."""
    rate = _decimal_positive(max_usd_per_1k_total_tokens)
    cost_cap = _decimal_positive(approved_max_cost_usd)
    if cost_cap > MAX_JOB_COST_USD:
        raise PreflightBlocked("APPROVED_CAP_EXCEEDS_WORKER_JOB_LIMIT")

    raw_receipt = _read_limited(official_gate_receipt)
    _sha256_pin(raw_receipt, trusted_gate_sha256)
    receipt = _parse_json(raw_receipt, code="OFFICIAL_RELEASE_RECEIPT_INVALID")
    integrity_digest = _official_release_integrity(receipt)
    version = _verify_local_official_tarball(artifact_tarball, integrity_digest)

    request = build_intended_request()
    validate_intended_request(request)
    extraction_request = build_intended_request(extraction=True)
    validate_intended_request(extraction_request, extraction=True)
    claims = _validate_offline_fixture(offline_fixture)

    # A UTF-8 byte count is a deliberately conservative local proxy for input
    # tokens, NOT a provider-confirmed quote or enforceable remote hard cap.
    prompt_bytes = len(request["messages"][0]["content"].encode("utf-8"))
    extraction_bytes = len(extraction_request["messages"][0]["content"].encode("utf-8"))
    estimated_cost = (
        (Decimal(prompt_bytes + request["max_tokens"] + extraction_bytes + extraction_request["max_tokens"])
         * rate / Decimal(1000))
        .quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    )
    if estimated_cost <= 0 or estimated_cost > cost_cap:
        raise PreflightBlocked("ESTIMATED_COST_EXCEEDS_APPROVED_CAP")

    return {
        "status": "OFFLINE_READY_FOR_OPERATOR_REVIEW",
        "artifact_version": version,
        "model": REQUIRED_MODEL,
        "prompt_version": "claim-extract-v1",
        "verified_tarball_sha512_against_pinned_receipt": True,
        "release_gate_sha256": trusted_gate_sha256,
        "probe_request_sha256": hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "extraction_request_sha256": hashlib.sha256(json.dumps(extraction_request, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "planned_model_calls_preflighted": 2,
        "probe_max_output_tokens": PROBE_MAX_OUTPUT_TOKENS,
        "extraction_max_output_tokens": extraction_request["max_tokens"],
        "claim_count_in_fixture": claims,
        "max_usd_per_1k_total_tokens": str(rate),
        "approved_max_cost_usd": str(cost_cap),
        "estimated_max_cost_usd": str(estimated_cost),
        "live_canary_executed": False,
        "paid_call_authorized": False,
        "live_budget_snapshot_verified": False,
        "provider_receipt_recorded": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-tgz", type=Path, required=True)
    parser.add_argument("--official-gate-receipt", type=Path, required=True)
    parser.add_argument("--trusted-gate-sha256", required=True)
    parser.add_argument("--offline-fixture", type=Path, required=True)
    parser.add_argument("--max-usd-per-1k-total-tokens", required=True)
    parser.add_argument("--approved-max-cost-usd", required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_offline_shadow_readiness(
            artifact_tarball=args.artifact_tgz,
            official_gate_receipt=args.official_gate_receipt,
            trusted_gate_sha256=args.trusted_gate_sha256,
            offline_fixture=args.offline_fixture,
            max_usd_per_1k_total_tokens=args.max_usd_per_1k_total_tokens,
            approved_max_cost_usd=args.approved_max_cost_usd,
        )
    except PreflightBlocked as exc:
        result = {"status": "BLOCKED", "reason_code": exc.code,
                  "live_canary_executed": False, "paid_call_authorized": False}
        print(json.dumps(result, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason_code": "UNEXPECTED_OFFLINE_INPUT_ERROR",
                          "live_canary_executed": False, "paid_call_authorized": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
