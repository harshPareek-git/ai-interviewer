"""Question bank for AI Engineer / Forward Deployed Engineer interviews (2026).

Each question has:
  id, category, difficulty (easy|medium|hard), type (technical|system_design|
  behavioral|coding), question text, and a rubric (list of key points a strong
  4+ YOE answer should hit). The rubric drives evaluation and follow-ups.
"""

QUESTIONS = [
    # ---------------- LLM fundamentals ----------------
    {
        "id": "llm-1", "category": "LLM Fundamentals", "difficulty": "easy",
        "type": "technical",
        "question": "What is the difference between temperature and top-p (nucleus) sampling, and when would you tune each in production?",
        "rubric": [
            "Temperature scales the logits/softmax sharpness (higher = more random)",
            "Top-p restricts sampling to the smallest set of tokens whose cumulative prob >= p",
            "They compose; often fix one and tune the other",
            "Low temp / low top-p for deterministic tasks (extraction, code), higher for creative",
            "Mentions greedy/temperature=0 for reproducibility and evals",
        ],
    },
    {
        "id": "llm-2", "category": "LLM Fundamentals", "difficulty": "medium",
        "type": "technical",
        "question": "A customer says the model 'hallucinates'. Walk me through how you'd diagnose and reduce hallucinations in a deployed LLM feature.",
        "rubric": [
            "Define hallucination and distinguish types (factual, faithfulness to context)",
            "Instrument: collect failing examples, build an eval set",
            "Grounding via RAG / providing sources; ask model to cite",
            "Prompt techniques: constrain, 'say I don't know', lower temperature",
            "Guardrails: verification step, LLM-as-judge, retrieval confidence thresholds",
            "Measure before/after with the eval set, not vibes",
        ],
    },
    {
        "id": "llm-3", "category": "LLM Fundamentals", "difficulty": "hard",
        "type": "technical",
        "question": "Explain the tradeoffs between fine-tuning, RAG, and prompt engineering. Given a client with 10k internal support docs updated weekly, which do you pick and why?",
        "rubric": [
            "Prompt eng: cheapest/fastest, limited by context window and knowledge",
            "RAG: injects fresh/large external knowledge, no retraining, good for changing data",
            "Fine-tuning: changes behavior/style/format, expensive, stale for facts",
            "Weekly-updated docs -> RAG is the primary choice (freshness without retraining)",
            "Could combine: fine-tune for format/tone + RAG for knowledge",
            "Mentions cost, latency, maintenance, eval",
        ],
    },
    # ---------------- RAG ----------------
    {
        "id": "rag-1", "category": "RAG", "difficulty": "medium",
        "type": "technical",
        "question": "Design a RAG pipeline end to end. What are the components and where does retrieval quality usually break?",
        "rubric": [
            "Ingestion: chunking strategy, embeddings, vector store",
            "Retrieval: similarity search, top-k, optional reranking, hybrid (BM25+vector)",
            "Generation: prompt with retrieved context, citation",
            "Common failures: bad chunking, embedding mismatch, low recall, lost-in-the-middle",
            "Fixes: reranker, query rewriting, metadata filtering, chunk overlap",
            "Evaluation: retrieval precision/recall + answer faithfulness",
        ],
    },
    {
        "id": "rag-2", "category": "RAG", "difficulty": "hard",
        "type": "technical",
        "question": "Your RAG system retrieves relevant documents but the final answers are still wrong. How do you debug this?",
        "rubric": [
            "Separate retrieval quality from generation quality (isolate the stage)",
            "Check: are the right chunks actually in the context window?",
            "Lost-in-the-middle / context ordering; reranking",
            "Prompt: is the model instructed to use ONLY the context?",
            "Faithfulness eval / LLM-as-judge on (context, answer) pairs",
            "Chunk size too small losing context, or too large diluting signal",
        ],
    },
    # ---------------- Agents ----------------
    {
        "id": "agent-1", "category": "Agents", "difficulty": "medium",
        "type": "technical",
        "question": "What is an agentic system and how does it differ from a single LLM call? What new failure modes appear?",
        "rubric": [
            "Agent = LLM + tools + loop (plan, act, observe) + memory",
            "Differs: multi-step, tool use, autonomy, state",
            "Failure modes: error compounding across steps, infinite loops, tool misuse",
            "Cost/latency blow-up, hallucinated tool args",
            "Mitigations: step limits, validation, human-in-loop, eval on task success rate",
        ],
    },
    {
        "id": "agent-2", "category": "Agents", "difficulty": "hard",
        "type": "system_design",
        "question": "Design an agent that resolves customer support tickets by reading docs, querying internal APIs, and drafting replies. How do you make it reliable and safe?",
        "rubric": [
            "Architecture: tools (search, API, draft), planner, memory",
            "Reliability: retries, validation of tool outputs, guardrails",
            "Safety: no destructive actions without confirmation, PII handling, scope limits",
            "Human-in-the-loop for low-confidence or high-risk actions",
            "Observability: tracing every step, logging",
            "Evaluation: task success rate, escalation rate, offline eval set",
        ],
    },
    # ---------------- Evaluation ----------------
    {
        "id": "eval-1", "category": "Evaluation", "difficulty": "medium",
        "type": "technical",
        "question": "How do you evaluate an LLM application when there's no single correct answer? Walk me through building an eval harness.",
        "rubric": [
            "Build a representative labeled/golden dataset from real traffic",
            "Metrics: task-specific (faithfulness, relevance, format) not just accuracy",
            "LLM-as-judge with a rubric; validate judge against human labels",
            "Regression testing: run on every change, track over time",
            "Offline + online (A/B, user feedback)",
            "Guard against judge bias, use pairwise comparisons where useful",
        ],
    },
    # ---------------- System design / production ----------------
    {
        "id": "sys-1", "category": "System Design", "difficulty": "hard",
        "type": "system_design",
        "question": "Design a production LLM API serving 1M requests/day with p95 latency < 2s and a tight cost budget. What are your key decisions?",
        "rubric": [
            "Caching (semantic + exact) to cut cost and latency",
            "Model routing: cheap model for easy, strong for hard",
            "Streaming responses for perceived latency",
            "Rate limiting, load balancing, fallback/failover between providers",
            "Observability: cost per request, latency, error rate, token usage",
            "Batching, async, timeouts, graceful degradation",
        ],
    },
    {
        "id": "sys-2", "category": "System Design", "difficulty": "medium",
        "type": "technical",
        "question": "How do you handle prompt versioning, testing, and safe rollout of prompt changes in production?",
        "rubric": [
            "Treat prompts as versioned artifacts (in code/registry)",
            "Eval suite runs on prompt changes (regression)",
            "Gradual rollout / A/B / canary",
            "Rollback plan, monitoring of quality metrics",
            "Separate prompt from code where it helps iteration",
        ],
    },
    # ---------------- FDE-specific / client-facing ----------------
    {
        "id": "fde-1", "category": "Forward Deployed", "difficulty": "medium",
        "type": "behavioral",
        "question": "As a Forward Deployed Engineer, a client insists on a feature you think is technically wrong for their use case. How do you handle it?",
        "rubric": [
            "Understand the underlying need behind the request (not just the ask)",
            "Communicate tradeoffs with data/examples, not opinion",
            "Propose an alternative that meets the real goal",
            "Balance client relationship with technical integrity",
            "Willingness to prototype/prove it; disagree and commit if needed",
        ],
    },
    {
        "id": "fde-2", "category": "Forward Deployed", "difficulty": "hard",
        "type": "behavioral",
        "question": "You're onsite with a client. Their data is messier than expected and the POC you promised in a week now looks impossible. What do you do?",
        "rubric": [
            "Communicate early and honestly with stakeholders",
            "Re-scope to a smaller demonstrable win (deliver value fast)",
            "Triage data issues; find the 20% that unblocks 80%",
            "Manage expectations while keeping momentum",
            "Document assumptions and a path to the full solution",
        ],
    },
    {
        "id": "fde-3", "category": "Forward Deployed", "difficulty": "medium",
        "type": "behavioral",
        "question": "Tell me about a time you had to learn a new technology or domain very quickly to deliver for a customer.",
        "rubric": [
            "Concrete situation with a real constraint/deadline (STAR format)",
            "Specific learning strategy (docs, prototyping, experts)",
            "Delivered outcome with measurable impact",
            "Reflection on what they'd do differently",
        ],
    },
    # ---------------- Coding / practical ----------------
    {
        "id": "code-1", "category": "Coding", "difficulty": "medium",
        "type": "coding",
        "question": "How would you implement a semantic cache for LLM responses? Describe the data structures and the similarity logic.",
        "rubric": [
            "Embed prompts into vectors",
            "Store (vector, response); on new query embed and find nearest neighbor",
            "Cosine similarity with a threshold to decide hit vs miss",
            "Vector index (flat for small, ANN like HNSW for scale)",
            "Handle staleness/invalidation, and false-positive risk of threshold",
        ],
    },
]


