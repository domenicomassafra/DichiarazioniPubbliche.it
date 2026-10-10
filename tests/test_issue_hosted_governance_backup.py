import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import issue_hosted_governance_backup as gov  # noqa: E402


class GovernanceBackupTests(unittest.TestCase):
    def test_unprotected_empty_rules_and_unreadable_projects_are_not_full_proof(self):
        calls = []

        def reader(args, *, allow_404=False):
            calls.append((args, allow_404))
            if args == [f"repos/{gov.REMOTE}"]:
                return {"full_name": gov.REMOTE, "default_branch": "main", "visibility": "public"}
            if args[0].endswith("/rulesets?per_page=100"):
                return []
            if args[0].endswith("/branches/main/protection"):
                return None
            if args[0] == "graphql":
                raise RuntimeError("DP606_PROJECT_SCOPE_MISSING")
            raise AssertionError(args)

        with patch.object(gov, "_gh_json", side_effect=reader):
            result = gov.capture_governance()
        self.assertFalse(result["governance_export_complete"])
        self.assertEqual(result["projects"]["status"], "UNVERIFIED_MISSING_READ_PROJECT_SCOPE")
        self.assertEqual(result["protection"]["status"], "ABSENT")
        self.assertEqual(result["rulesets"], [])
        self.assertFalse(result["hosted_mutation_performed"])
        self.assertEqual(len(calls), 4)

    def test_protected_rule_snapshot_and_zero_projects_is_complete_read_only(self):
        def reader(args, *, allow_404=False):
            endpoint = args[0]
            if endpoint == f"repos/{gov.REMOTE}":
                return {"full_name": gov.REMOTE, "default_branch": "main", "visibility": "public"}
            if endpoint.endswith("/rulesets?per_page=100"):
                return [{"id": 42}]
            if endpoint.endswith("/rulesets/42"):
                return {"id": 42, "name": "main-guard", "rules": [{"type": "pull_request"}]}
            if endpoint.endswith("/branches/main/protection"):
                return {"required_status_checks": {"strict": True}}
            if endpoint == "graphql":
                return {"data": {"repository": {"projectsV2": {"totalCount": 0}}}}
            raise AssertionError(args)

        with patch.object(gov, "_gh_json", side_effect=reader):
            result = gov.capture_governance()
        self.assertTrue(result["governance_export_complete"])
        self.assertEqual(result["protection"]["status"], "PRESENT")
        self.assertEqual(result["rulesets"][0]["rules"][0]["type"], "pull_request")
        self.assertTrue(result["owner_review_required"])
        self.assertFalse(result["rollback_executed"])

    def test_project_network_failure_must_not_be_called_missing_scope(self):
        def reader(args, *, allow_404=False):
            if args == [f"repos/{gov.REMOTE}"]:
                return {"full_name": gov.REMOTE, "default_branch": "main", "visibility": "public"}
            if args[0].endswith("/rulesets?per_page=100"):
                return []
            if args[0].endswith("/branches/main/protection"):
                return None
            if args[0] == "graphql":
                raise RuntimeError("DP606_HOSTED_READ_FAILED")
            raise AssertionError(args)

        with patch.object(gov, "_gh_json", side_effect=reader):
            state = gov.capture_governance()
        self.assertEqual(state["projects"]["status"], "UNVERIFIED_PROJECT_READ_FAILED")
        self.assertFalse(state["governance_export_complete"])

    def test_tampered_identity_or_unbounded_ruleset_list_refused(self):
        with patch.object(gov, "_gh_json", return_value={"full_name": "wrong", "default_branch": "main", "visibility": "public"}):
            with self.assertRaisesRegex(ValueError, "IDENTITY"):
                gov.capture_governance()
        with patch.object(gov, "_gh_json", side_effect=[
            {"full_name": gov.REMOTE, "default_branch": "main", "visibility": "public"},
            [{"id": index} for index in range(100)],
        ]):
            with self.assertRaisesRegex(ValueError, "UNBOUNDED"):
                gov.capture_governance()

    def test_private_exclusive_snapshot_persists_exact_payload(self):
        payload = {"remote": gov.REMOTE, "secret": "private-rule-metadata"}
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "hosted.json"
            digest = gov.write_private_snapshot(target, payload)
            import hashlib
            self.assertEqual(digest, hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(json.loads(target.read_text()), payload)
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                gov.write_private_snapshot(target, payload)

    def test_hosted_governance_snapshot_cannot_be_written_inside_public_repo(self):
        target = ROOT / "docs" / "ops" / "private-hosted-governance-should-not-exist.json"
        with self.assertRaisesRegex(ValueError, "PRIVATE_SNAPSHOT_OUTSIDE_REPO_REQUIRED"):
            gov.write_private_snapshot(target, {"private_rule": "not for Git"})
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
