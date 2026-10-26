from __future__ import annotations

import unittest
from copy import deepcopy

from dichiarazioni_pubbliche.ops.release_currentness_pg_v1 import (
    DisposableReleaseCurrentnessPg,
)

INDEX = "a" * 64
PROJECTION = "b" * 64
GENERATION = "c" * 64


class FixtureReadback(DisposableReleaseCurrentnessPg):
    """Fixture-only SQL-result boundary: no DB connection or psql process."""

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def _run(self, sql: str, **variables: str) -> object:
        return deepcopy(self.response)


class PrivateReleaseReadbackResponseTests(unittest.TestCase):
    def response(self) -> dict[str, object]:
        return {
            "status": "COHERENT_PRIVATE_REFERENCE",
            "reason": "PRIVATE_ONLY_NOT_DEPLOYED",
            "pointer_release": "release:current",
            "pointer_revision": 3,
            "index_hash": INDEX,
            "projection_hash": PROJECTION,
            "generation_hash": GENERATION,
            "source_stamp": "[]",
            "revocation_events": 0,
            "pending_invalidations": 0,
            "acknowledgements": 0,
            "publication_authorized": False,
            "host_ack_verified": False,
            "cdn_ack_verified": False,
        }

    def read(self, response: dict[str, object]):
        return FixtureReadback(response).read_private_reference(
            release_id="release:current", index_sha256=INDEX,
            projection_sha256=PROJECTION, generation_sha256=GENERATION,
            expected_revision=3,
        )

    def test_coherent_result_is_private_only(self):
        receipt = self.read(self.response())
        self.assertEqual(receipt.status, "COHERENT_PRIVATE_REFERENCE")
        self.assertFalse(receipt.publication_authorized)
        self.assertFalse(receipt.host_ack_verified)
        self.assertFalse(receipt.cdn_ack_verified)

    def test_changed_generation_cannot_claim_same_private_release(self):
        response = self.response()
        response["generation_hash"] = "f" * 64
        with self.assertRaisesRegex(RuntimeError, "DP518_RESPONSE_UNSAFE"):
            self.read(response)

    def test_conflicting_current_pointer_or_digest_cannot_claim_coherence(self):
        for field, wrong_value in (
            ("pointer_release", "release:older"),
            ("pointer_revision", 2),
            ("index_hash", "d" * 64),
            ("projection_hash", "e" * 64),
            ("reason", "OUTBOX_PENDING"),
        ):
            with self.subTest(field=field):
                response = self.response()
                response[field] = wrong_value
                with self.assertRaisesRegex(RuntimeError, "DP518_RESPONSE_UNSAFE"):
                    self.read(response)


if __name__ == "__main__":
    unittest.main()
