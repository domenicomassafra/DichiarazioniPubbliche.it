"""DP-418 private browser review: source-bound quote comparison, no mutation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest

from dichiarazioni_pubbliche.studio_candidate_review_ui import (
    build_candidate_comparison_read_model,
    render_candidate_comparison_workspace,
)
from tests.test_dp418_comparison_next import persisted_comparison


class PrivateQuoteReviewTests(unittest.TestCase):
    def setUp(self):
        match, promotion, sources = persisted_comparison(duplicate=True)
        sources.snapshots[("ATOMIC_CLAIM", "claim:same")].update(
            capture_id="capture:1", capture_sha256="c" * 64
        )
        model = build_candidate_comparison_read_model(
            match, promotion, sources,
            run_id=match.run_id, claim_candidate_id="candidate:1",
        )
        self.html = render_candidate_comparison_workspace(model).decode("utf-8")

    def test_operator_sees_two_ephemeral_quote_fields_and_source_passages(self):
        self.assertIn("Citazione A", self.html)
        self.assertIn("Citazione B", self.html)
        self.assertIn("passage:1", self.html)
        self.assertIn("passage:related", self.html)
        self.assertIn("data-private-quote-review", self.html)
        self.assertIn("data-same-source='true'", self.html)
        self.assertIn("nessuna decisione", self.html.lower())
        self.assertNotIn("SECRET NEVER IN COMPARE", self.html)
        self.assertNotIn("Il primo evento fu", self.html)

    @unittest.skipUnless(shutil.which("node"), "Node.js needed for private browser JS")
    def test_live_quote_proposals_keep_distinct_and_ambiguous_cases_separate(self):
        scripts = re.findall(r"<script>(.*?)</script>", self.html, re.DOTALL)
        self.assertEqual(len(scripts), 1)
        program = """
const vm = require('node:vm');
const fs = require('node:fs');
const context = {document:{querySelectorAll:()=>[]}, window:{addEventListener:()=>{}}};
vm.runInNewContext(fs.readFileSync(0,'utf8'), context);
const assess = context.assessQuoteComparison;
const text1='Il progetto inizierà a maggio.';
const text2='Il progetto non inizierà a maggio.';
const results = [
  assess(text1, text1, true, 'DUPLICATE_EXTRACTION', true),
  assess(text1, text2, true, 'DUPLICATE_EXTRACTION', true),
  assess(text1, text2, false, 'RELATED', true),
  assess(text1, text1, true, 'UNCERTAIN', true),
  assess(text1, text1, true, 'DUPLICATE_EXTRACTION', false),
  assess(text1, text1, false, 'SAME_PROPOSITION', true),
];
process.stdout.write(JSON.stringify(results));
"""
        run = subprocess.run(
            ["node", "-e", program], input=scripts[0], text=True,
            capture_output=True, timeout=5, check=True,
        )
        results = json.loads(run.stdout)
        self.assertEqual([r["code"] for r in results], [
            "POSSIBILE_DUPLICATO_PASSAGGIO",
            "DICHIARAZIONI_DISTINTE",
            "DICHIARAZIONI_DISTINTE",
            "CONFRONTO_AMBIGUO",
            "FONTE_BLOCCATA",
            "TESTO_RIPETUTO_FONTI_DIVERSE",
        ])
        self.assertTrue(all(r["approval"] is False for r in results))



if __name__ == "__main__":
    unittest.main()
