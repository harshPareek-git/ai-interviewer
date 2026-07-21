"""Interview engine: selects questions, runs the ask/answer/evaluate loop,
handles adaptive follow-ups, and aggregates a final report.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .evaluator import Evaluator
from .llm import LLM
from . import questions as qbank


@dataclass
class Turn:
    question: Dict
    answer: str
    evaluation: Dict
    is_follow_up: bool = False


@dataclass
class InterviewConfig:
    num_questions: int = 6
    categories: Optional[List[str]] = None  # None = all
    difficulty: Optional[str] = None        # None = mixed
    role: str = "AI Engineer / Forward Deployed Engineer"
    follow_ups: bool = True
    include_web: bool = False   # merge web-harvested questions
    include_tailored: bool = False  # merge JD/resume-tailored questions
    tailored_only: bool = False     # use ONLY tailored questions
    seed: Optional[int] = None


class Interview:
    def __init__(self, llm: LLM, config: InterviewConfig):
        self.llm = llm
        self.cfg = config
        self.evaluator = Evaluator(llm)
        self.turns: List[Turn] = []
        self._rng = random.Random(config.seed)

    def select_questions(self) -> List[Dict]:
        if self.cfg.tailored_only:
            pool = list(qbank.load_tailored())
            if not pool:
                pool = list(qbank.all_questions(include_web=self.cfg.include_web))
        else:
            pool = list(qbank.all_questions(
                include_web=self.cfg.include_web,
                include_tailored=self.cfg.include_tailored))
        if self.cfg.categories:
            pool = [q for q in pool if q["category"] in self.cfg.categories]
        if self.cfg.difficulty:
            pool = [q for q in pool if q["difficulty"] == self.cfg.difficulty]
        if not pool:
            pool = list(qbank.all_questions(include_web=self.cfg.include_web))
        self._rng.shuffle(pool)
        # spread across categories for a balanced interview
        seen, ordered = set(), []
        for q in pool:
            if q["category"] not in seen:
                ordered.append(q)
                seen.add(q["category"])
        for q in pool:
            if q not in ordered:
                ordered.append(q)
        return ordered[: self.cfg.num_questions]

    def evaluate_answer(self, question: Dict, answer: str) -> Dict:
        return self.evaluator.evaluate(question, answer)

    def record(self, question: Dict, answer: str, evaluation: Dict,
               is_follow_up: bool = False) -> None:
        self.turns.append(Turn(question, answer, evaluation, is_follow_up))

    def make_follow_up_question(self, base: Dict, follow_up_text: str) -> Dict:
        return {
            "id": base["id"] + "-fu",
            "category": base["category"],
            "difficulty": base["difficulty"],
            "type": base["type"],
            "question": follow_up_text,
            # reuse parent rubric loosely; follow-ups probe depth
            "rubric": base["rubric"],
        }

    # --- reporting -------------------------------------------------------
    def report(self) -> Dict:
        scored = [t for t in self.turns]
        if not scored:
            return {"overall": 0, "turns": 0}
        scores = [t.evaluation.get("score", 0) for t in scored]
        overall = round(sum(scores) / len(scores), 1)

        by_cat: Dict[str, List[int]] = {}
        for t in scored:
            by_cat.setdefault(t.question["category"], []).append(
                t.evaluation.get("score", 0))
        cat_avg = {c: round(sum(v) / len(v), 1) for c, v in by_cat.items()}

        strong = sorted(cat_avg.items(), key=lambda x: -x[1])[:2]
        weak = sorted(cat_avg.items(), key=lambda x: x[1])[:2]

        all_missed = []
        for t in scored:
            all_missed.extend(t.evaluation.get("missed", []))

        return {
            "overall": overall,
            "verdict": self._verdict(overall),
            "turns": len(scored),
            "category_scores": cat_avg,
            "strongest": [c for c, _ in strong],
            "weakest": [c for c, _ in weak],
            "top_gaps": all_missed[:8],
        }

    @staticmethod
    def _verdict(score: float) -> str:
        if score >= 8:
            return "Strong hire signal (senior level)"
        if score >= 6.5:
            return "Hire signal, some gaps to tighten"
        if score >= 5:
            return "Borderline; needs more depth and specifics"
        return "Not yet at bar; focus on fundamentals and concrete examples"
