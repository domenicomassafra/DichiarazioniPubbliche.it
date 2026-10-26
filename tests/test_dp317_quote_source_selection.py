"""DP-317: a licence-cleared public statement must be attributed to its speaker."""

import unittest

from tools.dp317_licence_quote_pilot import pick_quote


class QuoteSelectionTests(unittest.TestCase):
    def test_navigation_copy_cannot_become_a_persons_statement(self):
        source = b"""
        <p>Our priorities Our priorities Learn how the EU is building a
        sustainable, digital, and inclusive future through its seven key priorities.</p>
        <figure class="ecl-blockquote"><blockquote class="ecl-blockquote__quote">
          <p class="ecl-blockquote__citation">Our Union can choose to act together on a
          shared future, with a strong and independent voice in the world.</p>
          <footer><span class="ecl-blockquote__author">President von der Leyen</span></footer>
        </blockquote></figure>
        """
        quote, start, end = pick_quote(source)
        self.assertEqual(
            quote,
            "Our Union can choose to act together on a shared future, with a strong and independent voice in the world.",
        )
        self.assertEqual((start, end), (0, len(quote)))

    def test_unattributed_or_other_persons_quote_is_not_accepted(self):
        source = b"""
        <blockquote class="ecl-blockquote__quote">
          <p class="ecl-blockquote__citation">A speech by an unrelated public official should
          not be attributed to the President of the Commission.</p>
          <footer><span class="ecl-blockquote__author">Another speaker</span></footer>
        </blockquote>
        """
        with self.assertRaisesRegex(SystemExit, "DP317_PILOT_NO_QUOTE_CANDIDATE"):
            pick_quote(source)


if __name__ == "__main__":
    unittest.main()
