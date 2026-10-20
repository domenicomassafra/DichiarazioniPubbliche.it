"""Offline comparison and safety regressions for optional Trafilatura 2.3.1."""

import hashlib
import sys
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.capture_pipeline import (  # noqa: E402
    CaptureBodyStore, CapturePipelineError, StdlibVisibleTextParser,
    capture_content, verify_passage_roundtrip,
)
from dichiarazioni_pubbliche.capture_trafilatura_adapter import (  # noqa: E402
    TRAFILATURA_PARSER_VERSION, TrafilaturaHTMLParser,
)
from tests.test_capture_pipeline import (  # noqa: E402
    FakeCaptureStore, SequenceFetcher, fetched,
)


# Original synthetic text: illustrative extraction only, no third-party rights.
ITALIAN_ARTICLE = """<!doctype html><html lang="it"><head>
<meta charset="utf-8"><title>Notizie della mattina - Giornale esempio</title>
<meta property="og:title" content="Conferenza sul trasporto pubblico">
<meta property="article:published_time" content="2026-10-19T09:15:00+02:00">
<link rel="canonical" href="https://example.test/conferenza">
<script type="application/ld+json">{"@type":"NewsArticle","headline":"Conferenza sul trasporto pubblico","datePublished":"2026-10-19T09:15:00+02:00"}</script>
</head><body><header><nav>Home Politica Sport Economia Abbonati</nav></header>
<aside>Accetta tutti i cookie e iscriviti alla newsletter</aside>
<main><article><h1>Conferenza sul trasporto pubblico</h1>
<p>Durante la conferenza di questa mattina, gli amministratori hanno presentato
una proposta per migliorare le corse degli autobus nelle aree periferiche della città.
Il documento illustra le attività previste e le modalità con cui saranno raccolti
i suggerimenti degli abitanti, senza anticipare decisioni definitive.</p>
<p>Secondo il calendario illustrato nel corso dell'incontro, gli uffici pubblicheranno
una prima analisi dei flussi dei passeggeri dopo la consultazione con le associazioni.
La relazione sarà disponibile in formato digitale e resterà soggetta alle verifiche
tecniche e amministrative previste dai regolamenti.</p>
<p>La responsabile del progetto ha spiegato che questa fase serve a individuare i
percorsi più utilizzati e quelli dove le attese sono particolarmente lunghe. Le
proposte ricevute saranno valutate una per una prima della redazione del piano.
I partecipanti hanno chiesto informazioni sui criteri di selezione dei quartieri.</p>
</article></main><footer>Privacy Pubblicità Contattaci</footer></body></html>"""

INSTITUTIONAL_PAGE = """<html lang="it"><head><title>Avviso istituzionale</title>
<meta name="author" content="Ufficio comunicazione"></head><body>
<nav>Servizi Amministrazione Albo pretorio Contatti</nav>
<main><article><h1>Comunicazione dell'ufficio pubblico</h1>
<p>L'ufficio comunica l'apertura della consultazione sulle modalità di accesso ai servizi.
I cittadini possono presentare osservazioni sui moduli informativi disponibili sul sito.
La comunicazione riguarda un procedimento amministrativo ancora in corso.</p>
<p>Gli elaborati tecnici descrivono il percorso previsto per la raccolta delle domande.
Ogni osservazione ricevuta sarà catalogata con una ricevuta e un numero di protocollo.
La pubblicazione di questa comunicazione non costituisce approvazione delle proposte.</p>
<p>La scadenza indicata è puramente illustrativa per questa prova automatica.
Nessuna dichiarazione reale è attribuita a funzionari o persone identificabili.
L'ufficio precisa che un aggiornamento sarà diffuso attraverso i canali ufficiali.</p>
</article></main><footer>Note legali Cookie policy</footer></body></html>"""


def real_donor_available():
    try:
        return version("trafilatura") == "2.3.1"
    except PackageNotFoundError:
        return False


