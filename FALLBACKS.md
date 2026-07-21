# FALLBACKS.md — Issues faced while building the AI Interviewer

A running log of the real problems hit during development, why they happened,
and how each was resolved. Kept for transparency and to help anyone extending
the project.

---

## 1. Small local model produced malformed JSON (flaky evaluations)

**Symptom.** With `llama3.2:latest` (3B), the rubric evaluator intermittently
returned non-JSON or truncated JSON, so answers fell back to a neutral "5/10 –
evaluation model returned malformed output" score. Sometimes the same answer
scored fine, sometimes not.

**Cause.** Two things: (a) the model occasionally wrapped JSON in ``` fences or
added prose, and (b) long answers hit the `num_predict` cap and got truncated
mid-JSON.

**Fix.**
- Added a robust JSON extractor (`_extract_json`) that strips `<think>` blocks
  and code fences and finds the first balanced `{...}` block.
- Raised the token budget for JSON calls to 1200.
- Switched to **Ollama native constrained decoding** (`"format": "json"`) and
  OpenAI `response_format={"type":"json_object"}`. After this, a 5x stress test
  went from intermittent failures to **0/5 failures**.

---

## 2. Judge model too lenient (weak calibration)

**Symptom.** `llama3.2` rated an obviously vague answer 5/10 and hit the
malformed-output fallback often.

**Cause.** 3B models are weak graders and weak at strict structured output.

**Fix.** Downloaded and switched the default judge to **`qwen2.5:7b`**. Verified
it scores a vague RAG answer **2/10** and a strong one **7/10** with a
substantive critique. `llama3.2` documented as the faster/rougher fallback.

---

## 3. "I don't know" scored 5/10 instead of 0

**Symptom.** Typing "I dont know" produced a neutral 5 via the malformed-output
fallback, which is misleading, non-answers should score 0.

**Cause.** The empty-answer guard only caught empty strings, not phrases like
"idk", "not sure", "pass".

**Fix.** Added `_is_non_answer()` with a set of common non-answers; these now
score **0** with coaching feedback ("say what you DO know and reason out loud").

---

## 4. Live web search got rate-limited / blocked

**Symptom.** The harvester's DuckDuckGo HTML search returned 0 results after a
few calls; later it served an anti-bot challenge page. The built-in websearch
tool hit the same "anomaly challenge". Bing HTML returned a JS-only page with no
server-rendered result links.

**Cause.** DuckDuckGo/Bing throttle and fingerprint automated scraping by IP.

**Fix.**
- Fixed the DDG link regex first (results are protocol-relative
  `//duckduckgo.com/l/?uddg=...`, the original pattern required a single slash).
- Added a **curated seed-URL fallback** (reachable India-focused sources:
  AmbitionBox profiles, Simplilearn, GeeksforGeeks, Turing, DataCamp, plus a
  strong 2026 guide). When live search is blocked/thin, the harvester uses these
  so a good batch is always harvestable. `--no-seeds` disables it.

---

## 5. Harvest crash lost all progress

**Symptom.** A big harvest reached ~58 extracted questions, then Ollama threw an
`HTTP 500` (under thermal/load pressure) and the process died. The output file
still showed only the previous 7 because saving happened once at the very end.

**Cause.** Save-at-end design + an unhandled model error aborting the whole run.

**Fix.**
- **Incremental save after every page** (`_assign_ids_and_save`) so a crash
  never loses work.
- Wrapped `fetch_text` and `extract_questions` in try/except so one bad page
  logs and continues instead of aborting.
- On the next run the bank reached **85 questions** with nothing lost.

---

## 6. `ollama pull` killed by shell pipe (SIGPIPE)

**Symptom.** `ollama pull qwen2.5:7b | tail -3` appeared to "finish" instantly
and the model never showed up in `/api/tags`.

**Cause.** Piping the pull's progress output into `tail` closed the pipe and
sent SIGPIPE to the pull, terminating the download.

**Fix.** Run the pull **without a pipe**, redirecting to a log file
(`ollama pull qwen2.5:7b > /tmp/qwen_pull.log 2>&1`). Large model (~4.7 GB) then
downloaded fully.

---

## 7. Ollama server not staying up between calls

**Symptom.** `Connection refused` (Errno 61) from the LLM client after the
machine had been idle or `ollama serve` was killed.

**Cause.** No persistent Ollama daemon; earlier `pkill` also stopped it.

**Fix.** Each entry point checks `/api/tags` and starts `ollama serve` in the
background (`nohup`) if it's down. Documented `ollama serve` in the quickstart.

---

## 8. Reasoning model too slow / noisy for the "cheap" tier (sibling project)

**Note.** In the companion cost-optimizer project, `deepseek-r1:1.5b` emitted
long `<think>` blocks and took ~40s per hard prompt, making it a poor "fast"
tier. Relevant here because the interviewer's `_strip_think()` exists to remove
those `<think>...</think>` blocks if a reasoning model is ever used as the judge.

---

## 9. macOS has no `timeout` / long commands block the tool runner

**Symptom.** `timeout 180 python ...` failed with `timeout: command not found`;
long-running harvests/pulls exceeded the foreground command window.

**Cause.** `timeout` is a GNU coreutils tool, not present on stock macOS; and
interactive/long jobs shouldn't run in the foreground.

**Fix.** Ran long jobs as background tasks and polled for completion. For the
interactive interview, launched it in a real Terminal window via AppleScript
(`osascript`) so the user drives stdin directly.

---

## 10. Dashboard-style pitfalls carried as lessons

- **Multi-line stdin UX.** The CLI reads answers until a blank line; a naive
  single `input()` would truncate multi-sentence answers. Implemented an
  explicit multi-line reader with a `skip` sentinel.
- **Category filter vs web questions.** `--category` originally used
  `argparse` choices locked to curated categories, which rejected valid
  web/tailored categories. Relaxed to a free-form string.

---

_Last updated: 2026-07-21._
