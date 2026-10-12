"""DP-419: additive private PG metadata Capture->canonical Segment attestation.

The evidence digest is caller-supplied and unverified; neither IDs nor Capture
rights_status = CLEARED permit playback. No provider or media download here.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from typing import Any


_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_:/.-]{0,179}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_PARAMETERS = (
    'binding_id', 'event_id', 'expected_revision', 'action',
    'content_id', 'capture_id', 'capture_sha256', 'canonical_segment_id',
    'start_ms', 'end_ms', 'evidence_sha256', 'attestor_ref',
)
_SQL = """SELECT record_media_capture_segment_binding(
    :'binding_id', :'event_id', :'expected_revision'::integer, :'action',
    :'content_id', :'capture_id', :'capture_sha256', :'canonical_segment_id',
    :'start_ms'::bigint, :'end_ms'::bigint, :'evidence_sha256', :'attestor_ref'
)::text;"""


class PgMediaCaptureBindingStore:
    """Atomic PostgreSQL operations against caller-supplied local DSN only."""

    def __init__(self, dsn: str):
        if not isinstance(dsn, str) or not dsn.startswith('postgresql://'):
            raise ValueError('BINDING_DSN_REQUIRED')
        self._dsn = dsn

    def _execute(
        self, sql: str, values: Mapping[str, object], *,
        force_rollback: bool = False,
    ) -> dict[str, Any]:
        # psql single-quotes :'variable' as an SQL literal, never inline
        # untrusted SQL. Errors exclude DSN, query and private credentials.
        argv = ['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                '--dbname', self._dsn]
        for name, value in values.items():
            argv.extend(['-v', f'{name}={value}'])
        if force_rollback:
            sql = f'BEGIN;\n{sql}\nROLLBACK;'
        try:
            done = subprocess.run(
                argv, input=sql, text=True, capture_output=True,
                timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError('BINDING_STORE_UNAVAILABLE') from None
        if done.returncode != 0:
            match = re.search(r'BINDING_[A-Z_]+', done.stderr)
            raise RuntimeError(match.group(0) if match else 'BINDING_STORE_UNAVAILABLE')
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise RuntimeError('BINDING_RECEIPT_INVALID')
        try:
            result = json.loads(lines[0])
        except (TypeError, ValueError):
            raise RuntimeError('BINDING_RECEIPT_INVALID') from None
        if (
            not isinstance(result, dict)
            or result.get('contract_version') != 'studio-capture-segment-binding-pg-v1'
            or result.get('private_only') is not True
            or any(result.get(key) is not False for key in (
                'publication_authority', 'rights_clearance', 'seek_authorized',
            ))
        ):
            raise RuntimeError('BINDING_RECEIPT_INVALID')
        return result

    def inspect(self, *, binding_id: str) -> dict[str, Any]:
        if not isinstance(binding_id, str) or not _ID.fullmatch(binding_id):
            raise ValueError('BINDING_ID_INVALID')
        return self._execute(
            "SELECT inspect_media_capture_segment_binding(:'binding_id')::text;",
            {'binding_id': binding_id},
        )

    def record(self, **kwargs: object) -> dict[str, Any]:
        if set(kwargs) != set(_PARAMETERS):
            raise ValueError('BINDING_FIELDS_INVALID')
        if not all(isinstance(kwargs[key], str) and _ID.fullmatch(kwargs[key])
                   for key in ('binding_id', 'event_id', 'content_id', 'capture_id',
                               'canonical_segment_id', 'attestor_ref')):
            raise ValueError('BINDING_ID_INVALID')
        if not all(isinstance(kwargs[key], str) and _SHA.fullmatch(kwargs[key])
                   for key in ('capture_sha256', 'evidence_sha256')):
            raise ValueError('BINDING_HASH_INVALID')
        if (
            type(kwargs['expected_revision']) is not int
            or kwargs['expected_revision'] < 0
            or type(kwargs['start_ms']) is not int
            or type(kwargs['end_ms']) is not int
            or not 0 <= kwargs['start_ms'] < kwargs['end_ms'] <= 2**63 - 1
            or kwargs['action'] not in ('ATTEST', 'HOLD', 'REVOKE')
        ):
            raise ValueError('BINDING_INPUT_INVALID')
        return self._execute(_SQL, kwargs)

    def record_in_transaction(
        self, *, operation: Mapping[str, object], force_rollback: bool,
    ) -> dict[str, Any]:
        """Canary-only rollback of one all-or-nothing attestation transaction."""
        if force_rollback is not True or set(operation) != set(_PARAMETERS):
            raise ValueError('BINDING_ROLLBACK_INPUT_INVALID')
        return self._execute(_SQL, operation, force_rollback=True)


__all__ = ['PgMediaCaptureBindingStore']
