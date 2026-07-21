"""Interactive mock-interview CLI for AI Engineer / FDE prep.

Usage:
  python -m interviewer.cli                      # default 6-question mixed mock
  python -m interviewer.cli --n 4 --category RAG
  python -m interviewer.cli --difficulty hard --no-followups
  python -m interviewer.cli --voice              # speak questions (macOS)

Backend/model via env:
  INTERVIEWER_BACKEND=ollama (default) | openai
  INTERVIEWER_MODEL=llama3.2:latest (default) | qwen2.5:7b | gpt-4o-mini ...
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer import Interview, InterviewConfig, LLM, questions as qbank  # noqa: E402

console = Console()
SESS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")


def speak(text: str, enabled: bool):
    if enabled:
        try:
            subprocess.Popen(["say", text[:400]])
        except Exception:
            pass


def score_color(s: int) -> str:
    return "green" if s >= 7 else "yellow" if s >= 5 else "red"


def read_multiline(prompt: str) -> str:
    console.print(f"[dim]{prompt} (type your answer; blank line + Enter to submit, or 'skip')[/dim]")
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


def show_evaluation(ev: dict):
    color = score_color(ev.get("score", 0))
    console.print(f"\n[bold {color}]Score: {ev.get('score')}/10[/bold {color}]")
    if ev.get("strengths"):
        console.print(f"[green]✓ Strengths:[/green] {ev['strengths']}")
    if ev.get("gaps"):
        console.print(f"[yellow]△ To improve:[/yellow] {ev['gaps']}")
    if ev.get("missed"):
        console.print("[yellow]△ Missed points:[/yellow] " + "; ".join(ev["missed"][:5]))
    if ev.get("factual_errors"):
        console.print("[red]✗ Factual issues:[/red] " + "; ".join(ev["factual_errors"][:4]))
    if ev.get("ideal_answer"):
        console.print(Panel(ev["ideal_answer"], title="Model answer", border_style="cyan"))


def run(args):
    llm = LLM()
    console.print(Panel.fit(
        f"[bold]Mock Interview: AI Engineer / Forward Deployed Engineer[/bold]\n"
        f"backend=[cyan]{llm.backend}[/cyan]  model=[cyan]{llm.model}[/cyan]  "
        f"questions=[cyan]{args.n}[/cyan]",
        border_style="magenta"))
    if llm.backend == "ollama" and "llama3.2" in llm.model:
        console.print("[dim]Tip: for sharper evaluation, pull a bigger judge model, "
                      "e.g. `ollama pull qwen2.5:7b` then set INTERVIEWER_MODEL=qwen2.5:7b[/dim]\n")

    cfg = InterviewConfig(
        num_questions=args.n,
        categories=[args.category] if args.category else None,
        difficulty=args.difficulty,
        follow_ups=not args.no_followups,
        include_web=args.web,
        seed=args.seed,
    )
    interview = Interview(llm, cfg)
    selected = interview.select_questions()
    if args.web:
        n_web = len(qbank.load_harvested())
        console.print(f"[dim]Including {n_web} web-harvested questions in the pool.[/dim]\n")

    for i, q in enumerate(selected, 1):
        console.print(Rule(f"Question {i}/{len(selected)}  ·  {q['category']} · {q['difficulty']}"))
        console.print(f"[bold]{q['question']}[/bold]\n")
        speak(q["question"], args.voice)
        answer = read_multiline("Your answer")
        console.print("[dim]Evaluating...[/dim]")
        ev = interview.evaluate_answer(q, answer)
        interview.record(q, answer, ev)
        show_evaluation(ev)

        # adaptive follow-up if warranted and answer was reasonable
        if cfg.follow_ups and ev.get("follow_up") and ev.get("score", 0) >= 4 and answer:
            fq = interview.make_follow_up_question(q, ev["follow_up"])
            console.print(f"\n[italic magenta]Follow-up:[/italic magenta] [bold]{fq['question']}[/bold]\n")
            speak(fq["question"], args.voice)
            fa = read_multiline("Your answer")
            if fa:
                console.print("[dim]Evaluating...[/dim]")
                fev = interview.evaluate_answer(fq, fa)
                interview.record(fq, fa, fev, is_follow_up=True)
                show_evaluation(fev)
        console.print()

    show_report(interview)
    save_session(interview, llm)


def show_report(interview: Interview):
    r = interview.report()
    console.print(Rule("[bold]Interview Report[/bold]"))
    color = score_color(int(r["overall"]))
    console.print(f"[bold {color}]Overall: {r['overall']}/10  ·  {r['verdict']}[/bold {color}]\n")

    table = Table(title="Scores by category")
    table.add_column("Category")
    table.add_column("Avg", justify="right")
    for cat, sc in sorted(r["category_scores"].items(), key=lambda x: -x[1]):
        table.add_row(cat, f"[{score_color(int(sc))}]{sc}[/]")
    console.print(table)

    if r["strongest"]:
        console.print(f"[green]Strongest:[/green] {', '.join(r['strongest'])}")
    if r["weakest"]:
        console.print(f"[yellow]Focus next:[/yellow] {', '.join(r['weakest'])}")
    if r["top_gaps"]:
        console.print("\n[bold]Study these (recurring gaps):[/bold]")
        for g in r["top_gaps"]:
            console.print(f"  • {g}")


def save_session(interview: Interview, llm: LLM):
    os.makedirs(SESS_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SESS_DIR, f"session_{ts}.json")
    data = {
        "timestamp": ts,
        "model": llm.model, "backend": llm.backend,
        "report": interview.report(),
        "turns": [
            {"question": t.question["question"], "category": t.question["category"],
             "is_follow_up": t.is_follow_up, "answer": t.answer,
             "score": t.evaluation.get("score"),
             "gaps": t.evaluation.get("gaps"),
             "missed": t.evaluation.get("missed"),
             "ideal_answer": t.evaluation.get("ideal_answer")}
            for t in interview.turns
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    console.print(f"\n[dim]Session saved to {os.path.relpath(path)}[/dim]")


def main():
    ap = argparse.ArgumentParser(description="AI Engineer / FDE mock interviewer")
    ap.add_argument("--n", type=int, default=6, help="number of questions")
    ap.add_argument("--category", help="restrict to one category (e.g. RAG, Agents, Coding)")
    ap.add_argument("--difficulty", choices=["easy", "medium", "hard"], help="restrict difficulty")
    ap.add_argument("--web", action="store_true", help="include web-harvested real questions")
    ap.add_argument("--no-followups", action="store_true", help="disable adaptive follow-ups")
    ap.add_argument("--voice", action="store_true", help="speak questions (macOS 'say')")
    ap.add_argument("--seed", type=int, help="deterministic question selection")
    args = ap.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Interview interrupted. Bye.[/dim]")


if __name__ == "__main__":
    main()
