"""DP-516 private checkpoint on a *disposable* canonical PostgreSQL corpus.

Records only already-persisted canonical Capture/Passage lineage. This cannot
authenticate historical sources, license rights, approve DP-443, reserve costs,
dispatch ingestion, publish, or verify a live MiniPC. Never use against prod.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from dichiarazioni_pubbliche.historical_batch_gate_v1 import (
    BatchCheckpoint,
    CompletedCapture,
    HistoricalBatchDecision,
    HistoricalBatchItemProposal,
    MAX_BATCH_ITEMS,
    VERSION,
    _hash,
    _work_key,
    create_checkpoint,
)
from dichiarazioni_pubbliche.historical_corpus_preflight_v1 import (
    HistoricalManifest,
    preflight_historical_corpus,
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_./-]{0,199}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PG_ERROR = re.compile(r"DP516_PG_[A-Z_]+")


def _quoted(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or "\x00" in value
        or "$txn$" in value.lower()
    ):
        raise ValueError("DP516_PG_INPUT_INVALID")
    return "'" + value.replace("'", "''") + "'"


def _id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("DP516_PG_ID_INVALID")
    return value


def _sha(value: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError("DP516_PG_SHA_INVALID")
    return value


@dataclass(frozen=True)
class PgCheckpointResult:
    checkpoint: BatchCheckpoint
    replayed: bool
    dispatch_authorized: bool = False
    pilot_accepted_by_system: bool = False
    publication_authority: bool = False


_FIXTURE = """
CREATE TABLE IF NOT EXISTS dp516_pg_batch(
 batch_id text PRIMARY KEY, scope_id text NOT NULL,
 manifest_fingerprint text NOT NULL, revision bigint NOT NULL DEFAULT 0
 CHECK(revision >= 0));
CREATE TABLE IF NOT EXISTS dp516_pg_version(
 batch_id text NOT NULL REFERENCES dp516_pg_batch(batch_id),
 revision bigint NOT NULL CHECK(revision > 0),
 item_key text NOT NULL,
 person_id text NOT NULL REFERENCES person(id),
 source_id text NOT NULL REFERENCES source(id),
 content_id text NOT NULL REFERENCES content_item(id),
 capture_id text NOT NULL REFERENCES content_capture(id),
 passage_id text NOT NULL REFERENCES passage(id),
 rights_id text NOT NULL REFERENCES private_source_rights_record(id),
 rights_subject_sha text NOT NULL,
 rights_policy text NOT NULL,
 source_family text NOT NULL,
 source_sha text NOT NULL,
 quote_sha text NOT NULL,
 original_language text NOT NULL,
 observed_at timestamptz NOT NULL,
 canonical_url text NOT NULL,
 translation_sha text,
 translation_language text,
 translation_method text,
 receipt_sha text NOT NULL,
 document jsonb NOT NULL,
 PRIMARY KEY(batch_id,revision), UNIQUE(batch_id,item_key),
 CHECK (source_sha ~ '^[0-9a-f]{64}$' AND quote_sha ~ '^[0-9a-f]{64}$'
 AND receipt_sha ~ '^[0-9a-f]{64}$' AND rights_subject_sha ~ '^[0-9a-f]{64}$'),
 CHECK ((translation_sha IS NULL AND translation_language IS NULL
         AND translation_method IS NULL)
    OR (translation_sha ~ '^[0-9a-f]{64}$' AND translation_sha <> quote_sha
        AND translation_language <> original_language
        AND translation_language='it' AND length(translation_method)>0))
);
CREATE OR REPLACE FUNCTION dp516_pg_no_mutation() RETURNS trigger
LANGUAGE plpgsql AS $guard$
BEGIN RAISE EXCEPTION 'DP516_PG_APPEND_ONLY'; END $guard$;
DROP TRIGGER IF EXISTS dp516_pg_version_immutable ON dp516_pg_version;
CREATE TRIGGER dp516_pg_version_immutable
 BEFORE UPDATE OR DELETE ON dp516_pg_version
 FOR EACH ROW EXECUTE FUNCTION dp516_pg_no_mutation();
