"""DP-422 CLI route validation: public read model must own every emitted route."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "web" / "scripts" / "check-route-contract.mjs"
STATIC_ROUTES = ("/", "/esplora/", "/metodo/", "/correzioni/", "/dati/", "/progetto/")


def write_page(dist: Path, route: str, *, canonical: str | None = None, body: str = "") -> None:
    target = dist / route.strip("/") / "index.html" if route != "/" else dist / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '<html lang="it"><head><link rel="canonical" href="https://dichiarazionipubbliche.it'
        + (canonical or route)
        + '"></head><body>' + body + '</body></html>',
        encoding="utf-8",
    )


def check_routes(
    *, published: bool, alias_slug: str | None = None,
    person_alias_slugs: tuple[str, str] | None = None,
) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory(prefix="dp422-routes-") as tmp:
        dist = Path(tmp)
        for route in STATIC_ROUTES:
            write_page(dist, route)
        records = []
        if published:
            records.append({"kind": "finding", "route": "/dichiarazioni/finding-a/"})
            write_page(
                dist, "/dichiarazioni/finding-a/",
                body='<section id="storia">Versione pubblicata</section><a>Apri la fonte originale</a>',
            )
        if alias_slug is not None:
            write_page(
                dist, "/tracce/trace-a/",
                body="<h1>Cronologia revisionata</h1><a>Apri la fonte originale</a>"
                     "<p>senza attribuire intenzioni</p>",
            )
            write_page(dist, f"/compare/{alias_slug}/", canonical="/tracce/trace-a/")
        if person_alias_slugs is not None:
            records.append({"kind": "person", "route": "/persone/alfa/"})
            write_page(
                dist, "/persone/alfa/",
                body='<section class="person-chronology">Cronologia</section>'
                     '<p>non esiste un punteggio della persona</p>',
            )
            flat_slug, nested_slug = person_alias_slugs
            write_page(dist, f"/record/{flat_slug}/", canonical="/persone/alfa/")
            write_page(dist, f"/record/person/{nested_slug}/", canonical="/persone/alfa/")
        (dist / "search-index.v1.json").write_text(
            json.dumps({"records": records, "projection_sha256": "a" * 64}),
            encoding="utf-8",
        )
        return subprocess.run(
            ["node", str(CHECKER)],
            env={**os.environ, "DP_ROUTE_DIST": str(dist)},
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )


class DP422RouteContractBoundaryTest(unittest.TestCase):
    def test_empty_read_model_cannot_emit_trace_and_legacy_alias(self):
        result = check_routes(published=False, alias_slug="trace-a")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("approved-empty route", result.stderr)

    def test_populated_read_model_accepts_matching_trace_alias(self):
        result = check_routes(published=True, alias_slug="trace-a")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_alias_cannot_rebind_another_trace_identifier(self):
        result = check_routes(published=True, alias_slug="trace-other")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("legacy alias identifier", result.stderr)

    def test_populated_person_accepts_flat_and_nested_legacy_aliases_once_each(self):
        result = check_routes(published=True, person_alias_slugs=("alfa", "alfa"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 compatibility aliases", result.stdout)

    def test_person_alias_cannot_rebind_unrelated_identifier(self):
        for aliases in (("alfa", "altro"), ("altro", "alfa")):
            with self.subTest(aliases=aliases):
                result = check_routes(published=True, person_alias_slugs=aliases)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("legacy alias identifier", result.stderr)


if __name__ == "__main__":
    unittest.main()
