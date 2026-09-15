"""turnlag — measure what a caller actually feels on a voice-agent call."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from . import __version__
from .analyze import DEFAULT_MAX_GAP, Stats, infer_agent, measure, segment
from .parse import UnknownFormat, load
from .report import as_dict, summary, transcript, verdict

EXIT_OK = 0
EXIT_THRESHOLD = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turnlag",
        description=(
            "Measure perceived turn latency for a voice agent from a call "
            "recording's word timings: the gap between the caller's last word "
            "and the agent's first word back."
        ),
        epilog=(
            "Accepts Deepgram prerecorded, AssemblyAI, WhisperX, or a flat list "
            "of {start,end,text,speaker}. Exits 1 if --max-p50 is exceeded, so "
            "it can gate a deploy."
        ),
    )
    parser.add_argument("files", nargs="+", help="word-timing JSON files")
    parser.add_argument(
        "--agent",
        metavar="SPEAKER",
        help="speaker id of the agent (default: whoever speaks first, which is "
        "correct for inbound calls)",
    )
    parser.add_argument(
        "--max-p50",
        type=float,
        metavar="SECONDS",
        help="fail with exit 1 if median latency exceeds this",
    )
    parser.add_argument(
        "--max-gap",
        type=float,
        default=DEFAULT_MAX_GAP,
        metavar="SECONDS",
        help=f"ignore gaps longer than this (default: {DEFAULT_MAX_GAP:g})",
    )
    parser.add_argument(
        "--include-barge-in",
        action="store_true",
        help="count turns where the agent started before the caller finished "
        "(negative gaps); off by default so they do not flatter the median",
    )
    parser.add_argument(
        "--keep-backchannels",
        action="store_true",
        help='treat "mhm" / "yeah" as real turns (off by default)',
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("-q", "--quiet", action="store_true", help="stats only")
    parser.add_argument("--version", action="version", version=f"turnlag {__version__}")
    return parser


def analyze_file(path: str, args: argparse.Namespace) -> tuple[Stats, str, list, list] | None:
    words = load(path)
    turns = segment(words, drop_backchannels=not args.keep_backchannels)
    agent = args.agent or infer_agent(turns)
    if agent is None:
        return None
    known = {t.speaker for t in turns}
    if agent not in known:
        raise SystemExit(
            f"{path}: no speaker {agent!r}; found {', '.join(sorted(known))}"
        )
    gaps = measure(
        turns,
        agent,
        max_gap=args.max_gap,
        include_barge_in=args.include_barge_in,
    )
    stats = Stats.of(gaps)
    if stats is None:
        return None
    return stats, agent, turns, gaps


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    results, payloads, skipped = [], [], []
    for path in args.files:
        name = Path(path).name
        try:
            outcome = analyze_file(path, args)
        except FileNotFoundError:
            print(f"turnlag: {path}: no such file", file=sys.stderr)
            return EXIT_USAGE
        except (UnknownFormat, json.JSONDecodeError) as exc:
            print(f"turnlag: {path}: {exc}", file=sys.stderr)
            return EXIT_USAGE

        if outcome is None:
            skipped.append(name)
            continue

        stats, agent, turns, gaps = outcome
        results.append(stats)
        payloads.append(as_dict(name, stats, agent))

        if not args.json:
            print(f"### {name}   (agent = {agent})")
            if not args.quiet:
                print(transcript(turns, agent, gaps))
                print()
            print(summary(stats))
            print()

    for name in skipped:
        print(f"turnlag: {name}: no measurable turns", file=sys.stderr)

    if not results:
        print("turnlag: nothing to measure", file=sys.stderr)
        return EXIT_USAGE

    # Pool every gap across files so the overall p50 is one honest distribution
    # rather than an average of per-call medians, which quietly overweights
    # short calls.
    overall = statistics.median([p["p50"] for p in payloads]) if len(payloads) > 1 else payloads[0]["p50"]

    if args.json:
        body = {"calls": payloads}
        if len(payloads) > 1:
            body["median_of_call_p50"] = round(overall, 3)
            body["verdict"] = verdict(overall)
        print(json.dumps(body, indent=2))
    elif len(payloads) > 1:
        print(f"=== {len(payloads)} calls · median of per-call p50 = {overall:.2f}s "
              f"· {verdict(overall).upper()}")

    if args.max_p50 is not None and overall > args.max_p50:
        print(
            f"turnlag: FAIL p50 {overall:.2f}s exceeds --max-p50 {args.max_p50:.2f}s",
            file=sys.stderr,
        )
        return EXIT_THRESHOLD
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
