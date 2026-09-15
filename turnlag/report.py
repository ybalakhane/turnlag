"""Human-readable and machine-readable output."""

from __future__ import annotations

from .analyze import Gap, Stats, Turn

# Anything past this and a caller starts to wonder whether the line dropped.
# Not a standard, just the threshold where the pauses stop reading as thinking.
GOOD_P50 = 1.0
OK_P50 = 2.0


def verdict(p50: float) -> str:
    if p50 <= GOOD_P50:
        return "good"
    if p50 <= OK_P50:
        return "slow"
    return "bad"


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def transcript(turns: list[Turn], agent: str, gaps: list[Gap], width: int = 88) -> str:
    by_turn = {id(g.agent_turn): g for g in gaps}
    lines = []
    for turn in turns:
        who = "AGENT " if turn.speaker == agent else "CALLER"
        gap = by_turn.get(id(turn))
        suffix = ""
        if gap is not None:
            mark = "barge-in" if gap.barge_in else "after caller"
            suffix = f"   <- {gap.seconds:+.2f}s {mark}"
        lines.append(
            f"  [{turn.start:7.2f}-{turn.end:7.2f}] {who}: "
            f"{_clip(turn.text, width)}{suffix}"
        )
    return "\n".join(lines)


def summary(stats: Stats) -> str:
    grade = verdict(stats.median)
    line = (
        f"  perceived time-to-first-word   n={stats.n}  "
        f"min={stats.minimum:.2f}s  p50={stats.median:.2f}s  "
        f"p90={stats.p90:.2f}s  p95={stats.p95:.2f}s  max={stats.maximum:.2f}s"
    )
    if stats.barge_ins:
        line += f"\n  barge-ins: {stats.barge_ins}"
    return f"{line}\n  verdict: {grade.upper()} (p50 {stats.median:.2f}s)"


def as_dict(name: str, stats: Stats, agent: str) -> dict:
    return {
        "source": name,
        "agent_speaker": agent,
        "turns_measured": stats.n,
        "min": round(stats.minimum, 3),
        "p50": round(stats.median, 3),
        "mean": round(stats.mean, 3),
        "p90": round(stats.p90, 3),
        "p95": round(stats.p95, 3),
        "max": round(stats.maximum, 3),
        "barge_ins": stats.barge_ins,
        "verdict": verdict(stats.median),
    }
