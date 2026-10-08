"""Regression coverage for subtitle formats actually emitted by edge-tts."""
import pathlib
import tempfile
import unittest

from wortgefuehl_render import ass_time, parse_vtt_time, vtt_to_ass


class SubtitleTests(unittest.TestCase):
    def test_srt_and_webvtt_timestamps(self):
        for value, expected in [
            ("00:01:02,340", 62.34),
            ("00:01:02.340", 62.34),
            ("01:02.340", 62.34),
            ("00:00:02", 2.0),
            ("00:00:02.1", 2.1),
        ]:
            with self.subTest(value=value):
                self.assertAlmostEqual(parse_vtt_time(value), expected)

    def test_invalid_timestamps_fail_clearly(self):
        for value in ["broken", "00:61:00,000", "00:00:61,000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_vtt_time(value)

    def test_ass_rounding_carries_minutes_and_hours(self):
        self.assertEqual(ass_time(59.999), "0:01:00.00")
        self.assertEqual(ass_time(3599.999), "1:00:00.00")

    def test_edge_srt_with_vtt_filename_keeps_commas_and_intro_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "voice.vtt"
            target = pathlib.Path(tmp) / "captions.ass"
            source.write_text(
                "1\n00:00:00,100 --> 00:00:02,500\nDu weißt, was zählt.\n\n"
                "2\n00:00:02.600 --> 00:00:03.500\nVertrauen bleibt.\n",
                encoding="utf-8",
            )
            vtt_to_ass(source, target)
            text = target.read_text(encoding="utf-8")
            self.assertIn("0:00:01.60,0:00:04.00", text)
            self.assertIn("Du weißt, was zählt.", text)
            self.assertEqual(text.count("Dialogue:"), 2)
            self.assertIn("WrapStyle: 0", text)

    def test_empty_subtitles_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "voice.vtt"
            source.write_text("WEBVTT\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                vtt_to_ass(source, pathlib.Path(tmp) / "captions.ass")


if __name__ == "__main__":
    unittest.main()
