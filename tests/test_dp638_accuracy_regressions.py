"""Regressions found while auditing the first DP-638 production deployment."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from dichiarazioni_pubbliche import daily_capture as capture
from dichiarazioni_pubbliche import daily_config as config
from dichiarazioni_pubbliche import daily_model as model
from dichiarazioni_pubbliche import daily_statements as statements
from dichiarazioni_pubbliche import daily_verdict as verdict
from tests.test_dp638_daily_machine import FakeClient, item


class CaptureRegressionTest(unittest.TestCase):
    def test_model_suggested_private_url_is_refused_before_network(self):
        with self.assertRaises(model.DailyMachineError):
            model.fetch_text("http://127.0.0.1:20128/v1/models", opener=lambda request, timeout: (200, b"private"))

    def test_discovery_keeps_metadata_even_when_processing_budget_is_one(self):
        cfg = config.DailyConfig(
            sources=(item("official-camera-temi").source, item("official-consilium-press").source),
            models={}, limits={"max_items_per_run": 1}, relevance_rule={},
        )
        feed = '<rss><channel><item><title>Oggi</title><link>https://example.test/1</link><guid>1</guid><pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate></item></channel></rss>'
        rows, failures = capture.discover(cfg, fetcher=lambda url: feed)
        self.assertEqual(failures, [])
        self.assertEqual({row.source.id for row in rows}, {"official-camera-temi", "official-consilium-press"})

    def test_youtube_caption_capture_returns_and_cleans_its_scratch(self):
        scratch = []

        def runner(command, **kwargs):
            template = Path(command[command.index("-o") + 1])
            scratch.append(template.parent)
            (template.parent / "video.it.vtt").write_text(
                'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nLe parole dette davvero qui\n'
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        result = capture.capture_youtube(item(), runner=runner)
        self.assertEqual(result.body, "Le parole dette davvero qui")
        self.assertFalse(scratch[0].exists())


class AttributionRegressionTest(unittest.TestCase):
    quote = "Il governo ha stanziato due miliardi per i chip"

    def resolve(self, body, speaker="Adolfo Urso", kind="article"):
        statement = statements.ExtractedStatement(self.quote, speaker, "Ministro", "", "chip", "FACTUAL")
        return statements.resolve_speaker(statement, capture.Capture(kind, "https://example.test/1", body), item())

    def test_person_merely_mentioned_is_not_the_speaker(self):
        body = f'Adolfo Urso partecipa al convegno. Mario Rossi ha dichiarato: «{self.quote}».'
        self.assertEqual(self.resolve(body), "")

    def test_name_tokens_from_different_people_do_not_resolve(self):
        body = f'Adolfo Rossi incontra Mario Urso. Mario Rossi ha dichiarato: «{self.quote}».'
        self.assertEqual(self.resolve(body), "")

    def test_reported_indirect_speech_is_not_a_verbatim_statement(self):
        body = f'Adolfo Urso ha detto che {self.quote}.'
        self.assertEqual(self.resolve(body), "")

    def test_explicit_direct_quote_resolves(self):
        body = f'Adolfo Urso ha dichiarato: «{self.quote}».'
        self.assertEqual(self.resolve(body), "person:adolfo-urso")

    def test_labelled_transcript_resolves_but_unlabelled_does_not(self):
        self.assertEqual(self.resolve(f'Adolfo Urso: {self.quote}\n', kind="captions"), "person:adolfo-urso")
        self.assertEqual(self.resolve(f'Adolfo Urso presenta Mario Rossi\n{self.quote}', kind="captions"), "")


class VerdictRegressionTest(unittest.TestCase):
    def test_page_with_only_a_generic_word_is_not_independent_evidence(self):
        result = verdict.verify_evidence(
            {"url": "https://other.test/misc"},
            quote="Il governo ha abolito la tassa sulle auto elettriche",
            source_url="https://example.test/1",
            fetcher=lambda url, **kw: (200, "<article>" + "Il governo si riunisce per parlare di sport. " * 12 + "</article>"),
        )
        self.assertFalse(result.usable)

    def test_claim_with_no_searchable_words_has_no_supporting_evidence(self):
        result = verdict.verify_evidence(
            {"url": "https://other.test/misc"}, quote="Io, tu, si, no",
            source_url="https://example.test/1",
            fetcher=lambda url, **kw: (200, "<article>" + "Meteo sereno per tutta la settimana. " * 12 + "</article>"),
        )
        self.assertFalse(result.usable)

    def test_irrelevant_download_is_not_evidence(self):
        result = verdict.verify_evidence(
            {"url": "https://other.test/weather"}, quote="I disoccupati sono scesi al 6 per cento",
            source_url="https://example.test/1",
            fetcher=lambda url, **kw: (200, "<article>" + "Le previsioni meteo annunciano sole sulla costa. " * 10 + "</article>"),
        )
        self.assertFalse(result.usable)

    def test_independent_check_runs_also_for_unverifiable_and_opinion(self):
        for proposed in ("NOT_VERIFIABLE", "OPINION"):
            with self.subTest(proposed=proposed):
                client = FakeClient([json.dumps({"verdict": proposed, "explanation": "Primo passaggio", "evidence": []}), json.dumps({"verdict": proposed, "explanation": "Controllo"})])
                result = verdict.decide_verdict(
                    client, verdict_model="first/model-a", check_model="second/model-b",
                    statement=statements.ExtractedStatement("Questa legge non mi piace", "Adolfo Urso", "", "", "legge", "OPINION"),
                    statement_date="2026-11-12", source_url="https://example.test/1",
                    speaker="Adolfo Urso", speaker_role="", context="Questa legge non mi piace",
                )
                self.assertEqual(result["model_calls"], 2)
                self.assertEqual(result["agreement"], "AGREE")


if __name__ == "__main__":
    unittest.main()