CREATE OR REPLACE FUNCTION dp516_pg_guard(r dp516_pg_version)
RETURNS void LANGUAGE plpgsql AS $guard$
BEGIN
 PERFORM 1
 FROM person p
 JOIN content_item ci ON true
 JOIN source s ON s.id=ci.source_id
 JOIN content_capture ca ON ca.content_id=ci.id
 JOIN passage pa ON pa.capture_id=ca.id AND pa.content_id=ci.id
 JOIN private_source_rights_record rr ON rr.content_id=ci.id
 WHERE p.id=r.person_id AND p.is_public_figure
   AND s.id=r.source_id AND ci.id=r.content_id
   AND ca.id=r.capture_id AND pa.id=r.passage_id AND rr.id=r.rights_id
   AND ci.canonical_url=r.canonical_url
   AND ci.language=r.original_language AND pa.language=r.original_language
   AND ca.content_sha256=r.source_sha AND pa.text_sha256=r.quote_sha
   AND ca.observed_at=r.observed_at
   AND ci.rights_status='CLEARED' AND ca.rights_status='CLEARED'
   AND ca.status='CAPTURED' AND ca.hold_status='NONE'
   AND rr.source_family=r.source_family
   AND rr.subject_fingerprint=r.rights_subject_sha
   AND rr.locator_kind='URL' AND rr.locator_value=r.canonical_url
   AND rr.record_visibility='PRIVATE'
   AND rr.policy_version=r.rights_policy AND rr.rights_status='CLEARED'
   AND rr.reviewed_at IS NOT NULL AND rr.reviewer_ref IS NOT NULL
   AND rr.rights_receipt_ref IS NOT NULL
   AND (rr.expires_at IS NULL OR rr.expires_at > now())
   AND rr.permitted_uses @> ARRAY['FETCH','STORE_BODY','PARSE_TEXT']::text[]
   AND (r.translation_sha IS NULL OR
        rr.permitted_uses @> ARRAY['TRANSLATE']::text[])
   AND NOT EXISTS(SELECT 1 FROM private_source_rights_record successor
      WHERE successor.supersedes_id=rr.id)
   AND (SELECT count(*) FROM private_source_rights_record sibling
        WHERE sibling.content_id=ci.id AND sibling.source_family=r.source_family
          AND NOT EXISTS(SELECT 1 FROM private_source_rights_record newer_right
              WHERE newer_right.supersedes_id=sibling.id))=1
   AND NOT EXISTS(SELECT 1 FROM content_capture newer
      WHERE newer.content_id=ci.id AND newer.id<>ca.id
        AND newer.observed_at>=ca.observed_at)
 FOR UPDATE OF p,ci,s,ca,pa,rr;
 IF NOT FOUND THEN
   RAISE EXCEPTION 'DP516_PG_LINEAGE_OR_RIGHTS_STALE';
 END IF;
END $guard$;
"""


class IsolatedHistoricalCheckpointPg:
    """Never authorizes jobs. Operates only inside dp516_disposable on loopback."""

    def __init__(self, dsn: str, *, allow_disposable_postgres: bool = False):
        parsed = urlsplit(dsn)
        if (
            allow_disposable_postgres is not True
            or parsed.scheme not in {"postgresql", "postgres"}
            or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username != "postgres"
            or not parsed.port
            or parsed.path != "/dp516_disposable"
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not shutil.which("psql")
        ):
            raise ValueError("DP516_PG_DISPOSABLE_ONLY")
        self.dsn = dsn

    def _sql(self, sql: str) -> str:
        result = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-d", self.dsn],
            input=sql,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            match = _PG_ERROR.search(result.stderr)
            raise ValueError(match.group(0) if match else "DP516_PG_QUERY_FAILED")
        return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""

    def install_fixture_schema(self) -> None:
        self._sql(_FIXTURE)

    def _load(self, batch_id: str) -> tuple[BatchCheckpoint | None, int]:
        bid = _quoted(_id(batch_id))
        raw = self._sql(f"""
BEGIN;
DO $check$
DECLARE r dp516_pg_version;
BEGIN
 FOR r IN SELECT * FROM dp516_pg_version WHERE batch_id={bid} ORDER BY revision LOOP
   PERFORM dp516_pg_guard(r);
 END LOOP;
