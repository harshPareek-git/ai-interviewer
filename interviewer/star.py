"""Interactive STAR behavioral-interview coach.

Usage:
  python -m interviewer.star            # 4 behavioral questions, STAR-scored
  python -m interviewer.star --n 6
  python -m interviewer.star --voice
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer.llm import LLM  # noqa: E402
from interviewer.star_coach import StarCoach  # noqa: E402

console = Console()
SESS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")


def speak(text, enabled):
    if enabled:
        try:
            subprocess.Popen(["say", text[:400]])
        except Exception:
            pass


def color(s):
    return "green" if s >= 7 else "yellow" if s >= 5 else "red"


def read_multiline(prompt):
    console.print(f"[dim]{prompt} (blank line + Enter to submit, or 'skip')[/dim]")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().lower() == "skip" and not lines:
            return ""
        if line == "" and lines:
            break
        if line == "" and not lines:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def show_star(ev):
    c = color(ev.get("score", 0))
    console.print(f"\n[bold {c}]STAR score: {ev.get('score')}/10[/bold {c}]")
    t = Table(show_header=True)
    for part in ("situation", "task", "action", "result"):
        t.add_column(part.capitalize(), justify="center")
    t.add_row(*[f"[{color(ev.get(p,0))}]{ev.get(p,0)}[/]"
                for p in ("situation", "task", "action", "result")])
    console.print(t)
    if ev.get("missing"):
        console.print(f"[yellow]Weak/missing:[/yellow] {', '.join(ev['missing'])}")
    if ev.get("feedback"):
        console.print(f"[cyan]Coaching:[/cyan] {ev['feedback']}")
    if ev.get("improved_answer"):
        console.print(Panel(ev["improved_answer"], title="Stronger STAR answer",
                            border_style="cyan"))


def run(args):
    llm = LLM()
    coach = StarCoach(llm)
    console.print(Panel.fit(
        f"[bold]STAR Behavioral Coach[/bold]\n"
        f"backend=[cyan]{llm.backend}[/cyan]  model=[cyan]{llm.model}[/cyan]  "
        f"questions=[cyan]{args.n}[/cyan]\n"
        f"[dim]Answer using Situation - Task - Action - Result.[/dim]",
        border_style="magenta"))

    qs = coach.questions(args.n, seed=args.seed)
    turns = []
    for i, q in enumerate(qs, 1):
        console.print(Rule(f"Behavioral {i}/{len(qs)}"))
        console.print(f"[bold]{q}[/bold]\n")
        speak(q, args.voice)
        ans = read_multiline("Your answer")
        console.print("[dim]Evaluating...[/dim]")
        ev = coach.evaluate(q, ans)
        show_star(ev)
        turns.append({"question": q, "answer": ans, "eval": ev})

        if ev.get("follow_up") and ans and ev.get("score", 0) >= 3:
            console.print(f"\n[italic magenta]Follow-up:[/italic magenta] [bold]{ev['follow_up']}[/bold]\n")
            speak(ev["follow_up"], args.voice)
            fa = read_multiline("Your answer")
            if fa:
                console.print("[dim]Evaluating...[/dim]")
                fev = coach.evaluate(ev["follow_up"], fa)
                show_star(fev)
                turns.append({"question": ev["follow_up"], "answer": fa,
                              "eval": fev, "is_follow_up": True})
        console.print()

    show_report(turns)
    save_session(turns, llm)


def show_report(turns):
    graded = [t for t in turns if isinstance(t["eval"].get("score"), int)]
    if not graded:
        return
    overall = round(sum(t["eval"]["score"] for t in graded) / len(graded), 1)
    console.print(Rule("[bold]Behavioral Report[/bold]"))
    c = color(int(overall))
    console.print(f"[bold {c}]Overall STAR: {overall}/10[/bold {c}]")
    # average each STAR component
    comps = ("situation", "task", "action", "result")
    avgs = {p: round(sum(t["eval"].get(p, 0) for t in graded) / len(graded), 1) for p in comps}
    weakest = min(avgs, key=avgs.get)
    console.print("Component averages: " +
                  "  ".join(f"{p.capitalize()} {avgs[p]}" for p in comps))
    console.print(f"[yellow]Weakest STAR component:[/yellow] {weakest.capitalize()} "
                  f"— practice making this explicit in every answer.")


def save_session(turns, llm):
    os.makedirs(SESS_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SESS_DIR, f"behavioral_{ts}.json")
    with open(path, "w") as f:
        json.dump({"timestamp": ts, "model": llm.model, "mode": "behavioral",
                   "turns": turns}, f, indent=2)
    console.print(f"\n[dim]Session saved to {os.path.relpath(path)}[/dim]")


def main():
    ap = argparse.ArgumentParser(description="STAR behavioral interview coach")
    ap.add_argument("--n", type=int, default=4, help="number of behavioral questions")
    ap.add_argument("--voice", action="store_true", help="speak questions (macOS 'say')")
    ap.add_argument("--seed", type=int, help="deterministic question selection")
    args = ap.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Bye.[/dim]")


if __name__ == "__main__":
    main()
