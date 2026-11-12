from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche import daily_capture as dc  # noqa: E402
from dichiarazioni_pubbliche import daily_config as dcfg  # noqa: E402
from dichiarazioni_pubbliche import daily_machine as dmm  # noqa: E402
from dichiarazioni_pubbliche import daily_model as dmodel  # noqa: E402
from dichiarazioni_pubbliche import daily_publication as dp  # noqa: E402
from dichiarazioni_pubbliche import daily_statements as dst  # noqa: E402
from dichiarazioni_pubbliche import daily_text as dtext  # noqa: E402
from dichiarazioni_pubbliche import daily_verdict as dvd  # noqa: E402
from dichiarazioni_pubbliche.public_schema import validate_public_bundle  # noqa: E402
from dichiarazioni_pubbliche.source_adapters import DiscoveredContent  # noqa: E402

CONFIG_PATH = ROOT / "config" / "daily-sources.v1.json"


class FakeClient:
    """Deterministic stand-in for the OmniRoute client."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, model, messages, *, operation, max_tokens=1600, temperature=0.0):
        self.calls.append(dmodel.ModelReply(model, "", {}, 0.1, operation))
        text = self.replies.pop(0) if self.replies else "{}"
        return dmodel.ModelReply(model, text, {"total_tokens": 10}, 0.1, operation)


def item(source_id="ansa-politica", title="Titolo", published="2026-11-12T08:00:00+00:00"):
    source = dcfg.SourceSpec(
        id=source_id,
        name=source_id,
        publisher="ANSA",
        kind="public_rss",
        discovery_url="https://example.test/feed.xml",
    )
    content = DiscoveredContent(
        source_id=source_id,
        platform="public_rss",
        external_id="https://example.test/1",
        title=title,
        canonical_url="https://example.test/1",
        published_at=published,
    )
    return dc.DiscoveredItem(source=source, content=content)


FEED_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<rss version=\"2.0\"><channel><title>ANSA</title>"
    "<item><title>Titolo</title><link>https://example.test/1</link>"
    "<guid>https://example.test/1</guid>"
    "<pubDate>Thu, 12 Nov 2026 08:00:00 GMT</pubDate>"
    "<description>Descrizione</description></item></channel></rss>"
)

EVIDENCE_HTML = (
    "<article><p>Il governo ha stanziato due miliardi per i chip con un annuncio del "
    "ministro Adolfo Urso, secondo quanto riporta la nota ufficiale diffusa oggi dal "
    "ministero delle Imprese e del Made in Italy. La misura sul settore dei "
    "semiconduttori verra' dettagliata nelle prossime settimane.</p></article>"
)

BODY = (
    "Il ministro Adolfo Urso ha detto che il governo investira' due miliardi nel settore dei chip "
    "e che l'annuncio arrivera' entro la fine del mese.\n\n"
    "Secondo il ministro la misura serve a ridurre la dipendenza dall'estero."
)


class ConfigTest(unittest.TestCase):
    def test_config_loads_real_sources(self):
        config = dcfg.load_config(CONFIG_PATH)
        self.assertGreaterEqual(len(config.sources), 20)
        kinds = {source.kind for source in config.sources}
        self.assertIn("public_rss", kinds)
        self.assertIn("youtube_channel", kinds)
        for source in config.sources:
            self.assertTrue(source.discovery_url.startswith("https://"), source.id)
            self.assertTrue(source.publisher.strip(), source.id)
        self.assertTrue(config.model("statements"))
        self.assertNotEqual(config.model("verdict"), config.model("check"))


class VerbatimTest(unittest.TestCase):
    def test_matches_without_punctuation_and_accents(self):
        found = dtext.find_verbatim(BODY, "il governo investira due miliardi nel settore dei chip")
        self.assertIsNotNone(found)
        start, end = found
        self.assertEqual(BODY[start:end].lower().count("due miliardi"), 1)

    def test_rejects_paraphrase(self):
        self.assertIsNone(dtext.find_verbatim(BODY, "il governo spende due miliardi nei semiconduttori"))

    def test_rejects_short_fragment(self):
        self.assertIsNone(dtext.find_verbatim(BODY, "due miliardi"))

    def test_html_prefers_article_body(self):
        markup = (
            "<nav><div>Vai alla navigazione principale Vai al contenuto Vai al footer xxxxxxxxxxxxxxx</div></nav>"
            "<article><p>" + ("Testo utile dell'articolo con molte parole. " * 12) + "</p></article>"
        )
        text = dtext.html_to_text(markup)
        self.assertNotIn("Vai alla navigazione", text)
        self.assertIn("Testo utile dell'articolo", text)

    def test_vtt_is_deduplicated(self):
        payload = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCiao a tutti\n\n"
            "00:00:02.000 --> 00:00:03.000\nCiao a tutti\n\n"
            "00:00:03.000 --> 00:00:04.000\niniziamo\n"
        )
        segments = dc.parse_vtt(payload)
        self.assertEqual([segment.text for segment in segments], ["Ciao a tutti", "iniziamo"])
        self.assertEqual(segments[1].start_ms, 3000)


class SpeakerTest(unittest.TestCase):
    def test_resolves_named_speaker(self):
        statement = dst.ExtractedStatement(
            quote="il governo investira'", speaker="Adolfo Urso", speaker_role="Ministro",
            moment="", topic="chip", nature="FACTUAL",
        )
        capture = dc.Capture(kind="article", url="https://example.test/1", body=BODY)
        self.assertEqual(dst.resolve_speaker(statement, capture, item()), "person:adolfo-urso")

    def test_unknown_speaker_is_not_published(self):
        statement = dst.ExtractedStatement(
            quote="il governo investira'", speaker="", speaker_role="",
            moment="", topic="chip", nature="FACTUAL",
        )
        capture = dc.Capture(kind="article", url="https://example.test/1", body=BODY)
        self.assertEqual(dst.resolve_speaker(statement, capture, item()), "")


class VerdictTest(unittest.TestCase):
    def _statement(self):
        return dst.ExtractedStatement(
            quote="il governo investira' due miliardi nel settore dei chip",
            speaker="Adolfo Urso",
            speaker_role="Ministro",
            moment="par. 1",
            topic="chip",
            nature="FACTUAL",
        )

    def test_opinion_gets_no_verdict(self):
        client = FakeClient(
            [json.dumps({"verdict": "OPINION", "explanation": "E' un giudizio.", "evidence": []})]
        )
        result = dvd.decide_verdict(
            client,
            verdict_model="m-verdict",
            check_model="m-check",
            statement=self._statement(),
            statement_date="2026-11-12",
            source_url="https://example.test/1",
            speaker="Adolfo Urso",
            speaker_role="Ministro",
            context=BODY,
        )
        self.assertEqual(result["verdict"], "OPINION")
        self.assertEqual(result["evidence"], [])
        self.assertEqual(len(client.calls), 1)

    def test_unverifiable_when_evidence_cannot_be_fetched(self):
        client = FakeClient(
            [
                json.dumps(
                    {
                        "verdict": "TRUE",
                        "explanation": "Confermato.",
                        "evidence": [{"url": "https://broken.test/x", "title": "t", "publisher": "p"}],
                    }
                )
            ]
        )
        result = dvd.decide_verdict(
            client,
            verdict_model="m-verdict",
            check_model="m-check",
            statement=self._statement(),
            statement_date="2026-11-12",
            source_url="https://example.test/1",
            speaker="Adolfo Urso",
            speaker_role="Ministro",
            context=BODY,
            fetcher=lambda url, **kwargs: (404, ""),
        )
        self.assertEqual(result["verdict"], "NOT_VERIFIABLE")
        self.assertEqual(result["evidence"], [])

    def test_disagreement_becomes_not_verifiable(self):
        evidence_body = (
            "<article><p>Il governo ha stanziato due miliardi per i chip con un annuncio "
            "del ministro Adolfo Urso, secondo quanto riporta la nota ufficiale diffusa "
            "oggi dal ministero delle Imprese e del Made in Italy. La misura sul settore "
            "dei semiconduttori verra' dettagliata nelle prossime settimane.</p></article>"
        )
        client = FakeClient(
            [
                json.dumps(
                    {
                        "verdict": "TRUE",
                        "explanation": "Confermato dalla fonte ufficiale.",
                        "evidence": [{"url": "https://example.test/2", "title": "t", "publisher": "p"}],
                    }
                ),
                json.dumps({"verdict": "FALSE", "explanation": "La fonte dice il contrario."}),
            ]
        )
        result = dvd.decide_verdict(
            client,
            verdict_model="m-verdict",
            check_model="m-check",
            statement=self._statement(),
            statement_date="2026-11-12",
            source_url="https://example.test/1",
            speaker="Adolfo Urso",
            speaker_role="Ministro",
            context=BODY,
            fetcher=lambda url, **kwargs: (200, evidence_body),
        )
        self.assertEqual(result["agreement"], "DISAGREE")
        self.assertEqual(result["verdict"], "NOT_VERIFIABLE")
        self.assertEqual(len(result["evidence"]), 1)


class PublicationTest(unittest.TestCase):
    def _row(self, **overrides):
        row = {
            "id": "statement:abc",
            "content_id": "content:1",
            "quote": "il governo investira' due miliardi nel settore dei chip",
            "quote_offset": BODY.find("il governo investira'"),
            "speaker_name": "Adolfo Urso",
            "speaker_role": "Ministro",
            "speaker_key": "person:adolfo-urso",
            "topic": "chip",
            "claim_nature": "FACTUAL",
            "statement_date": "2026-11-12",
            "source_url": "https://example.test/1",
            "source_title": "Titolo",
            "source_publisher": "ANSA",
            "source_published_at": "2026-11-12T08:00:00+00:00",
            "created_at": "2026-11-12T20:00:00+00:00",
            "capture_kind": "article",
            "capture_body": BODY,
            "moment": {"moment_label": "par. 1", "moment_kind": "PARAGRAPH"},
            "verdict": "TRUE",
            "explanation": "Due miliardi stanziati.",
            "evidence": [{"url": "https://example.test/2", "title": "t", "publisher": "p"}],
            "agreement": "AGREE",
            "models": "m1|m2",
            "model_calls": 2,
            "duration_seconds": 12.5,
        }
        row.update(overrides)
        return row

    def test_dossier_is_verbatim_and_carries_the_verdict(self):
        dossier = dp.build_dossier(self._row())
        self.assertEqual(dossier["claim"], self._row()["quote"])
        self.assertIn(dossier["claim"], BODY)
        self.assertEqual(dossier["finding"]["assessment"], "SUPPORTED")
        self.assertEqual(dossier["source_methodology"]["verdict"]["label"], "Vero")
        self.assertFalse(dossier["source_methodology"]["opinion"])
        self.assertEqual(len(dossier["evidence"]), 2)

    def test_paraphrased_quote_is_refused(self):
        with self.assertRaises(dp.PublicationError):
            dp.build_dossier(self._row(quote="il governo spende due miliardi nei semiconduttori"))

    def test_unresolved_speaker_is_refused(self):
        with self.assertRaises(dp.PublicationError):
            dp.build_dossier(self._row(speaker_key="", speaker_name=""))

    def test_true_verdict_without_independent_link_is_refused(self):
        with self.assertRaises(dp.PublicationError):
            dp.build_dossier(self._row(evidence=[]))

    def test_not_verifiable_is_not_projected_by_public_v2(self):
        # public-v2 admits only SUPPORTED / FACTUALLY_FALSE / OUTDATED_DATA, so a
        # "not verifiable" statement stays in the database and in the summary.
        with self.assertRaisesRegex(dp.PublicationError, "NOT_VERIFIABLE"):
            dp.build_dossier(self._row(verdict="NOT_VERIFIABLE", evidence=[]))

    def test_opinion_is_not_projected_until_the_web_has_the_label(self):
        with self.assertRaisesRegex(dp.PublicationError, "OPINION_LABEL"):
            dp.build_dossier(
                self._row(verdict="OPINION", evidence=[], explanation="Giudizio personale.")
            )

    def test_partly_true_is_not_projected_until_the_web_has_the_label(self):
        with self.assertRaisesRegex(dp.PublicationError, "PARTLY_TRUE"):
            dp.build_dossier(self._row(verdict="PARTLY_TRUE"))

    def test_merge_keeps_existing_and_adds_new(self):
        dossier = dp.build_dossier(self._row())
        bundle = dp.merge_bundle(None, [dossier], [dp.build_content(dossier, self._row())], [])
        validate_public_bundle(bundle)
        self.assertEqual(bundle["dossier_count"], 1)
        again = dp.merge_bundle(bundle, [dossier], [], [])
        self.assertEqual(again["dossier_count"], 1)


class RunTest(unittest.TestCase):
    def test_run_writes_statements_and_publishes_verdicts(self):
        captured = {}

        class Store(dmm.DailyStore):
            def __init__(self):
                super().__init__(None)
                self.statements = []
                self.verdicts = []
                self.receipts = []

            def upsert_source(self, source):
                captured.setdefault("sources", []).append(source.id)

            def save_items(self, rows):
                captured["rows"] = rows
                return [row["content_id"] for row in rows]

            def capture_ids_today(self, day):
                return set()

            def save_capture(self, **kwargs):
                captured["capture"] = kwargs

            def save_statement(self, row):
                self.statements.append(row)

            def save_verdict(self, statement_id, verdict):
                self.verdicts.append((statement_id, verdict))

            def write_receipt(self, **kwargs):
                self.receipts.append(kwargs)

            def record_run(self, day, report, *, finished):
                captured["report"] = report

        store = Store()
        client = FakeClient(
            [
                json.dumps(
                    {
                        "statements": [
                            {
                                "quote": "il governo investira' due miliardi nel settore dei chip",
                                "speaker": "Adolfo Urso",
                                "speaker_role": "Ministro",
                                "moment": "par. 1",
                                "topic": "chip",
                                "nature": "FACTUAL",
                            },
                            {
                                "quote": "la misura serve a ridurre la dipendenza dall'estero",
                                "speaker": "",
                                "speaker_role": "",
                                "moment": "par. 2",
                                "topic": "chip",
                                "nature": "FACTUAL",
                            },
                        ]
                    }
                ),
                json.dumps(
                    {
                        "verdict": "TRUE",
                        "explanation": "Confermato.",
                        "evidence": [{"url": "https://example.test/2", "title": "t", "publisher": "p"}],
                    }
                ),
                json.dumps({"verdict": "TRUE", "explanation": "Regge."}),
            ]
        )
        config = dcfg.DailyConfig(
            sources=(item().source,),
            models={"statements": "m-extract", "verdict": "m-verdict", "check": "m-check"},
            limits={"max_items_per_run": 5, "max_items_per_source": 2},
            relevance_rule={"id": "PUBLIC_FIGURE_SPEAKING_IN_PUBLIC_ON_PUBLIC_INTEREST", "reason": "r"},
        )
        report = dmm.run_daily(
            config,
            store,
            client,
            run_date="2026-11-12",
            discovery_fetcher=lambda url: FEED_XML,
            article_fetcher=lambda url, **kwargs: (200, f"<article><p>{BODY}</p></article>"),
            evidence_fetcher=lambda url, **kwargs: (200, EVIDENCE_HTML),
            log=lambda message: None,
        )
        self.assertEqual(report["items"], 1)
        self.assertEqual(report["captures"], 1)
        self.assertEqual(report["statements"], 2)
        self.assertEqual(report["published"], 1)
        self.assertEqual(report["held"].get(dmm.HELD_NO_SPEAKER), 1)
        self.assertEqual(len(store.verdicts), 1)
        self.assertEqual(store.verdicts[0][1]["verdict"], "TRUE")
        self.assertGreaterEqual(report["model_calls"], 3)
        self.assertTrue(store.receipts)
        self.assertIn("ingestion_relevance", captured["rows"][0]["metadata"])


class SummaryTest(unittest.TestCase):
    def test_summary_lists_links_and_verdicts(self):
        class Store(dmm.DailyStore):
            def __init__(self):
                super().__init__(None)

            def published_since(self, day):
                return [
                    {
                        "speaker": "Adolfo Urso",
                        "quote": "Due miliardi per i chip",
                        "verdict": "TRUE",
                        "source_publisher": "ANSA",
                        "source_url": "https://example.test/1",
                    }
                ]

        text = dmm.evening_summary(Store(), "2026-11-12")
        self.assertIn("1 dichiarazioni", text)
        self.assertIn("https://example.test/1", text)
        self.assertIn("TRUE", text)


if __name__ == "__main__":
    unittest.main()
