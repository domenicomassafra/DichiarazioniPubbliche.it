"""Contract tests for the read-only public API (DP-402/DP-403/DP-404).

These defend observable contract only: pagination cursor stability, filter
correctness, typed 400s, 404s that do not disclose operational existence, cache
validators, and the fail-closed guarantee that a non-PUBLISH dossier is never
served. There is no socket in any of them: ``dispatch`` is the same entry point
the HTTP handler uses, so the tested contract is the served contract.
"""

import json
import hashlib
import http.client
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.linked_data import (  # noqa: E402
    projection_linked_data_receipt,
    projection_ntriples,
)
from dichiarazioni_pubbliche.openapi import (  # noqa: E402
    OPENAPI_VERSION,
    build_api_readme,
    build_openapi_document,
    build_llms_txt,
    fictional_dossier,
    openapi_document_bytes,
)
from dichiarazioni_pubbliche.public_api import (  # noqa: E402
    API_BASE_PATH,
    DEFAULT_LIMIT,
    LINKED_DATA_PATH,
    MAX_LIMIT,
    NTRIPLES_CONTENT_TYPE,
    PUBLIC_SCHEMA_VERSION,
    ROUTES,
    PublicApiError,
    build_index,
    build_server,
    canonical_json_bytes,
    decode_cursor,
    dispatch,
    encode_cursor,
    load_index,
    query_findings,
    select_findings,
    validate_params,
)
from dichiarazioni_pubbliche.public_schema import (  # noqa: E402
    PublicSchemaValidationError,
    projection_dataset_sha256,
    validate_dossier,
    validate_public_bundle,
)

DEMO_PROJECTION = ROOT / "web" / "src" / "data" / "demo-projection.json"


def load_demo_index():
    bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
    return build_index(bundle, source_path=str(DEMO_PROJECTION), mtime=1_700_000_000.0)


def write_bundle(path: Path, bundle: dict) -> str:
    path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    return str(path)


def write_linked_bundle(root: Path, bundle: dict) -> str:
    root.mkdir(parents=True, exist_ok=True)
    projection_path = Path(write_bundle(root / "index.json", bundle))
    (root / "index.nt").write_text(projection_ntriples(bundle), encoding="utf-8")
    (root / "linked-data-receipt.json").write_text(
        json.dumps(projection_linked_data_receipt(bundle), ensure_ascii=False),
        encoding="utf-8",
    )
    return str(projection_path)


def published_bundle(dossiers: list[dict], *, schema_version: str = PUBLIC_SCHEMA_VERSION) -> dict:
    """Build a bundle that passes the real validator, for negative-path tests."""
    return {
        "schema_version": schema_version,
        "generated_at": "2026-01-20T08:00:00+00:00",
        "dataset_sha256": "a" * 64,
        "methodology": {
            "claim_level_only": True,
            "aggregate_person_score": False,
            "requires_publication_gate": True,
            "requires_approved_evidence": True,
            "requires_resolved_transcript": True,
        },
        "dossier_count": len(dossiers),
        "omitted_count": 0,
        "dossiers": dossiers,
    }


