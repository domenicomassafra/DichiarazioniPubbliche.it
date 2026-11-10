"""DP-413: one unattended tick over the existing autonomous authorities.

Composition only. This module cannot grant rights, execute a model, serve
public bytes or replace an authority: capture, challenge, the two independent
reviewers, the public surface, the third auditor and the correction ledger stay
independent and fail closed. A tick reports what those authorities decided; it
is never by itself permission to publish.

The scheduler calls `AutonomousPipeline.run()` when source, challenge or
provider admission inputs change and once per UTC night for the third audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Protocol

from dichiarazioni_pubbliche.autonomous_operations import (
    AuditPacketAuthority, AutonomousOperations, CorrectionMetricEvent,
    ReviewAuthority, RunReceipt, daily_metrics,
)
from dichiarazioni_pubbliche.autonomous_runner_v3 import PersistentRunner, SQLiteRunJournal
from dichiarazioni_pubbliche.nightly_audit import (
    NightlyAuditCoordinator, NightlyLedger, NightlyResult,
)

DEFAULT_RECORD_LIMIT = 25
MAX_RECORD_LIMIT = 1000


class RecordQueue(Protocol):
    """Enumerate the private records a tick must re-evaluate, in stable order."""

    def current_record_ids(self) -> tuple[str, ...] | list[str]: ...


@dataclass(frozen=True)
class TickReport:
    """Durable-authority outcome of one tick; `metrics` is never zero-filled."""

    at: datetime
    status: str
    reason_codes: tuple[str, ...]
    processed: tuple[str, ...]
    deferred: tuple[str, ...]
    failed: tuple[str, ...]
    runs: tuple[RunReceipt, ...]
    audit: NightlyResult | None
    metrics: dict[str, int | str]

    @property
    def completed(self) -> bool:
        return self.status == "TICK_OK" and not self.failed


class AutonomousPipeline:
    """Bound one unattended tick without weakening any existing gate.

    A failing record cannot hide or stop the other records, an unavailable
    queue produces no model work, and the nightly audit runs at most once per
    UTC day through the coordinator's frozen manifest, not once per tick.
    """

    def __init__(
        self, *,
        operations: AutonomousOperations,
        runner: PersistentRunner,
        queue: RecordQueue,
        corrections: Callable[[], tuple[CorrectionMetricEvent, ...]],
        limit: int = DEFAULT_RECORD_LIMIT,
        audit_ledger: NightlyLedger | None = None,
        packet_authority: AuditPacketAuthority | None = None,
        third: ReviewAuthority | None = None,
    ) -> None:
        if not isinstance(operations, AutonomousOperations):
            raise ValueError("DP413_PIPELINE_OPERATIONS_REQUIRED")
        if not isinstance(runner, PersistentRunner):
            raise ValueError("DP413_PIPELINE_RUNNER_REQUIRED")
        if runner.operations is not operations or runner.journal is not operations.journal:
            raise ValueError("DP413_PIPELINE_JOURNAL_AUTHORITY_MISMATCH")
        if not isinstance(operations.journal, SQLiteRunJournal):
            raise ValueError("DP413_PIPELINE_DURABLE_JOURNAL_REQUIRED")
        if not callable(getattr(queue, "current_record_ids", None)):
            raise ValueError("DP413_PIPELINE_RECORD_QUEUE_REQUIRED")
        if not callable(corrections):
            raise ValueError("DP413_PIPELINE_CORRECTIONS_REQUIRED")
        if type(limit) is not int or not 1 <= limit <= MAX_RECORD_LIMIT:
            raise ValueError("DP413_PIPELINE_LIMIT_INVALID")
        audit_authorities = (audit_ledger, packet_authority, third)
        if any(item is not None for item in audit_authorities) and any(
            item is None for item in audit_authorities
        ):
            raise ValueError("DP413_PIPELINE_AUDIT_AUTHORITIES_INCOMPLETE")
        self.operations = operations
        self.runner = runner
        self.journal = operations.journal
        self.queue = queue
        self.corrections = corrections
        self.limit = limit
        self.packet_authority = packet_authority
        self.third = third
        self.coordinator = (
            NightlyAuditCoordinator(audit_ledger) if audit_ledger is not None else None
        )

    def _corrections(self) -> tuple[CorrectionMetricEvent, ...] | None:
        """The correction authority is required; an unavailable one is explicit."""
        try:
            events = self.corrections()
        except Exception:
            return None
        if not isinstance(events, (tuple, list)):
            return None
        return tuple(events)

    def _queue(self) -> tuple[tuple[str, ...] | None, str, tuple[str, ...]]:
        try:
            listed = self.queue.current_record_ids()
        except Exception:
            return None, "QUEUE_UNAVAILABLE", ("RECORD_QUEUE_UNAVAILABLE",)
        if not isinstance(listed, (tuple, list)):
            return None, "QUEUE_INVALID", ("RECORD_QUEUE_INVALID",)
        if any(
            type(record_id) is not str or not record_id.strip()
            or record_id != record_id.strip()
            for record_id in listed
        ) or len(set(listed)) != len(listed):
            return None, "QUEUE_INVALID", ("RECORD_QUEUE_INVALID",)
        return tuple(listed), "TICK_OK", ()

    def _audit(
        self, at: datetime, day: date | None,
        corrections: tuple[CorrectionMetricEvent, ...] | None,
    ) -> tuple[NightlyResult | None, str, tuple[str, ...]]:
        if day is None:
            return None, "TICK_OK", ()
        if self.coordinator is None:
            return None, "AUDIT_UNAVAILABLE", ("AUDIT_NOT_CONFIGURED",)
        if corrections is None:
            return None, "AUDIT_UNAVAILABLE", ("CORRECTIONS_UNAVAILABLE",)
        try:
            result = self.coordinator.run(
                operations=self.operations, packet_authority=self.packet_authority,
                third=self.third, events=self.journal.all_events(),
                corrections=corrections, day=day, now=at,
            )
        except (TypeError, ValueError):
            return None, "AUDIT_REJECTED", ("NIGHTLY_AUDIT_REJECTED",)
        except Exception:
            return None, "AUDIT_FAILED", ("NIGHTLY_AUDIT_FAILED",)
        return result, "TICK_OK", ()

    def run(
        self, *, now: datetime, provider_revision: str = "",
        audit_day: date | None = None,
    ) -> TickReport:
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise ValueError("DP413_PIPELINE_REQUIRES_TZ_AWARE_INSTANT")
        at = now.astimezone(timezone.utc)
        if type(provider_revision) is not str or len(provider_revision) > 256:
            raise ValueError("DP413_PIPELINE_PROVIDER_REVISION_INVALID")
        if audit_day is not None and (
            type(audit_day) is not date or audit_day > at.date()
        ):
            return TickReport(
                at, "AUDIT_REJECTED", ("NIGHTLY_AUDIT_DAY_INVALID",),
                (), (), (), (), None, {},
            )
        if audit_day is not None and self.coordinator is None:
            return TickReport(
                at, "AUDIT_UNAVAILABLE", ("AUDIT_NOT_CONFIGURED",),
                (), (), (), (), None, {},
            )
        selected, queue_status, reasons = self._queue()
        if selected is None:
            return TickReport(at, queue_status, reasons, (), (), (), (), None, {})
        corrections = self._corrections()
        if corrections is None:
            return TickReport(
                at, "METRICS_UNAVAILABLE", ("CORRECTIONS_UNAVAILABLE",),
                (), selected, (), (), None, {},
            )
        try:
            daily_metrics(self.journal.all_events(), at.date(), corrections=corrections)
        except (TypeError, ValueError):
            return TickReport(
                at, "METRICS_INVALID", ("METRICS_INVALID",),
                (), selected, (), (), None, {},
            )
        processed, deferred = selected[: self.limit], selected[self.limit:]
        runs: list[RunReceipt] = []
        failed: list[str] = []
        for record_id in processed:
            try:
                runs.append(self.runner.run(
                    record_id, now=at, provider_revision=provider_revision,
                ))
            except Exception:
                # One record's failure must not stop or hide the others; the
                # runner already withdrew anything it could not prove.
                failed.append(record_id)
        if failed:
            reasons = (*reasons, "RECORD_RUN_FAILED")
        audit, audit_status, audit_reasons = self._audit(at, audit_day, corrections)
        reasons = (*reasons, *audit_reasons)
        try:
            metrics = daily_metrics(
                self.journal.all_events(), at.date(), corrections=corrections,
            )
        except (TypeError, ValueError):
            metrics = {}
            reasons = (*reasons, "METRICS_INVALID")
            metrics_status = "METRICS_INVALID"
        else:
            metrics_status = "TICK_OK"
        status = next(
            (value for value in (audit_status, metrics_status) if value != "TICK_OK"),
            "RECORD_RUN_FAILED" if failed else "TICK_OK",
        )
        return TickReport(
            at, status, reasons, processed, deferred, tuple(failed),
            tuple(runs), audit, metrics,
        )


__all__ = ["AutonomousPipeline", "RecordQueue", "TickReport"]
