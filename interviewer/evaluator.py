"""Rubric-based answer evaluator.

Given a question, its rubric, and the candidate's answer, produces a structured
evaluation: score (0-10), which rubric points were covered/missed, strengths,
gaps, a concise ideal answer, and whether a follow-up probe is warranted.
"""
from __future__ import annotations

from typing import Dict

from .llm import LLM

EVAL_SYSTEM = """You are a senior technical interviewer at a top AI company \
hiring an AI Engineer / Forward Deployed Engineer with 4+ years of experience. \
You are rigorous, fair, and concise. You evaluate the candidate's answer \
against a rubric of key points. Calibrate to a HIGH bar: a 7+ means a strong, \
hireable senior-level answer. Reward correct, specific, practical answers; \
penalize vagueness, buzzwords without substance, and factual errors."""

EVAL_TEMPLATE = """QUESTION ({category}, {difficulty}, {qtype}):
{question}

RUBRIC (key points a strong answer should cover):
{rubric}

CANDIDATE ANSWER:
\"\"\"{answer}\"\"\"

Evaluate the answer. Return a JSON object with exactly these fields:
{{
  "score": <integer 0-10>,
  "covered": [<rubric points the candidate addressed, short strings>],
  "missed": [<important rubric points the candidate missed>],
  "strengths": "<1-2 sentences on what was good>",
  "gaps": "<1-2 sentences on what to improve>",
  "factual_errors": [<any incorrect claims, or empty list>],
  "ideal_answer": "<a tight model answer in 3-5 sentences>",
  "follow_up": "<one probing follow-up question a real interviewer would ask, or empty string>"
}}"""


class Evaluator:
    def __init__(self, llm: LLM):
        self.llm = llm

    def evaluate(self, question: Dict, answer: str) -> Dict:
        if not answer or len(answer.strip()) < 3:
            return {
                "score": 0,
                "covered": [], "missed": question["rubric"],
                "strengths": "No answer provided.",
                "gaps": "You skipped this question. Attempt an answer even if unsure.",
                "factual_errors": [],
                "ideal_answer": self._quick_ideal(question),
                "follow_up": "",
            }
        rubric_str = "\n".join(f"- {p}" for p in question["rubric"])
        user = EVAL_TEMPLATE.format(
            category=question["category"], difficulty=question["difficulty"],
            qtype=question["type"], question=question["question"],
            rubric=rubric_str, answer=answer.strip(),
        )
        result = self.llm.chat_json(EVAL_SYSTEM, user, temperature=0.2)
        return self._sanitize(result, question)

    def _sanitize(self, r: Dict, question: Dict) -> Dict:
        if r.get("_parse_error"):
            # fallback: keep the interview moving even if the judge glitched
            return {
                "score": 5, "covered": [], "missed": [],
                "strengths": "Evaluation model returned malformed output; scored neutrally.",
                "gaps": "Re-run with a stronger model (INTERVIEWER_MODEL) for detailed feedback.",
                "factual_errors": [], "ideal_answer": self._quick_ideal(question),
                "follow_up": "",
            }
        # clamp score
        try:
            r["score"] = max(0, min(10, int(round(float(r.get("score", 0))))))
        except Exception:
            r["score"] = 5
        for key, default in (("covered", []), ("missed", []), ("factual_errors", [])):
            if not isinstance(r.get(key), list):
                r[key] = default
        for key in ("strengths", "gaps", "ideal_answer", "follow_up"):
            if not isinstance(r.get(key), str):
                r[key] = ""
        if not r["ideal_answer"]:
            r["ideal_answer"] = self._quick_ideal(question)
        return r

    @staticmethod
    def _quick_ideal(question: Dict) -> str:
        return "A strong answer would cover: " + "; ".join(question["rubric"]) + "."
