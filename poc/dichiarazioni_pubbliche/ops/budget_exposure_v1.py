"""Private DP-512 outstanding-reservation exposure for billing consumers.

Both queries read canonical receipts and the additive worker reservation ledger.
They cannot attest provider charges or authorize paid dispatch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ReservedBudget:
    today_usd: Decimal
    today_attempts: int
    prior_attempts: int


@dataclass(frozen=True)
class BillingDayWindow:
    start_utc: datetime | None
    end_utc: datetime | None
    timezone_status: str


def read_billing_day_window(
    run: Callable[..., str], *, current: datetime
) -> BillingDayWindow:
    """Match the database's existing local-day admission window, including DST."""
    name = run("SELECT current_setting('TimeZone');").strip()
    try:
        zone = ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        return BillingDayWindow(None, None, "UNKNOWN")
    start = current.astimezone(zone).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=1)
    return BillingDayWindow(
        start.astimezone(timezone.utc), end.astimezone(timezone.utc), "KNOWN"
    )


def mark_unknown_billing_window(report: dict[str, Any]) -> None:
    """Keep private SLO output explicit when the database day is unavailable."""
    report["estimated_cost_usd_today"] = None
    for key in report["billing_today"]:
        if key not in {
            "window_timezone_status", "invoice_attested",
            "authorizes_dispatch", "provider_grouping_is_source_attribution",
        }:
            report["billing_today"][key] = None


