"""Timed captions constrain evidence to the selected intervention."""

import unittest

from tools.dp468_radio_radicale_vtt_crosscheck import (
    _caption_cues,
    _caption_urls,
    _longest_consecutive,
    _segment_window,
    _tokens,
)


URL = "https://www.radioradicale.it/scheda/760686/seduta-310a-xix-legislatura"
CAPTION = "https://www.radioradicale.it/trascrizioni/1/3/1/1/2/1311288.vtt"


class RadioRadicaleCaptionTests(unittest.TestCase):
    def page(self):
        return (
            '"vtt":["https:\\/\\/www.radioradicale.it\\/trascrizioni\\/'
            '1\\/3\\/1\\/1\\/2\\/1311288.vtt"]'
            '"int4913034":{"file":0,"offset":440}'
            '<li class="views-row intervento int4913034">'
            '<span class="duration">0:13:56</span>'
            f'<a href="{URL}#i=4913034">Manfredi Potenti</a></li>'
        )

    def test_window_does_not_count_words_from_another_speaker(self):
        page = self.page()
        self.assertEqual(_caption_urls(page), [CAPTION])
        file_index, start, duration = _segment_window(page, URL + "#i=4913034")
        self.assertEqual((file_index, start, duration), (0, 440, 836))
        cues = _caption_cues(
            b"WEBVTT\n\n1\n00:01:00.000 --> 00:01:08.000\n"
            b"the only exact phrase\n\n"
            b"2\n00:07:21.000 --> 00:07:25.000\n"
            b"the speaker discusses another issue\n"
        )
        selected = " ".join(
            words for first, last, words in cues
            if last >= start - 3 and first <= start + duration + 3
        )
        self.assertEqual(
            _longest_consecutive(_tokens("the only exact phrase"), _tokens(selected)), 0
        )
        self.assertEqual(
            _longest_consecutive(_tokens("the speaker discusses another issue"), _tokens(selected)), 5
        )

    def test_bad_media_metadata_or_cue_order_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "SEGMENT_MISSING"):
            _segment_window(
                self.page().replace('"offset":440', '"offset":null'), URL + "#i=4913034",
            )
        with self.assertRaisesRegex(ValueError, "CUE_INVALID"):
            _caption_cues(b"WEBVTT\n\n1\n00:00:05.000 --> 00:00:02.000\ninvalid\n")
        with self.assertRaisesRegex(ValueError, "(PLAYLIST|URL)_INVALID"):
            _caption_urls(self.page().replace("1311288.vtt", "1311288.vtt\\\",\\\"https:\\/\\/www.radioradicale.it\\/trascrizioni\\/1\\/3\\/1\\/1\\/2\\/1311288.vtt", 1))

    def test_partial_word_alignment_is_not_an_exact_quote_match(self):
        quote = _tokens("Una citazione esatta contiene tutte queste parole precise")
        captions = _tokens("Una citazione esatta contiene tuttavia parole diverse")
        self.assertEqual(_longest_consecutive(quote, captions), 4)
        self.assertNotEqual(_longest_consecutive(quote, captions), len(quote))


if __name__ == "__main__":
    unittest.main()
