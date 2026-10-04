from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PRIMARY_POLICY = ROOT / "config" / "transcription-policy.v1.json"
FALLBACK_POLICY = ROOT / "config" / "transcription-policy.v0.json"
DEFAULT_POLICY = PRIMARY_POLICY
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderState:
    provider_id: str
    healthy: bool = True
    quota_audio_seconds_remaining: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class RouteChoice:
    provider_id: str
    route: str
    role: str
    estimated_cost_usd: float | None
    reason: str


@dataclass(frozen=True)
class RoutingPlan:
    primary: RouteChoice
    secondary: RouteChoice | None
    escalation: RouteChoice | None
    publication_requires_agreement: bool


def load_policy(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        resolved = path
    elif PRIMARY_POLICY.exists():
        resolved = PRIMARY_POLICY
    else:
        resolved = FALLBACK_POLICY
        logger.info("Loaded legacy v0 config fallback: %s", resolved)
    return json.loads(resolved.read_text())


def _provider_state(
    provider: dict[str, Any],
    states: dict[str, ProviderState],
) -> ProviderState:
    return states.get(provider["id"], ProviderState(provider["id"]))


def _eligible(
    provider: dict[str, Any],
    state: ProviderState,
    *,
    language: str,
    duration_seconds: int,
    timestamps_required: bool,
    allow_unproven: bool,
) -> bool:
    if not state.enabled or not state.healthy:
        return False
    if not allow_unproven and not provider.get("proven_in_owner_runtime", False):
        return False
    if language == "it" and not provider.get("italian", False):
        return False
    if timestamps_required and provider.get("timestamp_support") is not True:
        return False
    remaining = state.quota_audio_seconds_remaining
    if remaining is not None and remaining < duration_seconds:
        return False
    return True


def _estimated_cost(provider: dict[str, Any], duration_seconds: int) -> float | None:
    hourly = provider.get("list_price_usd_per_audio_hour")
    if hourly is None:
        return None
    return round(float(hourly) * duration_seconds / 3600.0, 6)


def _choice(
    provider: dict[str, Any],
    duration_seconds: int,
    reason: str,
) -> RouteChoice:
    return RouteChoice(
        provider_id=provider["id"],
        route=provider["route"],
        role=provider["role"],
        estimated_cost_usd=_estimated_cost(provider, duration_seconds),
        reason=reason,
    )


def _first_by_roles(
    providers: list[dict[str, Any]],
    roles: tuple[str, ...],
    states: dict[str, ProviderState],
    *,
    language: str,
    duration_seconds: int,
    timestamps_required: bool,
    allow_unproven: bool = False,
    exclude_provider_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    excluded = exclude_provider_ids or set()
    for role in roles:
        for provider in providers:
            if provider["id"] in excluded or provider.get("role") != role:
                continue
            state = _provider_state(provider, states)
            if _eligible(
                provider,
                state,
                language=language,
                duration_seconds=duration_seconds,
                timestamps_required=timestamps_required,
                allow_unproven=allow_unproven,
            ):
                return provider
    return None


def plan_asr(
    *,
    duration_seconds: int,
    language: str = "it",
    risk_class: str = "NORMAL",
    timestamps_required: bool = True,
    states: dict[str, ProviderState] | None = None,
    policy: dict[str, Any] | None = None,
) -> RoutingPlan:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be > 0")
    if risk_class not in {"NORMAL", "SENSITIVE"}:
        raise ValueError("risk_class must be NORMAL or SENSITIVE")

    policy = policy or load_policy()
    states = states or {}
    providers = policy["providers"]

    primary = _first_by_roles(
        providers,
        ("remote_primary_asr", "local_second_opinion"),
        states,
        language=language,
        duration_seconds=duration_seconds,
        timestamps_required=timestamps_required,
    )
    if primary is None:
        raise RuntimeError("NO_ELIGIBLE_PRIMARY_ASR")

    primary_choice = _choice(
        primary,
        duration_seconds,
        "lowest-cost proven primary/fallback satisfying language, health, quota and timestamp requirements",
    )

    if risk_class == "NORMAL":
        return RoutingPlan(
            primary=primary_choice,
            secondary=None,
            escalation=None,
            publication_requires_agreement=False,
        )

    # Sensitive spans should be short and get an independent provider/model.
    # Timestamp support is not required from the second opinion because the
    # bounded audio window already supplies temporal scope.
    secondary = _first_by_roles(
        providers,
        ("remote_second_opinion", "local_second_opinion"),
        states,
        language=language,
        duration_seconds=duration_seconds,
        timestamps_required=False,
        exclude_provider_ids={primary["id"]},
    )
    if secondary is None:
        raise RuntimeError("NO_INDEPENDENT_SECONDARY_ASR")

    escalation = _first_by_roles(
        providers,
        ("accuracy_escalation", "local_accuracy_fallback"),
        states,
        language=language,
        duration_seconds=duration_seconds,
        timestamps_required=timestamps_required,
        exclude_provider_ids={primary["id"], secondary["id"]},
    )

    return RoutingPlan(
        primary=primary_choice,
        secondary=_choice(
            secondary,
            duration_seconds,
            "independent second opinion required for sensitive span",
        ),
        escalation=(
            _choice(
                escalation,
                duration_seconds,
                "third opinion only if primary and secondary disagree",
            )
            if escalation
            else None
        ),
        publication_requires_agreement=True,
    )
