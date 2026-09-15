# turnlag

Measure what a caller actually feels on a voice-agent call.

Your application logs measure server-side handling time. A caller feels
something different: the silence between their last word and your agent's first
word back. That silence is endpointing delay plus model time plus TTS
time-to-first-audio plus network, and most stacks never report it as one number
because no single component owns it.

`turnlag` measures it from the recording. No instrumentation, no vendor SDK, no
cooperation from the agent. If you can get word timings for a call, you can get
the number.

```
pip install turnlag        # or: python -m turnlag <file.json>
turnlag call.json
```

```
### call.json   (agent = speaker_0)
  [   0.08-   4.78] AGENT : Thanks for calling Northside Dental. This is Riley. What can I do for you?
  [   6.20-   8.96] CALLER: Hi. I'd like to book a cleaning next week.
  [  10.30-  13.24] AGENT : Let me check the schedule. Are mornings okay?   <- +1.34s after caller
  [  14.10-  15.02] CALLER: Mornings are best.
  [  18.64-  21.14] AGENT : I've got Monday at eight or Tuesday at nine.   <- +3.62s after caller
  [  22.02-  22.84] CALLER: Monday works.
  [  25.88-  28.92] AGENT : Booked for Monday at eight. Should I text the confirmation?   <- +3.04s after caller
  [  29.60-  30.16] CALLER: Yes please.
  [  31.20-  32.30] AGENT : Done. Anything else?   <- +1.04s after caller
  [  33.10-  34.48] CALLER: That's everything. Thanks.

  perceived time-to-first-word   n=4  min=1.04s  p50=2.19s  p90=3.62s  p95=3.62s  max=3.62s
  verdict: BAD (p50 2.19s)
```

## Input

Point it at word-timing JSON from any of these. The format is detected, not
configured.

- Deepgram prerecorded (`results.channels[].alternatives[].words[]`)
- AssemblyAI (`words[]`, millisecond timings)
- WhisperX diarized (`segments[].words[]`)
- A flat list of `{start, end, text, speaker}`

On a two-leg phone recording you do not need a diarizer at all. Transcribe the
stereo recording with `multichannel=true` and each party lands on its own
channel, which is more reliable than diarization and free.

## The parts that are easy to get wrong

Most of this tool is four decisions. They are the difference between a
plausible number and a correct one.

**Backchannels are not turns.** When a caller says "mhm" while your agent is
mid-sentence, they are not taking the floor. Segment naively and your agent's
next word looks like a 0.05s response, and your p50 improves every time a
caller is polite. `turnlag` folds a short interjection back into the
surrounding turn. Use `--keep-backchannels` if you disagree.

**Barge-in is excluded by default.** If your agent starts talking before the
caller finishes, the gap is negative. Averaging that in flatters the median for
behavior a caller experiences as being interrupted. Use `--include-barge-in` to
count them; they are reported separately either way.

**One long pause must not poison the distribution.** A caller who goes quiet
for 40 seconds is not your agent being slow. Gaps above `--max-gap` (default
20s) are dropped.

**Percentiles are nearest-rank, not interpolated.** A real call gives you 8 to
20 measurements. An interpolated p95 over 8 samples reports a latency that no
caller ever experienced. Nearest-rank always returns a number that actually
happened.

## In CI

Exits non-zero when the median crosses your line, so a regression fails the
build instead of arriving as a complaint.

```sh
turnlag recordings/*.json --max-p50 1.5
```

```
turnlag: FAIL p50 2.19s exceeds --max-p50 1.50s
```

`--json` emits per-call records for dashboards.

## What counts as good

No standard exists, so this is a judgment call and the tool states it plainly
rather than hiding it: at or under **1.0s** reads as conversational, up to
**2.0s** reads as slow but tolerable, and past that callers start talking over
the agent or checking whether the line dropped. Override the verdict by
ignoring it — the numbers are the output, the grade is a convenience.

## Why I wrote it

I run a voice agent on a live dental phone line. My logs said it was fast. I
believed that for months.

Then I measured four recorded calls this way and got a median
time-to-first-word of **2.1s, 3.0s, 3.3s, and 3.35s** — roughly three seconds
of silence after the caller stops talking, on a system I would have described
as responsive. The logs were not lying; they were answering a different
question. Handler time was tens of milliseconds. Everything else lived in
endpointing thresholds and TTS time-to-first-audio, which no single log line
covered.

I would rather have the number that embarrasses me than the one that
flatters me, so the tool ships with a grading scale that calls my own agent bad.

## Tests

```sh
python -m unittest discover -s tests
```

26 tests, no dependencies, standard library only.

## License

MIT
