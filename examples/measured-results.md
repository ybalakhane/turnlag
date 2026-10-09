# Measured results, 2026-08-18 acceptance calls

Per-call output of `python -m turnlag <file>` with no flags. Eighteen
word-timing files from acceptance-test calls on 2026-08-18: synthetic test
callers, a test schedule, the author's own voice agent, no real patients.
Test calls, not production traffic. The word-timing JSON is not in this
repository.

Method: two-channel phone recordings turned into word timings, then turnlag's
defaults. Backchannels are folded, barge-in is excluded, gaps over 20s are
dropped, and p90 and p95 are nearest-rank. The printed p50 is
`statistics.median`. When the number of replies is even, that is the average
of the two central gaps. A call is included at 2 or more measured replies.

On this set the defaults did not fold a backchannel or drop a gap. Every
included gap was already non-negative and at most 20 seconds. The agent on
every included call is `speaker_0`, whoever speaks first.

The text report below rounds to hundredths of a second. `--json` keeps three
decimals. That changes three included p50s, and the one-reply call, as noted
under each. The underlying median is the same.

## Included (11 calls, 2 or more measured replies)

Nine medians are between 1.93s and 3.38s. Two are worse: 5.64s and 4.78s.

```
### A-cut1-CA3a723ad0471ab73b328cd5a265f922d1.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=8  min=1.04s  p50=3.35s  p90=3.82s  p95=3.82s  max=3.82s
  verdict: BAD (p50 3.35s)
```

`--json` p50 is 3.351.

```
### A-cut1-CAacf9a259461271bb594e59be63eec501.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=8  min=0.04s  p50=2.10s  p90=3.56s  p95=3.56s  max=3.56s
  verdict: BAD (p50 2.10s)
```

`--json` p50 is 2.101.

```
### A-cut1-CAeab589138e261d0019161a5ff554d8ec.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=6  min=0.04s  p50=3.26s  p90=3.56s  p95=3.56s  max=3.56s
  verdict: BAD (p50 3.26s)
```

`--json` p50 is 3.259.

```
### A-orig-CAdb4dfaa43705d9b949a666a9b5f74b91.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=6  min=0.04s  p50=3.38s  p90=4.10s  p95=4.10s  max=4.10s
  verdict: BAD (p50 3.38s)
```

```
### B-CA21764d5e9efa6bd7fea4f106ca061a6d.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=4  min=1.68s  p50=1.93s  p90=2.64s  p95=2.64s  max=2.64s
  verdict: SLOW (p50 1.93s)
```

```
### B-CA9876e32c5312c981897dcb6c7c374860.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=4  min=2.82s  p50=3.03s  p90=3.36s  p95=3.36s  max=3.36s
  verdict: BAD (p50 3.03s)
```

```
### C-CA1613a3eeff5c68eea44b4bec0a4526e9.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=8  min=0.02s  p50=5.64s  p90=7.72s  p95=7.72s  max=7.72s
  verdict: BAD (p50 5.64s)
```

```
### C-CA25241abc75feed305103626138d83eb4.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=9  min=0.00s  p50=3.10s  p90=3.80s  p95=3.80s  max=3.80s
  verdict: BAD (p50 3.10s)
```

```
### D-CAde9c85ce0e11d528eb5041d59dd4a4af.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=3  min=0.02s  p50=4.78s  p90=6.52s  p95=6.52s  max=6.52s
  verdict: BAD (p50 4.78s)
```

```
### S-CA7d0294c3000ca7e72a956148f0d08b6c.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=2  min=1.38s  p50=2.18s  p90=2.98s  p95=2.98s  max=2.98s
  verdict: BAD (p50 2.18s)
```

```
### S-CAccda38671fb8648e370e3ebd5cade27c.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=2  min=1.32s  p50=2.65s  p90=3.98s  p95=3.98s  max=3.98s
  verdict: BAD (p50 2.65s)
```

On these sample sizes the nearest-rank p95 is the same gap as the max.

## Not included (7 files)

`A-CAdb4dfaa43705d9b949a666a9b5f74b91.words.json` is `[]`. turnlag exits 2 and
reports that no reader recognized the payload. Same call id as
A-orig-CAdb4dfaa43705d9b949a666a9b5f74b91, which is included above.

Each of these four exits 2 with `no measurable turns`:

- C-CA8121ba0ab4fcc986fd5d66ffe5eba3f5.words.json
- C-CA99d2979be6a387992b15aa4f3ed1aeef.words.json
- C-CAe7b8703f92b8d772a4d89434ab79764f.words.json
- C-CAf45c48d5f58d027b82058b5e3135d459.words.json

Each is about 3.7 seconds. One channel says "We are sorry. An application
error has occurred." The other channel is the agent greeting. Whoever speaks
first is the error message, and there is no later caller-then-agent gap.

`D-CA3a5632728910920d348c43a6fbc1883f.words.json` exits 2 with `no measurable
turns`. The Spanish call. turnlag reads 108 words, all speaker_0. The English
greeting and the Spanish request are on one channel, so there is no second
speaker and no gap.

```
### D-CA272aae672e99e2358e864a8241b5005b.words.json   (agent = speaker_0)
  perceived time-to-first-word   n=1  min=0.02s  p50=0.02s  p90=0.02s  p95=0.02s  max=0.02s
  verdict: GOOD (p50 0.02s)
```

`--json` p50 is 0.019. One measured reply. The file has three speakers. That
0.02s gap is the opening speaker saying "Take your time" as the caller
finishes. The Spanish replies belong to a third speaker, so the default agent
does not count them. One reply is below the two-reply rule, so this call is
not in the eleven.
