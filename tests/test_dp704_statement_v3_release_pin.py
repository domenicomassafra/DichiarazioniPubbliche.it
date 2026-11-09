"""#704 review: the fence and the response must observe one pinned v3 release."""

import json
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))
sys.path.insert(0, str(ROOT / "tests"))

from dichiarazioni_pubbliche import statement_correction_intake as intake_module  # noqa: E402
from dichiarazioni_pubbliche import public_v3_http as release_module  # noqa: E402
from dichiarazioni_pubbliche.live_correction_http import build_live_correction_server  # noqa: E402
from dichiarazioni_pubbliche.public_statement_authority import PublicStatementChallengeStore  # noqa: E402
from dp468_authority_support import MemoryPostgres  # noqa: E402
from tests.test_dp437_public_opinion_api import ReviewedSyntheticOpinions  # noqa: E402
from tests.test_dp466_live_correction import FakeLedger, LiveCorrectionHttpTests  # noqa: E402


def rotate(projection: Path, authority: Path, bundle) -> None:
    """Publish one release: the snapshot content carries its own fingerprint.

    A reader that crosses this window sees either the old release or a
    snapshot whose own fingerprint is not yet the pointer's: both must fail
    closed, never serve one as the other.
    """
    projection.write_text(json.dumps(bundle), encoding="utf-8")
    authority.write_text(bundle["dataset_sha256"] + "\n", encoding="ascii")


def hold_release(projection: Path, authority: Path, bundle) -> None:
    """Withdraw the release before the challenged snapshot can be served."""
    authority.write_text(bundle["dataset_sha256"] + "\n", encoding="ascii")


class _RotatingPurge:
    """Serve exactly one request from a release that predates the challenge."""

    def __init__(self, projection: Path, authority: Path, corrected):
        self.projection = projection
        self.authority = authority
        self.corrected = corrected
        self.points = 0

    def __call__(self, target):
        # The withdrawal that acknowledges a correction must not republish the
        # contended version: the pointer keeps naming the exact release the
        # correction just read.
        rotate(self.projection, self.authority, self.corrected)
        self.points += 1
        return True


