"""DP-413 native gateway readback must authenticate one exact execution."""
import hashlib
import json
import unittest
from copy import deepcopy
from dataclasses import replace

from dichiarazioni_pubbliche.autonomous_publication import AgentReview
from dichiarazioni_pubbliche.autonomous_runner_v3 import _json
from dichiarazioni_pubbliche.omniroute_execution_authority import (
    OmniRouteExecutionAuthority,
)


MODEL = "antigravity/gemini-3.8-flash-tiered"
TAG = "dp413-" + "a" * 32
CALL_ID = "gateway-call-1"
RESPONSE_ID = "upstream-completion-1"
KEY_ID = "key:dp"
CONNECTION_ID = "connection:pro"


def fixture():
    request = {
        "model": MODEL, "messages": [{"role": "user", "content": "perché citazione test"}],
        "temperature": 0, "max_tokens": 512,
    }
    prompt_hash = hashlib.sha256(_json(request).encode()).hexdigest()
    receipt = AgentReview(
        "agent:primary", MODEL, "c" * 64, ("PROVENANCE",), True,
        provider="omniroute", provider_request_id=RESPONSE_ID,
        returned_model="gemini-3.8-flash-tiered", prompt_sha256=prompt_hash,
        usage={"prompt_tokens": 50, "completion_tokens": 10},
        session_tag=TAG,
        stage_citations={"PROVENANCE": ["source-record"]},
    )
    detail = {
        "id": CALL_ID, "status": 200, "active": False,
        "detailState": "ready", "sessionTag": TAG, "error": None,
        "apiKeyId": KEY_ID, "connectionId": CONNECTION_ID,
        "requestedModel": MODEL, "provider": "antigravity",
        "model": "gemini-3.8-flash-tiered", "comboName": None,
        "resilienceActions": None, "hasRequestBody": True,
        "hasResponseBody": True,
        "requestBody": {**request, "_omniroute": {"internal": True}},
        "responseBody": {
            "id": RESPONSE_ID, "model": "gemini-3.8-flash-tiered",
            "usage": {"prompt_tokens": 50, "completion_tokens": 10,
                      "total_tokens": 60},
            "choices": [{"message": {"content": json.dumps({
                "evidence_sha256": "c" * 64,
                "checked_stages": ["PROVENANCE"],
                "stage_citations": {"PROVENANCE": ["source-record"]},
                "accepted": True,
            })}}],
        },
    }
    route = {
        "requestId": CALL_ID, "request": {"id": CALL_ID, "requestedModel": MODEL},
        "routeType": "direct", "comboUsed": False,
        "decisionReplay": {"runtime": {
            "source": "call_logs", "exact": True,
            "selectedCallLogId": CALL_ID, "provider": "antigravity",
            "model": "gemini-3.8-flash-tiered",
            "status": 200, "connectionId": CONNECTION_ID,
        }},
        "selectedTarget": {"provider": "antigravity",
                           "model": "gemini-3.8-flash-tiered",
                           "status": 200, "connectionId": CONNECTION_ID},
        "providerSelected": "antigravity", "modelUsed": "gemini-3.8-flash-tiered",
        "fallbacksTriggered": [],
        "decision": {"providerSelected": "antigravity",
                     "modelUsed": "gemini-3.8-flash-tiered",
                     "status": 200, "fallbacksTriggered": []},
    }
    values = {
        "/api/keys": {"keys": [{
            "id": KEY_ID, "isActive": True, "revokedAt": None,
            "modelAccessMode": "restricted", "allowedModels": [MODEL],
            "allowedConnections": [CONNECTION_ID], "allowedCombos": [],
        }]},
        "/api/usage/call-logs?model=antigravity%2Fgemini-3.8-flash-tiered&limit=100": [
            {"id": CALL_ID, "provider": "antigravity", "status": 200,
             "sessionTag": TAG}
        ],
        "/api/usage/call-logs/" + CALL_ID: detail,
        "/api/usage/route-explain/" + CALL_ID: route,
    }
    return receipt, values


class OmniRouteExecutionAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.receipt, self.values = fixture()
        self.reads = []
        self.verifier = OmniRouteExecutionAuthority(
            management_token="fake-management-token", dp_key_id=KEY_ID,
            allowed_connection_ids=frozenset({CONNECTION_ID}),
            read=self.read,
        )

    def read(self, path):
        self.reads.append(path)
        return self.values[path]

    def test_authenticated_direct_gateway_execution_is_verified(self):
        self.assertTrue(self.verifier(self.receipt))
        self.assertIn("/api/usage/route-explain/" + CALL_ID, self.reads)

    def test_accepted_review_without_provider_stage_citations_is_not_witnessed(self):
        detail = self.values["/api/usage/call-logs/" + CALL_ID]
        verdict = json.loads(detail["responseBody"]["choices"][0]["message"]["content"])
        verdict["stage_citations"] = {}
        detail["responseBody"]["choices"][0]["message"]["content"] = json.dumps(verdict)
        self.assertFalse(self.verifier(self.receipt))

    def test_genuine_provider_rejection_with_empty_citations_is_witnessed(self):
        detail = self.values["/api/usage/call-logs/" + CALL_ID]
        verdict = json.loads(detail["responseBody"]["choices"][0]["message"]["content"])
        verdict["accepted"] = False
        verdict["stage_citations"] = {"PROVENANCE": []}
        detail["responseBody"]["choices"][0]["message"]["content"] = json.dumps(verdict)
        rejected = replace(self.receipt, accepted=False,
                           stage_citations={"PROVENANCE": []})
        self.assertTrue(self.verifier(rejected))

    def test_unrelated_sessions_do_not_trigger_management_detail_reads(self):
        endpoint = "/api/usage/call-logs?model=antigravity%2Fgemini-3.8-flash-tiered&limit=100"
        unrelated = [{"id": f"unrelated-{n}", "provider": "antigravity",
                      "status": 200, "sessionTag": "another-session"}
                     for n in range(75)]
        self.values[endpoint] = unrelated + self.values[endpoint]
        self.assertTrue(self.verifier(self.receipt))
        self.assertEqual(
            [path for path in self.reads if path.startswith("/api/usage/call-logs/")],
            ["/api/usage/call-logs/" + CALL_ID],
        )

    def test_failed_gateway_attempt_in_same_session_blocks_review_witness(self):
        endpoint = "/api/usage/call-logs?model=antigravity%2Fgemini-3.8-flash-tiered&limit=100"
        original = list(self.values[endpoint])
        failed = {"id": "failed-attempt", "provider": "antigravity",
                  "status": 502, "sessionTag": TAG}
        for rows in ([failed] + original, original + [failed]):
            with self.subTest(first_failed=rows[0] is failed):
                self.values[endpoint] = rows
                self.assertFalse(self.verifier(self.receipt))

    def test_matching_summary_must_match_detail_id_and_session(self):
        endpoint = "/api/usage/call-logs?model=antigravity%2Fgemini-3.8-flash-tiered&limit=100"
        self.values[endpoint] = [{"id": "other-call", "provider": "antigravity",
                                  "status": 200, "sessionTag": TAG}]
        original = self.values["/api/usage/call-logs/" + CALL_ID]
        for mismatch in ({"id": CALL_ID}, {"id": "other-call", "sessionTag": "different"}):
            with self.subTest(mismatch=mismatch):
                self.values["/api/usage/call-logs/other-call"] = {**original, **mismatch}
                self.assertFalse(self.verifier(self.receipt))

    def test_conflicting_requested_and_review_model_ids_are_rejected(self):
        self.assertFalse(self.verifier({**vars(self.receipt),
                                        "requested_model": MODEL,
                                        "model_id": "antigravity/another-model"}))

    def test_forged_journal_receipt_cannot_reuse_another_gateway_call(self):
        altered = {**vars(self.receipt), "session_tag": "dp413-" + "b" * 32}
        self.assertFalse(self.verifier(altered))
        altered = {**vars(self.receipt), "stage_citations": {
            "PROVENANCE": ["fabricated"],
        }}
        self.assertFalse(self.verifier(altered))
        self.values["/api/usage/call-logs/" + CALL_ID]["responseBody"]["choices"][0][
            "message"]["content"] = json.dumps({
                "evidence_sha256": "f" * 64,
                "checked_stages": ["PROVENANCE"],
                "stage_citations": {"PROVENANCE": ["source-record"]},
                "accepted": True,
            })
        self.assertFalse(self.verifier(self.receipt))
        altered = {**vars(self.receipt), "provider_request_id": "invented"}
        self.assertFalse(self.verifier(altered))
        altered = {**vars(self.receipt), "prompt_sha256": "d" * 64}
        self.assertFalse(self.verifier(altered))
        altered = {**vars(self.receipt), "usage": {
            "prompt_tokens": 999, "completion_tokens": 10,
        }}
        self.assertFalse(self.verifier(altered))

    def test_revoked_key_connection_or_route_cannot_witness(self):
        key = self.values["/api/keys"]["keys"][0]
        detail = self.values["/api/usage/call-logs/" + CALL_ID]
        route = self.values["/api/usage/route-explain/" + CALL_ID]
        for field, value in (
            ("allowedConnections", []), ("allowedModels", []),
            ("modelAccessMode", "all"), ("revokedAt", "2026-11-11T00:00:00Z"),
            ("isActive", False), ("expiresAt", "2026-11-10T00:00:00Z"),
        ):
            with self.subTest(field=field):
                modified = deepcopy(key)
                modified[field] = value
                self.values["/api/keys"] = {"keys": [modified]}
                self.assertFalse(self.verifier(self.receipt))
        self.values["/api/keys"] = {"keys": [key]}
        detail["connectionId"] = "connection:paid"
        self.assertFalse(self.verifier(self.receipt))
        detail["connectionId"] = CONNECTION_ID
        route["routeType"] = "combo"
        self.assertFalse(self.verifier(self.receipt))
        route["routeType"] = "direct"
        route["decisionReplay"]["runtime"]["exact"] = False
        self.assertFalse(self.verifier(self.receipt))

    def test_unattributed_fallback_holds_but_unrelated_session_is_ignored(self):
        route = self.values["/api/usage/route-explain/" + CALL_ID]
        route["fallbacksTriggered"] = [{"id": "nearby-call"}]
        path = "/api/usage/call-logs/nearby-call"
        self.assertFalse(self.verifier(self.receipt))
        self.values[path] = {"id": "nearby-call", "sessionTag": TAG}
        self.assertFalse(self.verifier(self.receipt))
        self.values[path] = {"id": "nearby-call", "sessionTag": "other-session"}
        self.assertTrue(self.verifier(self.receipt))

    def test_missing_management_evidence_fails_closed(self):
        self.values.pop("/api/usage/route-explain/" + CALL_ID)
        self.assertFalse(self.verifier(self.receipt))
        self.assertFalse(self.verifier({**vars(self.receipt), "session_tag": None}))


if __name__ == "__main__":
    unittest.main()
