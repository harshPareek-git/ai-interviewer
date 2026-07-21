"""Depth-probing follow-up generator.

Real senior interviewers don't accept the first answer, they keep asking
"but why?", "what breaks at scale?", "how did you measure that?" until they hit
the edge of your understanding. This module generates the NEXT probing question
from the actual answer you gave, targeting the vaguest or least-supported part,
and chains several levels deep.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .llm import LLM

PROBE_SYSTEM = (
    "You are a rigorous senior interviewer for AI Engineer / Forward Deployed "
    "Engineer roles. You probe the candidate's LAST answer to test the true "
    "depth of their understanding. Ask ONE sharp follow-up that targets the "
    "weakest, vaguest, or least-supported part of their answer, or pushes for a "
    "concrete example, a tradeoff, a number, or 'why'. Stay on the same topic and "
    "go deeper, do not switch subjects. Keep it to a single question a candidate "
    "can answer verbally."
)

PROBE_TEMPLATE = """ORIGINAL QUESTION:
{question}

CONVERSATION SO FAR (each candidate answer followed by depth so far):
{history}

The candidate's LAST answer:
\"\"\"{answer}\"\"\"

Its evaluation noted these gaps/missed points: {gaps}

Produce ONE deeper follow-up question. Return ONLY JSON:
{{
  "follow_up": "the single deeper question",
  "targets": "what weakness/claim this probes",
  "stop": true|false   // true if the topic is fully exhausted or the answer was strong and complete
}}"""


class Prober:
    def __init__(self, llm: LLM, max_depth: int = 2, min_score_to_probe: int = 3):
        self.llm = llm
        self.max_depth = max_depth
        self.min_score_to_probe = min_score_to_probe

    def next_probe(self, question: Dict, history: List[Dict],
                   last_answer: str, last_eval: Dict) -> Optional[Dict]:
        """Return a follow-up dict {question, targets} or None to stop."""
        # don't probe empty/non-answers or already-exhausted chains
        if not last_answer or last_answer.strip().lower() in (
                "i don't know", "idk", "skip", "not sure"):
            return None
        if len(history) >= self.max_depth:
            return None

        hist_str = "\n".join(
            f"- Q: {h['q'][:120]}\n  A: {h['a'][:200]}" for h in history
        ) or "(this is the first follow-up)"
        gaps = "; ".join(last_eval.get("missed", [])[:4]) or last_eval.get("gaps", "")

        result = self.llm.chat_json(
            PROBE_SYSTEM,
            PROBE_TEMPLATE.format(question=question["question"], history=hist_str,
                                  answer=last_answer.strip()[:1200], gaps=gaps),
            temperature=0.4,
        )
        if not isinstance(result, dict) or result.get("_parse_error"):
            return None
        if result.get("stop") is True:
            return None
        fu = str(result.get("follow_up", "")).strip()
        if len(fu) < 8:
            return None
        return {
            "id": question["id"] + f"-probe{len(history)+1}",
            "category": question["category"],
            "difficulty": question["difficulty"],
            "type": question["type"],
            "question": fu,
            "targets": str(result.get("targets", "")).strip(),
            # probes are judged on depth against the parent rubric
            "rubric": question["rubric"],
            "is_probe": True,
        }