class StatementV3ReleasePinTests(unittest.TestCase):
    """Check exactly what the public response served, not a second snapshot."""

    setUp = LiveCorrectionHttpTests.setUp
    tearDown = LiveCorrectionHttpTests.tearDown
    request = LiveCorrectionHttpTests.request
    auth_headers = LiveCorrectionHttpTests.auth_headers

    def fixtures(self):
        root = Path(self.temp.name)
        source = ReviewedSyntheticOpinions()
        source.subjects[0].row["version_id"] = "statement-version:1-corrected"
        for proof in source.subjects[0].gates.values():
            proof["version_id"] = "statement-version:1-corrected"
        corrected = source.build()
        source.subjects[0].row["version_id"] = "statement-version:1"
        for proof in source.subjects[0].gates.values():
            proof["version_id"] = "statement-version:1"
        held = source.build()
        candidate = root / "pin-v3.json"
        current = root / "pin-v3-sha256"
        candidate.write_text(json.dumps(corrected), encoding="utf-8")
        current.write_text(corrected["dataset_sha256"] + "\n", encoding="ascii")
        return root, candidate, current, corrected, held

    def serve(self, root, candidate, current, store, purge):
        service = self.server.RequestHandlerClass.account_service
        server = build_live_correction_server(
            str(root / "projection.json"), host="127.0.0.1", port=0,
            static_dir=str(root / "static"), account_service=service,
            correction_ledger=FakeLedger(), correction_enqueue=lambda *_: True,
            correction_purge=purge, correction_reserve=lambda *_: True,
            statement_projection_path=candidate,
            statement_current_fingerprint_path=current,
            statement_challenge_store=store,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        # The live server must fence with the very store this test inspects.
        self.assertIs(server.RequestHandlerClass.statement_correction_intake.store, store)
        return server

    def test_the_challenged_version_is_never_served_after_the_fence(self):
        root, candidate, current, corrected, held = self.fixtures()
        store = PublicStatementChallengeStore(store=MemoryPostgres())
        rotation = _RotatingPurge(candidate, current, corrected)
        server = self.serve(root, candidate, current, store, rotation)
        original_port = self.port
        self.port = server.server_port
        self.addCleanup(setattr, self, "port", original_port)

        # The correction reads the corrected release, challenges its version
        # and then withdraws it, so the pointer now serves exactly the version
        # that is under an open hold.
        self.assertEqual(self.request("GET", "/api/v3/statements")[0], 200)
        status, _, receipt = self.request(
            "POST", "/intake/corrections",
            {"statement_id": "statement:1", "version_id": "statement-version:1-corrected",
             "reason": "La citazione non corrisponde alla fonte"},
            self.auth_headers(),
        )
        self.assertEqual(status, 202)
        self.assertEqual(receipt["state"], "HOLD")
        self.assertEqual(rotation.points, 1)
        self.assertTrue(store.current_hold("statement:1", "statement-version:1-corrected"))

        # The withdrawn release serves the challenged version: no public
        # surface may return it, and the fence must not re-read the pointer.
        self.assertEqual(self.request("GET", "/api/v3/statements")[0], 503)
        self.assertEqual(self.request("GET", "/api/v3/statements/statement:1")[0], 503)
        self.assertEqual(self.request("GET", "/api/v3/opinions")[0], 503)
        self.assertEqual(self.request("GET", "/")[0], 503)

    def test_a_pinned_release_with_a_terminal_clearance_is_served_unchanged(self):
        root, candidate, current, corrected, held = self.fixtures()
        store = PublicStatementChallengeStore(store=MemoryPostgres())
        server = self.serve(root, candidate, current, store, lambda *_: True)
        original_port = self.port
        self.port = server.server_port
        self.addCleanup(setattr, self, "port", original_port)

        status, _, receipt = self.request(
            "POST", "/intake/corrections",
            {"statement_id": "statement:1", "version_id": "statement-version:1-corrected",
             "reason": "La citazione non corrisponde alla fonte"},
            self.auth_headers(),
        )
        self.assertEqual(status, 202)
        self.assertEqual(self.request("GET", "/")[0], 503)
        store.append_event(
            request_id=receipt["request_id"], status="REJECTED",
            reason_code="NO_CHANGE_REQUIRED", actor_ref="reviewer:one",
            occurred_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        # A cleared version is served only by a release published after the
        # challenge: repin the same content with a later release timestamp.
        republished = dict(corrected, generated_at=(
            datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
        ).isoformat())
        rotate(candidate, current, republished)
        status, _, listing = self.request("GET", "/api/v3/statements")
        self.assertEqual(status, 200)
        self.assertEqual(
            [row["version_id"] for row in listing["data"]
             if row["statement_id"] == "statement:1"],
            ["statement-version:1-corrected"],
        )

    def test_a_rotated_release_after_the_fence_is_refused_not_served(self):
        root, candidate, current, corrected, held = self.fixtures()
        store = PublicStatementChallengeStore(store=MemoryPostgres())
        server = self.serve(root, candidate, current, store, lambda *_: True)
        original_port = self.port
        self.port = server.server_port
        self.addCleanup(setattr, self, "port", original_port)

        # Read the release, then move the pointer before it can be served.
        rotates = {"points": 0}
        read = release_module.pinned_release

        def read_then_rotate(*args, **kwargs):
            pinned = read(*args, **kwargs)
            rotates["points"] += 1
            rotate(candidate, current, held)
            return pinned

        intake_module.pinned_release = read_then_rotate
        self.addCleanup(setattr, intake_module, "pinned_release", read)
        status, _, body = self.request("GET", "/api/v3/statements")
        self.assertEqual(rotates["points"], 1)
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "PUBLIC_PROJECTION_UNAVAILABLE")

    def test_html_rechecks_v3_release_after_initial_clearance(self):
        root, candidate, current, corrected, held = self.fixtures()
        store = PublicStatementChallengeStore(store=MemoryPostgres())
        store.open_request(
            statement_id="statement:1", version_id="statement-version:1",
            intake_ref="intake:html-rotation", requester_ref_sha256="a" * 64,
            reason_sha256="b" * 64,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            actor_ref="oidc:html-test",
        )
        server = self.serve(root, candidate, current, store, lambda *_: True)
        old_port = self.port
        self.port = server.server_port
        self.addCleanup(setattr, self, "port", old_port)
        original = intake_module.StatementCorrectionIntake.published_release_pin
        observed = {"first": False}

        def rotate_after_check(intake):
            pinned = original(intake)
            if pinned is not None and not observed["first"]:
                observed["first"] = True
                rotate(candidate, current, held)
            return pinned

        intake_module.StatementCorrectionIntake.published_release_pin = rotate_after_check
        self.addCleanup(setattr, intake_module.StatementCorrectionIntake,
                        "published_release_pin", original)
        self.assertEqual(self.request("GET", "/")[0], 503)
        self.assertTrue(observed["first"])
        rotate(candidate, current, corrected)
        observed["first"] = False
        self.assertEqual(self.request("GET", "/api/v1/health")[0], 503)
        rotate(candidate, current, corrected)
        observed["first"] = False
        self.assertEqual(self.request("HEAD", "/")[0], 503)

    def test_v3_route_errors_keep_status_and_head_has_no_body(self):
        root, candidate, current, corrected, held = self.fixtures()
        store = PublicStatementChallengeStore(store=MemoryPostgres())
        server = self.serve(root, candidate, current, store, lambda *_: True)
        old_port = self.port
        self.port = server.server_port
        self.addCleanup(setattr, self, "port", old_port)
        self.assertEqual(self.request("GET", "/api/v3/statements/statement:absent")[0], 404)
        self.assertEqual(self.request("GET", "/api/v3/statements?unknown=1")[0], 400)
        import http.client
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        connection.request("HEAD", "/api/v3/statements?unknown=1")
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        self.assertEqual(response.read(), b"")


if __name__ == "__main__":
    unittest.main()
