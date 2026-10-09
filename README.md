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
pip install "git+https://github.com/ybalakhane/turnlag"
turnlag call.json          # from a checkout: python -m turnlag call.json
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

I measured recorded test calls from a voice agent I built. The logs said it
was fast. I believed that for months.

The result is the set below: eleven of those calls had at least two measured
replies. Nine medians fall between 1.93s and 3.38s, and two are worse, 4.78s
and 5.64s. Roughly three seconds of silence after the caller stops talking, on
a system I would have described as responsive, and sometimes longer. The logs
were not lying; they were answering a different question. Handler time was
tens of milliseconds. Everything else lived in endpointing thresholds and TTS
time-to-first-audio, which no single log line covered.

I would rather have the number that embarrasses me than the one that
flatters me, so the tool ships with a grading scale that calls my own agent bad.

## Measured results

Eighteen word-timing files from acceptance-test calls on 2026-08-18. Synthetic
test callers, a test schedule, my own voice agent, no real patients. These are
test calls, not production traffic.

Each file is a two-channel phone recording turned into word timings. I ran
`python -m turnlag` on every file at the defaults: backchannels folded,
barge-in excluded, gaps over 20s dropped, nearest-rank percentiles for p90 and
p95. The p50 below is the median the tool prints. With an even number of
replies that median is the average of the two central gaps. A call is listed
when that run measured 2 or more replies.

On this set the defaults did not fold a backchannel or drop a gap. Every
included gap was already non-negative and at most 20 seconds.

| Call | n | min | p50 |
| --- | ---: | ---: | ---: |
| A-cut1-CA3a723ad0471ab73b328cd5a265f922d1 | 8 | 1.04s | 3.35s |
| A-cut1-CAacf9a259461271bb594e59be63eec501 | 8 | 0.04s | 2.10s |
| A-cut1-CAeab589138e261d0019161a5ff554d8ec | 6 | 0.04s | 3.26s |
| A-orig-CAdb4dfaa43705d9b949a666a9b5f74b91 | 6 | 0.04s | 3.38s |
| B-CA21764d5e9efa6bd7fea4f106ca061a6d | 4 | 1.68s | 1.93s |
| B-CA9876e32c5312c981897dcb6c7c374860 | 4 | 2.82s | 3.03s |
| C-CA1613a3eeff5c68eea44b4bec0a4526e9 | 8 | 0.02s | 5.64s |
| C-CA25241abc75feed305103626138d83eb4 | 9 | 0.00s | 3.10s |
| D-CAde9c85ce0e11d528eb5041d59dd4a4af | 3 | 0.02s | 4.78s |
| S-CA7d0294c3000ca7e72a956148f0d08b6c | 2 | 1.38s | 2.18s |
| S-CAccda38671fb8648e370e3ebd5cade27c | 2 | 1.32s | 2.65s |

Nine of those eleven medians sit between 1.93s and 3.38s. Two are worse:
C-CA1613a3eeff5c68eea44b4bec0a4526e9 at 5.64s (n=8) and
D-CAde9c85ce0e11d528eb5041d59dd4a4af at 4.78s (n=3). Ten are past 2.0s, which
this tool calls bad. The 1.93s call is slow.

The text report rounds to hundredths of a second. `--json` keeps three
decimals, so three of these p50s print as 3.351s, 2.101s, and 3.259s. Same
medians.

Seven files are not in the table.

- C-CA8121ba0ab4fcc986fd5d66ffe5eba3f5, C-CA99d2979be6a387992b15aa4f3ed1aeef,
  C-CAe7b8703f92b8d772a4d89434ab79764f, and
  C-CAf45c48d5f58d027b82058b5e3135d459. About 3.7 seconds each. One channel
  says "We are sorry. An application error has occurred." The other channel is
  the agent greeting. There is no caller-then-agent gap, so turnlag reports no
  measurable turns.
- A-CAdb4dfaa43705d9b949a666a9b5f74b91 is an empty list. Same call id as the
  A-orig row above, which has the words. turnlag rejects the empty file
  because no reader recognizes the payload.
- D-CA3a5632728910920d348c43a6fbc1883f, the Spanish call. All 108 words are
  speaker_0: the English greeting and the Spanish request landed on one
  channel, so there is no second speaker and no gap.
- D-CA272aae672e99e2358e864a8241b5005b. One measured reply, 0.02s in the text
  report and 0.019s in `--json`. The file has three speakers. That 0.02s gap is
  the opening speaker saying "Take your time" as the caller finishes. The
  Spanish replies belong to a third speaker, so the default agent (whoever
  speaks first) does not count them. One reply is below the two-reply rule.

The lines the tool printed, including p90, p95, and max, are in
[examples/measured-results.md](examples/measured-results.md). The word-timing
files themselves are not in this repository.

## Tests

```sh
python -m unittest discover -s tests
```

26 tests, no dependencies, standard library only.

## License

MIT
