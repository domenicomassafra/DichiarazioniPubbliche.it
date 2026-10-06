from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from dichiarazioni_pubbliche.ops.taxonomy import actionable
from dichiarazioni_pubbliche.provenance_quarantine import (
    BoundedDependencyGraph,
    HoldScopeTarget,
)
from dichiarazioni_pubbliche.source_revalidation import (
    RevalidationDecision,
    RevalidationDisposition,
)
from dichiarazioni_pubbliche.source_revalidation_hold import (
    SourceRevalidationHoldReceipt,
)


SOURCE_REVALIDATION_ALERT_VERSION = "source-revalidation-alert-v1"
MAX_ALERT_CHANGE_CODES = 16
MAX_ALERT_PUBLIC_IDS = 50
MAX_DIGEST_ALERTS = 200

_EVIDENCE_CHANGE_CODES = frozenset(
    {
        "RIGHTS_STATE_BLOCKED",
        "RIGHTS_STATE_CHANGED",
        "RIGHTS_EXPIRED",
        "AUTHORITY_SCOPE_EXPIRED",
    }
)


class SourceRevalidationAlertError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = str(code or "SOURCE_REVALIDATION_ALERT_ERROR").strip().upper()[:200]
        super().__init__(self.code)


def _text(value: object, name: str, *, maximum: int = 256) -> str:
    if isinstance(value, bool):
        raise SourceRevalidationAlertError(f"SOURCE_REVALIDATION_ALERT_{name}_INVALID")
    text = str(value or "").strip()
    if not text:
        raise SourceRevalidationAlertError(f"SOURCE_REVALIDATION_ALERT_{name}_REQUIRED")
    if len(text) > maximum:
        raise SourceRevalidationAlertError(f"SOURCE_REVALIDATION_ALERT_{name}_TOO_LONG")
    return text


def _change_codes(decision: RevalidationDecision) -> tuple[str, ...]:
    codes = tuple(
        sorted(
            set(decision.material_change_codes + decision.benign_change_codes)
        )
    )
    if len(codes) > MAX_ALERT_CHANGE_CODES:
        raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_CHANGE_CODE_LIMIT")
    for code in codes:
        _text(code, "CHANGE_CODE", maximum=120)
    return codes


def _category(codes: tuple[str, ...]) -> str:
    return "EVIDENCE" if any(code in _EVIDENCE_CHANGE_CODES for code in codes) else "SOURCE"


def _taxonomy_row(category: str) -> dict[str, object]:
    rows = actionable(({"category": category, "count": 1},))
    if len(rows) != 1:
        raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_TAXONOMY_INVALID")
    row = rows[0]
    if not row.get("operator_action"):
        raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_ACTION_MISSING")
    return row


@dataclass(frozen=True)
class SourceRevalidationOperatorAlert:
    alert_id: str
    source_id: str
    provider_id: str
    source_version: str
    disposition: str
    event_key: str
    change_codes: tuple[str, ...]
    category: str
    severity: str
    page: bool
    affected_public_ids: tuple[str, ...]
    affected_ids_truncated: bool
    hold_id: str | None = None
    hold_event_id: str | None = None
    version: str = SOURCE_REVALIDATION_ALERT_VERSION


def build_source_revalidation_operator_alert(
    *,
    decision: RevalidationDecision,
    source_id: str,
    provider_id: str,
    source_version: str,
    graph: BoundedDependencyGraph,
    hold_receipt: SourceRevalidationHoldReceipt | None = None,
) -> SourceRevalidationOperatorAlert | None:
    source = _text(source_id, "SOURCE_ID")
    provider = _text(provider_id, "PROVIDER_ID")
    version = _text(source_version, "SOURCE_VERSION")
    event_key = _text(decision.event_key, "EVENT_KEY", maximum=64)
    codes = _change_codes(decision)

    if decision.disposition is RevalidationDisposition.UNCHANGED:
        if decision.needs_targeted_hold or hold_receipt is not None:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_DECISION_CONFLICT")
        return None

    scope = HoldScopeTarget.source(
        provider_id=provider,
        source_id=source,
        source_version=version,
    )
    impact = graph.dry_run(scope, receipt_id_limit=MAX_ALERT_PUBLIC_IDS)
    category = _category(codes)
    taxonomy = _taxonomy_row(category)

    if decision.disposition is RevalidationDisposition.HOLD_REQUIRED:
        if not decision.needs_targeted_hold or hold_receipt is None:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_HOLD_RECEIPT_REQUIRED")
        if hold_receipt.decision_event_key != event_key:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_HOLD_EVENT_KEY_MISMATCH")
        if hold_receipt.request.scope != scope:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_HOLD_SCOPE_MISMATCH")
        if hold_receipt.hold.impact.impact_binding_sha256 != impact.impact_binding_sha256:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_HOLD_IMPACT_MISMATCH")
        hold_id = hold_receipt.hold.hold_id
        hold_event_id = hold_receipt.hold.event_id
    else:
        if decision.needs_targeted_hold or hold_receipt is not None:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_DECISION_CONFLICT")
        hold_id = None
        hold_event_id = None

    return SourceRevalidationOperatorAlert(
        alert_id=f"source-revalidation-alert:{event_key}",
        source_id=source,
        provider_id=provider,
        source_version=version,
        disposition=decision.disposition.value,
        event_key=event_key,
        change_codes=codes,
        category=category,
        severity=str(taxonomy["severity"]),
        page=bool(taxonomy["page"]),
        affected_public_ids=impact.affected_public_ids,
        affected_ids_truncated=impact.ids_truncated,
        hold_id=hold_id,
        hold_event_id=hold_event_id,
    )


def bounded_revalidation_alert_digest(
    alerts: Iterable[SourceRevalidationOperatorAlert | None],
) -> tuple[SourceRevalidationOperatorAlert, ...]:
    rows = tuple(alert for alert in alerts if alert is not None)
    if len(rows) > MAX_DIGEST_ALERTS:
        raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_DIGEST_LIMIT")
    by_event_key: dict[str, SourceRevalidationOperatorAlert] = {}
    for alert in rows:
        previous = by_event_key.get(alert.event_key)
        if previous is not None and previous != alert:
            raise SourceRevalidationAlertError("SOURCE_REVALIDATION_ALERT_REPLAY_CONFLICT")
        by_event_key[alert.event_key] = alert
    severity_order = {
        "OUTAGE": 0,
        "CRITICAL": 1,
        "WARNING": 2,
        "NOTICE": 3,
        "INFO": 4,
    }
    return tuple(
        sorted(
            by_event_key.values(),
            key=lambda alert: (
                severity_order.get(alert.severity, 99),
                alert.category,
                alert.event_key,
            ),
        )
    )


__all__ = [
    "MAX_ALERT_PUBLIC_IDS",
    "MAX_DIGEST_ALERTS",
    "SOURCE_REVALIDATION_ALERT_VERSION",
    "SourceRevalidationAlertError",
    "SourceRevalidationOperatorAlert",
    "bounded_revalidation_alert_digest",
    "build_source_revalidation_operator_alert",
]
