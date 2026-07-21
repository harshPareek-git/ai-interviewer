import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer.llm import _extract_json, _strip_think
from interviewer.engine import Interview, InterviewConfig
from interviewer.evaluator import Evaluator
from interviewer import questions as qbank


class FakeLLM:
    """Deterministic stand-in so tests run offline without Ollama."""
    def __init__(self, score=7):
        self.backend = "fake"
        self.model = "fake"
        self._score = score

    def chat_json(self, system, user, temperature=0.3, retries=2):
        return {
            "score": self._score,
            "covered": ["a"], "missed": ["b"],
            "strengths": "good", "gaps": "more depth",
            "factual_errors": [], "ideal_answer": "ideal",
            "follow_up": "why?",
        }


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fences_and_think():
    s = "<think>reasoning</think>\n```json\n{\"score\": 8}\n```"
    assert _extract_json(s) == {"score": 8}


def test_strip_think():
    assert _strip_think("<think>x</think>hello").strip() == "hello"


def test_question_bank_integrity():
    ids = [q["id"] for q in qbank.QUESTIONS]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    for q in qbank.QUESTIONS:
        assert q["rubric"] and isinstance(q["rubric"], list)
        assert q["difficulty"] in ("easy", "medium", "hard")
        assert q["question"].strip()


def test_evaluator_empty_answer_scores_zero():
    ev = Evaluator(FakeLLM())
    q = qbank.QUESTIONS[0]
    r = ev.evaluate(q, "")
    assert r["score"] == 0
    assert r["missed"] == q["rubric"]


def test_evaluator_clamps_and_shapes():
    ev = Evaluator(FakeLLM(score=99))
    r = ev.evaluate(qbank.QUESTIONS[0], "some answer here")
    assert r["score"] == 10  # clamped
    assert isinstance(r["covered"], list)


def test_question_selection_balanced_and_bounded():
    interview = Interview(FakeLLM(), InterviewConfig(num_questions=4, seed=1))
    qs = interview.select_questions()
    assert len(qs) == 4
    # should prefer distinct categories first
    cats = [q["category"] for q in qs]
    assert len(set(cats)) >= 3


def test_report_aggregates():
    interview = Interview(FakeLLM(score=8), InterviewConfig(num_questions=3, seed=2))
    for q in interview.select_questions():
        ev = interview.evaluate_answer(q, "a decent answer")
        interview.record(q, "a decent answer", ev)
    r = interview.report()
    assert r["overall"] == 8.0
    assert "Strong hire" in r["verdict"]
    assert r["turns"] == 3


def test_category_filter():
    interview = Interview(FakeLLM(), InterviewConfig(num_questions=5, categories=["RAG"], seed=1))
    qs = interview.select_questions()
    assert all(q["category"] == "RAG" for q in qs)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} tests passed")
    sys.exit(0 if passed == len(fns) else 1)