CATEGORIES = sorted({q["category"] for q in QUESTIONS})


def load_harvested():
    """Load web-harvested questions from data/harvested_questions.json if present."""
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "harvested_questions.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            qs = json.load(f).get("questions", [])
    except Exception:
        return []
    # normalize to the expected schema
    out = []
    for q in qs:
        if not q.get("question") or not q.get("rubric"):
            continue
        out.append({
            "id": q.get("id", "web"),
            "category": q.get("category", "LLM Fundamentals"),
            "difficulty": q.get("difficulty", "medium"),
            "type": q.get("type", "technical"),
            "question": q["question"],
            "rubric": q["rubric"],
            "source": q.get("source", "web"),
        })
    return out


def all_questions(include_web: bool = False, include_tailored: bool = False):
    """Return curated questions, optionally merged with harvested/tailored questions."""
    pool = list(QUESTIONS)
    if include_web:
        pool += load_harvested()
    if include_tailored:
        pool += load_tailored()
    return pool


def load_tailored():
    """Load JD/resume-tailored questions from data/tailored_questions.json."""
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "tailored_questions.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            qs = json.load(f).get("questions", [])
    except Exception:
        return []
    out = []
    for q in qs:
        if not q.get("question") or not q.get("rubric"):
            continue
        out.append({
            "id": q.get("id", "jd"),
            "category": q.get("category", "System Design"),
            "difficulty": q.get("difficulty", "medium"),
            "type": q.get("type", "technical"),
            "question": q["question"],
            "rubric": q["rubric"],
            "source": q.get("source", "tailored"),
        })
    return out


def categories(include_web: bool = False):
    return sorted({q["category"] for q in all_questions(include_web)})


def by_category(cat: str):
    return [q for q in QUESTIONS if q["category"] == cat]


def get(qid: str):
    return next((q for q in QUESTIONS if q["id"] == qid), None)