END $check$;
SELECT jsonb_build_object(
  'batch', (SELECT to_jsonb(b) FROM dp516_pg_batch b WHERE batch_id={bid}),
  'versions', coalesce((SELECT jsonb_agg(jsonb_build_object(
    'revision',revision,'document',document, 'item_key',item_key,
    'receipt_sha',receipt_sha,'person_id',person_id,'content_id',content_id,
    'source_family',source_family,'source_sha',source_sha) ORDER BY revision)
    FROM dp516_pg_version WHERE batch_id={bid}), '[]'::jsonb))::text;
COMMIT;""")
        snapshot = json.loads(raw)
        rows = snapshot["versions"]
        head = snapshot["batch"]
        if not rows:
            if head is not None and head["revision"] != 0:
                raise ValueError("DP516_PG_HISTORY_TAMPERED")
            return None, 0
        if (
            head is None
            or head["revision"] != len(rows)
            or head["manifest_fingerprint"]
            != rows[0]["document"]["manifest_fingerprint"]
            or head["batch_id"] != batch_id
        ):
            raise ValueError("DP516_PG_HISTORY_TAMPERED")
        latest: BatchCheckpoint | None = None
        for number, row in enumerate(rows, 1):
            data = row["document"]
            receipts = tuple(CompletedCapture(**entry) for entry in data["completed"])
            expected = create_checkpoint(
                data["batch_id"],
                data["manifest_fingerprint"],
                receipts,
                revision=data["revision"],
                failed=data["failed"],
            )
            if row["revision"] != number or data != json.loads(
                json.dumps(asdict(expected))
            ):
                raise ValueError("DP516_PG_CHECKPOINT_TAMPERED")
            new = [r for r in receipts if latest is None or r not in latest.completed]
            if len(new) != 1 or (
                new[0].item_key,
                new[0].person_id,
                new[0].content_id,
                new[0].source_family,
                new[0].capture_sha256,
                new[0].persisted_receipt_sha256,
            ) != (
                row["item_key"],
                row["person_id"],
                row["content_id"],
                row["source_family"],
                row["source_sha"],
                row["receipt_sha"],
            ):
                raise ValueError("DP516_PG_HISTORY_TAMPERED")
            if latest and (
                expected.manifest_fingerprint != latest.manifest_fingerprint
                or expected.batch_id != latest.batch_id
                or len(receipts) != len(latest.completed) + 1
                or not set(latest.completed).issubset(receipts)
            ):
                raise ValueError("DP516_PG_HISTORY_TAMPERED")
            latest = expected
        return latest, len(rows)

    def read(self, batch_id: str) -> BatchCheckpoint | None:
        return self._load(batch_id)[0]

    def verify_current(self, checkpoint: BatchCheckpoint, batch_id: str) -> bool:
        if (
            not isinstance(checkpoint, BatchCheckpoint)
            or checkpoint.batch_id != batch_id
        ):
            return False
        try:
            return self.read(batch_id) == checkpoint
        except ValueError:
            return False

    def append(
        self,
        *,
        manifests: tuple[HistoricalManifest, ...],
        decision: HistoricalBatchDecision,
        proposal: HistoricalBatchItemProposal,
        capture: CompletedCapture,
        scope_id: str,
        source_id: str,
        capture_id: str,
        expected_revision: int,
        original_quote_sha256: str,
        translated_quote_sha256: str | None = None,
        translation_language: str | None = None,
        translation_method: str | None = None,
    ) -> PgCheckpointResult:
        if (
            not isinstance(decision, HistoricalBatchDecision)
            or decision.status != "PRIVATE_REVIEW_PLAN"
            or decision.dispatch_authorized
            or decision.public_eligible
            or decision.pilot_accepted_by_system
            or not isinstance(proposal, HistoricalBatchItemProposal)
            or proposal not in decision.proposals
            or proposal.dispatch_authorized
            or not isinstance(capture, CompletedCapture)
            or type(expected_revision) is not int
            or expected_revision < 0
        ):
            raise ValueError("DP516_PG_PRIVATE_PLAN_REQUIRED")
        try:
            corpus = preflight_historical_corpus(
                manifests,
                now=max(entry.observed_at for m in manifests for entry in m.entries),
            )
        except (ValueError, TypeError, AttributeError):
            raise ValueError("DP516_PG_MANIFEST_DRIFT") from None
        if (
            corpus.manifest_fingerprint != decision.manifest_fingerprint
            or decision.batch_id
            != "batch:" + _hash([VERSION, _id(scope_id), corpus.manifest_fingerprint])
        ):
            raise ValueError("DP516_PG_MANIFEST_DRIFT")
        if (
            corpus.missing_primary_subjects
            or not 1 <= len(corpus.rows) <= MAX_BATCH_ITEMS
            or any(
                row.state != "PRIVATE_REVIEW_ONLY" or row.holds for row in corpus.rows
            )
        ):
            raise ValueError("DP516_PG_CORPUS_HELD")
        entry_rows = [
            (m, e)
            for m in manifests
            for e in m.entries
            if m.person_id == proposal.person_id and e.content_id == proposal.content_id
        ]
        if len(entry_rows) != 1:
            raise ValueError("DP516_PG_PERSON_SCOPE_INVALID")
        manifest, entry = entry_rows[0]
        if (
            not any(
                row.content_id == entry.content_id
                and row.state == "PRIVATE_REVIEW_ONLY"
                and not row.holds
                for row in corpus.rows
            )
            or entry.source_kind not in {"PRIMARY_ORIGINAL", "ARCHIVE_COPY"}
            or entry.exact_locator is None
            or entry.exact_locator.passage_id is None
            or (
                proposal.person_id,
                proposal.content_id,
                proposal.source_family,
                proposal.capture_sha256,
            )
            != (
                capture.person_id,
                capture.content_id,
                capture.source_family,
                capture.capture_sha256,
            )
            or capture.item_key != proposal.item_key
            or capture.item_key
            != _work_key(
                manifest.person_id,
                entry.source_family,
                entry.content_id,
                entry.source_version_sha256,
            )
            or entry.source_version_sha256 != capture.capture_sha256
        ):
            raise ValueError("DP516_PG_SOURCE_SCOPE_INVALID")
        if any(
            v is not None
            for v in (
                translated_quote_sha256,
                translation_language,
                translation_method,
            )
        ):
            if (
                not all(
                    isinstance(v, str) and v
                    for v in (
                        translated_quote_sha256,
                        translation_language,
                        translation_method,
                    )
                )
                or translation_language != "it"
                or entry.original_language == "it"
            ):
                raise ValueError("DP516_PG_TRANSLATION_SEPARATION_REQUIRED")
            if translated_quote_sha256 == original_quote_sha256:
                raise ValueError("DP516_PG_TRANSLATION_SEPARATION_REQUIRED")
            _id(translation_method)
            _sha(translated_quote_sha256)
        for value in (
            source_id,
            capture_id,
            manifest.person_id,
            entry.exact_locator.passage_id,
            entry.rights_record_id,
        ):
            _id(value)
        _sha(original_quote_sha256)
        _sha(capture.persisted_receipt_sha256)
        prior, revision = self._load(decision.batch_id)
        if prior and prior.manifest_fingerprint != decision.manifest_fingerprint:
            raise ValueError("DP516_PG_MANIFEST_DRIFT")
        completed = (
            tuple(sorted((*prior.completed, capture), key=lambda c: c.item_key))
            if prior
            else (capture,)
        )
        if prior and any(c.item_key == capture.item_key for c in prior.completed):
            completed = prior.completed
        checkpoint = create_checkpoint(
            decision.batch_id,
            decision.manifest_fingerprint,
            completed,
            revision=revision + (completed != (prior.completed if prior else ())),
        )

        # The CAS and all canonical lineage/right checks happen together in PG.
        def val(value: str) -> str:
            return _quoted(value)

        def translation(value: str | None) -> str:
            return "NULL" if value is None else val(value)

        if entry.rights_record is None:
            raise ValueError("DP516_PG_RIGHTS_MISSING")
        row_data = (
            decision.batch_id,
            proposal.item_key,
            proposal.person_id,
            source_id,
            proposal.content_id,
            capture_id,
            entry.exact_locator.passage_id,
            entry.rights_record_id,
            entry.rights_record.subject_fingerprint,
            entry.rights_policy_version,
            proposal.source_family,
            proposal.capture_sha256,
            original_quote_sha256,
            entry.original_language,
        )
        row_sql = ",".join(val(v) for v in row_data)
        observed = _quoted(entry.observed_at.isoformat())
        final_payload = _quoted(json.dumps(asdict(checkpoint), sort_keys=True))
        script = f"""
