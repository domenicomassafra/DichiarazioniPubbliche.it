"""PostgreSQL persistence and readback for DP-413E nightly audits.

Every run has one deterministic day ID; retries reuse its immutable sample.
The public writer, packet authority and audit model remain separate services.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from typing import Any

from dichiarazioni_pubbliche.autonomous_operations import RunReceipt
from dichiarazioni_pubbliche.nightly_audit import NightlyManifest
from dichiarazioni_pubbliche.queue_runtime import PsqlRuntime


class PgNightlyAuditLedger:
    def __init__(self, runtime: PsqlRuntime):
        self.db = runtime

    def begin(self, manifest: NightlyManifest) -> NightlyManifest:
        raw = self.db.run('''
            INSERT INTO autonomous_nightly_audit_run
                (run_id, audit_day, denominator, sampled_ids, started_at)
            VALUES (:'run_id', :'day'::date, :'denominator'::integer,
                    :'sampled'::jsonb, :'started_at'::timestamptz)
            ON CONFLICT DO NOTHING;
            SELECT row_to_json(t)::text FROM (
                SELECT run_id, audit_day, denominator, sampled_ids, started_at
                FROM autonomous_nightly_audit_run WHERE audit_day = :'day'::date
            ) t;
        ''', run_id=manifest.run_id, day=manifest.day.isoformat(),
            denominator=manifest.denominator,
            sampled=json.dumps(manifest.sampled),
            started_at=manifest.started_at.isoformat())
        # An existing date may not have the expected version/run ID; the
        # coordinator rejects that manifest instead of mixing run formats.
        data = json.loads(raw.splitlines()[-1])
        return NightlyManifest(
            data['run_id'], date.fromisoformat(data['audit_day']),
            data['denominator'], tuple(data['sampled_ids']),
            datetime.fromisoformat(data['started_at']),
        )

    def recorded(self, run_id: str) -> dict[str, RunReceipt]:
        raw = self.db.run('''
            SELECT COALESCE(json_agg(row_to_json(t))::text, '[]') FROM (
                SELECT record_id, disposition, evidence_sha256,
                       reason_codes, audited_at
                FROM autonomous_nightly_audit_result
                WHERE run_id = :'run_id' ORDER BY record_id
            ) t;
        ''', run_id=run_id)
        rows = json.loads(raw)
        return {
            row['record_id']: RunReceipt(
                row['record_id'], row['disposition'], row['evidence_sha256'],
                tuple(row['reason_codes']), datetime.fromisoformat(row['audited_at']),
            ) for row in rows
        }

    def append(self, run_id: str, receipt: RunReceipt, evidence: dict[str, object]) -> None:
        self.db.run('''
            INSERT INTO autonomous_nightly_audit_result
                (run_id, record_id, disposition, evidence_sha256, reason_codes, audited_at, evidence)
            SELECT :'run_id', :'record_id', :'disposition', NULLIF(:'evidence_sha256', ''),
                   :'reasons'::jsonb, :'audited_at'::timestamptz, :'evidence'::jsonb
            WHERE EXISTS (
                SELECT 1 FROM autonomous_nightly_audit_run
                WHERE run_id = :'run_id' AND sampled_ids ? :'record_id'
            )
            ON CONFLICT DO NOTHING;
        ''', run_id=run_id, record_id=receipt.record_id, disposition=receipt.disposition,
            evidence_sha256=receipt.evidence_sha256 or '',
            reasons=json.dumps(receipt.reason_codes), audited_at=receipt.at.isoformat(),
            evidence=json.dumps(evidence, sort_keys=True))
        if receipt.record_id not in self.recorded(run_id):
            raise RuntimeError('NIGHTLY_AUDIT_RESULT_NOT_PERSISTED')

    def complete(self, run_id: str, metrics: dict[str, int | str], at: datetime) -> None:
        self.db.run('''
            INSERT INTO autonomous_nightly_audit_complete
                (run_id, completed_at, metrics)
            SELECT r.run_id, :'completed_at'::timestamptz, :'metrics'::jsonb
            FROM autonomous_nightly_audit_run r
            WHERE r.run_id = :'run_id'
              AND (SELECT count(*) FROM autonomous_nightly_audit_result z
                   WHERE z.run_id = r.run_id) = jsonb_array_length(r.sampled_ids)
            ON CONFLICT DO NOTHING;
        ''', run_id=run_id, completed_at=at.isoformat(),
            metrics=json.dumps(metrics, sort_keys=True))
        if self.readback(run_id) is None:
            raise RuntimeError('NIGHTLY_AUDIT_COMPLETION_NOT_PERSISTED')

    def readback(self, run_id: str) -> dict[str, Any] | None:
        raw = self.db.run('''
            SELECT metrics::text FROM autonomous_nightly_audit_complete
            WHERE run_id = :'run_id';
        ''', run_id=run_id)
        return json.loads(raw) if raw else None

    def latest(self) -> dict[str, Any] | None:
        raw = self.db.run('''
            SELECT row_to_json(t)::text FROM (
                SELECT r.run_id, r.audit_day, r.started_at, r.denominator,
                       r.sampled_ids,
                       (SELECT count(*) FROM autonomous_nightly_audit_result z
                        WHERE z.run_id = r.run_id) AS persisted_results,
                       c.completed_at, c.metrics
                FROM autonomous_nightly_audit_run r
                LEFT JOIN autonomous_nightly_audit_complete c ON c.run_id = r.run_id
                ORDER BY r.audit_day DESC LIMIT 1
            ) t;
        ''')
        return json.loads(raw) if raw else None


    def results_readback(self, run_id: str) -> list[dict[str, Any]]:
        raw = self.db.run('''
            SELECT COALESCE(json_agg(row_to_json(t))::text, '[]') FROM (
                SELECT record_id, disposition, evidence_sha256, reason_codes,
                       audited_at, evidence
                FROM autonomous_nightly_audit_result
                WHERE run_id = :'run_id' ORDER BY record_id
            ) t;
        ''', run_id=run_id)
        return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Read private persisted DP-413E audit runs')
    parser.add_argument('--run-id', help='Specific immutable run; default latest UTC day')
    args = parser.parse_args(argv)
    db = PsqlRuntime(os.environ.get('DICHIARAZIONI_PUBBLICHE_DATABASE_URL'))
    ledger = PgNightlyAuditLedger(db)
    latest = ledger.latest()
    if latest is None:
        print(json.dumps({'status': 'NO_RUN', 'reason': 'NO_NIGHTLY_AUDIT_EXECUTION'}))
        return 2
    run_id = args.run_id or latest['run_id']
    if args.run_id and args.run_id != latest['run_id']:
        # Readback for historical runs is explicit and returns their immutable
        # manifest via the same store contract; do not mislabel as latest.
        data = db.run('''
            SELECT row_to_json(t)::text FROM (
                SELECT r.run_id, r.audit_day, r.started_at, r.denominator,
                       r.sampled_ids, c.completed_at, c.metrics
                FROM autonomous_nightly_audit_run r
                LEFT JOIN autonomous_nightly_audit_complete c ON c.run_id = r.run_id
                WHERE r.run_id = :'run_id'
            ) t;
        ''', run_id=run_id)
        if not data:
            print(json.dumps({'status': 'RUN_NOT_FOUND', 'run_id': run_id}))
            return 2
        latest = json.loads(data)
    latest['results'] = ledger.results_readback(run_id)
    latest['status'] = 'COMPLETE' if latest['completed_at'] else 'INCOMPLETE'
    print(json.dumps(latest, ensure_ascii=False, sort_keys=True))
    return 0 if latest['status'] == 'COMPLETE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
