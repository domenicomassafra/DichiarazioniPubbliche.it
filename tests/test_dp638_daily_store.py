import copy
import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.daily_config import (  # noqa: E402
    DailyConfigError,
    load_config,
)
from dichiarazioni_pubbliche.daily_store import (  # noqa: E402
    DailyCaptureRecord,
    DailyStore,
    FACTUAL_VERDICTS,
)

TEXT = "Una frase esatta."


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
        "quote": TEXT,
        "quote_offset": 0,
        "speaker_name": "Persona pubblica",
        "claim_nature": "FACTUAL",
        "status": "CANDIDATE",
        "metadata": {"extractor": "fixture"},
    }
    row.update(overrides)
    return row


def daily_capture_record(**overrides):
    record = {
        "id": "capture-1",
        "content_capture_id": "content-capture-1",
        "content_id": "content-1",
        "source_id": "source-1",
        "kind": "article_text",
        "url": "https://example.org/article",
        "char_count": len(TEXT),
        "content_sha256": "a" * 64,
        "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "media_type": "text/html",
        "metadata": {"parser": "fixture"},
    }
    record.update(overrides)
    return DailyCaptureRecord(**record)


class FakeSourceUseGuard:
    def __init__(self, *, permitted=True):
        self.permitted = permitted
        self.bindings = []
        self.uses = []

    def bind_capture(self, **kwargs):
        self.bindings.append(("capture", kwargs))

    def bind_fetched(self, **kwargs):
        self.bindings.append(("fetched", kwargs))

    def require(self, use, *, content_sha256=None, media_type=None):
        self.uses.append((use, content_sha256, media_type))
        return SimpleNamespace(
            use=use,
            status="PERMITTED" if self.permitted else "DENIED",
            reason_code="SOURCE_USE_PERMITTED" if self.permitted else "SOURCE_USE_NOT_PERMITTED",
            action_code="NONE" if self.permitted else "REVIEW_SPECIFIC_USE",
            record_id="rights-record-1" if self.permitted else None,
            decision_fingerprint="b" * 64 if self.permitted else None,
            permitted=self.permitted,
        )


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
    def test_capture_write_is_idempotent_and_links_authorized_existing_capture(self):
        capture = daily_capture_record()
        guard = FakeSourceUseGuard()
        with patch.object(DailyStore, "run", return_value="capture-1") as run:
            saved = DailyStore().save_capture(
                capture, captured_text=TEXT, source_use_guard=guard
            )

        self.assertTrue(saved)
        sql = run.call_args.args[0].lower()
        params = run.call_args.kwargs
        self.assertIn("on conflict (id) do nothing", sql)
        self.assertIn("from content_capture existing_capture", sql)
        self.assertIn("existing_capture.rights_status = 'cleared'", sql)
        self.assertIn("existing_capture.hold_status = 'none'", sql)
        self.assertIn("existing_capture.retention_class in", sql)
        self.assertIn("lower(source.source_type) not in ('public_rss', 'rss')", sql)
        self.assertNotIn("insert into source", sql)
        self.assertNotIn("insert into content_item", sql)
        self.assertEqual(params["content_capture_id"], capture.content_capture_id)
        self.assertEqual(
            json.loads(params["metadata"])["source_use_decision"]["record_id"],
            "rights-record-1",
        )
        self.assertEqual(guard.uses[0][0], "EXTRACT_CANDIDATES")

    def test_capture_write_requires_a_permitted_source_use_decision(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_USE_NOT_PROVEN"):
            DailyStore().save_capture(
                daily_capture_record(),
                captured_text=TEXT,
                source_use_guard=FakeSourceUseGuard(permitted=False),
            )

    def test_capture_write_checks_normalized_text_length_and_hash(self):
        with patch.object(DailyStore, "run") as run:
            with self.assertRaisesRegex(ValueError, "CHAR_COUNT_MISMATCH"):
                DailyStore().save_capture(
                    daily_capture_record(),
                    captured_text=TEXT + " extra",
                    source_use_guard=FakeSourceUseGuard(),
                )
            with self.assertRaisesRegex(ValueError, "TEXT_HASH_MISMATCH"):
                DailyStore().save_capture(
                    daily_capture_record(text_sha256="c" * 64),
                    captured_text=TEXT,
                    source_use_guard=FakeSourceUseGuard(),
                )
            run.assert_not_called()

    def test_capture_metadata_read_never_returns_private_body(self):
        expected = {
            "id": "capture-1",
            "content_id": "content-1",
            "content_capture_id": "content-capture-1",
            "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
            "char_count": 4,
            "rights_status": "CLEARED",
            "retention_class": "DURABLE_PRIVATE",
            "media_type": "text/html",
        }
        with patch.object(DailyStore, "run", return_value=json.dumps(expected)) as run:
            result = DailyStore().read_capture_metadata("capture-1")

        self.assertEqual(result, expected)
        sql = run.call_args.args[0].lower()
        self.assertIn("text_sha256", sql)
        self.assertIn("content_capture existing_capture", sql)
        self.assertIn("existing_capture.rights_status", sql)
        self.assertNotIn("body_ref", sql)
        self.assertNotIn("select body", sql)
        self.assertNotIn("daily_capture.body", sql)

    def test_daily_store_does_not_duplicate_existing_store_ownership(self):
        for method in ("upsert_source", "save_items", "set_relevance", "write_receipt", "read_capture_body"):
            with self.subTest(method=method):
                self.assertFalse(hasattr(DailyStore, method))

    def test_statement_candidates_are_append_only_and_cannot_be_marked_published(self):
        capture = daily_capture_record()
        guard = FakeSourceUseGuard()
        with patch.object(DailyStore, "run", return_value="statement-1") as run:
            saved = DailyStore().save_statement(
                statement_row(),
                capture=capture,
                captured_text=TEXT,
                source_use_guard=guard,
            )

        self.assertTrue(saved)
        sql = run.call_args.args[0].lower()
        self.assertIn("on conflict (id) do nothing", sql)
        self.assertNotIn("do update", sql)
        self.assertEqual(run.call_args.kwargs["status"], "CANDIDATE")
        self.assertIn("from daily_capture", sql)
        self.assertIn("daily_capture.content_capture_id = :'content_capture_id'", sql)
        self.assertIn("existing_capture.rights_status = 'cleared'", sql)
        self.assertIn("daily_capture.text_sha256 = :'text_sha256'", sql)

    def test_statement_requires_explicit_claim_nature(self):
        row = statement_row()
        row.pop("claim_nature")
        with self.assertRaisesRegex(ValueError, "DAILY_STATEMENT_NATURE_REQUIRED"):
            DailyStore().save_statement(
                row,
                capture=daily_capture_record(),
                captured_text=TEXT,
                source_use_guard=FakeSourceUseGuard(),
            )

        with self.assertRaisesRegex(ValueError, "STATUS_INVALID"):
            DailyStore().save_statement(
                statement_row(status="PUBLISHED"),
                capture=daily_capture_record(),
                captured_text=TEXT,
                source_use_guard=FakeSourceUseGuard(),
            )

    def test_statement_quote_offset_rejects_boolean_and_negative_values(self):
        for offset in (True, -1):
            with self.subTest(offset=offset), self.assertRaisesRegex(
                ValueError, "QUOTE_OFFSET_INVALID"
            ):
                DailyStore().save_statement(
                    statement_row(quote_offset=offset),
                    capture=daily_capture_record(),
                    captured_text=TEXT,
                    source_use_guard=FakeSourceUseGuard(),
                )

    def test_statement_requires_exact_quote_and_text_hash(self):
        capture = daily_capture_record()
        with patch.object(DailyStore, "run") as run:
            with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_CAPTURE"):
                DailyStore().save_statement(
                    statement_row(quote="Citazione inventata"),
                    capture=capture,
                    captured_text=TEXT,
                    source_use_guard=FakeSourceUseGuard(),
                )
            run.assert_not_called()

            with self.assertRaisesRegex(ValueError, "TEXT_HASH_MISMATCH"):
                DailyStore().save_statement(
                    statement_row(),
                    capture=replace(capture, text_sha256="c" * 64),
                    captured_text=TEXT,
                    source_use_guard=FakeSourceUseGuard(),
                )
            run.assert_not_called()

    def test_statement_rechecks_source_use_before_persisting_quote(self):
        with patch.object(DailyStore, "run") as run:
            with self.assertRaisesRegex(ValueError, "SOURCE_USE_NOT_PROVEN"):
                DailyStore().save_statement(
                    statement_row(),
                    capture=daily_capture_record(),
                    captured_text=TEXT,
                    source_use_guard=FakeSourceUseGuard(permitted=False),
                )
            run.assert_not_called()

    def test_statement_opinion_is_persisted_as_nature_without_a_factual_verdict(self):
        capture = daily_capture_record()
        with patch.object(DailyStore, "run", return_value="statement-1") as run:
            saved = DailyStore().save_statement(
                statement_row(claim_nature="OPINION", status="CANDIDATE"),
                capture=capture,
                captured_text=TEXT,
                source_use_guard=FakeSourceUseGuard(),
            )
        self.assertTrue(saved)
        self.assertEqual(run.call_args.kwargs["claim_nature"], "OPINION")

        with self.assertRaisesRegex(ValueError, "DAILY_VERDICT_INVALID"):
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
        self.assertIn("ON CONFLICT (statement_id) DO NOTHING", sql)
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
        with patch.object(DailyStore, "run", return_value=""):
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

if __name__ == "__main__":
    unittest.main()
