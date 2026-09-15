"""Readers that turn a vendor's word-timing payload into a flat word list.

Every reader returns a list of Word. Timings are seconds from the start of the
recording. A word without a speaker id is dropped: turn detection is the whole
point here, and a stream we cannot attribute is worse than no data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str
    speaker: str


class UnknownFormat(ValueError):
    """Raised when no reader recognizes the payload."""


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _speaker(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return f"speaker_{int(raw)}"
    text = str(raw).strip()
    return text or None


def _word(start: Any, end: Any, text: Any, speaker: Any) -> Word | None:
    s, e = _num(start), _num(end)
    who = _speaker(speaker)
    if s is None or e is None or who is None:
        return None
    label = str(text or "").strip()
    if not label:
        return None
    # Some vendors emit end < start on the final token of a segment.
    return Word(start=s, end=max(e, s), text=label, speaker=who)


def read_flat(payload: Any) -> list[Word]:
    """A bare list of word objects. This is what Deepgram's utterance dumps and
    most hand-rolled exporters look like once you strip the envelope."""
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in (None, "word"):
            continue
        word = _word(
            item.get("start"),
            item.get("end"),
            item.get("text") or item.get("word") or item.get("punctuated_word"),
            item.get("speaker_id", item.get("speaker", item.get("channel"))),
        )
        if word:
            out.append(word)
    return out


def read_deepgram(payload: Any) -> list[Word]:
    """Deepgram prerecorded response: results.channels[].alternatives[].words[].

    Multichannel calls carry the speaker on the channel index, not on the word,
    so fall back to the channel when diarization is off. On a two-leg phone
    recording that is exactly right: channel 0 is one party, channel 1 the other.
    """
    if not isinstance(payload, dict):
        return []
    channels = (payload.get("results") or {}).get("channels")
    if not isinstance(channels, list):
        return []
    out = []
    for index, channel in enumerate(channels):
        alternatives = (channel or {}).get("alternatives") or []
        if not alternatives:
            continue
        for item in alternatives[0].get("words") or []:
            if not isinstance(item, dict):
                continue
            word = _word(
                item.get("start"),
                item.get("end"),
                item.get("punctuated_word") or item.get("word"),
                item.get("speaker", index),
            )
            if word:
                out.append(word)
    out.sort(key=lambda w: w.start)
    return out


def read_assemblyai(payload: Any) -> list[Word]:
    """AssemblyAI transcript: top-level words[] with millisecond timings."""
    if not isinstance(payload, dict) or not isinstance(payload.get("words"), list):
        return []
    out = []
    for item in payload["words"]:
        if not isinstance(item, dict):
            continue
        start, end = _num(item.get("start")), _num(item.get("end"))
        if start is None or end is None:
            continue
        word = _word(start / 1000.0, end / 1000.0, item.get("text"), item.get("speaker"))
        if word:
            out.append(word)
    return out


def read_whisperx(payload: Any) -> list[Word]:
    """WhisperX diarized output: segments[].words[] with a speaker per word."""
    if not isinstance(payload, dict) or not isinstance(payload.get("segments"), list):
        return []
    out = []
    for segment in payload["segments"]:
        if not isinstance(segment, dict):
            continue
        fallback = segment.get("speaker")
        for item in segment.get("words") or []:
            if not isinstance(item, dict):
                continue
            word = _word(
                item.get("start"),
                item.get("end"),
                item.get("word") or item.get("text"),
                item.get("speaker", fallback),
            )
            if word:
                out.append(word)
    return out


READERS: tuple[Callable[[Any], list[Word]], ...] = (
    read_deepgram,
    read_assemblyai,
    read_whisperx,
    read_flat,
)


def parse(payload: Any) -> list[Word]:
    """Try every reader, take the first that finds words.

    Order matters: the envelope formats are checked before the flat reader,
    because a Deepgram response is also a dict and would otherwise fall through
    to a reader that returns nothing and looks like an empty call.
    """
    for reader in READERS:
        words = reader(payload)
        if words:
            return sorted(words, key=lambda w: (w.start, w.end))
    raise UnknownFormat(
        "no reader recognized this payload — supported: Deepgram prerecorded, "
        "AssemblyAI, WhisperX, or a flat list of {start,end,text,speaker}"
    )


def load(path: str | Path) -> list[Word]:
    with open(path, encoding="utf-8") as handle:
        return parse(json.load(handle))
