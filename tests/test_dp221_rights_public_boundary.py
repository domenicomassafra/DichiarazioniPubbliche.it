import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "poc"))

from dichiarazioni_pubbliche.linked_data import projection_ntriples  # noqa: E402
from dichiarazioni_pubbliche.policy.excerpt_policy import (  # noqa: E402
    ExcerptRequest,
    RightsStatus,
    decide_excerpt,
    render_attributed_excerpt,
)
from dichiarazioni_pubbliche.public_api import API_BASE_PATH, dispatch  # noqa: E402
from dichiarazioni_pubbliche.public_projection import (  # noqa: E402
    build_public_projection,
    projection_jsonld,
    write_public_bundle,
)
from dichiarazioni_pubbliche.wording_contract import (  # noqa: E402
    WordingType,
    make_derived_wording,
    make_summary_wording,
    make_translation_wording,
)
from tests.test_public_projection import (  # noqa: E402
    FakeSource,
    reset_row_wording,
    valid_row,
)


PRIVATE_BODIES = {
    "SOURCE_OCCURRENCE": "PRIVATE_SOURCE_OCCURRENCE_BODY_SENTINEL",
    "PARAPHRASE": "PRIVATE_PARAPHRASE_BODY_SENTINEL",
    "SUMMARY": "PRIVATE_SUMMARY_BODY_SENTINEL",
    "TRANSLATION": "PRIVATE_TRANSLATION_BODY_SENTINEL",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_body_row() -> dict:
    body = PRIVATE_BODIES["SOURCE_OCCURRENCE"]
    row = valid_row()
    row["normalized_claim"] = body
    reset_row_wording(row, source_text_sha256=_sha256(body))
    return row


def _derived_body_row(kind: str) -> dict:
    body = PRIVATE_BODIES[kind]
    row = valid_row()
    row["normalized_claim"] = body
    occurrence_id = f"statement:{row['claim_id']}"
    if kind == "PARAPHRASE":
        representation = make_derived_wording(
            wording_type=WordingType.PARAPHRASE,
            occurrence_id=occurrence_id,
            text=body,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_method="EDITORIAL_PARAPHRASE",
            derivation_version="dp221-rights-boundary-v1",
        )
    elif kind == "SUMMARY":
        representation = make_summary_wording(
            occurrence_id=occurrence_id,
            summary=body,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            language="it",
            derivation_version="dp221-rights-boundary-v1",
        )
    elif kind == "TRANSLATION":
        representation = make_translation_wording(
            occurrence_id=occurrence_id,
            source_text="Distinct private source wording.",
            translated_text=body,
            source_wording_type=WordingType.VERBATIM_ORIGINAL,
            source_language="en",
            target_language="it",
            method="HUMAN",
            derivation_version="dp221-rights-boundary-v1",
            human_reviewed=True,
        )
    else:  # pragma: no cover - helper is called only with the closed vocabulary above.
        raise AssertionError(kind)
    reset_row_wording(row, representations=(representation,))
    return row


class Dp221RightsPublicBoundaryTests(unittest.TestCase):
    def test_dp305_blocks_private_bodies_for_source_and_every_derived_wording_kind(self):
        blocked_states = (
            RightsStatus.UNKNOWN,
            RightsStatus.UNRESOLVED,
            RightsStatus.BLOCKED,
            RightsStatus.LEGAL_HOLD,
            RightsStatus.RIGHTS_HOLD,
            RightsStatus.TAKEDOWN_HOLD,
            RightsStatus.REVOKED,
        )
        for kind, body in PRIVATE_BODIES.items():
            for rights_status in blocked_states:
                with self.subTest(kind=kind, rights_status=rights_status.value):
                    request = ExcerptRequest(
                        excerpt_text=body,
                        rights_status=rights_status,
                    )
                    decision = decide_excerpt(request)
                    self.assertFalse(decision.allowed)
                    with self.assertRaisesRegex(ValueError, "EXCERPT_NOT_ALLOWED"):
                        render_attributed_excerpt(request, decision)

    def test_private_source_and_derived_bodies_are_omitted_before_every_public_serializer(self):
        rows = {
            "SOURCE_OCCURRENCE": _source_body_row(),
            "PARAPHRASE": _derived_body_row("PARAPHRASE"),
            "SUMMARY": _derived_body_row("SUMMARY"),
            "TRANSLATION": _derived_body_row("TRANSLATION"),
        }

        for kind, row in rows.items():
            with self.subTest(kind=kind):
                payload = build_public_projection(FakeSource([row]))
                self.assertEqual(payload["dossier_count"], 0)
                self.assertEqual(payload["omitted_count"], 1)

                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                jsonld = json.dumps(
                    projection_jsonld(payload),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                rdf = projection_ntriples(payload)
                for sentinel in PRIVATE_BODIES.values():
                    self.assertNotIn(sentinel, serialized)
                    self.assertNotIn(sentinel, jsonld)
                    self.assertNotIn(sentinel, rdf)

                with tempfile.TemporaryDirectory() as tmp:
                    output_dir = Path(tmp) / "public"
                    write_public_bundle(output_dir, payload)
                    claim_files = list((output_dir / "claims").glob("*")) if (output_dir / "claims").exists() else []
                    self.assertEqual(claim_files, [])
                    for path in (
                        output_dir / "index.json",
                        output_dir / "index.jsonld",
                        output_dir / "index.nt",
                        output_dir / "linked-data-receipt.json",
                    ):
                        public_bytes = path.read_text(encoding="utf-8")
                        for sentinel in PRIVATE_BODIES.values():
                            self.assertNotIn(sentinel, public_bytes)

                    api_index = dispatch(
                        "GET",
                        f"{API_BASE_PATH}/index.json",
                        projection_path=output_dir / "index.json",
                    )
                    api_findings = dispatch(
                        "GET",
                        f"{API_BASE_PATH}/findings",
                        projection_path=output_dir / "index.json",
                    )
                    self.assertEqual(api_index.status, 200)
                    self.assertEqual(api_findings.status, 200)
                    self.assertEqual(json.loads(api_findings.body)["data"], [])
                    for sentinel in PRIVATE_BODIES.values():
                        self.assertNotIn(sentinel.encode("utf-8"), api_index.body)
                        self.assertNotIn(sentinel.encode("utf-8"), api_findings.body)


if __name__ == "__main__":
    unittest.main()