class TrafilaturaAdapterTests(unittest.TestCase):
    def mocked_donor(self, output):
        fake = SimpleNamespace(extract=unittest.mock.Mock(return_value=output))
        self.enterContext(patch(
            "dichiarazioni_pubbliche.capture_trafilatura_adapter.version",
            return_value="2.3.1",
        ))
        self.enterContext(patch(
            "dichiarazioni_pubbliche.capture_trafilatura_adapter.import_module",
            return_value=fake,
        ))
        return fake.extract

    def test_primary_body_omits_boilerplate_and_preserves_metadata(self):
        extraction = self.mocked_donor(
            "Durante la conferenza gli uffici hanno presentato il programma.\n"
            "Il documento sarà verificato dopo la consultazione."
        )
        body = ITALIAN_ARTICLE.encode("utf-8")
        stdlib = StdlibVisibleTextParser().parse(fetched(body))
        result = TrafilaturaHTMLParser().parse(fetched(body))
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.parser_method, "TRAFILATURA_HTML")
        self.assertEqual(result.parser_version, TRAFILATURA_PARSER_VERSION)
        self.assertIn("Abbonati", stdlib.canonical_text)
        self.assertNotIn("Abbonati", result.canonical_text)
        self.assertNotIn("cookie", result.canonical_text)
        self.assertNotIn("Conferenza sul trasporto pubblico", result.canonical_text)
        self.assertEqual(result.metadata["meta"]["og:title"], "Conferenza sul trasporto pubblico")
        self.assertEqual(
            result.metadata["meta"]["article:published_time"],
            "2026-10-19T09:15:00+02:00",
        )
        self.assertEqual(
            result.metadata["jsonld_identity"][0]["datePublished"],
            "2026-10-19T09:15:00+02:00",
        )
        self.assertEqual(
            stdlib.metadata["jsonld_identity"][0]["datePublished"],
            result.metadata["jsonld_identity"][0]["datePublished"],
        )
        self.assertNotIn("2026-10-19T09:15", result.canonical_text)
        self.assertEqual(result.metadata["canonical_url_candidates"], ["https://example.test/conferenza"])
        self.assertEqual(result.metadata["html_extraction"]["actual_parser"], TRAFILATURA_PARSER_VERSION)
        self.assertEqual(extraction.call_count, 1)
        self.assertIn("<main>", extraction.call_args.args[0])
        self.assertEqual(extraction.call_args.kwargs["include_comments"], False)
        self.assertEqual(extraction.call_args.kwargs["include_tables"], False)
        for span in result.spans:
            self.assertEqual(result.canonical_text[span.start_char:span.end_char], span.text)
            self.assertEqual(span.text_sha256, hashlib.sha256(span.text.encode("utf-8")).hexdigest())

    def test_missing_package_falls_back_to_unmodified_stdlib(self):
        with patch("dichiarazioni_pubbliche.capture_trafilatura_adapter.version", side_effect=PackageNotFoundError):
            result = TrafilaturaHTMLParser().parse(fetched(INSTITUTIONAL_PAGE.encode()))
        baseline = StdlibVisibleTextParser().parse(fetched(INSTITUTIONAL_PAGE.encode()))
        self.assertEqual(result.parser_method, baseline.parser_method)
        self.assertEqual(result.parser_version, baseline.parser_version)
        self.assertEqual(result.canonical_text, baseline.canonical_text)
        self.assertEqual(result.spans, baseline.spans)
        self.assertEqual(result.metadata["html_extraction"]["fallback_reason"], "TRAFILATURA_UNAVAILABLE")

    def test_unpinned_version_and_exception_fall_back(self):
        with patch("dichiarazioni_pubbliche.capture_trafilatura_adapter.version", return_value="2.4.0"):
            wrong = TrafilaturaHTMLParser().parse(fetched(INSTITUTIONAL_PAGE.encode()))
        self.assertEqual(wrong.metadata["html_extraction"]["fallback_reason"], "TRAFILATURA_VERSION_MISMATCH")
        failing_extract = self.mocked_donor(None)
        failing_extract.side_effect = ValueError("invalid malformed markup")
        failed = TrafilaturaHTMLParser().parse(fetched(INSTITUTIONAL_PAGE.encode()))
        self.assertEqual(failed.parser_method, "STDLIB_VISIBLE_TEXT")
        self.assertEqual(failed.metadata["html_extraction"]["fallback_reason"], "TRAFILATURA_EXTRACTION_FAILED")

    def test_empty_body_holds_even_when_navigation_is_visible(self):
        self.mocked_donor(None)
        body = b"<html><nav>Privacy Cookie Menu</nav><script>hidden()</script></html>"
        self.assertEqual(StdlibVisibleTextParser().parse(fetched(body)).status, "SUCCEEDED")
        result = TrafilaturaHTMLParser().parse(fetched(body))
        self.assertEqual((result.status, result.error_category), ("FAILED", "PARSER_EMPTY_TEXT"))
        self.assertEqual(result.canonical_text, "")
        self.assertEqual(result.spans, ())

    def test_charset_policy_and_disabled_metadata(self):
        extraction = self.mocked_donor("L'ufficio riceverà osservazioni e valutazioni.")
        body = '<html><body><article>La città è aperta.</article></body></html>'.encode("latin-1")
        response = fetched(body)
        response = response.__class__(**{**vars(response), "charset": "latin-1"})
        result = TrafilaturaHTMLParser(extract_metadata=False).parse(response)
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.metadata, {})
        self.assertIn("città", extraction.call_args.args[0])

    def test_malformed_oversized_output_and_unsupported_media_fail_closed(self):
        self.mocked_donor("A" * 512_001)
        result = TrafilaturaHTMLParser().parse(fetched(b"<article>Source.</article>"))
        self.assertEqual(result.error_category, "PARSER_TEXT_TOO_LARGE")
        binary = TrafilaturaHTMLParser().parse(fetched(b"%PDF-1.5", media_type="application/pdf"))
        self.assertEqual(binary.error_category, "PARSER_UNSUPPORTED_MEDIA_TYPE")

    def test_pipeline_receipts_sha_selector_and_no_extra_fetch(self):
        self.mocked_donor("Questo testo appartiene alla fonte osservata.\nUn secondo paragrafo controllabile.")
        body = ITALIAN_ARTICLE.encode()
        source = fetched(body)
        transport = SequenceFetcher(source)
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            receipt = capture_content(
                content_id="content:trafilatura-articolo", url=source.final_url,
                store=store, body_store=CaptureBodyStore(Path(tmp)),
                observed_at="2026-10-19T10:00:00+00:00",
                fetcher=transport, parser=TrafilaturaHTMLParser(),
            )
            self.assertEqual(transport.calls, 1)
            self.assertEqual(receipt.parse_status, "SUCCEEDED")
            self.assertEqual(receipt.content_sha256, hashlib.sha256(body).hexdigest())
            self.assertEqual(len(store.captures), 1)
            capture = next(iter(store.captures.values()))["record"]
            self.assertEqual(capture.final_url, source.final_url)
            self.assertEqual(capture.parser_version, TRAFILATURA_PARSER_VERSION)
            self.assertEqual(capture.metadata["source_metadata"]["html_extraction"]["requested_parser"], TRAFILATURA_PARSER_VERSION)
            self.assertEqual(capture.status, "CAPTURED")
            self.assertNotEqual(capture.rights_status, "APPROVED")
            for pid in receipt.passage_ids:
                passage = store.passages[pid]
                self.assertTrue(verify_passage_roundtrip(
                    body=body, media_type="text/html", charset="utf-8",
                    passage=passage, parser=TrafilaturaHTMLParser(),
                ))
            succeeded = [value for key, value in store.events.items() if key[1] == "PARSE_SUCCEEDED"]
            self.assertEqual(len(succeeded), 1)
            self.assertEqual(succeeded[0]["receipt"]["parser_version"], TRAFILATURA_PARSER_VERSION)

    def test_guards_reject_unsafe_url_and_oversized_body_before_parse(self):
        extraction = self.mocked_donor("Never reached")
        body = ITALIAN_ARTICLE.encode()
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            fetcher = SequenceFetcher(fetched(body))
            common = dict(content_id="content:unsafe", store=store,
                          body_store=CaptureBodyStore(Path(tmp)), fetcher=fetcher,
                          parser=TrafilaturaHTMLParser())
            with self.assertRaisesRegex(CapturePipelineError, "CAPTURE_URL_NONPUBLIC_IP"):
                capture_content(url="https://127.0.0.1/", **common)
            self.assertEqual(fetcher.calls, 0)
            with self.assertRaisesRegex(CapturePipelineError, "CAPTURE_RESPONSE_TOO_LARGE"):
                capture_content(url="https://example.test/article", max_response_bytes=16, **common)
            self.assertEqual(extraction.call_count, 0)
            with self.assertRaisesRegex(CapturePipelineError, "RIGHTS_DENIED"):
                capture_content(
                    url="https://example.test/article", **common,
                    rights_guard=lambda: self.fail_if_rights_not_cleared(),
                )
            self.assertEqual(fetcher.calls, 1)  # The oversized fetch was refused before parsing.
            self.assertEqual(extraction.call_count, 0)

    @staticmethod
    def fail_if_rights_not_cleared():
        raise CapturePipelineError("RIGHTS_DENIED")

    def test_empty_extraction_persists_private_capture_but_no_passages(self):
        self.mocked_donor(None)
        body = b"<html><body><nav>Privacy Cookie Abbonati</nav></body></html>"
        with tempfile.TemporaryDirectory() as tmp:
            store = FakeCaptureStore()
            result = capture_content(
                content_id="content:empty-donor", url="https://example.test/empty",
                store=store, body_store=CaptureBodyStore(Path(tmp)),
                fetcher=SequenceFetcher(fetched(body)), parser=TrafilaturaHTMLParser(),
            )
        self.assertEqual(result.parse_status, "FAILED")
        self.assertEqual(result.reason_code, "PARSER_EMPTY_TEXT")
        self.assertEqual(result.passage_ids, ())
        self.assertEqual(result.content_sha256, hashlib.sha256(body).hexdigest())
        self.assertEqual(len(store.captures), 1)
        self.assertFalse(store.passages)


