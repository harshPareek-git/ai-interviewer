"""Cross-session progress tracker.

Reads all saved sessions and shows how your scores trend over time and which
categories remain weak, so you know exactly what to study before the real
interview.

Usage:  python -m interviewer.progress
"""
from __future__ import annotations

import glob
import json
import os
import sys

from rich.console import Console
from rich.table import Table

SESS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")
console = Console()


def load_sessions():
    out = []
    for f in sorted(glob.glob(os.path.join(SESS_DIR, "session_*.json"))):
        try:
            with open(f) as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    # behavioral (STAR) sessions: synthesize a comparable report block
    for f in sorted(glob.glob(os.path.join(SESS_DIR, "behavioral_*.json"))):
        try:
            with open(f) as fh:
                s = json.load(fh)
        except Exception:
            continue
        scores = [t.get("eval", {}).get("score") for t in s.get("turns", [])]
        scores = [x for x in scores if isinstance(x, (int, float))]
        overall = round(sum(scores) / len(scores), 1) if scores else 0
        turns = [{"category": "Behavioral",
                  "score": t.get("eval", {}).get("score"),
                  "missed": t.get("eval", {}).get("missing", [])}
                 for t in s.get("turns", [])]
        out.append({
            "timestamp": s.get("timestamp", "?"),
            "report": {"overall": overall, "verdict": "behavioral round",
                       "category_scores": {"Behavioral": overall}},
            "turns": turns,
        })
    out.sort(key=lambda x: x.get("timestamp", ""))
    return out


def main():
    sessions = load_sessions()
    if not sessions:
        console.print("[yellow]No sessions yet. Run a mock interview first:[/yellow] "
                      "python -m interviewer.cli")
        return

    console.print(f"[bold]Progress across {len(sessions)} session(s)[/bold]\n")

    trend = Table(title="Overall score over time")
    trend.add_column("Session")
    trend.add_column("Date")
    trend.add_column("Overall", justify="right")
    trend.add_column("Verdict")
    for i, s in enumerate(sessions, 1):
        r = s.get("report", {})
        ts = s.get("timestamp", "?")
        trend.add_row(str(i), ts, str(r.get("overall", "?")), r.get("verdict", ""))
    console.print(trend)

    # aggregate category scores across sessions
    cat_totals = {}
    for s in sessions:
        for cat, sc in s.get("report", {}).get("category_scores", {}).items():
            cat_totals.setdefault(cat, []).append(sc)

    if cat_totals:
        cat_table = Table(title="Average by category (all sessions)")
        cat_table.add_column("Category")
        cat_table.add_column("Avg", justify="right")
        cat_table.add_column("Attempts", justify="right")
        for cat, scores in sorted(cat_totals.items(), key=lambda x: sum(x[1]) / len(x[1])):
            avg = round(sum(scores) / len(scores), 1)
            color = "green" if avg >= 7 else "yellow" if avg >= 5 else "red"
            cat_table.add_row(cat, f"[{color}]{avg}[/]", str(len(scores)))
        console.print(cat_table)

    # recurring gaps
    gap_counts = {}
    for s in sessions:
        for t in s.get("turns", []):
            for m in (t.get("missed") or []):
                gap_counts[m] = gap_counts.get(m, 0) + 1
    if gap_counts:
        console.print("\n[bold]Most recurring gaps to study:[/bold]")
        for gap, n in sorted(gap_counts.items(), key=lambda x: -x[1])[:10]:
            console.print(f"  • ({n}x) {gap}")

    if len(sessions) >= 2:
        first = sessions[0]["report"].get("overall", 0)
        last = sessions[-1]["report"].get("overall", 0)
        delta = round(last - first, 1)
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        console.print(f"\n[bold]Trend:[/bold] {first} → {last}  ({arrow} {abs(delta)})")


if __name__ == "__main__":
    main()
