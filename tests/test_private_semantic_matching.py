"""DP-157: synthetic, deterministic Italian embedding gold; no weight download."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from tests.test_candidate_matching import item
from dichiarazioni_pubbliche.candidate_matching import (
    matching_input_fingerprint, rank_candidate_matches,
)
from dichiarazioni_pubbliche.private_semantic_matching import (
    MAX_TARGETS, _verified_receipt, _worker, hints_from_vectors, run_private_semantic_matching,
)


def pair(left, right, *, same_entity=True):
    entities = ("person:giulia-rossi",) if same_entity else ("person:giulio-rossi",)
    return (
        item("CLAIM_CANDIDATE", "candidate:it", left, content_id="content:original",
             entities=("person:giulia-rossi",), claim_type="NUMERIC_STATISTIC",
             temporal_scope={"reference_period": "2025"}),
        item("ATOMIC_CLAIM", "claim:it", right, content_id="content:other",
             entities=entities, claim_type="NUMERIC_STATISTIC",
             temporal_scope={"reference_period": "2025"}),
    )


class PrivateSemanticMatchingTests(unittest.TestCase):
    def test_italian_paraphrase_is_private_uncertain_hold_and_replay_untouched(self):
        left, right = pair("Le entrate fiscali sono cresciute nel 2025.",
                           "Nel 2025 è aumentato il gettito delle imposte.")
        fingerprint = matching_input_fingerprint(left, (right,))
        deterministic = rank_candidate_matches(left, (right,))
        hints = hints_from_vectors(left, (right,), ([1.0, 0.0], [0.99, 0.01]))
        self.assertEqual(len(hints), 1)
        self.assertEqual((hints[0].match_class, hints[0].disposition, hints[0].method),
                         ("UNCERTAIN", "HOLD", "MODEL_SUGGESTION"))
        self.assertEqual(deterministic, rank_candidate_matches(left, (right,)))
        self.assertEqual(fingerprint, matching_input_fingerprint(left, (right,)))
        self.assertFalse(any(h.disposition == "PROPOSE_CLUSTER" for h in hints))

    def test_negation_quotation_homonym_period_type_numeric_negative_gold(self):
        originals = pair("La giunta ha approvato il bilancio 2025.",
                         "Il bilancio 2025 è stato approvato dalla giunta.")
        left, right = originals
        variants = [
            ("La giunta non ha approvato il bilancio 2025.", {}, "negazione"),
            ('"La giunta ha approvato il bilancio 2025."', {}, "citazione"),
            (right.proposition.normalized_text, {"same_entity": False}, "omonimia"),
        ]
        for text, options, label in variants:
            changed_left, changed_right = pair(left.proposition.normalized_text, text, **options)
            with self.subTest(label=label):
                self.assertEqual(hints_from_vectors(changed_left, (changed_right,),
                                                    ([1.0, 0.0], [1.0, 0.0])), ())
        for kind, changed in (
            ("periodo", item("ATOMIC_CLAIM", "claim:later", right.proposition.normalized_text,
                             entities=("person:giulia-rossi",), claim_type="NUMERIC_STATISTIC",
                             temporal_scope={"reference_period": "2026"})),
            ("tipo", item("ATOMIC_CLAIM", "claim:opinion", right.proposition.normalized_text,
                          entities=("person:giulia-rossi",), claim_type="OPINION",
                          temporal_scope={"reference_period": "2025"})),
            ("numero", item("ATOMIC_CLAIM", "claim:number", "Il bilancio 2024 fu approvato.",
                            entities=("person:giulia-rossi",), claim_type="NUMERIC_STATISTIC",
                            temporal_scope={"reference_period": "2025"})),
        ):
            with self.subTest(label=kind):
                self.assertEqual(hints_from_vectors(left, (changed,), ([1.0, 0.0], [1.0, 0.0])), ())

    def test_republication_does_not_grant_cluster_and_exact_remains_native(self):
        left, right = pair("Il gettito tributario è aumentato nel 2025.",
                           "Nel 2025 crescono le entrate delle tasse.")
        # Re-publication has the same content but a distinct selector; semantics
        # cannot silently approve equivalence or independence of evidence.
        from dataclasses import replace
        right = replace(right, proposition=replace(right.proposition,
                                                  content_id="content:original",
                                                  provenance_key="passage:copy"))
        hints = hints_from_vectors(left, (right,), ([1.0, 0.0], [0.99, 0.01]))
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0].disposition, "HOLD")
        self.assertEqual(hints[0].match_class, "UNCERTAIN")
        exact_left, exact_right = pair("Il dato resta identico.", "Il dato resta identico.")
        self.assertEqual(hints_from_vectors(exact_left, (exact_right,),
                                            ([1.0, 0.0], [1.0, 0.0])), ())
        self.assertEqual(rank_candidate_matches(exact_left, (exact_right,))[0].disposition,
                         "PROPOSE_CLUSTER")

    def test_ill_formed_vectors_and_input_budgets_fail_closed(self):
        left, right = pair("Il gettito tributario cresce nel 2025.",
                           "Nel 2025 le imposte incassate salgono.")
        for vectors in (([0, 0], [0, 0]), ([float("nan"), 0], [1, 0]),
                        ([1, 0], [1]), ([1, 0], [float("inf"), 0]),
                        ([1e308, 1e308], [1e308, 1e308]),
                        ([10 ** 400, 0], [1, 0]),
                        ([2, 0], [2, 0])):
            with self.subTest(vectors=vectors):
                self.assertEqual(hints_from_vectors(left, (right,), vectors), ())
        self.assertEqual(hints_from_vectors(left, (right,) * (MAX_TARGETS + 1),
                                            ([1, 0],) * (MAX_TARGETS + 2)), ())
        self.assertEqual(hints_from_vectors(left, (right,), ([1, 0],)), ())

    def test_disabled_non_minipc_and_missing_receipt_never_spawn(self):
        left, right = pair("La somma è aumentata nel 2025.",
                           "Nel 2025 crescono i totali.")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(run_private_semantic_matching(left, [right]).state, "DISABLED")
        with patch.dict(os.environ, {"DP_PRIVATE_SEMANTIC_ENABLED": "1"}):
            with patch("dichiarazioni_pubbliche.private_semantic_matching.platform.system",
                       return_value="Darwin"):
                self.assertEqual(run_private_semantic_matching(left, [right]).reason, "MINIPC_ONLY")
            with patch("dichiarazioni_pubbliche.private_semantic_matching.platform.system",
                       return_value="Linux"), patch(
                           "dichiarazioni_pubbliche.private_semantic_matching.platform.node",
                           return_value="udodo"):
                self.assertEqual(run_private_semantic_matching(left, [right]).reason,
                                 "MODEL_RECEIPT_REQUIRED")

    def test_direct_worker_invocation_requires_explicit_opt_in(self):
        payload = '{"texts":["test a","test b"],"manifest":"/missing.json"}'
        with patch.dict(os.environ, {}, clear=True), patch("sys.stdin", io.StringIO(payload)):
            with self.assertRaisesRegex(ValueError, "EXPLICIT_OPT_IN_REQUIRED"):
                _worker()

    def test_private_worker_receives_no_service_secrets(self):
        left, right = pair("Le entrate aumentano nel 2025.",
                           "Nel 2025 cresce il gettito.")
        with patch.dict(os.environ, {"DP_PRIVATE_SEMANTIC_ENABLED": "1",
                                  "PRIVATE_API_TOKEN": "synthetic-secret"}, clear=True), patch(
            "dichiarazioni_pubbliche.private_semantic_matching.platform.system", return_value="Linux"
        ), patch("dichiarazioni_pubbliche.private_semantic_matching.platform.node",
                 return_value="udodo"), patch(
            "dichiarazioni_pubbliche.private_semantic_matching._verified_receipt",
            return_value=({"model_id": "local/test", "revision": "a" * 40}, "b" * 64)
        ), patch("dichiarazioni_pubbliche.private_semantic_matching.importlib.metadata.version",
                 return_value="6.1.0"), patch(
            "dichiarazioni_pubbliche.private_semantic_matching.subprocess.run"
        ) as spawn:
            spawn.return_value.returncode = 0
            spawn.return_value.stdout = "[[1.0,0.0],[1.0,0.0]]"
            result = run_private_semantic_matching(left, (right,), manifest_path="/private/receipt")
            self.assertEqual((result.state, len(result.hints)), ("HOLD", 1))
            child_env = spawn.call_args.kwargs["env"]
            self.assertNotIn("PRIVATE_API_TOKEN", child_env)
            self.assertEqual(child_env["DP_PRIVATE_SEMANTIC_ENABLED"], "1")
            self.assertEqual(child_env["HF_HUB_OFFLINE"], "1")

    def test_model_weights_and_license_are_separately_hash_gated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "local-model"
            model.mkdir()
            (model / "LICENSE").write_text("Reviewed test license only")
            (model / "weights.safetensors").write_bytes(b"synthetic-not-a-real-model")
            files = {name: hashlib.sha256((model / name).read_bytes()).hexdigest()
                     for name in ("LICENSE", "weights.safetensors")}
            receipt = {"model_id": "local/example", "revision": "a" * 40,
                       "license_spdx": "Apache-2.0", "license_source_url": "https://example.org/license",
                       "license_reviewed": True, "model_dir": str(model), "files": files}
            path = root / "model-receipt.json"
            path.write_text(json.dumps(receipt))
            self.assertEqual(_verified_receipt(str(path))[0]["revision"], "a" * 40)
            # A coherent local file inventory cannot override a missing package.
            left, right = pair("La somma cresce nel 2025.", "Nel 2025 il totale aumenta.")
            with patch.dict(os.environ, {"DP_PRIVATE_SEMANTIC_ENABLED": "1"}), patch(
                "dichiarazioni_pubbliche.private_semantic_matching.platform.system", return_value="Linux"
            ), patch("dichiarazioni_pubbliche.private_semantic_matching.platform.node",
                     return_value="udodo"), patch(
                "dichiarazioni_pubbliche.private_semantic_matching.importlib.metadata.version",
                side_effect=PackageNotFoundError("sentence-transformers")
            ):
                missing = run_private_semantic_matching(left, [right], manifest_path=str(path))
                self.assertEqual((missing.state, missing.hints), ("BLOCKED", ()))
            (model / "weights.safetensors").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "MODEL_SHA256_MISMATCH"):
                _verified_receipt(str(path))
            (model / "weights.safetensors").write_bytes(b"synthetic-not-a-real-model")
            receipt["license_reviewed"] = False
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "MODEL_LICENSE_OR_REVISION_BLOCKED"):
                _verified_receipt(str(path))
            receipt["license_reviewed"] = True
            receipt["license_spdx"] = "unknown"
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "MODEL_LICENSE_OR_REVISION_BLOCKED"):
                _verified_receipt(str(path))
            receipt["license_spdx"] = "Apache-2.0"
            path.write_text(json.dumps(receipt))
            (model / "unlisted.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "MODEL_FILE_INVENTORY_MISMATCH"):
                _verified_receipt(str(path))


if __name__ == "__main__":
    unittest.main()
