import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.daily_config import (  # noqa: E402
    DailyConfigError,
    load_config,
)
from dichiarazioni_pubbliche.daily_store import (  # noqa: E402
    CaptureRecord,
    DailyStore,
    FACTUAL_VERDICTS,
)


def statement_row(**overrides):
    row = {
        "id": "statement-1",
        "content_id": "content-1",
        "capture_id": "capture-1",
        "source_id": "source-1",
        "source_url": "https://example.org/article",
        "source_title": "Titolo",
        "source_publisher": "Editore",
        "statement_date": "2026-11-23",
        "quote": "Una frase esatta.",
        "quote_offset": 12,
        "speaker_name": "Persona pubblica",
        "claim_nature": "FACTUAL",
        "status": "CANDIDATE",
        "metadata": {"extractor": "fixture"},
    }
    row.update(overrides)
    return row


class DailyConfigTests(unittest.TestCase):
    def test_default_source_registry_is_valid_and_has_no_model_or_delivery_authority(self):
        config = load_config()

        self.assertEqual(len(config.sources), 29)
        self.assertEqual(len({source.id for source in config.sources}), 29)
        self.assertTrue(all(source.discovery_url.startswith("https://") for source in config.sources))
        self.assertTrue(all(source.max_items > 0 for source in config.sources))
        self.assertNotIn("models", config.raw)
        self.assertNotIn("evening", config.raw)
        self.assertEqual(config.limit("max_items_per_run", 0), 20)

    def test_youtube_adapter_payload_preserves_channel_identity_and_limit(self):
        source = next(source for source in load_config().sources if source.kind == "youtube_channel")
        payload = source.adapter_payload()

        self.assertEqual(payload["channel_id"], source.channel_id)
        self.assertEqual(payload["max_items_per_run"], source.max_items)
        self.assertEqual(payload["discovery_url"], source.discovery_url)

    def test_rejects_model_or_message_delivery_configuration(self):
        base = copy.deepcopy(load_config().raw)
        for forbidden in ("models", "evening"):
            with self.subTest(field=forbidden), tempfile.TemporaryDirectory() as tmp:
                payload = copy.deepcopy(base)
                payload[forbidden] = {}
                path = Path(tmp) / "sources.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(DailyConfigError, "CANNOT_AUTHORIZE"):
                    load_config(path)

    def test_rejects_duplicate_ids_and_non_https_discovery(self):
        base = copy.deepcopy(load_config().raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            duplicate = copy.deepcopy(base)
            duplicate["sources"].append(copy.deepcopy(duplicate["sources"][0]))
            path.write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaisesRegex(DailyConfigError, "ID_INVALID_OR_DUPLICATE"):
                load_config(path)

            insecure = copy.deepcopy(base)
            insecure["sources"][0]["discovery_url"] = "http://example.org/feed"
            path.write_text(json.dumps(insecure), encoding="utf-8")
            with self.assertRaisesRegex(DailyConfigError, "DISCOVERY_URL_INVALID"):
                load_config(path)

    def test_rejects_invalid_youtube_source_and_non_positive_limits(self):
        base = copy.deepcopy(load_config().raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            invalid_channel = copy.deepcopy(base)
            youtube = next(row for row in invalid_channel["sources"] if row["kind"] == "youtube_channel")
            youtube.pop("channel_id")
            path.write_text(json.dumps(invalid_channel), encoding="utf-8")
            with self.assertRaisesRegex(DailyConfigError, "YOUTUBE_CHANNEL_ID_REQUIRED"):
                load_config(path)

            invalid_limit = copy.deepcopy(base)
            invalid_limit["limits"]["max_items_per_run"] = 0
            path.write_text(json.dumps(invalid_limit), encoding="utf-8")
            with self.assertRaisesRegex(DailyConfigError, "INVALID_POSITIVE_INTEGER"):
                load_config(path)


class DailyStoreTests(unittest.TestCase):
    def test_capture_write_is_idempotent_and_records_exact_body_hash(self):
        capture = CaptureRecord(
            kind="article_text",
            url="https://example.org/article",
            body="Testo catturato\ncon accenti è.",
            metadata={"parser": "fixture"},
        )
        with patch.object(DailyStore, "run", return_value="capture-1") as run:
            saved = DailyStore().save_capture(
                capture_id="capture-1",
                content_id="content-1",
                source_id="source-1",
                capture=capture,
            )

        self.assertTrue(saved)
        sql = run.call_args.args[0]
        params = run.call_args.kwargs
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertEqual(params["body"], capture.body)
        self.assertEqual(params["sha"], hashlib.sha256(capture.body.encode()).hexdigest())

    def test_capture_metadata_read_never_returns_private_body(self):
        expected = {
            "id": "capture-1",
            "content_id": "content-1",
            "text_sha256": "a" * 64,
            "char_count": 4,
        }
        with patch.object(DailyStore, "run", return_value=json.dumps(expected)) as run:
            result = DailyStore().read_capture_metadata("capture-1")

        self.assertEqual(result, expected)
        sql = run.call_args.args[0].lower()
        self.assertIn("text_sha256", sql)
        self.assertNotIn("select body", sql)
        self.assertNotIn("capture_row.body", sql)

    def test_capture_body_requires_explicit_private_read_method(self):
        with patch.object(DailyStore, "run", return_value="testo privato") as run:
            body = DailyStore().read_capture_body("capture-1")

        self.assertEqual(body, "testo privato")
        self.assertIn("SELECT body FROM daily_capture", run.call_args.args[0])

    def test_statement_candidates_are_append_only_and_cannot_be_marked_published(self):
        with patch.object(DailyStore, "run", return_value="statement-1") as run:
            saved = DailyStore().save_statement(statement_row())

        self.assertTrue(saved)
        sql = run.call_args.args[0]
        self.assertIn("ON CONFLICT (id) DO NOTHING", sql)
        self.assertNotIn("DO UPDATE", sql)
        self.assertEqual(run.call_args.kwargs["status"], "CANDIDATE")
        self.assertIn("FROM daily_capture capture", sql)
        self.assertIn("substr(", sql)
        self.assertIn("capture.content_id = :'content_id'", sql)
        self.assertIn("capture.source_id = :'source_id'", sql)

        with self.assertRaisesRegex(ValueError, "STATUS_INVALID"):
            DailyStore().save_statement(statement_row(status="PUBLISHED"))

    def test_statement_quote_offset_rejects_boolean_and_negative_values(self):
        for offset in (True, -1):
            with self.subTest(offset=offset), self.assertRaisesRegex(
                ValueError, "QUOTE_OFFSET_INVALID"
            ):
                DailyStore().save_statement(statement_row(quote_offset=offset))

    def test_statement_opinion_is_persisted_as_nature_without_a_factual_verdict(self):
        with patch.object(DailyStore, "run", return_value="statement-1") as run:
            saved = DailyStore().save_statement(
                statement_row(claim_nature="OPINION", status="CANDIDATE")
            )
        self.assertTrue(saved)
        self.assertEqual(run.call_args.kwargs["claim_nature"], "OPINION")

        with self.assertRaisesRegex(ValueError, "FACTUAL_VERDICT_INVALID"):
            DailyStore().save_verdict("statement-1", {"verdict": "OPINION"})

    def test_statement_can_move_from_candidate_to_a_held_state_without_rewriting_quote(self):
        with patch.object(DailyStore, "run", return_value="statement-1") as run:
            changed = DailyStore().set_statement_status(
                "statement-1", status="HELD_NO_SPEAKER", reason="Attribuzione assente"
            )

        self.assertTrue(changed)
        sql = run.call_args.args[0]
        self.assertIn("SET status = :'status', status_reason = :'reason'", sql)
        self.assertNotIn("quote =", sql)
        self.assertIn("status = 'CANDIDATE' OR status = :'status'", sql)
        with self.assertRaisesRegex(ValueError, "STATUS_TRANSITION_INVALID"):
            DailyStore().set_statement_status(
                "statement-1", status="CANDIDATE", reason="reopen"
            )

    def test_factual_verdict_values_match_owner_decision(self):
        self.assertEqual(
            FACTUAL_VERDICTS,
            {
                "TRUE",
                "MOSTLY_TRUE",
                "MISLEADING",
                "FALSE",
                "NOT_VERIFIABLE",
                "CONTRADICTORY_WITH_ITSELF",
            },
        )
        verdict = {
            "verdict": "CONTRADICTORY_WITH_ITSELF",
            "explanation": "Le due parti della frase si contraddicono.",
            "evidence": [{"url": "https://example.org/evidence"}],
            "first_pass": {"verdict": "CONTRADICTORY_WITH_ITSELF"},
            "check_pass": {"verdict": "CONTRADICTORY_WITH_ITSELF"},
            "agreement": "AGREED",
            "models": "reviewed-model-identities",
            "model_calls": 2,
            "duration_seconds": 1.25,
        }
        with patch.object(DailyStore, "run", return_value="t") as run:
            saved = DailyStore().save_verdict("statement-1", verdict)

        self.assertTrue(saved)
        sql = run.call_args.args[0]
        self.assertIn("statement.claim_nature = 'FACTUAL'", sql)
        self.assertIn("statement.status = 'CANDIDATE'", sql)
        self.assertIn("ON CONFLICT (statement_id) DO UPDATE", sql)
        self.assertEqual(run.call_args.kwargs["verdict"], "CONTRADICTORY_WITH_ITSELF")

    def test_verdict_write_reports_missing_or_opinion_statement(self):
        verdict = {
            "verdict": "TRUE",
            "evidence": [],
            "first_pass": {"verdict": "TRUE"},
            "check_pass": {"verdict": "TRUE"},
            "models": "model-a/model-b",
            "model_calls": 2,
        }
        with patch.object(DailyStore, "run", return_value="f"):
            self.assertFalse(DailyStore().save_verdict("opinion-1", verdict))

    def test_verdict_requires_both_passes_and_two_model_calls(self):
        with self.assertRaisesRegex(ValueError, "PASSES_INVALID"):
            DailyStore().save_verdict(
                "statement-1",
                {
                    "verdict": "TRUE",
                    "first_pass": {},
                    "check_pass": {"verdict": "TRUE"},
                    "models": "model-a/model-b",
                    "model_calls": 2,
                },
            )
        with self.assertRaisesRegex(ValueError, "METRICS_INVALID"):
            DailyStore().save_verdict(
                "statement-1",
                {
                    "verdict": "TRUE",
                    "first_pass": {"verdict": "TRUE"},
                    "check_pass": {"verdict": "TRUE"},
                    "models": "model-a/model-b",
                    "model_calls": 1,
                },
            )

    def test_statement_reads_are_explicit_and_exclude_capture_body(self):
        expected = [{"id": "statement-1", "quote": "Una frase", "status": "CANDIDATE"}]
        with patch.object(DailyStore, "run", return_value=json.dumps(expected)) as run:
            result = DailyStore().read_statements(since="2026-11-23", status="CANDIDATE")

        self.assertEqual(result, expected)
        sql = run.call_args.args[0].lower()
        self.assertIn("statement.quote", sql)
        self.assertIn("verdict.explanation", sql)
        self.assertNotIn("daily_capture.body", sql)
        self.assertNotIn("select body", sql)

    def test_statement_read_rejects_invalid_status_and_unbounded_limit(self):
        with self.assertRaisesRegex(ValueError, "STATUS_INVALID"):
            DailyStore().read_statements(since="2026-11-23", status="PUBLISHED")
        with self.assertRaisesRegex(ValueError, "READ_LIMIT_INVALID"):
            DailyStore().read_statements(since="2026-11-23", limit=1001)

    def test_run_contract_has_no_published_counter(self):
        with patch.object(DailyStore, "run", return_value="") as run:
            DailyStore().record_run(
                "2026-11-23",
                {
                    "items": 3,
                    "captures": 2,
                    "statements": 1,
                    "verdicts": 1,
                    "held_statements": 0,
                },
                finished=True,
            )
        sql = run.call_args.args[0]
        self.assertIn("held_statements", sql)
        self.assertNotIn("published", sql.lower())
        self.assertEqual(run.call_args.kwargs["status"], "COMPLETED")

    def test_run_finish_state_must_match_status(self):
        with self.assertRaisesRegex(ValueError, "FINISH_STATE_MISMATCH"):
            DailyStore().record_run(
                "2026-11-23", {}, finished=False, status="COMPLETED"
            )

    def test_receipt_does_not_assume_an_external_subscription(self):
        with patch.object(DailyStore, "run", return_value="") as run:
            receipt_id = DailyStore().write_receipt(
                content_id="content-1",
                provider_id="provider-1",
                model_id="model-1",
                operation="STATEMENT_EXTRACTION",
                request_key="request-1",
                latency_seconds=1.2,
                usage={"total_tokens": 42},
            )

        self.assertTrue(receipt_id.startswith("receipt:"))
        self.assertEqual(run.call_args.kwargs["billing_basis"], "UNKNOWN")

    def test_migration_is_additive_and_contains_owner_verdict_contract(self):
        migration = (
            ROOT / "db" / "migrations" / "20261112-add-dp638-daily-machine.sql"
        ).read_text(encoding="utf-8")
        self.assertEqual(migration.count("CREATE TABLE IF NOT EXISTS daily_"), 4)
        self.assertNotIn("UPDATE processing_job", migration)
        self.assertNotIn("DROP TABLE", migration)
        self.assertIn("CONTRADICTORY_WITH_ITSELF", migration)
        self.assertIn("daily_verdict_factual_only", migration)
        self.assertIn("daily_statement_status_check", migration)


if __name__ == "__main__":
    unittest.main()
