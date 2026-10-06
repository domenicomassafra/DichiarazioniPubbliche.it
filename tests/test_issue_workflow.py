import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.check_issue_workflow import (  # noqa: E402
    MockIssue,
    self_test,
    validate_manifest,
    validate_mock_issue,
    validate_policy,
    validate_state_transition,
    validate_templates,
)


class IssueWorkflowTests(unittest.TestCase):
    def test_repository_contract_is_green(self):
        self.assertEqual(validate_manifest(), [])
        self.assertEqual(validate_policy(), [])
        self.assertEqual(validate_templates(), [])
        self.assertEqual(self_test(), [])

    def test_public_security_label_and_report_fail_closed(self):
        problems = validate_mock_issue(
            MockIssue(
                title="DP-606: security details",
                ticket_id="DP-606",
                body="Sanitized placeholder only.",
                labels=("security-private",),
                security_report=True,
            )
        )
        self.assertIn("SECURITY_REPORT_MUST_USE_PRIVATE_PATH", problems)
        self.assertIn("ISSUE_LABEL_NOT_PUBLIC:security-private", problems)

    def test_state_machine_is_closed_and_reversible_only_where_declared(self):
        self.assertEqual(validate_state_transition("needs-triage", "ready"), ())
        self.assertEqual(validate_state_transition("in-progress", "blocked"), ())
        self.assertIn("STATE_TRANSITION_FORBIDDEN", validate_state_transition("closed", "ready"))
        self.assertIn("STATE_SOURCE_UNKNOWN", validate_state_transition("invented", "ready"))

    def test_issue_requires_exact_existing_ticket_and_matching_title(self):
        bad = validate_mock_issue(
            MockIssue("DP-606: item", "DP-605", "safe", ("maintenance", "needs-triage"))
        )
        self.assertIn("ISSUE_TITLE_TICKET_MISMATCH", bad)
        missing = validate_mock_issue(
            MockIssue("DP-999: item", "DP-999", "safe", ("maintenance", "needs-triage"))
        )
        self.assertIn("ISSUE_TICKET_LINK_INVALID", missing)


if __name__ == "__main__":
    unittest.main()