@unittest.skipUnless(real_donor_available(), "trafilatura==2.3.1 optional extra absent")
class RealTrafilaturaFixtureTests(unittest.TestCase):
    def test_italian_article_and_institutional_boilerplate(self):
        for html in (ITALIAN_ARTICLE, INSTITUTIONAL_PAGE):
            with self.subTest(page=html[0:40]):
                body = html.encode("utf-8")
                donor = TrafilaturaHTMLParser().parse(fetched(body))
                baseline = StdlibVisibleTextParser().parse(fetched(body))
                self.assertEqual(donor.status, "SUCCEEDED", donor.error_category)
                self.assertLess(len(donor.canonical_text), len(baseline.canonical_text))
                self.assertNotIn("Cookie policy", donor.canonical_text)
                self.assertNotIn("Abbonati", donor.canonical_text)
                self.assertTrue(donor.spans)
                if html == ITALIAN_ARTICLE:
                    self.assertEqual(
                        donor.metadata["jsonld_identity"][0]["datePublished"],
                        "2026-10-19T09:15:00+02:00",
                    )
                    self.assertEqual(
                        donor.metadata["meta"]["article:published_time"],
                        baseline.metadata["meta"]["article:published_time"],
                    )
                else:
                    self.assertNotIn("article:published_time", donor.metadata["meta"])
                    self.assertFalse(any(
                        "datePublished" in row for row in donor.metadata["jsonld_identity"]
                    ))


if __name__ == "__main__":
    unittest.main()