BEGIN;
CREATE TEMP TABLE dp516_pg_action(value text NOT NULL) ON COMMIT DROP;
INSERT INTO dp516_pg_batch(batch_id,scope_id,manifest_fingerprint,revision)
 VALUES({val(decision.batch_id)},{val(scope_id)},
 {val(decision.manifest_fingerprint)},0) ON CONFLICT DO NOTHING;
DO $txn$
DECLARE b dp516_pg_batch; old dp516_pg_version; item dp516_pg_version;
BEGIN
 SELECT * INTO b FROM dp516_pg_batch WHERE batch_id={val(decision.batch_id)} FOR UPDATE;
 IF b.manifest_fingerprint<>{val(decision.manifest_fingerprint)}
    OR b.scope_id<>{val(scope_id)}
 THEN RAISE EXCEPTION 'DP516_PG_MANIFEST_DRIFT'; END IF;
 FOR old IN SELECT * FROM dp516_pg_version
   WHERE batch_id={val(decision.batch_id)} ORDER BY revision LOOP
   PERFORM dp516_pg_guard(old);
 END LOOP;
 SELECT * INTO item FROM dp516_pg_version
   WHERE batch_id={val(decision.batch_id)} AND item_key={val(proposal.item_key)};
 IF FOUND THEN
   IF item.person_id<>{val(proposal.person_id)}
      OR item.source_id<>{val(source_id)} OR item.content_id<>{val(proposal.content_id)}
      OR item.capture_id<>{val(capture_id)}
      OR item.receipt_sha<>{val(capture.persisted_receipt_sha256)}
      OR item.quote_sha<>{val(original_quote_sha256)}
      OR item.translation_sha IS DISTINCT FROM {translation(translated_quote_sha256)}
      OR item.translation_language IS DISTINCT FROM {translation(translation_language)}
      OR item.translation_method IS DISTINCT FROM {translation(translation_method)}
   THEN RAISE EXCEPTION 'DP516_PG_REPLAY_CONFLICT'; END IF;
   INSERT INTO dp516_pg_action VALUES('REPLAY');
 ELSIF b.revision<>{expected_revision} THEN
   RAISE EXCEPTION 'DP516_PG_REVISION_CONFLICT';
 ELSE
   INSERT INTO dp516_pg_version(
     batch_id,item_key,person_id,source_id,content_id,capture_id,passage_id,
     rights_id,rights_subject_sha,rights_policy,source_family,source_sha,
     quote_sha,original_language,revision,observed_at,canonical_url,
     translation_sha,translation_language,translation_method,receipt_sha,document)
   VALUES({row_sql},b.revision + 1,{observed},{val(entry.locator_url)},
      {translation(translated_quote_sha256)},{translation(translation_language)},
      {translation(translation_method)},{val(capture.persisted_receipt_sha256)},
      {final_payload}::jsonb);
   SELECT * INTO item FROM dp516_pg_version
     WHERE batch_id={val(decision.batch_id)} AND revision=b.revision+1;
   PERFORM dp516_pg_guard(item);
   UPDATE dp516_pg_batch SET revision=revision+1
    WHERE batch_id={val(decision.batch_id)};
   INSERT INTO dp516_pg_action VALUES('APPENDED');
 END IF;
END $txn$;
SELECT value FROM dp516_pg_action;
COMMIT;
"""
        action = self._sql(script)
        persisted, _ = self._load(decision.batch_id)
        if persisted is None:
            raise ValueError("DP516_PG_CHECKPOINT_MISSING")
        if capture not in persisted.completed:
            raise ValueError("DP516_PG_CHECKPOINT_DIVERGED")
        return PgCheckpointResult(persisted, action == "REPLAY")


__all__ = ["IsolatedHistoricalCheckpointPg", "PgCheckpointResult"]
