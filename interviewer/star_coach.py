"""STAR behavioral coach.

A dedicated behavioral-interview mode. It asks common FDE/AI-engineer behavioral
questions and scores each answer on the STAR framework (Situation, Task, Action,
Result), the structure top companies expect. It flags which STAR components are
missing and rewrites a tighter version so you learn the shape of a great answer.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .llm import LLM

BEHAVIORAL_QUESTIONS = [
    "Tell me about a time you had to deliver under a tight deadline with incomplete information.",
    "Describe a conflict with a teammate or client and how you resolved it.",
    "Tell me about a time you had to learn a new technology quickly to ship something.",
    "Describe a project that failed or went wrong. What happened and what did you learn?",
    "Tell me about a time you disagreed with a stakeholder's technical decision.",
    "Describe the most technically challenging problem you've solved end to end.",
    "Tell me about a time you had to influence someone without authority.",
    "Describe a time you received tough feedback and how you responded.",
    "Tell me about a time you had to make a decision with significant tradeoffs.",
    "Describe a time you went above and beyond for a customer or user.",
]

STAR_SYSTEM = (
    "You are a senior behavioral interviewer at a top tech company hiring a "
    "Forward Deployed / AI Engineer. You evaluate answers strictly on the STAR "
    "framework: Situation, Task, Action, Result. A great answer is specific, "
    "shows individual ownership ('I' not just 'we'), includes a concrete "
    "measurable result, and reflects learning. Penalize vagueness, no metrics, "
    "and answers that are all context with no action/result."
)

STAR_TEMPLATE = """BEHAVIORAL QUESTION:
{question}

CANDIDATE ANSWER:
\"\"\"{answer}\"\"\"

Evaluate on STAR. Return ONLY JSON:
{{
  "score": <int 0-10>,
  "situation": <int 0-10, was the context clear and concise>,
  "task": <int 0-10, was their specific responsibility clear>,
  "action": <int 0-10, specific actions THEY took>,
  "result": <int 0-10, concrete/measurable outcome + learning>,
  "missing": [<which STAR parts were weak or absent>],
  "feedback": "<2-3 sentences of specific coaching>",
  "improved_answer": "<a tight STAR-structured rewrite in 4-6 sentences>",
  "follow_up": "<one probing behavioral follow-up, or empty>"
}}"""


class StarCoach:
    def __init__(self, llm: LLM):
        self.llm = llm

    def questions(self, n: int, seed: Optional[int] = None) -> List[str]:
        import random
        rng = random.Random(seed)
        qs = list(BEHAVIORAL_QUESTIONS)
        rng.shuffle(qs)
        return qs[:n]

    def evaluate(self, question: str, answer: str) -> Dict:
        a = (answer or "").strip()
        if len(a) < 10:
            return {
                "score": 0, "situation": 0, "task": 0, "action": 0, "result": 0,
                "missing": ["Situation", "Task", "Action", "Result"],
                "feedback": ("No real answer. Behavioral answers should follow STAR: set "
                             "the Situation, your Task, the Actions you took, and the Result."),
                "improved_answer": "",
                "follow_up": "",
            }
        res = self.llm.chat_json(STAR_SYSTEM,
                                 STAR_TEMPLATE.format(question=question, answer=a),
                                 temperature=0.2)
        return self._sanitize(res)

    def _sanitize(self, r: Dict) -> Dict:
        if not isinstance(r, dict) or r.get("_parse_error"):
            return {
                "score": 5, "situation": 5, "task": 5, "action": 5, "result": 5,
                "missing": [],
                "feedback": "Evaluation model returned malformed output; scored neutrally. "
                            "Try a stronger model via INTERVIEWER_MODEL.",
                "improved_answer": "", "follow_up": "",
            }
        for k in ("score", "situation", "task", "action", "result"):
            try:
                r[k] = max(0, min(10, int(round(float(r.get(k, 0))))))
            except Exception:
                r[k] = 5
        if not isinstance(r.get("missing"), list):
            r["missing"] = []
        for k in ("feedback", "improved_answer", "follow_up"):
            if not isinstance(r.get(k), str):
                r[k] = ""
        return r
