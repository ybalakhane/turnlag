"""Behavioral tests. Each asserts against real output, not source text."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from turnlag.analyze import (  # noqa: E402
    Stats,
    infer_agent,
    is_backchannel,
    measure,
    percentile,
    segment,
)
from turnlag.parse import UnknownFormat, Word, parse  # noqa: E402


def w(start, end, text, speaker):
    return Word(start=start, end=end, text=text, speaker=speaker)


class TestSegmentation(unittest.TestCase):
    def test_consecutive_words_from_one_speaker_form_one_turn(self):
        turns = segment([w(0, 1, "hi", "a"), w(1, 2, "there", "a")])
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].text, "hi there")

    def test_backchannel_inside_a_run_does_not_split_the_turn(self):
        # The caller says "mhm" while the agent talks. Naive segmentation reads
        # the agent's next word as a 0.05s "response" and reports a fake win.
        words = [
            w(0.0, 2.0, "checking", "agent"),
            w(2.1, 2.3, "mhm", "caller"),
            w(2.35, 4.0, "the schedule", "agent"),
        ]
        turns = segment(words)
        self.assertEqual(len(turns), 1, "backchannel must not split the agent turn")
        gaps = measure(turns, "agent")
        self.assertEqual(gaps, [], "a folded backchannel must produce no measurement")

    def test_keeping_backchannels_restores_the_split(self):
        words = [
            w(0.0, 2.0, "checking", "agent"),
            w(2.1, 2.3, "mhm", "caller"),
            w(2.35, 4.0, "the schedule", "agent"),
        ]
        self.assertEqual(len(segment(words, drop_backchannels=False)), 3)

    def test_real_words_are_never_treated_as_backchannel(self):
        self.assertFalse(is_backchannel([w(0, 1, "cancel", "caller")]))
        self.assertTrue(is_backchannel([w(0, 1, "mhm", "caller")]))
        self.assertFalse(
            is_backchannel([w(0, 1, x, "caller") for x in "yeah ok but no wait".split()]),
            "a long utterance is a real turn even if it opens with a filler",
        )


class TestMeasurement(unittest.TestCase):
    def setUp(self):
        self.words = [
            w(0.0, 1.0, "hello", "agent"),
            w(2.0, 3.0, "book me", "caller"),
            w(4.5, 5.0, "sure", "agent"),
        ]

    def test_gap_is_caller_end_to_agent_start(self):
        gaps = measure(segment(self.words), "agent")
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0].seconds, 1.5)

    def test_agent_is_inferred_as_whoever_speaks_first(self):
        self.assertEqual(infer_agent(segment(self.words)), "agent")

    def test_barge_in_excluded_by_default_and_flagged_when_included(self):
        words = [
            w(0.0, 1.0, "hello", "agent"),
            w(2.0, 4.0, "i wanted to ask", "caller"),
            w(3.5, 4.2, "of course", "agent"),
        ]
        turns = segment(words)
        self.assertEqual(measure(turns, "agent"), [])
        gaps = measure(turns, "agent", include_barge_in=True)
        self.assertEqual(len(gaps), 1)
        self.assertTrue(gaps[0].barge_in)
        self.assertLess(gaps[0].seconds, 0)

    def test_long_pause_is_excluded_so_one_hold_cannot_poison_the_median(self):
        words = [
            w(0.0, 1.0, "hello", "agent"),
            w(2.0, 3.0, "hold on", "caller"),
            w(90.0, 91.0, "still here", "agent"),
        ]
        self.assertEqual(measure(segment(words), "agent"), [])

    def test_agent_to_agent_sequence_yields_no_measurement(self):
        words = [w(0, 1, "one", "agent"), w(5, 6, "two", "caller")]
        self.assertEqual(measure(segment(words), "agent"), [])


class TestPercentile(unittest.TestCase):
    def test_nearest_rank_returns_an_observed_value(self):
        values = [1.0, 2.0, 3.0, 4.0]
        for p in (50, 90, 95, 100):
            self.assertIn(percentile(values, p), values)

    def test_p95_of_a_short_call_is_the_worst_turn(self):
        self.assertEqual(percentile([1.0, 2.0, 9.0], 95), 9.0)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            percentile([], 50)


class TestStats(unittest.TestCase):
    def test_stats_of_no_gaps_is_none(self):
        self.assertIsNone(Stats.of([]))

    def test_counts_barge_ins(self):
        words = [
            w(0.0, 1.0, "hello", "agent"),
            w(2.0, 4.0, "i wanted", "caller"),
            w(3.5, 4.2, "yes", "agent"),
            w(5.0, 6.0, "a cleaning please", "caller"),
            w(7.0, 8.0, "booked", "agent"),
        ]
        gaps = measure(segment(words), "agent", include_barge_in=True)
        stats = Stats.of(gaps)
        self.assertEqual(stats.n, 2)
        self.assertEqual(stats.barge_ins, 1)


class TestParsers(unittest.TestCase):
    def test_flat_list(self):
        payload = [{"start": 0, "end": 1, "text": "hi", "speaker_id": "speaker_0"}]
        self.assertEqual(parse(payload)[0].text, "hi")

    def test_deepgram_uses_channel_when_diarization_is_off(self):
        payload = {
            "results": {
                "channels": [
                    {"alternatives": [{"words": [{"start": 0, "end": 1, "word": "hi"}]}]},
                    {"alternatives": [{"words": [{"start": 2, "end": 3, "word": "yes"}]}]},
                ]
            }
        }
        words = parse(payload)
        self.assertEqual(len(words), 2)
        self.assertNotEqual(words[0].speaker, words[1].speaker)

    def test_assemblyai_milliseconds_become_seconds(self):
        payload = {"words": [{"start": 1500, "end": 2000, "text": "hi", "speaker": "A"}]}
        word = parse(payload)[0]
        self.assertAlmostEqual(word.start, 1.5)
        self.assertAlmostEqual(word.end, 2.0)

    def test_whisperx_segment_speaker_falls_through_to_words(self):
        payload = {
            "segments": [
                {"speaker": "SPEAKER_01", "words": [{"start": 0, "end": 1, "word": "hi"}]}
            ]
        }
        self.assertEqual(parse(payload)[0].speaker, "SPEAKER_01")

    def test_words_without_a_speaker_are_dropped(self):
        payload = [
            {"start": 0, "end": 1, "text": "hi", "speaker_id": "a"},
            {"start": 1, "end": 2, "text": "unattributed"},
        ]
        self.assertEqual(len(parse(payload)), 1)

    def test_unknown_payload_raises_rather_than_reporting_an_empty_call(self):
        with self.assertRaises(UnknownFormat):
            parse({"something": "else"})

    def test_end_before_start_is_clamped(self):
        self.assertEqual(parse([{"start": 5, "end": 4, "text": "x", "speaker": "a"}])[0].end, 5)


class TestCLI(unittest.TestCase):
    def run_cli(self, payload, *args):
        path = Path(self.tmp) / "call.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "turnlag", str(path), *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    def setUp(self):
        import tempfile

        self._dir = tempfile.TemporaryDirectory()
        self.tmp = self._dir.name
        self.slow = [
            {"start": 0.0, "end": 1.0, "text": "hello", "speaker_id": "a"},
            {"start": 2.0, "end": 3.0, "text": "book me", "speaker_id": "b"},
            {"start": 6.0, "end": 7.0, "text": "sure", "speaker_id": "a"},
        ]

    def tearDown(self):
        self._dir.cleanup()

    def test_exits_nonzero_when_threshold_exceeded(self):
        result = self.run_cli(self.slow, "--max-p50", "1.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stderr)

    def test_exits_zero_when_within_threshold(self):
        result = self.run_cli(self.slow, "--max-p50", "5.0")
        self.assertEqual(result.returncode, 0)

    def test_json_output_carries_the_measurement(self):
        result = self.run_cli(self.slow, "--json")
        body = json.loads(result.stdout)
        self.assertAlmostEqual(body["calls"][0]["p50"], 3.0)
        self.assertEqual(body["calls"][0]["verdict"], "bad")

    def test_unknown_speaker_is_an_error_not_a_silent_empty_result(self):
        result = self.run_cli(self.slow, "--agent", "nobody")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no speaker", result.stderr)

    def test_missing_file_reports_usage_error(self):
        result = subprocess.run(
            [sys.executable, "-m", "turnlag", "/nonexistent.json"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