def private_receipt_groups(billing: Any) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Group canonical attempts for the digest without receipt IDs or raw bodies."""
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for group in billing.groups:
        for attempt in group.attempts:
            key = (group.provider_id, group.operation, attempt.status)
            row = groups.setdefault(
                key,
                {
                    "provider_id": group.provider_id,
                    "operation": group.operation,
                    "status": attempt.status,
                    "count": 0,
                    "cost_usd": Decimal("0"),
                    "cash_uncertain": False,
                    "cost_basis": "RECORDED_OR_ESTIMATED_NOT_AUTHENTICATED",
                },
            )
            row["count"] += 1
            row["cost_usd"] += (
                attempt.recorded_measured_usd
                or attempt.provisional_estimated_usd
                or Decimal("0")
            )
            row["cash_uncertain"] |= (
                attempt.cash_uncertainty
                or attempt.billing_basis in {"EXTERNAL_PLAN", "ZERO_COST"}
                or (
                    attempt.billing_basis == "ESTIMATED_ONLY"
                    and attempt.provisional_estimated_usd == Decimal("0")
                )
                or (
                    attempt.billing_basis == "MEASURED_PROVIDER_COST"
                    and attempt.recorded_measured_usd == Decimal("0")
                )
            )
    return groups


def read_reserved_budget(
    run: Callable[..., str], *, since: str, until: str
) -> ReservedBudget:
    """Read only bounded aggregate amounts; no job, account or provider IDs."""
    row = json.loads(
        run(
            """
        SELECT json_build_object(
            'daily_amount', COALESCE(sum(upper_bound_usd) FILTER (
                WHERE reserved_at >= :'since'::timestamptz
                  AND reserved_at < :'until'::timestamptz
            ), 0),
            'daily_count', count(*) FILTER (
                WHERE reserved_at >= :'since'::timestamptz
                  AND reserved_at < :'until'::timestamptz
            ),
            'prior_count', count(*) FILTER (
                WHERE reserved_at < :'since'::timestamptz
            )
        )::text FROM worker_budget_reservation WHERE state='RESERVED';
        """,
            since=since,
            until=until,
        )
    )
    amount = Decimal(str(row["daily_amount"]))
    if not amount.is_finite() or amount < 0:
        raise ValueError("DP512_RESERVATION_AMOUNT_INVALID")
    return ReservedBudget(
        today_usd=amount,
        today_attempts=int(row["daily_count"]),
        prior_attempts=int(row["prior_count"]),
    )


def scheduler_cost_today(run: Callable[..., str], source_id: str | None) -> float:
    """Same admitted daily exposure and stale-liability holds as the worker."""
    receipt_source = ""
    reservation_source = ""
    variables: dict[str, object] = {}
    if source_id is not None:
        receipt_source = "AND c.source_id = :'source_id'"
        reservation_source = "AND h.source_id = :'source_id'"
        variables["source_id"] = source_id
    raw = run(
        f"""
        SELECT CASE WHEN EXISTS (
            SELECT 1 FROM provider_receipt r
            LEFT JOIN content_item c ON c.id = r.content_id
            WHERE (CASE
                WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                    THEN r.measured_cost_usd IS NULL OR r.measured_cost_usd <= 0
                WHEN r.billing_basis='ESTIMATED_ONLY'
                    THEN r.estimated_cost_usd IS NULL OR r.estimated_cost_usd <= 0
                ELSE TRUE
            END)
            {receipt_source}
        ) OR EXISTS (
            SELECT 1 FROM worker_budget_reservation h
            WHERE h.state='RESERVED'
              AND h.reserved_at < date_trunc('day', now())
              {reservation_source}
        ) THEN 'Infinity' ELSE (
        SELECT (COALESCE(sum(
            CASE
                WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                    THEN r.measured_cost_usd
                ELSE r.estimated_cost_usd
            END
        ), 0) + (
            SELECT COALESCE(sum(h.upper_bound_usd), 0)
            FROM worker_budget_reservation h
            WHERE h.state='RESERVED'
              AND h.reserved_at >= date_trunc('day', now())
              {reservation_source}
        ))::text
        FROM provider_receipt r
        LEFT JOIN content_item c ON c.id = r.content_id
        WHERE COALESCE(r.started_at, r.completed_at, now()) >= date_trunc('day', now())
        {receipt_source}) END;
        """,
        **variables,
    )
    result = float(raw or 0)
    # An invalid/non-finite upper bound must never look like remaining budget.
    if result != result or result < 0:
        return float("inf")
    return result


def worker_cost_snapshot(
    run: Callable[..., str], source_id: str
) -> tuple[float, float]:
    """Global/source cost plus today's holds; unknown liability returns infinity."""
    raw = run(
        """
        SELECT json_build_object(
            'global_unknown', EXISTS (
                SELECT 1 FROM provider_receipt outstanding
                WHERE CASE
                    WHEN outstanding.billing_basis='MEASURED_PROVIDER_COST'
                        THEN outstanding.measured_cost_usd IS NULL OR outstanding.measured_cost_usd <= 0
                    WHEN outstanding.billing_basis='ESTIMATED_ONLY'
                        THEN outstanding.estimated_cost_usd IS NULL OR outstanding.estimated_cost_usd <= 0
                    ELSE TRUE
                END
            ) OR EXISTS (
                SELECT 1 FROM worker_budget_reservation h
                WHERE h.state='RESERVED'
                  AND h.reserved_at < date_trunc('day',now())
            ),
            'source_unknown', EXISTS (
                SELECT 1 FROM provider_receipt outstanding
                JOIN content_item outstanding_content ON outstanding_content.id=outstanding.content_id
                WHERE outstanding_content.source_id=:'source_id'
                AND CASE
                    WHEN outstanding.billing_basis='MEASURED_PROVIDER_COST'
                        THEN outstanding.measured_cost_usd IS NULL OR outstanding.measured_cost_usd <= 0
                    WHEN outstanding.billing_basis='ESTIMATED_ONLY'
                        THEN outstanding.estimated_cost_usd IS NULL OR outstanding.estimated_cost_usd <= 0
                    ELSE TRUE
                END
            ) OR EXISTS (
                SELECT 1 FROM worker_budget_reservation h
                WHERE h.state='RESERVED'
                  AND h.source_id=:'source_id'
                  AND h.reserved_at < date_trunc('day',now())
            ),
            'global', COALESCE(sum(
                CASE
                    WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                        THEN r.measured_cost_usd
                    ELSE r.estimated_cost_usd
                END
            ), 0) + (
                SELECT COALESCE(sum(h.upper_bound_usd),0)
                FROM worker_budget_reservation h
                WHERE h.state='RESERVED'
                  AND h.reserved_at >= date_trunc('day',now())
            ),
            'source', COALESCE(sum(
                CASE
                    WHEN r.billing_basis='MEASURED_PROVIDER_COST'
                        THEN r.measured_cost_usd
                    ELSE r.estimated_cost_usd
                END
            ) FILTER (WHERE c.source_id = :'source_id'), 0) + (
                SELECT COALESCE(sum(h.upper_bound_usd),0)
                FROM worker_budget_reservation h
                WHERE h.state='RESERVED'
                  AND h.source_id=:'source_id'
                  AND h.reserved_at >= date_trunc('day',now())
            )
        )::text
        FROM provider_receipt r
        LEFT JOIN content_item c ON c.id = r.content_id
        WHERE COALESCE(r.started_at, r.completed_at, now())
            >= date_trunc('day', now());
        """,
        source_id=source_id,
    )
    row = json.loads(raw or '{"global":0,"source":0}')
    global_cost = (
        float("inf") if row.get("global_unknown") is True else float(row["global"])
    )
    source_cost = (
        float("inf") if row.get("source_unknown") is True else float(row["source"])
    )
    if global_cost != global_cost or global_cost < 0:
        global_cost = float("inf")
    if source_cost != source_cost or source_cost < 0:
        source_cost = float("inf")
    return global_cost, source_cost
