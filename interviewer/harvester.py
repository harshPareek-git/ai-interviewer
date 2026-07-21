"""Web harvester: scans the internet for real interview questions (India-focused
sources like AmbitionBox/Glassdoor India plus 2026 AI-eng guides), uses the LLM
to extract questions and auto-generate scoring rubrics, dedupes, and writes them
into data/harvested_questions.json for the interviewer to load.

Usage:
  python -m interviewer.harvester --max-pages 6
  python -m interviewer.harvester --query "Forward Deployed Engineer interview India"

Pure-Python networking (urllib) so it works without extra deps. Search uses the
DuckDuckGo HTML endpoint; fetch uses a simple readable-text extractor.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interviewer.llm import LLM  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUT_PATH = os.path.join(DATA_DIR, "harvested_questions.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# India-focused default searches for AI Engineer / FDE roles.
DEFAULT_QUERIES = [
    "AI Engineer interview questions India AmbitionBox",
    "Machine Learning Engineer interview questions India Glassdoor",
    "LLM RAG interview questions asked 2026",
    "Forward Deployed Engineer interview questions",
    "GenAI engineer interview questions India experienced",
]


# --------------------------------------------------------------------------
# networking
# --------------------------------------------------------------------------
def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return raw.decode("latin-1", errors="ignore")


def ddg_search(query: str, max_results: int = 6) -> List[str]:
    """Return result URLs from DuckDuckGo's HTML endpoint."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        page = _get(url)
    except Exception as e:
        print(f"  ! search failed for '{query}': {e}")
        return []
    # result links look like //duckduckgo.com/l/?uddg=<encoded real url>
    links = re.findall(r'href="((?://duckduckgo\.com)?/l/\?uddg=[^"]+)"', page)
    urls = []
    for l in links:
        m = re.search(r"uddg=([^&]+)", l)
        if not m:
            continue
        real = urllib.parse.unquote(m.group(1))
        if real.startswith("http") and real not in urls:
            urls.append(real)
    # also catch direct result__a hrefs as a fallback
    if not urls:
        urls = [u for u in re.findall(r'href="(https?://[^"]+)"', page)
                if "duckduckgo" not in u][:max_results]
    return urls[:max_results]


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def fetch_text(url: str, timeout: int = 20) -> str:
    """Very small readable-text extractor: strip scripts/styles/tags."""
    try:
        page = _get(url, timeout=timeout)
    except Exception as e:
        print(f"  ! fetch failed {url}: {e}")
        return ""
    page = re.sub(r"<script.*?</script>", " ", page, flags=re.DOTALL | re.IGNORECASE)
    page = re.sub(r"<style.*?</style>", " ", page, flags=re.DOTALL | re.IGNORECASE)
    page = re.sub(r"<(br|/p|/div|/li|/h[1-6])\s*>", "\n", page, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", page)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = _WS_RE.sub("\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# LLM extraction
# --------------------------------------------------------------------------
EXTRACT_SYSTEM = (
    "You extract real technical/behavioral interview questions for AI Engineer "
    "and Forward Deployed Engineer roles from messy web page text. Ignore "
    "navigation, ads, and unrelated content. Only keep genuine interview "
    "questions relevant to AI/ML/LLM engineering or client-facing FDE work."
)

EXTRACT_TEMPLATE = """From the PAGE TEXT below, extract up to {k} distinct real \
interview questions relevant to an AI Engineer / Forward Deployed Engineer role.

For EACH question produce an object with:
- "question": the question text, cleaned up into one clear sentence
- "category": one of [LLM Fundamentals, RAG, Agents, Evaluation, System Design, \
Fine-tuning, MLOps, Coding, Behavioral, Forward Deployed, ML Fundamentals]
- "difficulty": one of [easy, medium, hard]
- "rubric": a list of 3-5 short key points a strong 4+ YOE answer should cover

Return ONLY a JSON object: {{"questions": [ ... ]}}. No commentary.

PAGE TEXT:
\"\"\"{text}\"\"\""""


def extract_questions(llm: LLM, text: str, k: int = 8) -> List[Dict]:
    if len(text) < 200:
        return []
    # cap text to keep the local model happy
    snippet = text[:6000]
    result = llm.chat_json(EXTRACT_SYSTEM,
                           EXTRACT_TEMPLATE.format(k=k, text=snippet),
                           temperature=0.2)
    qs = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(qs, list):
        return []
    cleaned = []
    for q in qs:
        if not isinstance(q, dict):
            continue
        qt = str(q.get("question", "")).strip()
        if len(qt) < 12:
            continue
        rubric = q.get("rubric")
        if not isinstance(rubric, list) or not rubric:
            rubric = ["Correct, specific, and practical explanation",
                      "Mentions real-world tradeoffs", "Gives a concrete example"]
        cleaned.append({
            "question": qt,
            "category": str(q.get("category", "LLM Fundamentals")).strip() or "LLM Fundamentals",
            "difficulty": (str(q.get("difficulty", "medium")).strip().lower()
                           if str(q.get("difficulty", "")).strip().lower() in
                           ("easy", "medium", "hard") else "medium"),
            "type": "technical",
            "rubric": [str(x).strip() for x in rubric[:6] if str(x).strip()],
        })
    return cleaned


# --------------------------------------------------------------------------
# dedupe + persistence
# --------------------------------------------------------------------------
def _norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()


def load_existing() -> List[Dict]:
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH) as f:
                return json.load(f).get("questions", [])
        except Exception:
            return []
    return []


def save(questions: List[Dict], sources: List[str]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"count": len(questions), "sources": sources,
                   "questions": questions}, f, indent=2)


def harvest(queries: List[str], max_pages: int, per_page: int,
            append: bool = True) -> Dict:
    llm = LLM()
    print(f"Harvesting interview questions  (model={llm.model})")
    existing = load_existing() if append else []
    seen = {_norm(q["question"]) for q in existing}
    collected = list(existing)
    sources: List[str] = []

    urls: List[str] = []
    for q in queries:
        print(f"• search: {q}")
        for u in ddg_search(q, max_results=4):
            if u not in urls:
                urls.append(u)
    urls = urls[:max_pages]
    print(f"  -> {len(urls)} pages to scan")

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        text = fetch_text(url)
        if not text:
            continue
        qs = extract_questions(llm, text, k=per_page)
        added = 0
        for q in qs:
            key = _norm(q["question"])
            if key in seen:
                continue
            seen.add(key)
            q["source"] = url
            collected.append(q)
            added += 1
        if added:
            sources.append(url)
        print(f"    +{added} new questions (total {len(collected)})")

    # assign stable ids
    for idx, q in enumerate(collected):
        q.setdefault("id", f"web-{idx+1}")
    save(collected, sources)
    print(f"\nSaved {len(collected)} questions to {os.path.relpath(OUT_PATH)}")
    return {"total": len(collected), "new_sources": sources}


def main():
    ap = argparse.ArgumentParser(description="Harvest real interview questions from the web")
    ap.add_argument("--query", action="append", help="custom search query (repeatable)")
    ap.add_argument("--max-pages", type=int, default=6, help="max pages to scan")
    ap.add_argument("--per-page", type=int, default=8, help="max questions per page")
    ap.add_argument("--fresh", action="store_true", help="ignore existing harvested file")
    args = ap.parse_args()
    queries = args.query if args.query else DEFAULT_QUERIES
    harvest(queries, args.max_pages, args.per_page, append=not args.fresh)


if __name__ == "__main__":
    main()