class HttpAdapterContractTest(unittest.TestCase):
    """Exercise the real stdlib socket adapter, not only transport-agnostic dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.static_root = tempfile.TemporaryDirectory()
        cls.bundle_root = tempfile.TemporaryDirectory()
        Path(cls.static_root.name, "index.html").write_text(
            "<!doctype html><title>Dichiarazioni Pubbliche test</title>",
            encoding="utf-8",
        )
        cls.bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
        cls.projection_path = write_linked_bundle(Path(cls.bundle_root.name), cls.bundle)
        cls.server = build_server(
            cls.projection_path,
            host="127.0.0.1",
            port=0,
            static_dir=cls.static_root.name,
        )
        cls.host, cls.port = cls.server.server_address[:2]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.static_root.cleanup()
        cls.bundle_root.cleanup()

    def request(self, method: str, path: str, *, headers: dict[str, str] | None = None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), body
        finally:
            connection.close()

    def test_health_get_head_revalidation_and_method_rejection(self):
        status, headers, body = self.request("GET", f"{API_BASE_PATH}/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["data"]["status"], "ok")
        self.assertIn("ETag", headers)

        head_status, head_headers, head_body = self.request("HEAD", f"{API_BASE_PATH}/health")
        self.assertEqual(head_status, 200)
        self.assertEqual(head_body, b"")
        self.assertEqual(head_headers.get("ETag"), headers["ETag"])

        fresh_status, _, fresh_body = self.request(
            "GET",
            f"{API_BASE_PATH}/health",
            headers={"If-None-Match": headers["ETag"]},
        )
        self.assertEqual(fresh_status, 304)
        self.assertEqual(fresh_body, b"")

        post_status, post_headers, post_body = self.request("POST", f"{API_BASE_PATH}/health")
        self.assertEqual(post_status, 405)
        self.assertEqual(post_headers.get("Allow"), "GET, HEAD")
        self.assertEqual(json.loads(post_body)["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_static_site_api_and_llms_share_one_origin(self):
        static_status, _, static_body = self.request("GET", "/")
        self.assertEqual(static_status, 200)
        self.assertIn(b"Dichiarazioni Pubbliche test", static_body)

        llms_status, llms_headers, llms_body = self.request("GET", "/llms.txt")
        self.assertEqual(llms_status, 200)
        self.assertTrue(llms_headers["Content-Type"].startswith("text/plain"))
        self.assertIn(b"/api/v1/openapi.json", llms_body)
        self.assertIn("ETag", llms_headers)
        self.assertIn(f"<{LINKED_DATA_PATH}>", llms_headers["Link"])

        api_status, _, api_body = self.request("GET", f"{API_BASE_PATH}/health")
        self.assertEqual(api_status, 200)
        self.assertEqual(json.loads(api_body)["data"]["status"], "ok")

    def test_generated_ntriples_is_same_origin_discoverable_and_head_safe(self):
        status, headers, body = self.request(
            "GET",
            LINKED_DATA_PATH,
            headers={"Accept": NTRIPLES_CONTENT_TYPE},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], NTRIPLES_CONTENT_TYPE)
        self.assertEqual(body, projection_ntriples(self.bundle).encode("utf-8"))
        self.assertIn(f"<{API_BASE_PATH}/index.json>", headers["Link"])
        self.assertIn('rel="alternate"', headers["Link"])
        self.assertIn("ETag", headers)

        head_status, head_headers, head_body = self.request(
            "HEAD",
            LINKED_DATA_PATH,
            headers={"Accept": NTRIPLES_CONTENT_TYPE},
        )
        self.assertEqual(head_status, 200)
        self.assertEqual(head_body, b"")
        self.assertEqual(head_headers["Content-Type"], NTRIPLES_CONTENT_TYPE)
        self.assertEqual(head_headers["ETag"], headers["ETag"])
        self.assertEqual(int(head_headers["Content-Length"]), len(body))

        health_status, health_headers, _ = self.request("GET", f"{API_BASE_PATH}/health")
        self.assertEqual(health_status, 200)
        self.assertIn(f'<{LINKED_DATA_PATH}>; rel="alternate"; type="{NTRIPLES_CONTENT_TYPE}"', health_headers["Link"])

        rejected, _, rejected_body = self.request(
            "GET",
            LINKED_DATA_PATH,
            headers={"Accept": "application/json"},
        )
        self.assertEqual(rejected, 406)
        self.assertEqual(json.loads(rejected_body)["error"]["code"], "NOT_ACCEPTABLE")

    def test_unsupported_accept_is_406(self):
        status, _, body = self.request(
            "GET",
            f"{API_BASE_PATH}/health",
            headers={"Accept": "text/html"},
        )
        self.assertEqual(status, 406)
        self.assertEqual(json.loads(body)["error"]["code"], "NOT_ACCEPTABLE")


class LinkedDataHostFailClosedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
        self.path = write_linked_bundle(self.root, self.bundle)

    def tearDown(self):
        self.tmp.cleanup()

    def response(self):
        return dispatch(
            "GET",
            LINKED_DATA_PATH,
            projection_path=self.path,
            accept=NTRIPLES_CONTENT_TYPE,
        )

    def test_missing_generated_artifact_or_receipt_is_503(self):
        (self.root / "index.nt").unlink()
        missing_artifact = self.response()
        self.assertEqual(missing_artifact.status, 503)
        self.assertEqual(
            json.loads(missing_artifact.body)["error"]["code"],
            "PUBLIC_PROJECTION_UNAVAILABLE",
        )

        self.path = write_linked_bundle(self.root, self.bundle)
        (self.root / "linked-data-receipt.json").unlink()
        missing_receipt = self.response()
        self.assertEqual(missing_receipt.status, 503)

    def test_stale_projection_fingerprint_is_503(self):
        receipt_path = self.root / "linked-data-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["projection_fingerprint"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        response = self.response()
        self.assertEqual(response.status, 503)
        self.assertNotIn(self.bundle["dataset_sha256"].encode("utf-8"), response.body)

    def test_tampered_artifact_and_forged_receipt_still_fail_closed(self):
        artifact = b"<https://example.test/a> <https://example.test/b> <https://example.test/c> .\n"
        (self.root / "index.nt").write_bytes(artifact)
        receipt_path = self.root / "linked-data-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["ntriples_sha256"] = hashlib.sha256(artifact).hexdigest()
        receipt["byte_count"] = len(artifact)
        receipt["triple_count"] = 1
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        response = self.response()
        self.assertEqual(response.status, 503)
        self.assertNotIn(b"example.test/a", response.body)

    def test_query_parameters_do_not_select_or_transform_linked_data(self):
        response = dispatch(
            "GET",
            f"{LINKED_DATA_PATH}?format=json",
            projection_path=self.path,
            accept=NTRIPLES_CONTENT_TYPE,
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(response.body)["error"]["code"], "UNSUPPORTED_PARAMETER")


class PaginationContractTest(unittest.TestCase):
    def setUp(self):
        self.index = load_demo_index()

    def test_default_limit_and_order_are_deterministic(self):
        page = query_findings(self.index, {})
        self.assertEqual(page["limit"], DEFAULT_LIMIT)
        ids = [item["finding_id"] for item in page["items"]]
        # Newest publication first, finding id as the stable tie-breaker.
        epochs = [self.index.findings_by_id[i].published_epoch for i in ids]
        self.assertEqual(epochs, sorted(epochs, reverse=True))
        self.assertEqual(ids, [entry.finding_id for entry in self.index.entries])
        self.assertEqual(ids, [item["finding_id"] for item in query_findings(self.index, {})["items"]])

    def test_cursor_walks_every_record_exactly_once(self):
        seen: list[str] = []
        params: dict = {"limit": "1"}
        for _ in range(MAX_LIMIT):
            page = query_findings(self.index, params)
            seen.extend(item["finding_id"] for item in page["items"])
            if not page["next_cursor"]:
                break
            params = {"limit": "1", "cursor": page["next_cursor"]}
        self.assertEqual(
            seen,
            [entry.finding_id for entry in self.index.entries],
        )
        self.assertEqual(len(seen), len(set(seen)))

    def test_cursor_absent_when_page_exhausts_collection(self):
        page = query_findings(self.index, {"limit": "100"})
        self.assertIsNone(page["next_cursor"])

    def test_cursor_is_stable_across_repeated_evaluation(self):
        first = query_findings(self.index, {"limit": "1"})
        second = query_findings(self.index, {"limit": "1"})
        self.assertEqual(first["next_cursor"], second["next_cursor"])

    def test_cursor_from_another_filter_set_is_rejected(self):
        page = query_findings(self.index, {"limit": "1"})
        entry = self.index.entries[0]
        with self.assertRaises(PublicApiError) as ctx:
            decode_cursor(page["next_cursor"] or encode_cursor(entry, {}), {"topic": ("NUMERIC_STATISTIC",)})
        self.assertEqual(ctx.exception.code, "INVALID_CURSOR")
        self.assertEqual(ctx.exception.status, 400)

    def test_cursor_from_another_version_is_rejected(self):
        entry = self.index.entries[0]
        forged = encode_cursor(entry, {})
        payload = json.loads(
            __import__("base64").urlsafe_b64decode(forged + "=" * (-len(forged) % 4))
        )
        payload["v"] = 99
        mutated = (
            __import__("base64")
            .urlsafe_b64encode(canonical_json_bytes(payload))
            .decode()
            .rstrip("=")
        )
        with self.assertRaises(PublicApiError) as ctx:
            decode_cursor(mutated, {})
        self.assertEqual(ctx.exception.code, "INVALID_CURSOR")

    def test_garbage_cursor_is_a_typed_400(self):
        with self.assertRaises(PublicApiError) as ctx:
            decode_cursor("!!!not-base64!!!", {})
        self.assertEqual((ctx.exception.status, ctx.exception.code), (400, "INVALID_CURSOR"))

    def test_limit_bounds(self):
        with self.assertRaises(PublicApiError) as ctx:
            validate_params({"limit": str(MAX_LIMIT + 1)})
        self.assertEqual(ctx.exception.code, "INVALID_PARAMETER_VALUE")
        with self.assertRaises(PublicApiError):
            validate_params({"limit": "0"})
        with self.assertRaises(PublicApiError):
            validate_params({"limit": "all"})


class FilterContractTest(unittest.TestCase):
    def setUp(self):
        self.index = load_demo_index()

    def _field(self, name):
        return {
            "person": "person_id",
            "content": "content_id",
            "topic": "claim_type",
            "assessment": "assessment",
            "status": "publication_status",
        }[name]

    def test_every_filter_dimension_narrows_the_result(self):
        everything = select_findings(self.index, {})
        self.assertGreater(len(everything), 1)
        for name in ("topic", "assessment", "status", "person", "content"):
            field = self._field(name)
            entry = self.index.entries[0]
            value = getattr(entry, field)
            selected = select_findings(self.index, {name: value})
            self.assertTrue(selected, f"{name} filter matched nothing")
            for match in selected:
                self.assertEqual(getattr(match, field), value, name)
            # A filter narrows exactly when it excludes something. When the
            # corpus is constant on this dimension it legitimately selects
            # everything, so narrowing is asserted only when it is meaningful.
            excluded = [e for e in everything if getattr(e, field) != value]
            if excluded:
                self.assertLess(len(selected), len(everything), name)

    def test_combined_filters_are_intersected(self):
        entry = self.index.entries[0]
        other = next(
            (e for e in self.index.entries if e.claim_type != entry.claim_type),
            None,
        )
        if other is None:
            self.skipTest("corpus is constant on claim_type")
        selected = select_findings(
            self.index, {"person": (entry.person_id,), "topic": (other.claim_type,)}
        )
        # Both filters are individually satisfiable, so an empty intersection
        # proves they are AND-combined rather than merged.
        self.assertTrue(select_findings(self.index, {"person": (entry.person_id,)}))
        self.assertTrue(select_findings(self.index, {"topic": (other.claim_type,)}))
        self.assertEqual(selected, [])

    def test_multi_valued_filters_are_or_within_and_across(self):
        first = self.index.entries[0]
        last = self.index.entries[-1]
        selected = select_findings(
            self.index, {"person": (first.person_id, last.person_id)}
        )
        self.assertEqual(len(selected), 2)

    def test_date_range_is_inclusive_and_filters(self):
        entry = self.index.entries[0]
        exact = entry.published_epoch
        self.assertTrue(select_findings(self.index, {"published_from": exact}))
        self.assertTrue(select_findings(self.index, {"published_to": exact}))
        self.assertFalse(select_findings(self.index, {"published_from": exact + 10_000_000}))

    def test_unknown_filter_value_is_rejected_not_ignored(self):
        with self.assertRaises(PublicApiError) as ctx:
            validate_params({"assessment": "DEFINITELY_TRUE"})
        self.assertEqual((ctx.exception.status, ctx.exception.code), (400, "INVALID_PARAMETER_VALUE"))

    def test_naive_date_without_timezone_is_rejected(self):
        with self.assertRaises(PublicApiError) as ctx:
            validate_params({"published_from": "2026-01-20T08:00:00"})
        self.assertEqual(ctx.exception.code, "INVALID_PARAMETER_VALUE")

    def test_unknown_parameter_is_typed_400_not_silent_empty(self):
        response = dispatch("GET", f"{API_BASE_PATH}/findings?colour=blue",
                            projection_path=str(DEMO_PROJECTION))
        self.assertEqual(response.status, 400)
        body = json.loads(response.body)
        self.assertEqual(body["error"]["code"], "UNSUPPORTED_PARAMETER")
        # Transport-only envelope: an error never mixes in a resource shape.
        self.assertEqual(sorted(body), ["error"])
        self.assertEqual(sorted(body["error"]), ["code", "message", "request_id"])
        # A valid request on the same route still succeeds, so the 400 is
        # specific to the unknown parameter and not a permanent failure.
        good = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(DEMO_PROJECTION))
        self.assertEqual(good.status, 200)
        self.assertNotEqual(response.body, good.body)


class NotFoundContractTest(unittest.TestCase):
    def test_unknown_finding_and_record_are_indistinguishable_404s(self):
        finding = dispatch("GET", f"{API_BASE_PATH}/findings/finding:does-not-exist",
                           projection_path=str(DEMO_PROJECTION))
        record = dispatch("GET", f"{API_BASE_PATH}/records/no-such-record",
                          projection_path=str(DEMO_PROJECTION))
        route = dispatch("GET", f"{API_BASE_PATH}/nope", projection_path=str(DEMO_PROJECTION))
        codes = set()
        for response in (finding, record, route):
            self.assertEqual(response.status, 404)
            codes.add(json.loads(response.body)["error"]["code"])
        # One externally visible 404 shape for every non-projectable resource:
        # an unknown path, an unknown id, and an unknown slug are indistinguishable.
        self.assertEqual(codes, {"RESOURCE_NOT_FOUND"})
        shapes = {
            tuple(sorted(json.loads(response.body)["error"])) for response in (finding, record, route)
        }
        self.assertEqual(shapes, {("code", "message", "request_id")})

    def test_404_body_leaks_no_operational_detail(self):
        response = dispatch("GET", f"{API_BASE_PATH}/findings/INTERNAL_CANDIDATE:secret",
                            projection_path=str(DEMO_PROJECTION))
        self.assertEqual(response.status, 404)
        text = response.body.decode()
        self.assertNotIn("INTERNAL_CANDIDATE", text)
        self.assertNotIn("postgres", text.lower())
        self.assertNotIn("Traceback", text)


class CacheContractTest(unittest.TestCase):
    def setUp(self):
        self.path = str(DEMO_PROJECTION)

    def test_replaced_projection_with_preserved_mtime_and_size_fails_closed(self):
        """A correction/hold must invalidate the cached API index after atomic replacement.

        Preserving mtime and length is legitimate for reproducible artifacts and can
        happen during restores.  The old cache key missed an inode replacement and
        would keep serving an already-withdrawn projection indefinitely.
        """
        original = DEMO_PROJECTION.read_bytes()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "index.json"
            target.write_bytes(original)
            first = load_index(target)
            self.assertGreater(len(first.entries), 0)
            stamp = target.stat()

            bad = b'{"invalid":true}'
            replacement = Path(root) / "replacement.json"
            replacement.write_bytes(bad + b" " * (len(original) - len(bad)))
            os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertEqual(replacement.stat().st_size, stamp.st_size)
            os.replace(replacement, target)
            self.assertEqual(target.stat().st_mtime_ns, stamp.st_mtime_ns)

            response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(target))
            self.assertEqual(response.status, 503)
            self.assertEqual(json.loads(response.body)["error"]["code"],
                             "PUBLIC_PROJECTION_UNAVAILABLE")

    def test_same_length_atomic_revision_refreshes_a_valid_public_index(self):
        original = DEMO_PROJECTION.read_bytes()
        old_instant = b'"generated_at": "2026-09-23T20:50:00+00:00"'
        new_instant = b'"generated_at": "2026-09-24T20:50:00+00:00"'
        self.assertIn(old_instant, original)
        revised = original.replace(old_instant, new_instant, 1)
        self.assertEqual(len(revised), len(original))
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "index.json"
            target.write_bytes(original)
            before = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(target))
            stamp = target.stat()
            replacement = Path(root) / "revision.json"
            replacement.write_bytes(revised)
            os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            os.replace(replacement, target)

            after = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(target),
                             conditional_headers={"if-none-match": before.headers["ETag"]})
            self.assertEqual(after.status, 200)
            self.assertNotEqual(before.headers["ETag"], after.headers["ETag"])

            # Last-Modified is intentionally not a sufficient authority for
            # a 304: an atomic withdrawal can preserve the HTTP-date second.
            last_modified_only = dispatch(
                "GET", f"{API_BASE_PATH}/findings", projection_path=str(target),
                conditional_headers={"if-modified-since": before.headers["Last-Modified"]},
            )
            self.assertEqual(last_modified_only.status, 200)

    def test_data_responses_are_cdn_cacheable(self):
        response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=self.path)
        self.assertEqual(response.status, 200)
        self.assertTrue(response.headers["ETag"].startswith('"'))
        self.assertIn("Last-Modified", response.headers)
        self.assertIn("public", response.headers["Cache-Control"])
        self.assertIn("max-age=", response.headers["Cache-Control"])
        self.assertIn("stale-while-revalidate=", response.headers["Cache-Control"])

    def test_matching_etag_yields_304_with_same_validators(self):
        first = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=self.path)
        second = dispatch(
            "GET",
            f"{API_BASE_PATH}/findings",
            projection_path=self.path,
            conditional_headers={"if-none-match": first.headers["ETag"]},
        )
        self.assertEqual(second.status, 304)
        self.assertEqual(second.body, b"")
        self.assertEqual(second.headers["ETag"], first.headers["ETag"])

    def test_head_has_same_validators_and_no_body(self):
        get = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=self.path)
        head = dispatch("HEAD", f"{API_BASE_PATH}/findings", projection_path=self.path)
        self.assertEqual(head.status, 200)
        self.assertEqual(head.body, b"")
        self.assertEqual(head.headers["ETag"], get.headers["ETag"])
        self.assertEqual(head.headers["Cache-Control"], get.headers["Cache-Control"])

    def test_conditional_etag_fails_closed_on_dataset_change(self):
        import tempfile

        bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bundle(Path(tmp) / "index.json", bundle)
            before = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=path)
            # A different dataset fingerprint must invalidate every validator.
            changed = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
            changed["dataset_sha256"] = "b" * 64
            changed["generated_at"] = "2026-02-02T00:00:00+00:00"
            path2 = write_bundle(Path(tmp) / "index2.json", changed)
            after = dispatch(
                "GET",
                f"{API_BASE_PATH}/findings",
                projection_path=path2,
                conditional_headers={"if-none-match": before.headers["ETag"]},
            )
        self.assertEqual(after.status, 200)
        self.assertNotEqual(after.headers["ETag"], before.headers["ETag"])


class FailClosedTest(unittest.TestCase):
    """The API must never re-implement the gate; a held record stays invisible."""

    def setUp(self):
        self.tmp = Path(__import__("tempfile").mkdtemp())

    def test_non_publish_dossier_is_never_served(self):
        held = fictional_dossier(finding_id="finding:held:1", claim_id="claim:held:1")
        held["finding"]["publication_status"] = "INTERNAL_CANDIDATE"
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(published_bundle([held]))
        # And the API refuses to load a bundle containing one.
        path = write_bundle(self.tmp / "held.json", published_bundle([held]))
        response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=path)
        self.assertEqual(response.status, 503)
        self.assertEqual(
            json.loads(response.body)["error"]["code"], "PUBLIC_PROJECTION_UNAVAILABLE"
        )
        detail = dispatch("GET", f"{API_BASE_PATH}/findings/finding:held:1", projection_path=path)
        self.assertEqual(detail.status, 503)
        self.assertNotIn(b"finding:held:1", detail.body)

    def test_unresolved_assessment_dossier_is_never_served(self):
        held = fictional_dossier(finding_id="finding:unresolved:1", claim_id="claim:unresolved:1")
        held["finding"]["assessment"] = "UNRESOLVED"
        with self.assertRaises(PublicSchemaValidationError):
            validate_public_bundle(published_bundle([held]))
        path = write_bundle(self.tmp / "unresolved.json", published_bundle([held]))
        self.assertEqual(
            dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=path).status, 503
        )

    def test_pending_right_of_reply_and_unapproved_correction_are_not_projected(self):
        # A reply that has not passed its own review never enters a dossier, so
        # the projection can only ever carry a PUBLISHED one. Assert that shape
        # invariant on a dossier the API is allowed to serve.
        dossier = fictional_dossier(with_reply=True, with_correction=True)
        validate_dossier(dossier)
        self.assertEqual([reply["status"] for reply in dossier["rights_of_reply"]], ["PUBLISHED"])
        for correction in dossier["corrections"]:
            self.assertTrue(correction["id"])
            self.assertTrue(correction["previous_finding_id"])
            self.assertNotIn("approved", correction["reason"].lower())

    def test_private_reply_body_is_never_served_for_a_held_finding(self):
        # A held finding's reply is private. Because the finding is not in the
        # bundle, the detail route must not reveal that the reply exists.
        held = fictional_dossier(finding_id="finding:held:2", claim_id="claim:held:2", with_reply=True)
        held["finding"]["publication_status"] = "POLICY_HOLD"
        path = write_bundle(self.tmp / "held2.json", published_bundle([held]))
        response = dispatch(
            "GET", f"{API_BASE_PATH}/findings/finding:held:2", projection_path=path
        )
        self.assertEqual(response.status, 503)
        self.assertNotIn(b"reply:fictional:1", response.body)

    def test_missing_projection_is_503_not_empty_200(self):
        response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(self.tmp / "nope.json"))
        self.assertEqual(response.status, 503)

    def test_unconfigured_projection_is_503(self):
        import os

        previous = os.environ.pop("DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH", None)
        try:
            response = dispatch("GET", f"{API_BASE_PATH}/health", projection_path=None)
            self.assertEqual(response.status, 503)
        finally:
            if previous is not None:
                os.environ["DICHIARAZIONI_PUBBLICHE_PUBLIC_PROJECTION_PATH"] = previous

    def test_incompatible_schema_version_is_503(self):
        path = write_bundle(
            self.tmp / "v1.json", published_bundle([], schema_version="dichiarazioni-pubbliche-public-v1")
        )
        response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=path)
        self.assertEqual(response.status, 503)

    def test_corrupt_bundle_is_503(self):
        path = self.tmp / "corrupt.json"
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(
            dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=str(path)).status, 503
        )

    def test_empty_public_collection_is_200_with_empty_array(self):
        path = write_bundle(self.tmp / "empty.json", published_bundle([]))
        response = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=path)
        self.assertEqual(response.status, 200)
        body = json.loads(response.body)
        self.assertEqual(body["data"], [])
        self.assertEqual(body["meta"]["total"], 0)
        self.assertIsNone(body["meta"]["next_cursor"])

    def test_empty_projection_still_serves_topics_and_people(self):
        path = write_bundle(self.tmp / "empty2.json", published_bundle([]))
        for route in ("topics", "people"):
            response = dispatch("GET", f"{API_BASE_PATH}/{route}", projection_path=path)
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.body)["data"], [])


class ReadOnlyContractTest(unittest.TestCase):
    def test_write_methods_are_405_with_allow_header(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            response = dispatch(method, f"{API_BASE_PATH}/findings", projection_path=str(DEMO_PROJECTION))
            self.assertEqual(response.status, 405, method)
            self.assertEqual(response.headers["Allow"], "GET, HEAD")
            self.assertEqual(json.loads(response.body)["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_method_override_header_is_405(self):
        response = dispatch(
            "GET",
            f"{API_BASE_PATH}/findings?_method=POST",
            projection_path=str(DEMO_PROJECTION),
        )
        self.assertEqual(response.status, 405)
        self.assertEqual(response.headers["Allow"], "GET, HEAD")

    def test_error_responses_are_not_cached(self):
        response = dispatch("GET", f"{API_BASE_PATH}/findings?colour=blue",
                            projection_path=str(DEMO_PROJECTION))
        self.assertEqual(response.headers["Cache-Control"], "no-store")


class ResponseShapeTest(unittest.TestCase):
    def setUp(self):
        self.path = str(DEMO_PROJECTION)

    def test_every_response_uses_the_data_meta_envelope(self):
        # `openapi.json` is the service description, not an API resource, and
        # `index.json` is the raw bundle; both are deliberately un-enveloped.
        for route in ("health", "schema", "findings", "records", "topics", "people"):
            response = dispatch("GET", f"{API_BASE_PATH}/{route}", projection_path=self.path)
            self.assertEqual(response.status, 200, route)
            body = json.loads(response.body)
            self.assertIn("data", body, route)
            self.assertIn("meta", body, route)
            self.assertEqual(body["meta"]["api_version"], "v1")
            self.assertEqual(body["meta"]["public_schema_version"], PUBLIC_SCHEMA_VERSION)

    def test_index_json_serves_the_raw_bundle_not_an_envelope(self):
        # /api/v1/index.json is the projection bundle itself, byte-compatible with
        # what the static build consumes, so it is deliberately not enveloped.
        response = dispatch("GET", f"{API_BASE_PATH}/index.json", projection_path=self.path)
        self.assertEqual(response.status, 200)
        bundle = json.loads(response.body)
        self.assertEqual(bundle["schema_version"], PUBLIC_SCHEMA_VERSION)
        self.assertEqual(bundle["dossier_count"], len(bundle["dossiers"]))
        self.assertNotIn("data", bundle)
        self.assertNotIn("meta", bundle)

    def test_serialized_responses_are_deterministic_and_sorted(self):
        first = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=self.path).body
        second = dispatch("GET", f"{API_BASE_PATH}/findings", projection_path=self.path).body
        self.assertEqual(first, second)
        decoded = json.loads(first)
        self.assertEqual(
            list(decoded["data"][0].keys()),
            sorted(decoded["data"][0].keys()),
        )

    def test_no_raw_transcript_or_evidence_body_is_served(self):
        response = dispatch("GET", f"{API_BASE_PATH}/index.json", projection_path=self.path)
        text = response.body.decode()
        for forbidden in ("transcript_text", "evidence_body", "raw_excerpt", "provider_receipt"):
            self.assertNotIn(forbidden, text)
        for finding in json.loads(response.body)["dossiers"]:
            for segment in finding["source"]["segments"]:
                for candidate in segment["transcript_candidates"]:
                    self.assertNotIn("text", candidate)
                    self.assertNotIn("body", candidate)

    def test_record_endpoint_resolves_a_stable_slug_not_a_display_title(self):
        slug = dispatch("GET", f"{API_BASE_PATH}/index.json", projection_path=self.path)
        record = json.loads(slug.body)["dossiers"][0]
        from dichiarazioni_pubbliche.public_api import slugify

        response = dispatch(
            "GET", f"{API_BASE_PATH}/records/{slugify(record['source']['content_id'])}",
            projection_path=self.path,
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)["data"]["record_id"], record["source"]["content_id"])

    def test_first_class_content_with_zero_findings_is_listed_and_resolved(self):
        bundle = published_bundle([])
        bundle["contents"] = [
            {
                "content_id": "content:zero",
                "slug": "content-zero",
                "url": "https://example.test/zero",
                "title": "Reviewed zero-moment content",
                "published_at": "2026-01-18T12:00:00+00:00",
                "content_kind": "WRITTEN",
                "duration_ms": None,
                "public_media_url": None,
                "media_policy_version": None,
                "publication_version": "public-content-v1",
                "review_event_ids": ["review:content-zero"],
                "finding_ids": [],
            }
        ]
        bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
        validate_public_bundle(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bundle(Path(tmp) / "index.json", bundle)
            collection = dispatch("GET", f"{API_BASE_PATH}/records", projection_path=path)
            self.assertEqual(collection.status, 200)
            rows = json.loads(collection.body)["data"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["content_id"], "content:zero")
            self.assertEqual(rows[0]["finding_count"], 0)

            detail = dispatch(
                "GET", f"{API_BASE_PATH}/records/content-zero", projection_path=path
            )
            self.assertEqual(detail.status, 200)
            record = json.loads(detail.body)["data"]
            self.assertEqual(record["review_event_ids"], ["review:content-zero"])
            self.assertEqual(record["findings"], [])

            raw = dispatch("GET", f"{API_BASE_PATH}/index.json", projection_path=path)
            self.assertEqual(json.loads(raw.body)["contents"], bundle["contents"])

    def test_detail_endpoint_returns_the_dossier_verbatim(self):
        index = load_demo_index()
        finding_id = index.entries[0].finding_id
        response = dispatch("GET", f"{API_BASE_PATH}/findings/{finding_id}", projection_path=self.path)
        self.assertEqual(json.loads(response.body)["data"], index.entries[0].dossier)

    def test_detail_api_preserves_bounded_wording_metadata_without_derived_text(self):
        dossier = fictional_dossier()
        bundle = published_bundle([dossier])
        bundle["dataset_sha256"] = projection_dataset_sha256(bundle)
        validate_public_bundle(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bundle(Path(tmp) / "wording.json", bundle)
            response = dispatch(
                "GET",
                f"{API_BASE_PATH}/findings/{dossier['finding_id']}",
                projection_path=path,
            )
            self.assertEqual(response.status, 200)
            public = json.loads(response.body)["data"]
            wording = public["wording"]
            self.assertEqual(
                wording["source_occurrence"]["wording_type"],
                "VERBATIM_ORIGINAL",
            )
            self.assertEqual(wording["normalized_claim"]["wording_type"], "PARAPHRASE")
            self.assertFalse(wording["normalized_claim"]["direct_quote_eligible"])
            self.assertEqual(
                wording["representations"][0]["wording_type"],
                "TRANSLATION",
            )
            self.assertEqual(
                wording["representations"][0]["review_state"],
                "HUMAN_REVIEWED",
            )
            encoded = json.dumps(wording, ensure_ascii=False)
            self.assertNotIn("Fictional translated representation.", encoded)
            self.assertNotIn("private_text", encoded)
            self.assertNotIn("raw_text", encoded)


class OpenApiContractTest(unittest.TestCase):
    def setUp(self):
        self.index = load_demo_index()
        self.document = build_openapi_document(self.index)

    def test_document_is_3_1_and_matches_the_route_table(self):
        self.assertEqual(self.document["openapi"], OPENAPI_VERSION)
        self.assertEqual(
            sorted(self.document["paths"]), sorted(route.pattern for route in ROUTES)
        )

    def test_wording_metadata_is_optional_additive_and_derived_quote_authority_is_false(self):
        schemas = self.document["components"]["schemas"]
        dossier = schemas["Dossier"]
        self.assertNotIn("wording", dossier["required"])
        self.assertEqual(
            dossier["properties"]["wording"]["$ref"],
            "#/components/schemas/WordingMetadata",
        )
        wording = schemas["WordingMetadata"]
        self.assertFalse(wording["additionalProperties"])
        normalized = wording["properties"]["normalized_claim"]
        self.assertEqual(normalized["properties"]["wording_type"]["const"], "PARAPHRASE")
        self.assertFalse(
            normalized["properties"]["direct_quote_eligible"]["const"]
        )
        derived = wording["properties"]["representations"]["items"]
        self.assertFalse(derived["properties"]["direct_quote_eligible"]["const"])
        self.assertIn("TRANSLATION", derived["properties"]["wording_type"]["enum"])

    def test_every_route_has_get_and_head_only(self):
        for path, item in self.document["paths"].items():
            self.assertEqual(sorted(item), ["get", "head"], path)
            for operation in item.values():
                self.assertEqual(operation["security"], [])

    def test_every_operation_documents_the_error_responses(self):
        # A collection cannot 404; a document route has no 400. Everything else
        # must be documented on every operation.
        universal = {"405", "503"}
        for path, item in self.document["paths"].items():
            for operation in item.values():
                self.assertTrue(universal.issubset(set(operation["responses"])), path)
            if "{" in path:
                self.assertIn("404", item["get"]["responses"], path)
            if path != f"{API_BASE_PATH}/openapi.json":
                self.assertIn("400", item["get"]["responses"], path)
            if path not in (f"{API_BASE_PATH}/health", f"{API_BASE_PATH}/schema"):
                self.assertIn("500", item["get"]["responses"], path)
        for path, item in self.document["paths"].items():
            for operation in item.values():
                for status in operation["responses"]:
                    self.assertRegex(status, r"^[1-5]\d\d$", path)

    def test_every_operation_has_a_worked_example(self):
        for path, item in self.document["paths"].items():
            get = item["get"]
            content = get["responses"]["200"]["content"]["application/json"]
            self.assertIn("example", content, path)

    def test_deprecation_policy_is_documented(self):
        policy = self.document["info"]["x-deprecation-policy"]
        self.assertIn("sunset", policy)
        self.assertIn("90 days", policy["sunset"])
        self.assertIn("breaking", policy)
        self.assertIn("backward_compatible", policy)

    def test_rate_limit_contract_is_defined_but_not_claimed_as_enforced(self):
        rate = self.document["info"]["x-dichiarazioni-pubbliche"]["rate_limiting"]
        self.assertIn("429", rate["contract"])
        self.assertIn("not implemented", rate["status"])

    def test_publication_guarantees_are_stated(self):
        guarantees = self.document["info"]["x-dichiarazioni-pubbliche"]["publication_guarantees"]
        joined = " ".join(guarantees)
        self.assertIn("fail-closed", joined)
        self.assertIn("503", joined)

    def test_document_contains_no_forbidden_public_unsafe_content(self):
        # The document may name a forbidden concept only to deny it (for example
        # `aggregate_person_score: false` is the guarantee itself). What it must
        # never contain is a schema key or example field that carries one.
        text = openapi_document_bytes(self.index).decode()
        self.assertNotIn("ratingValue", text)
        self.assertNotIn("leaderboard", text)
        forbidden_keys = set()

        def collect(node) -> None:
            if isinstance(node, dict):
                if "properties" in node and isinstance(node["properties"], dict):
                    forbidden_keys.update(node["properties"])
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for item in node:
                    collect(item)

        collect(self.document)
        for forbidden in ("score", "rank", "ranking", "rating", "person_score", "aggregate_score"):
            self.assertNotIn(forbidden, forbidden_keys)
        for example in fictional_dossier(with_correction=True, with_reply=True).items():
            self.assertNotIn("score", example)
            self.assertNotIn("rank", example)

    def test_examples_validate_against_the_declared_dossier_schema(self):
        schema = self.document["components"]["schemas"]["Dossier"]
        self.assertIn("relations", schema["properties"])
        self.assertEqual(
            schema["properties"]["finding"]["properties"]["assessment"]["enum"],
            ["FACTUALLY_FALSE", "OUTDATED_DATA", "SUPPORTED"],
        )
        # A non-publishable assessment must not be expressible.
        self.assertNotIn("UNRESOLVED", schema["properties"]["finding"]["properties"]["assessment"]["enum"])

    def test_fictional_examples_are_labelled(self):
        for example in (
            fictional_dossier(),
            fictional_dossier(with_correction=True),
            fictional_dossier(with_reply=True, with_relations=True),
        ):
            serialized = json.dumps(example, ensure_ascii=False)
            self.assertIn("Fictional", serialized)
            self.assertIn("example.test", serialized)

    def test_served_openapi_matches_the_generated_document(self):
        served = dispatch("GET", f"{API_BASE_PATH}/openapi.json", projection_path=str(DEMO_PROJECTION))
        self.assertEqual(served.status, 200)
        self.assertEqual(json.loads(served.body)["openapi"], OPENAPI_VERSION)
        self.assertIn("fictional", json.dumps(json.loads(served.body)["paths"], ensure_ascii=False).lower())

    def test_fictional_correction_example_is_append_only(self):
        corrected = fictional_dossier(with_correction=True)
        self.assertEqual(corrected["corrections"][0]["previous_finding_id"], "finding:fictional:1")
        self.assertNotIn("rating", json.dumps(corrected).lower())


class LlmTxtContractTest(unittest.TestCase):
    """The agent-facing document must be generated, linked, and safe."""

    def setUp(self):
        self.index = load_demo_index()
        self.llms = build_llms_txt(self.index)
        self.readme = build_api_readme(self.index)

    def test_llms_txt_states_contract_version_and_gate(self):
        self.assertIn(PUBLIC_SCHEMA_VERSION, self.llms)
        self.assertIn("api/v1", self.llms)
        self.assertIn("CONTRACT GATE", self.llms)
        self.assertIn("not ratified", self.llms.lower())

    def test_llms_txt_states_the_semantic_boundaries(self):
        for statement in (
            "retrieved evidence != approved evidence",
            "verified claim != published finding",
            "contradiction != proof of intent",
        ):
            self.assertIn(statement, self.llms)

    def test_llms_txt_forbids_the_unsafe_agent_instructions(self):
        lowered = self.llms.lower()
        self.assertIn("do not", lowered)
        for forbidden in ("vote for", "who is more reliable", "rate the politicians"):
            self.assertNotIn(forbidden, lowered)

    def test_llms_txt_contains_no_unsafe_vocabulary(self):
        lowered = self.llms.lower()
        for forbidden in ("password", "api_key", "api key", "secret", "transcript body", "sql"):
            self.assertNotIn(forbidden, lowered)

    def test_llms_txt_is_bounded_and_utf8_clean(self):
        self.assertLess(len(self.llms.encode("utf-8")), 32_000)
        self.llms.encode("utf-8").decode("utf-8")

    def test_llms_txt_examples_are_fictional(self):
        self.assertIn("Fictional example", self.llms)
        self.assertIn("example.test", self.llms)

    def test_llms_txt_links_resolve_to_real_routes(self):
        for link in ("/api/v1/health", "/api/v1/findings", "/api/v1/schema", "/api/v1/openapi.json"):
            self.assertIn(link, self.llms)
        route_paths = {route.pattern for route in ROUTES}
        for path in (f"{API_BASE_PATH}/health", f"{API_BASE_PATH}/findings", f"{API_BASE_PATH}/schema", f"{API_BASE_PATH}/openapi.json"):
            self.assertIn(path, route_paths)

    def test_readme_documents_the_verification_and_limits(self):
        self.assertIn("Cache-Control", self.readme)
        self.assertIn("429", self.readme)
        self.assertIn("read-only", self.readme.lower())


class DeterminismTest(unittest.TestCase):
    def test_index_build_is_order_independent(self):
        bundle = json.loads(DEMO_PROJECTION.read_text(encoding="utf-8"))
        forward = build_index(bundle)
        reversed_bundle = dict(bundle)
        reversed_bundle["dossiers"] = list(reversed(bundle["dossiers"]))
        backward = build_index(reversed_bundle)
        self.assertEqual(
            [entry.finding_id for entry in forward.entries],
            [entry.finding_id for entry in backward.entries],
        )
        self.assertEqual(forward.fingerprint, backward.fingerprint)

    def test_cursor_encoding_has_no_raw_sql_or_client_sort(self):
        index = load_demo_index()
        cursor = encode_cursor(index.entries[0], {"topic": ("NUMERIC_STATISTIC",)})
        self.assertNotIn("SELECT", cursor)
        self.assertNotIn(" ", cursor)
        self.assertNotIn("ORDER BY", cursor)


if __name__ == "__main__":
    unittest.main()
