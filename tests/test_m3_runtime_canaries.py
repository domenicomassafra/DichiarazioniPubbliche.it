from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    EXCERPT_PROFILE_APPROVED,
    EXCERPT_PUBLIC_USE_REQUIRED,
    ExcerptDecisionCode,
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
    render_attributed_excerpt,
)
from dichiarazioni_pubbliche.challenge_intake import (  # noqa: E402
    ChallengeLaunchProfile,
    ChallengeServiceState,
    submit_challenge,
)
from dichiarazioni_pubbliche.policy.challenge_workflow import ChallengeKind  # noqa: E402
from dichiarazioni_pubbliche.policy.intake_policy import (  # noqa: E402
    RateLimitProfile,
    RateLimitState,
    RateScope,
)
from dichiarazioni_pubbliche.projection_cleanup import (  # noqa: E402
    ProjectionArtifact,
    cleanup_takedown_current_artifacts,
)
from dichiarazioni_pubbliche.queue_runtime import (  # noqa: E402
    ProcessingJob,
    QueueRuntimeStore,
)
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    PublicProjectionStore,
    build_public_projection,
)
from dichiarazioni_pubbliche.review_admin import publish_correction  # noqa: E402
from dichiarazioni_pubbliche.source_intelligence import (  # noqa: E402
    SourceIntelligenceStore,
    load_source_intelligence_contract,
)
from dichiarazioni_pubbliche.worker_handlers_verification import (  # noqa: E402
    VerificationRelationReanalysisJobHandlers,
)
from dichiarazioni_pubbliche.wording_contract import wording_contract_metadata  # noqa: E402
from dichiarazioni_pubbliche.right_of_reply_intake import (  # noqa: E402
    ReplayKind,
    RightOfReplyLaunchProfile,
    ServiceReason,
    ServiceState,
    submit_right_of_reply,
)
from dichiarazioni_pubbliche.rights_complaint_bridge import RightsComplaintBridge  # noqa: E402
from dichiarazioni_pubbliche.rights_registry import (  # noqa: E402
    PrivateRightsRegistryStore,
    RightsSubject,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pg_bin(name: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    pg_config = shutil.which("pg_config")
    if pg_config:
        bindir = subprocess.run(
            [pg_config, "--bindir"], text=True, capture_output=True, check=True
        ).stdout.strip()
        candidate = Path(bindir) / name
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"PostgreSQL tool unavailable: {name}")


def _run(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result.stdout


class M3RuntimeCanaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for name in ("initdb", "pg_ctl", "psql"):
            _pg_bin(name)
        cls.tmp = tempfile.TemporaryDirectory(prefix="dp-m3-runtime-canary-")
        cls.root = Path(cls.tmp.name)
        cls.data_dir = cls.root / "data"
        cls.port = _free_port()
        cls.pg_ctl = _pg_bin("pg_ctl")
        _run(
            [
                _pg_bin("initdb"), "-D", str(cls.data_dir), "--username=postgres",
                "--auth=trust", "--encoding=UTF8", "--no-locale",
            ]
        )
        _run(
            [
                cls.pg_ctl, "-D", str(cls.data_dir), "-l", str(cls.root / "postgres.log"),
                "-o", f"-F -p {cls.port} -h 127.0.0.1 -k {cls.root}", "-w", "start",
            ]
        )
        cls.database_url = f"postgresql://postgres@127.0.0.1:{cls.port}/postgres"
        _run(
            [
                _pg_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname",
                cls.database_url, "-f", str(ROOT / "db" / "schema.v1.sql"),
            ]
        )
        _run(
            [
                _pg_bin("psql"), "-X", "-v", "ON_ERROR_STOP=1", "--dbname",
                cls.database_url, "-f", str(ROOT / "db" / "job_queue.v1.sql"),
            ]
        )
        cls.store = QueueRuntimeStore(cls.database_url)
        SourceIntelligenceStore(cls.database_url).sync_contract(load_source_intelligence_contract())
        cls._seed()

    @classmethod
    def tearDownClass(cls) -> None:
        _run([cls.pg_ctl, "-D", str(cls.data_dir), "-m", "fast", "-w", "stop"])
        cls.tmp.cleanup()

    @classmethod
    def _seed(cls) -> None:
        raw = "Synthetic cleared excerpt body for machine-only acceptance."
        raw_hash = hashlib.sha256(raw.encode()).hexdigest()
        cls.store.run(
            """
            INSERT INTO content_item(id, canonical_url, title, processing_status)
            VALUES
              ('content:dp302-canary','https://example.test/dp302','DP302 canary','PROCESSED'),
              ('content:dp305-canary','https://example.test/dp305','DP305 canary','PROCESSED');
            INSERT INTO atomic_claim(id,content_id,normalized_claim,claim_type,temporal_scope,check_worthy,metadata)
            VALUES
              ('claim:dp302-canary','content:dp302-canary','Synthetic reply target','CURRENT_POLICY','{}'::jsonb,true,'{}'::jsonb),
              ('claim:dp305-canary','content:dp305-canary','Synthetic rights target','CURRENT_POLICY','{}'::jsonb,true,'{}'::jsonb);
            INSERT INTO finding(id,claim_id,assessment,rationale,publication_status,policy_version,model_bundle)
            VALUES
              ('finding:dp302-canary','claim:dp302-canary','UNRESOLVED','Synthetic private intake target','POLICY_HOLD','policy:canary','{}'::jsonb),
              ('finding:dp305-canary','claim:dp305-canary','UNRESOLVED','Synthetic rights target','PUBLISH','policy:canary','{}'::jsonb);
            INSERT INTO evidence(id,canonical_url,source_type)
            VALUES ('evidence:dp305-canary','https://example.test/dp305/evidence','OFFICIAL_RECORD');
            INSERT INTO finding_evidence(finding_id,evidence_id,relation)
            VALUES ('finding:dp305-canary','evidence:dp305-canary','CONTEXT');
            INSERT INTO transcript_variant(id,content_id,provider_id,source_kind,raw_text_sha256,raw_text)
            VALUES ('variant:dp305-canary','content:dp305-canary','fixture','OFFICIAL',:'raw_hash',:'raw');
            INSERT INTO transcript_segment(id,variant_id,segment_index,start_ms,end_ms,text)
            VALUES ('segment:dp305-canary','variant:dp305-canary',0,0,1000,:'raw');
            """,
            raw_hash=raw_hash,
            raw=raw,
        )
        normalized_claim = "Il valore sintetico è 10."
        source_wording = "La fonte sintetica dichiara che il valore osservato è 10."
        quote_hash = hashlib.sha256(source_wording.encode()).hexdigest()
        wording = wording_contract_metadata(
            occurrence_id="statement:dp303-canary",
            source_text_sha256=quote_hash,
            normalized_claim=normalized_claim,
            language="it",
            derivation_version="candidate-extraction-v1",
        )
        cls.store.run(
            """
            INSERT INTO person(id,canonical_name) VALUES ('person:dp303-canary','Persona sintetica DP303');
            INSERT INTO content_item(id,canonical_url,title,published_at,processing_status)
            VALUES ('content:dp303-canary','https://example.test/dp303','DP303 canary','2026-09-21T10:00:00+00:00','PROCESSED');
            INSERT INTO atomic_claim(
              id,content_id,speaker_person_id,normalized_claim,claim_type,temporal_scope,
              check_worthy,extraction_version,metadata
            ) VALUES (
              'claim:dp303-canary','content:dp303-canary','person:dp303-canary',:'claim',
              'NUMERIC_STATISTIC','{"statement_date":"2026-09-21"}'::jsonb,true,
              'candidate-extraction-v1',jsonb_build_object(
                'speech_mode','DIRECT_UTTERANCE',
                'context_integrity',jsonb_build_object('state','CLEAR_AUTOMATIC','quote_sha256',:'quote_hash'),
                'wording',:'wording'::jsonb
              )
            );
            INSERT INTO claim_text_provenance(
              id,claim_id,content_id,person_id,selector_type,quote_sha256,source_sha256,
              attribution_method,status,source_ref
            ) VALUES (
              'text-provenance:dp303-canary','claim:dp303-canary','content:dp303-canary',
              'person:dp303-canary','TEXT_QUOTE_HASH',:'quote_hash',repeat('c',64),
              'SOURCE_QUOTE','APPROVED','{"url":"https://example.test/dp303"}'::jsonb
            );
            INSERT INTO evidence(
              id,canonical_url,publisher,source_type,publication_date,observed_at,
              content_sha256,reference_period,rights_status,independence_group,metadata
            ) VALUES (
              'evidence:dp303-canary','https://example.test/dp303/evidence','Synthetic Authority',
              'PRIMARY_OFFICIAL','2026-09-01','2026-09-22T10:00:00+00:00',repeat('a',64),
              '2026','UNKNOWN','istat-sdmx:2026',
              '{"evidence_source_id":"istat-sdmx","authoritative":true}'::jsonb
            );
            INSERT INTO claim_evidence_candidate(
              claim_id,evidence_id,retrieval_method,retrieval_version,relation_candidate,status,statement_cutoff
            ) VALUES (
              'claim:dp303-canary','evidence:dp303-canary','SYNTHETIC_FIXTURE','fixture-v1',
              'SUPPORT','APPROVED','2026-09-21'
            );
            INSERT INTO evidence_observation(
              id,evidence_id,observation_type,metric,value_numeric,unit,reference_period,
              extraction_method,extraction_version,status
            ) VALUES (
              'observation:dp303-canary','evidence:dp303-canary','NUMERIC_VALUE','tax_rate',10,
              'percent','2026','SYNTHETIC_FIXTURE','fixture-v1','APPROVED'
            );
            INSERT INTO finding(id,claim_id,assessment,rationale,publication_status,policy_version,created_at)
            VALUES (
              'finding:dp303-previous','claim:dp303-canary','SUPPORTED','Previous synthetic finding',
              'PUBLISH','policy-v1','2026-09-22T09:00:00+00:00'
            );
            INSERT INTO review_event(id,entity_type,entity_id,action,created_at)
            VALUES
              ('review:provenance-dp303','CLAIM_TEXT_PROVENANCE','text-provenance:dp303-canary','APPROVED','2026-09-22T10:01:00+00:00'),
              ('review:evidence-candidate-dp303','CLAIM_EVIDENCE_CANDIDATE','claim:dp303-canary|evidence:dp303-canary|fixture-v1','APPROVED','2026-09-22T10:01:30+00:00'),
              ('review:observation-dp303','EVIDENCE_OBSERVATION','observation:dp303-canary','APPROVED','2026-09-22T10:01:45+00:00'),
              ('review:previous-dp303','FINDING','finding:dp303-previous','APPROVED','2026-09-22T10:02:00+00:00');
            """,
            claim=normalized_claim,
            quote_hash=quote_hash,
            wording=json.dumps(wording, ensure_ascii=False, separators=(",", ":")),
        )

    def test_dp302_enabled_private_intake_load_failure_and_replay(self) -> None:
        profile = RightOfReplyLaunchProfile(
            configured=True,
            enabled=True,
            rate_profile=RateLimitProfile(
                scope=RateScope.PER_FINDING,
                limit=100,
                window_seconds=3600,
                configured=True,
            ),
        )
        rate_state = RateLimitState(submissions_in_window=0)
        receipts = []
        for index in range(12):
            payload = {
                "finding_id": "finding:dp302-canary",
                "body": f"Synthetic private reply {index}.",
                "submitter_name": "Synthetic submitter",
                "submitter_role": "Fixture",
                "evidence_urls": [f"https://example.test/reference/{index}"],
                "policy_version": "reply-intake-policy-v1",
                "request_fingerprint": f"fixture-{index}",
            }
            receipt = submit_right_of_reply(
                self.store,
                payload,
                launch_profile=profile,
                rate_state=rate_state,
                clock=lambda: datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(receipt.state, ServiceState.RECEIVED_PRIVATE, receipt)
            self.assertTrue(receipt.created)
            self.assertTrue(receipt.is_bounded())
            receipts.append((payload, receipt))

        replay = submit_right_of_reply(
            self.store,
            receipts[0][0],
            launch_profile=profile,
            rate_state=rate_state,
        )
        self.assertEqual(replay.state, ServiceState.RECEIVED_PRIVATE)
        self.assertEqual(replay.replay, ReplayKind.DUPLICATE)
        self.assertFalse(replay.created)

        failure = submit_right_of_reply(
            self.store,
            {**receipts[0][0], "finding_id": "finding:missing"},
            launch_profile=profile,
            rate_state=rate_state,
        )
        self.assertEqual(failure.state, ServiceState.NOT_RECEIVED)
        self.assertEqual(failure.reason, ServiceReason.PERSISTENCE_ERROR.value)
        self.assertTrue(failure.is_bounded())

        summary = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'reply_count',count(*),
                  'private_count',count(*) FILTER (WHERE public_visibility='PRIVATE'),
                  'under_review_count',count(*) FILTER (WHERE status='UNDER_REVIEW'),
                  'public_count',count(*) FILTER (WHERE public_visibility='PUBLIC')
                )::text FROM right_of_reply WHERE finding_id='finding:dp302-canary';
                """
            )
        )
        self.assertEqual(summary, {
            "reply_count": 12,
            "private_count": 12,
            "under_review_count": 12,
            "public_count": 0,
        })
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM processing_job WHERE job_type='REGISTER_REANALYSIS' AND content_id='content:dp302-canary';"
            ),
            "12",
        )

    def test_dp305_rights_excerpt_expiry_hold_and_cleanup(self) -> None:
        self.assertFalse(EXCERPT_PROFILE_APPROVED)
        registry = PrivateRightsRegistryStore(self.database_url)
        subject = RightsSubject(
            source_family="SYNTHETIC_DP305_CANARY",
            locator_kind="URL",
            locator_value="https://example.test/dp305/source",
            content_id="content:dp305-canary",
            evidence_id="evidence:dp305-canary",
            transcript_segment_id="segment:dp305-canary",
        )
        cleared = registry.record_rights(
            subject=subject,
            policy_version="dp305-machine-canary-v1",
            rights_status=RightsStatus.CLEARED,
            rights_receipt_ref="rights-receipt:synthetic:dp305:cleared",
            permitted_uses=(EXCERPT_PUBLIC_USE_REQUIRED,),
            attribution_requirements=("SOURCE_URL",),
            reviewed_at="2026-10-01T10:00:00+00:00",
            expires_at="2026-10-07T10:00:00+00:00",
            reviewer_ref="reviewer:synthetic:dp305",
        )
        source_hash = hashlib.sha256(
            b"Synthetic cleared excerpt body for machine-only acceptance."
        ).hexdigest()
        request = ExcerptRequest(
            excerpt_text="Synthetic cleared excerpt body",
            rights_status=cleared.rights_status,
            permitted_public_uses=cleared.permitted_uses,
            rights_reviewed_on="2026-10-01",
            rights_expires_on="2026-10-07",
            today="2026-10-06",
            source_url=subject.locator_value,
            content_id=subject.content_id,
            segment_id=subject.transcript_segment_id,
            transcript_variant_id="variant:dp305-canary",
            timestamp_start_seconds=0.1,
            timestamp_end_seconds=1,
            source_content_sha256=source_hash,
            observed_source_sha256=source_hash,
            excerpt_review_approved=True,
            profile_approved=True,
            max_excerpt_chars=200,
            total_source_chars=2000,
        )
        allowed = decide_excerpt(request)
        self.assertTrue(allowed.allowed)
        rendered = render_attributed_excerpt(request, allowed)
        rendered_text = json.dumps(rendered, sort_keys=True)
        self.assertIn("Synthetic cleared excerpt body", rendered_text)
        self.assertNotIn("rights-receipt", rendered_text)
        self.assertNotIn("reviewer:synthetic", rendered_text)

        expired_request = ExcerptRequest(**{**request.__dict__, "today": "2026-10-08"})
        expired = decide_excerpt(expired_request)
        self.assertFalse(expired.allowed)
        self.assertIn(ExcerptDecisionCode.RIGHTS_EXPIRED, expired.codes)
        with self.assertRaises(ValueError):
            render_attributed_excerpt(expired_request, expired)

        expired_record = registry.record_rights(
            subject=subject,
            policy_version="dp305-machine-canary-v2",
            rights_status=RightsStatus.EXPIRED,
            rights_receipt_ref="rights-receipt:synthetic:dp305:expired",
            permitted_uses=(),
            attribution_requirements=("SOURCE_URL",),
            reviewed_at="2026-10-08T10:00:00+00:00",
            reviewer_ref="reviewer:synthetic:dp305",
            supersedes_record_id=cleared.id,
        )
        bridge = RightsComplaintBridge(self.database_url)
        triage = bridge.submit(
            finding_id="finding:dp305-canary",
            rights_record_id=expired_record.id,
            complaint_ref="complaint:synthetic:dp305",
            actor_ref="actor:synthetic:rights-intake",
        )
        hold_event = bridge.approve_hold(
            triage.request.request_id,
            reviewer_actor_ref="reviewer:synthetic:rights-hold",
        )
        self.assertEqual(hold_event.event.to_state.value, "PUBLIC_HOLD_APPROVED")
        hold = bridge.current_hold("finding:dp305-canary")
        self.assertEqual(hold.disposition.value, "HOLD")

        with tempfile.TemporaryDirectory(prefix="dp305-public-cleanup-") as raw_root:
            cleanup_root = Path(raw_root)
            public_file = cleanup_root / "public" / "finding.json"
            private_file = cleanup_root / "private" / "source.txt"
            public_file.parent.mkdir(parents=True)
            private_file.parent.mkdir(parents=True)
            public_file.write_text(rendered_text, encoding="utf-8")
            private_body = "PRIVATE_RAW_TRANSCRIPT_BODY"
            private_file.write_text(private_body, encoding="utf-8")
            receipt = cleanup_takedown_current_artifacts(
                cleanup_root,
                finding_id="finding:dp305-canary",
                hold=hold,
                artifacts=(
                    ProjectionArtifact(
                        "finding:current", "public/finding.json", "finding",
                        "finding:dp305-canary", "CURRENT", True,
                    ),
                    ProjectionArtifact(
                        "finding:private", "private/source.txt", "finding",
                        "finding:dp305-canary", "CURRENT", False,
                    ),
                ),
            )
            self.assertTrue(receipt.complete)
            self.assertFalse(public_file.exists())
            self.assertTrue(private_file.exists())
            self.assertEqual(private_file.read_text(encoding="utf-8"), private_body)
            receipt_text = repr(receipt)
            self.assertNotIn(private_body, receipt_text)
            self.assertNotIn("rights-receipt", receipt_text)

        current = registry.read_current(subject)
        self.assertIsNotNone(current)
        self.assertEqual(current.id, expired_record.id)
        self.assertEqual(current.record_visibility, "PRIVATE")
        replay = bridge.challenges.replay_request(triage.request.request_id)
        self.assertFalse(replay.blockers)
        self.assertEqual(len(replay.events), 3)

    def test_dp303_enabled_correction_runs_real_reanalysis_and_public_projection(self) -> None:
        class Harness(VerificationRelationReanalysisJobHandlers):
            pass

        harness = Harness()
        harness.store = self.store
        harness.source_intelligence_contract = load_source_intelligence_contract()
        content = self.store.content("content:dp303-canary")
        initial = ProcessingJob(
            job_id="job:dp303-initial-verification",
            content_id=content.content_id,
            job_type="VERIFY_CLAIM",
            attempt=1,
            payload={
                "claim_id": "claim:dp303-canary",
                "verification_kind": "numeric_exact",
                "verification_rule": {
                    "metric": "tax_rate",
                    "value": 10,
                    "reference_period": "2026",
                },
                "statement_date": "2026-09-21",
                "estimated_cost_usd": 0,
            },
        )
        harness.verify_claim(initial, content)
        current_id = self.store.run(
            "SELECT id FROM finding WHERE claim_id='claim:dp303-canary' AND id<>'finding:dp303-previous' ORDER BY created_at DESC,id DESC LIMIT 1;"
        )
        self.assertTrue(current_id.startswith("finding:"))
        rationale = self.store.run(
            "SELECT rationale FROM finding WHERE id=:'finding_id';", finding_id=current_id
        )
        self.store.run(
            """
            UPDATE finding SET publication_status='PUBLISH' WHERE id=:'finding_id';
            INSERT INTO review_event(id,entity_type,entity_id,action,created_at)
            VALUES ('review:current-dp303','FINDING',:'finding_id','APPROVED','2026-09-22T10:05:00+00:00');
            """,
            finding_id=current_id,
            rationale=rationale,
        )

        profile = ChallengeLaunchProfile(
            configured=True,
            enabled=True,
            enabled_kinds=frozenset({ChallengeKind.CORRECTION}),
            rate_profile=RateLimitProfile(
                scope=RateScope.GLOBAL, limit=10, window_seconds=3600, configured=True
            ),
        )
        receipt = submit_challenge(
            self.store,
            {
                "kind": "CORRECTION",
                "finding_id": current_id,
                "previous_finding_id": "finding:dp303-previous",
                "reason": "Synthetic reviewed correction canary.",
                "changed_fields": {"assessment": ["SUPPORTED", "SUPPORTED"]},
            },
            launch_profile=profile,
            rate_state=RateLimitState(),
            clock=lambda: datetime(2026, 10, 6, 21, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(receipt.state, ChallengeServiceState.REANALYSIS_PENDING_PRIVATE, receipt)
        self.assertIsNotNone(receipt.receipt_id)

        def persisted_job(job_type: str) -> ProcessingJob:
            row = json.loads(
                self.store.run(
                    """
                    SELECT json_build_object('id',id,'content_id',content_id,'payload',payload)::text
                    FROM processing_job
                    WHERE content_id='content:dp303-canary' AND job_type=:'job_type'
                    ORDER BY created_at DESC,id DESC LIMIT 1;
                    """,
                    job_type=job_type,
                )
            )
            return ProcessingJob(
                job_id=row["id"], content_id=row["content_id"], job_type=job_type,
                attempt=1, payload=row["payload"],
            )

        harness.register_reanalysis(persisted_job("REGISTER_REANALYSIS"), content)
        harness.reanalyze_claim(persisted_job("REANALYZE_CLAIM"), content)
        harness.verify_claim(persisted_job("VERIFY_CLAIM"), content)
        trigger = json.loads(
            self.store.run(
                """
                SELECT json_build_object('status',status,'source_id',source_id,'id',id)::text
                FROM reanalysis_trigger
                WHERE claim_id='claim:dp303-canary' AND trigger_type='CORRECTION'
                ORDER BY created_at DESC,id DESC LIMIT 1;
                """
            )
        )
        self.assertEqual(trigger["status"], "PROCESSED")
        self.assertEqual(
            self.store.run(
                "SELECT count(*)::text FROM finding WHERE claim_id='claim:dp303-canary' AND id<>ALL(ARRAY['finding:dp303-previous',:'current_id']);",
                current_id=current_id,
            ),
            "0",
        )

        publish_correction(
            self.store,
            correction_id=str(receipt.receipt_id),
            actor_ref="reviewer:synthetic:dp303",
            reason="Synthetic machine-only correction review",
        )
        correction_state = json.loads(
            self.store.run(
                """
                SELECT json_build_object(
                  'visibility',public_visibility,'current_status',(SELECT publication_status FROM finding WHERE id=:'current_id'),
                  'previous_status',(SELECT publication_status FROM finding WHERE id='finding:dp303-previous')
                )::text FROM correction WHERE id=:'correction_id';
                """,
                correction_id=receipt.receipt_id,
                current_id=current_id,
            )
        )
        self.assertEqual(correction_state["visibility"], "PUBLIC")
        self.assertEqual(correction_state["current_status"], "PUBLISH")
        self.assertEqual(correction_state["previous_status"], "CORRECTED")

        projection = build_public_projection(
            PublicProjectionStore(self.database_url),
            generated_at="2026-10-06T21:30:00+00:00",
        )
        projected = [row for row in projection["dossiers"] if row["finding_id"] == current_id]
        self.assertEqual(len(projected), 1, projection)
        self.assertTrue(projected[0]["corrections"])
        self.assertEqual(projected[0]["corrections"][0]["previous_finding_id"], "finding:dp303-previous")


if __name__ == "__main__":
    unittest.main()
