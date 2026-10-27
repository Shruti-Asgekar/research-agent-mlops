"""Task-automation agent: web search -> three-bullet summary.

This is the Experiment 9 workflow, packaged as a reusable module for deployment.
Secrets are read from environment variables only; nothing is hard-coded.
"""
import logging
import os
import re
import time

from ddgs import DDGS
from langchain_openai import ChatOpenAI
from openai import OpenAI

# ---------------------------------------------------------------- configuration
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
MAX_TOPIC_CHARS = 200
PREFERRED_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                    "qwen/qwen3-32b", "openai/gpt-oss-120b"]
SKIP_WORDS = ("whisper", "orpheus", "guard", "tts", "compound", "allam")

# --------------------------------------------------------------------- logging
logger = logging.getLogger("research_agent")
if not logger.handlers:
    _handler = logging.StreamHandler()          # stdout/stderr -> platform logs
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

# --------------------------------------------------------------------- prompts
SYSTEM_PROMPT = ("You are a careful research assistant. Use ONLY the search results "
                 "provided. Do not invent facts.")
USER_PROMPT = ("Topic: {topic}\n\nSearch results:\n{raw}\n\n"
               "Write a research brief of EXACTLY three bullet points. Each bullet must be "
               "one clear sentence that states a distinct, current finding about the topic. "
               "Output only the three bullets, each starting with '- '. No title, no extra text.")

_BULLET_RE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+(.*\S)\s*$")
_model_cache = None


# --------------------------------------------------------------- small helpers
def get_api_key():
    """Read the API key from the environment (never from the source code)."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set. Provide it as an environment "
                           "variable or a platform secret.")
    return key


def get_model():
    """Return the chat model to use (env override, else auto-detect from the key)."""
    global _model_cache
    if _model_cache:
        return _model_cache
    forced = os.environ.get("LLM_MODEL", "").strip()
    if forced:
        _model_cache = forced
        return _model_cache
    client = OpenAI(api_key=get_api_key(), base_url=BASE_URL)
    available = [m.id for m in client.models.list().data]
    chosen = next((m for m in PREFERRED_MODELS if m in available), None)
    if chosen is None:
        chosen = next((m for m in available
                       if not any(w in m.lower() for w in SKIP_WORDS)), None)
    if chosen is None:
        raise RuntimeError("No usable chat model is available for this API key.")
    _model_cache = chosen
    logger.info("Model selected | %s", chosen)
    return chosen


def extract_bullets(text):
    """Return the bullet/numbered lines of `text` with their markers removed."""
    bullets = []
    for line in text.splitlines():
        match = _BULLET_RE.match(line)
        if match:
            bullets.append(match.group(1).strip())
    return bullets


def format_results(results):
    """Turn a list of search-result dicts into one block of plain text."""
    blocks = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        body = r.get("body", "")
        source = r.get("href") or r.get("url", "")
        blocks.append(f"[{i}] {title}\n{body}\nSource: {source}")
    return "\n\n".join(blocks)


# ------------------------------------------------------------ Stage 1: search
def search_web(topic, max_results=5):
    """Query DuckDuckGo for `topic` and return the raw results as text."""
    last_err = None
    for attempt in range(1, 4):                 # retry on temporary rate limits
        try:
            results = DDGS().text(topic, max_results=max_results)
            if not results:                     # fall back to news results
                results = DDGS().news(topic, max_results=max_results)
            if results:
                return format_results(results)
            last_err = "no results returned"
        except Exception as exc:                # noqa: BLE001
            last_err = exc
            logger.warning("Search attempt %d failed | %s", attempt, exc)
        time.sleep(3)
    raise RuntimeError(f"Web search failed after 3 tries: {last_err}")


# --------------------------------------------------------- Stage 2: summarize
def summarize(topic, raw_results, temperature=None):
    """Ask the LLM for exactly three bullet points; returns a list of strings."""
    llm = ChatOpenAI(model=get_model(),
                     temperature=TEMPERATURE if temperature is None else temperature,
                     api_key=get_api_key(), base_url=BASE_URL)
    messages = [("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT.format(topic=topic, raw=raw_results))]
    bullets = []
    for attempt in range(1, 4):                 # retry if the model breaks the format
        text = llm.invoke(messages).content
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        bullets = extract_bullets(text)
        if len(bullets) >= 3:
            return bullets[:3]                  # enforce exactly three
        logger.warning("Summary attempt %d returned %d bullets", attempt, len(bullets))
    return bullets


# --------------------------------------------------------- chained workflow
def research_brief(topic, progress=None):
    """Single entry point: topic in, three-bullet brief out (with timings)."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("Please enter a topic.")
    if len(topic) > MAX_TOPIC_CHARS:
        raise ValueError(f"Topic is too long (max {MAX_TOPIC_CHARS} characters).")
    say = progress or (lambda message: None)

    logger.info("Request received | topic=%r", topic)
    start = time.perf_counter()
    try:
        say("Stage 1/2: Searching the web ...")
        raw = search_web(topic)
        after_search = time.perf_counter()
        logger.info("Search finished | %.2fs", after_search - start)

        say("Stage 2/2: Summarizing the findings ...")
        bullets = summarize(topic, raw)
        end = time.perf_counter()
    except Exception:
        logger.exception("Request failed | topic=%r | after %.2fs",
                         topic, time.perf_counter() - start)
        raise

    result = {
        "topic": topic,
        "bullets": bullets,
        "raw": raw,
        "model": get_model(),
        "search_seconds": after_search - start,
        "summary_seconds": end - after_search,
        "total_seconds": end - start,
    }
    logger.info("Request completed | topic=%r | search=%.2fs | summarize=%.2fs | "
                "total=%.2fs | model=%s", topic, result["search_seconds"],
                result["summary_seconds"], result["total_seconds"], result["model"])
    return result
