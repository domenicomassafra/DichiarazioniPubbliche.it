"""Explicit worker provider admission; no implicit network or model fallback.

The official OmniRoute claim route and the scheduled Groq ASR route remain
separate. A local lane is enabled only by an owner-provisioned configuration.
Presence of an API key alone never authorizes an external audio transfer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dichiarazioni_pubbliche.claim_runtime import OmniRouteClaimClient
from dichiarazioni_pubbliche.local_asr import WhisperCppLocalTranscriber
from dichiarazioni_pubbliche.local_claim_ollama import LocalOllamaClaimClient


PREFIX = "DICHIARAZIONI_PUBBLICHE_"


@dataclass(frozen=True)
class ProviderClients:
    claim_client: OmniRouteClaimClient | None
    local_asr: WhisperCppLocalTranscriber | None
    groq_api_key: str | None
    claim_rate: float | None


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(PREFIX + name, "0")
    if value not in {"0", "1"}:
        raise ValueError(f"{name}_MUST_BE_EXPLICIT_0_OR_1")
    return value == "1"


def configure_provider_clients(env: Mapping[str, str]) -> ProviderClients:
    """Pure configuration gate: constructs adapters without making requests.

    Remote audio requires separate owner approval for terms, confidentiality,
    budget and entitlement. An approved free quota is never inferred from an
    installed OmniRoute connection or Antigravity IDE plan.
    """
    omni_key = env.get("OMNIROUTE_API_KEY", "").strip()
    claim_rate_raw = env.get(PREFIX + "CLAIM_MAX_USD_PER_1K_TOTAL_TOKENS")
    try:
        claim_rate = (float(claim_rate_raw) if claim_rate_raw not in {None, ""} else None)
    except ValueError as exc:
        raise ValueError("CLAIM_COST_RATE_INVALID") from exc
    if claim_rate is not None and (claim_rate < 0 or claim_rate == float("inf")
                                   or claim_rate != claim_rate):
        raise ValueError("CLAIM_COST_RATE_INVALID")

    local_claim = _flag(env, "LOCAL_CLAIM_ENABLED")
    if local_claim and omni_key:
        raise ValueError("LOCAL_CLAIM_CONFLICTS_WITH_OFFICIAL_OMNIROUTE")
    if local_claim and claim_rate_raw != "0":
        raise ValueError("LOCAL_CLAIM_REQUIRES_EXPLICIT_ZERO_EXTERNAL_TOKEN_COST")
    if local_claim:
        claim_client = LocalOllamaClaimClient(
            expected_model_digest=env.get(PREFIX + "LOCAL_CLAIM_MODEL_SHA256", ""),
        )
    elif omni_key:
        claim_client = OmniRouteClaimClient(
            api_key=omni_key,
            base_url=env.get(PREFIX + "OMNIROUTE_BASE_URL", "http://127.0.0.1:20128"),
        )
    else:
        claim_client = None

    local_asr = None
    if _flag(env, "LOCAL_ASR_ENABLED"):
        names = ("LOCAL_ASR_AUDIO_ROOT", "LOCAL_ASR_CLI", "LOCAL_ASR_MODEL", "LOCAL_ASR_MODEL_SHA256")
        if not all(env.get(PREFIX + name) for name in names):
            raise ValueError("LOCAL_ASR_RUNTIME_NOT_CONFIGURED")
        local_asr = WhisperCppLocalTranscriber(
            audio_root=Path(env[PREFIX + names[0]]),
            cli_path=Path(env[PREFIX + names[1]]),
            model_path=Path(env[PREFIX + names[2]]),
            model_sha256=env[PREFIX + names[3]],
        )

    groq_api_key = None
    if _flag(env, "GROQ_REMOTE_ASR_ENABLED"):
        for gate in (
            "GROQ_REMOTE_ASR_TERMS_ACCEPTED",
            "GROQ_REMOTE_ASR_CONFIDENTIALITY_APPROVED",
            "GROQ_REMOTE_ASR_SPEND_APPROVED",
        ):
            if not _flag(env, gate):
                raise ValueError(f"{gate}_REQUIRED")
        groq_api_key = env.get("GROQ_API_KEY", "").strip() or None
        if not groq_api_key:
            raise ValueError("GROQ_REMOTE_ASR_DEDICATED_CREDENTIAL_REQUIRED")
    return ProviderClients(claim_client, local_asr, groq_api_key, claim_rate)
