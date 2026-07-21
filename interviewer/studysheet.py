"""Study-sheet export.

Reads your past interview sessions, finds your weakest categories and the
rubric points you keep missing, and writes a concise markdown revision
cheat-sheet, grouped by topic with crisp study notes (LLM-synthesized) plus the
exact model answers you were shown. Perfect for last-minute revision.

Usage:
  python -m interviewer.studysheet                 # from all sessions
  python -m interviewer.studysheet --out sheet.md
  python -m interviewer.studysheet --no-llm        # skip synthesis, faster
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer.llm import LLM  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS_DIR = os.path.join(BASE, "sessions")
DEFAULT_OUT = os.path.join(BASE, "study_sheet.md")

SYNTH_SYSTEM = (
    "You are a concise AI-engineering tutor. Given a topic and a list of points a "
    "candidate keeps missing in interviews, write crisp, correct revision notes "
    "that would let them answer those points well. Be specific and practical."
)

SYNTH_TEMPLATE = """TOPIC: {topic}

The candidate keeps missing these points in interviews:
{points}

Write revision notes as 4-7 short bullet points (one line each) that directly
teach these missing points. Return ONLY JSON: {{"notes": ["...", "..."]}}"""


def load_sessions() -> List[Dict]:
    out = []
    for f in sorted(glob.glob(os.path.join(SESS_DIR, "session_*.json"))):
        try:
            with open(f) as fh:
                out.append(json.load(fh))
        except Exception:
            continue
    return out


def aggregate(sessions: List[Dict]):
    """Return per-category: scores, missed-point counts, and sample model answers."""
    cat_scores = defaultdict(list)
    cat_missed = defaultdict(lambda: defaultdict(int))
    cat_ideal = defaultdict(list)
    weak_turns = []  # (score, category, question, ideal)
    for s in sessions:
        for t in s.get("turns", []):
            cat = t.get("category", "General")
            score = t.get("score")
            if isinstance(score, (int, float)):
                cat_scores[cat].append(score)
            for m in (t.get("missed") or []):
                cat_missed[cat][m] += 1
            if t.get("ideal_answer") and len(cat_ideal[cat]) < 3:
                cat_ideal[cat].append((t.get("question", ""), t["ideal_answer"]))
            if isinstance(score, (int, float)) and score < 6:
                weak_turns.append((score, cat, t.get("question", ""),
                                   t.get("ideal_answer", "")))
    return cat_scores, cat_missed, cat_ideal, weak_turns


def build(sessions: List[Dict], use_llm: bool = True) -> str:
    cat_scores, cat_missed, cat_ideal, weak_turns = aggregate(sessions)
    if not cat_scores:
        return "# Study sheet\n\nNo graded answers found yet. Run a mock interview first.\n"

    llm = LLM() if use_llm else None
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Interview Revision Cheat-Sheet", f"_generated {now} from "
             f"{len(sessions)} session(s)_", ""]

    # ranked weakest first
    cat_avg = {c: sum(v) / len(v) for c, v in cat_scores.items()}
    order = sorted(cat_avg, key=lambda c: cat_avg[c])

    lines.append("## Priority order (weakest first)\n")
    for c in order:
        lines.append(f"- **{c}** — avg {cat_avg[c]:.1f}/10 over {len(cat_scores[c])} answer(s)")
    lines.append("")

    for c in order:
        lines.append(f"## {c}  (avg {cat_avg[c]:.1f}/10)")
        missed = sorted(cat_missed[c].items(), key=lambda x: -x[1])
        if missed:
            lines.append("\n**You keep missing:**")
            for point, n in missed[:8]:
                tag = f" _(x{n})_" if n > 1 else ""
                lines.append(f"- {point}{tag}")
        # synthesized revision notes
        if use_llm and missed:
            pts = "\n".join(f"- {p}" for p, _ in missed[:8])
            try:
                res = llm.chat_json(SYNTH_SYSTEM,
                                    SYNTH_TEMPLATE.format(topic=c, points=pts),
                                    temperature=0.3)
                notes = res.get("notes") if isinstance(res, dict) else None
                if isinstance(notes, list) and notes:
                    lines.append("\n**Revision notes:**")
                    for nline in notes[:8]:
                        lines.append(f"- {str(nline).strip()}")
            except Exception:
                pass
        # sample model answers
        if cat_ideal[c]:
            lines.append("\n**Model answers to review:**")
            for q, ideal in cat_ideal[c]:
                if q:
                    lines.append(f"- _{q.strip()[:110]}_")
                lines.append(f"  - {ideal.strip()}")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Export a revision cheat-sheet from your sessions")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output markdown path")
    ap.add_argument("--no-llm", action="store_true", help="skip LLM synthesis (faster)")
    args = ap.parse_args()

    sessions = load_sessions()
    if not sessions:
        print("No sessions found. Run a mock interview first: python -m interviewer.cli")
        return
    print(f"Building study sheet from {len(sessions)} session(s)"
          f"{' (no LLM)' if args.no_llm else ' with LLM synthesis'}...")
    md = build(sessions, use_llm=not args.no_llm)
    with open(args.out, "w") as f:
        f.write(md)
    print(f"Wrote {os.path.relpath(args.out)}")


if __name__ == "__main__":
    main()
