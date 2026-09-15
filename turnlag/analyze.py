"""Turn segmentation and perceived-latency measurement.

The number this module produces is the gap between the caller's last word and
the agent's next first word. That is what a human on the phone actually feels,
and it is the sum of four things your application logs usually cannot see
together: endpointing delay, model time, TTS time-to-first-audio, and network.

Everything here works off a recording, so it is vendor-neutral and needs no
instrumentation in the agent itself.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from .parse import Word

# Words that are almost always listener noise rather than a real turn. A caller
# saying "mhm" while the agent is mid-sentence is not taking the floor, and
# counting it as a turn boundary invents a sub-100ms "response" that never
# happened. This single rule is the difference between a plausible number and a
# correct one.
BACKCHANNELS = frozenset(
    """
    mhm mm mmm hmm uh-huh uhhuh huh yeah yep yup ok okay right sure gotcha
    aha ah oh uh um er wow nice cool good great alright
    """.split()
)

# A gap longer than this is the caller thinking, being put on hold, or a
# diarization error — not the agent being slow. Counting it would let one
# pause poison the whole distribution.
DEFAULT_MAX_GAP = 20.0


def _normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalpha() or ch == "-")


def is_backchannel(words: list[Word]) -> bool:
    """True if a run of words is pure listener noise."""
    if not words or len(words) > 3:
        return False
    tokens = [_normalize(w.text) for w in words]
    return all(token in BACKCHANNELS for token in tokens if token)


@dataclass
class Turn:
    speaker: str
    words: list[Word] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class Gap:
    """One measured agent response."""

    seconds: float
    caller_turn: Turn
    agent_turn: Turn

    @property
    def barge_in(self) -> bool:
        """The agent started speaking before the caller finished."""
        return self.seconds < 0


def segment(words: list[Word], drop_backchannels: bool = True) -> list[Turn]:
    """Group consecutive words by speaker into turns.

    With drop_backchannels on, a short interjection that sits inside another
    speaker's run is folded away so the surrounding run stays a single turn.
    """
    runs: list[Turn] = []
    for word in words:
        if runs and runs[-1].speaker == word.speaker:
            runs[-1].words.append(word)
        else:
            runs.append(Turn(speaker=word.speaker, words=[word]))

    if not drop_backchannels:
        return runs

    kept: list[Turn] = []
    for index, run in enumerate(runs):
        interrupts_same_speaker = (
            0 < index < len(runs) - 1
            and runs[index - 1].speaker == runs[index + 1].speaker
            and runs[index - 1].speaker != run.speaker
        )
        if interrupts_same_speaker and is_backchannel(run.words):
            continue
        if kept and kept[-1].speaker == run.speaker:
            kept[-1].words.extend(run.words)
        else:
            kept.append(Turn(speaker=run.speaker, words=list(run.words)))
    return kept


def infer_agent(turns: list[Turn]) -> str | None:
    """The agent answers the phone, so it speaks first.

    True for inbound calls, which is the common case. Override it with --agent
    for outbound, where the human says "hello" first.
    """
    return turns[0].speaker if turns else None


def measure(
    turns: list[Turn],
    agent: str,
    max_gap: float = DEFAULT_MAX_GAP,
    include_barge_in: bool = False,
) -> list[Gap]:
    """Every caller turn followed by an agent turn yields one measurement."""
    gaps: list[Gap] = []
    for index, turn in enumerate(turns):
        if index == 0 or turn.speaker != agent:
            continue
        previous = turns[index - 1]
        if previous.speaker == agent:
            continue
        seconds = turn.start - previous.end
        if seconds < 0 and not include_barge_in:
            continue
        if seconds > max_gap:
            continue
        gaps.append(Gap(seconds=seconds, caller_turn=previous, agent_turn=turn))
    return gaps


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile.

    Deliberately not interpolated: with the 8-to-20 turns a real call produces,
    an interpolated p95 reports a latency that no caller ever experienced.
    Nearest-rank always returns a number that actually happened.
    """
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(round(p / 100.0 * len(ordered) + 0.5))))
    return ordered[rank - 1]


@dataclass
class Stats:
    n: int
    minimum: float
    median: float
    mean: float
    p90: float
    p95: float
    maximum: float
    barge_ins: int = 0

    @classmethod
    def of(cls, gaps: list[Gap]) -> "Stats | None":
        values = [g.seconds for g in gaps]
        if not values:
            return None
        return cls(
            n=len(values),
            minimum=min(values),
            median=statistics.median(values),
            mean=statistics.fmean(values),
            p90=percentile(values, 90),
            p95=percentile(values, 95),
            maximum=max(values),
            barge_ins=sum(1 for g in gaps if g.barge_in),
        )
