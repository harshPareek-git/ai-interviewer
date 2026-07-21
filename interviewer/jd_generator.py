"""JD- and resume-aware question generator.

Given a job description (and optionally your resume), the LLM generates tailored
interview questions that:
  - probe the specific skills/tools the JD demands
  - dig into the exact projects/claims on your resume (where a candidate
    inflating experience gets caught)
  - match the seniority the JD asks for

Each generated question comes with an auto-rubric so it plugs straight into the
existing evaluator/engine. Output is saved to data/tailored_questions.json.

Usage:
  python -m interviewer.jd_generator --jd jd.txt --resume resume.txt --n 8
  python -m interviewer.jd_generator --jd-text "..." --n 6
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer.llm import LLM  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT_PATH = os.path.join(DATA_DIR, "tailored_questions.json")

GEN_SYSTEM = (
    "You are a senior hiring interviewer for AI Engineer / Forward Deployed "
    "Engineer roles. You design sharp, specific interview questions tailored to "
    "a given job description and candidate resume. You especially probe whether "
    "the candidate truly has the depth their resume claims: ask about decisions, "
    "tradeoffs, failures, and 'why' behind projects. Avoid generic trivia."
)

GEN_TEMPLATE = """Generate {n} tailored interview questions for this role.

JOB DESCRIPTION:
\"\"\"{jd}\"\"\"

CANDIDATE RESUME:
\"\"\"{resume}\"\"\"

Rules:
- Mix question sources: some from JD-required skills, some drilling into the \
resume's specific projects/claims (probe depth, tradeoffs, and 'why').
- Calibrate difficulty to the seniority in the JD.
- Each question must be answerable verbally in an interview.

Return ONLY a JSON object: {{"questions": [ {{
  "question": "...",
  "category": one of [LLM Fundamentals, RAG, Agents, Evaluation, System Design, \
Fine-tuning, MLOps, Coding, Behavioral, Forward Deployed, ML Fundamentals],
  "difficulty": one of [easy, medium, hard],
  "targets": "what this question tests / which JD or resume item it maps to",
  "rubric": [3-5 short key points a strong answer must cover]
}} ] }}"""


def _clean(qs, source_tag: str) -> List[Dict]:
    out = []
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            continue
        qt = str(q.get("question", "")).strip()
        if len(qt) < 12:
            continue
        rubric = q.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            rubric = ["Correct and specific", "Explains tradeoffs", "Concrete example"]
        diff = str(q.get("difficulty", "medium")).strip().lower()
        out.append({
            "id": f"{source_tag}-{i+1}",
            "question": qt,
            "category": str(q.get("category", "System Design")).strip() or "System Design",
            "difficulty": diff if diff in ("easy", "medium", "hard") else "medium",
            "type": "technical",
            "targets": str(q.get("targets", "")).strip(),
            "rubric": [str(x).strip() for x in rubric[:6] if str(x).strip()],
            "source": "tailored",
        })
    return out


def generate(jd: str, resume: str = "", n: int = 8,
             llm: Optional[LLM] = None) -> List[Dict]:
    llm = llm or LLM()
    if not jd.strip():
        raise ValueError("job description is empty")
    user = GEN_TEMPLATE.format(n=n, jd=jd.strip()[:4000],
                               resume=(resume.strip()[:3000] or "(not provided)"))
    result = llm.chat_json(GEN_SYSTEM, user, temperature=0.5)
    qs = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(qs, list):
        return []
    return _clean(qs, "jd")


def save(questions: List[Dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"count": len(questions), "questions": questions}, f, indent=2)


def load_tailored() -> List[Dict]:
    if not os.path.exists(OUT_PATH):
        return []
    try:
        with open(OUT_PATH) as f:
            return json.load(f).get("questions", [])
    except Exception:
        return []


def _read(path: Optional[str], inline: Optional[str]) -> str:
    if inline:
        return inline
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def main():
    ap = argparse.ArgumentParser(description="Generate JD/resume-tailored interview questions")
    ap.add_argument("--jd", help="path to job description file")
    ap.add_argument("--jd-text", help="job description text inline")
    ap.add_argument("--resume", help="path to resume file")
    ap.add_argument("--resume-text", help="resume text inline")
    ap.add_argument("--n", type=int, default=8, help="number of questions")
    args = ap.parse_args()

    jd = _read(args.jd, args.jd_text)
    resume = _read(args.resume, args.resume_text)
    if not jd.strip():
        print("Provide a job description with --jd <file> or --jd-text \"...\"")
        sys.exit(1)

    llm = LLM()
    print(f"Generating {args.n} tailored questions  (model={llm.model})...")
    qs = generate(jd, resume, n=args.n, llm=llm)
    save(qs)
    print(f"\nGenerated {len(qs)} tailored questions -> {os.path.relpath(OUT_PATH)}\n")
    for i, q in enumerate(qs, 1):
        print(f"{i}. [{q['category']}/{q['difficulty']}] {q['question']}")
        if q.get("targets"):
            print(f"     ↳ tests: {q['targets']}")
    print("\nRun a tailored mock:  python -m interviewer.cli --tailored")


if __name__ == "__main__":
    main()
