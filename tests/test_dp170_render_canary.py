"""#170: private canary for one authorized selective JavaScript rendition."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT))

from dichiarazioni_pubbliche.source_watcher import FetchedBytes  # noqa: E402
from tools.dp170_render_canary import (  # noqa: E402
    CanaryRefused, SCHEMA, render_canary,
)

URL = "https://demo.example.test/todomvc/"
STATIC = b'<html><body><ul id="todo-list"></ul><script src="/app.js"></script></body></html>'
RENDERED = b'<html><body><ul id="todo-list"><li>one</li></ul><script src="/app.js"></script></body></html>'


def decision(**overrides):
    payload = {
        "id": "dp170-canary-test", "status": "APPROVED",
        "reviewer_ref": "ai-review:test", "approved_at": "2026-10-23T11:00:00Z",
        "hosts": ["demo.example.test"],
        "scopes": ["FETCH", "STORE_BODY", "PARSE_TEXT"],
    }
    payload.update(overrides)
    return payload


def response(body, url=URL):
    return FetchedBytes(body=body, final_url=url, status_code=200,
                        media_type="text/html", charset="utf-8",
                        content_length=len(body))


class FakeRenderer:
    def __init__(self, body=RENDERED, final_url=URL):
        self.body = body
        self.final_url = final_url
        self.sandbox_executable = ROOT / "poc/dichiarazioni_pubbliche/browser_renderer_netns.sh"
        self.last_receipt = {
            "renderer_id": "playwright-python",
            "playwright_version": "1.64.0",
            "egress_policy": "bwrap-unshare-net-pinned-https-v1",
        }
        self.guarded = 0

    def render(self, url, *, max_response_bytes, authorization_guard=None):
        if authorization_guard is not None:
            authorization_guard()
            self.guarded += 1
        return response(self.body, self.final_url)


class CanaryTests(unittest.TestCase):
    def run_canary(self, *, decision_payload=None, static=STATIC, rendered=RENDERED,
                   final_url=URL, url=URL):
        renderer = FakeRenderer(rendered, final_url)
        receipt = render_canary(
            url=url, decision=decision_payload or decision(),
            chromium_binary="/usr/bin/chromium",
            fetcher=lambda target, **kwargs: response(static),
            renderer_factory=lambda **kwargs: renderer,
        )
        return receipt, renderer

    def test_static_first_then_one_rendition_with_hashes_and_no_content(self):
        receipt, renderer = self.run_canary()
        self.assertEqual(receipt["schema"], SCHEMA)
        self.assertEqual(receipt["decision"], "RENDERED")
        self.assertEqual(receipt["static"]["bytes"], len(STATIC))
        self.assertEqual(receipt["rendered"]["bytes"], len(RENDERED))
        self.assertEqual(receipt["rendered"]["added_bytes"], len(RENDERED) - len(STATIC))
        self.assertEqual(receipt["publication"], "HOLD")
        self.assertFalse(receipt["rights"]["published"])
        self.assertEqual(receipt["side_effects"]["downloads"], 0)
        self.assertEqual(receipt["sandbox"]["chromium_binary"], "chromium")
        self.assertEqual(renderer.guarded, 1)
        serialized = json.dumps(receipt)
        # No page text and no local path leaks into the receipt.
        self.assertNotIn("todo-list", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_fragment_only_client_route_is_one_representation(self):
        receipt, _ = self.run_canary(final_url=URL + "#/active")
        self.assertTrue(receipt["rendered"]["fragment_only_url_change"])

    def test_other_url_change_or_no_js_delta_refuses(self):
        with self.assertRaisesRegex(CanaryRefused, "CANARY_FINAL_URL_CHANGED"):
            self.run_canary(final_url="https://demo.example.test/other/")
        with self.assertRaisesRegex(CanaryRefused, "CANARY_NO_JS_DELTA"):
            self.run_canary(rendered=STATIC)

    def test_rights_decision_is_mandatory_and_metadata_scoped(self):
        for payload in (
            decision(status="PENDING"), decision(scopes=["FETCH"]),
            decision(scopes=["FETCH", "STORE_BODY", "PARSE_TEXT", "PUBLISH"]),
            decision(hosts=["other.example.test"]), decision(hosts=[]),
            decision(reviewer_ref=""), decision(id=""),
        ):
            with self.subTest(payload=payload), self.assertRaises(CanaryRefused):
                self.run_canary(decision_payload=payload)
        with self.assertRaisesRegex(CanaryRefused, "CANARY_URL_INSECURE"):
            self.run_canary(url="http://demo.example.test/todomvc/")

    def test_redirected_static_fetch_is_refused(self):
        with self.assertRaisesRegex(CanaryRefused, "CANARY_REDIRECT_UNAUTHORIZED"):
            render_canary(
                url=URL, decision=decision(), chromium_binary="/usr/bin/chromium",
                fetcher=lambda target, **kwargs: response(STATIC, URL + "?x=1"),
                renderer_factory=lambda **kwargs: FakeRenderer(),
            )


if __name__ == "__main__":
    unittest.main()
