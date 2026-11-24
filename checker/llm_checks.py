"""
Checks that need understanding ("Is it clear?", "Does the summary match?"), answered by an LLM: through
Groq's cloud API (free tier, needs GROQ_API_KEY) or a small model inside the app (see local_model.py).
"""

import json
import os
import re

from checker import local_model
from checker.result import FAIL, PASS, SKIP, WARN, CheckResult

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
# Models offered in the app's dropdown (all tested on Groq). When Groq retires or adds models,
# override with GROQ_MODELS="model-a,model-b" in .env / Secrets instead of changing code.
MODELS = list(
    dict.fromkeys(
        [DEFAULT_MODEL]
        + [m.strip() for m in os.getenv("GROQ_MODELS", "qwen/qwen3.8-27b,openai/gpt-oss-20b,openai/gpt-oss-120b").split(",") if m.strip()]
    )
)
MAX_CHARS = 8000  # models lose track of very long input
MAX_ANSWER_TOKENS = 300  # without a cap, Groq reserves more than some models' limit per minute

# The document comes before the rule, so the local model reads it once and reuses it for the next rules.
# The local model is trained on this exact prompt: after a change, rebuild the dataset and train again.
PROMPT = """You are reviewing a team document against ONE rule.

Document:
\"\"\"
{text}
\"\"\"

Rule: {question}

Answer only with JSON in exactly this format:
{{"verdict": "pass" | "fail" | "unsure", "reason": "one short sentence", "quote": "the exact text that breaks the rule, or an empty string"}}"""

VERDICTS = {"pass": PASS, "fail": FAIL}
QUOTED_TERM = re.compile(r"['‘\"“]([^'’\"”]+)['’\"”]")
CAPITAL_TERM = re.compile(r"\b[A-Z][A-Za-z0-9+.#/]*[A-Z0-9+][A-Za-z0-9+#/]*")


def only_known_terms(known: list[str], reason: str, quote: str) -> bool:
    """
    Whether every term the AI complains about is a known one. Without a clear term it's False, so the fail stays.
    """
    named = QUOTED_TERM.findall(reason) or CAPITAL_TERM.findall(reason) or ([quote] if quote else [])
    known = {term.lower() for term in known}

    def is_known(text: str) -> bool:
        text = text.strip(" .,:;-*`").lower()
        return text in known or text.removesuffix("s") in known

    return bool(named) and all(is_known(term) or all(is_known(word) for word in term.split()) for term in named if term.strip())


def default_client(model: str = DEFAULT_MODEL):
    if model == local_model.MODEL_ID:
        return local_model.get_client()
    from groq import Groq

    return Groq()  # reads GROQ_API_KEY


def token_cap(model: str, tokens: int = MAX_ANSWER_TOKENS) -> dict:
    """
    gpt-oss models think before they answer, which a small cap would cut off.
    """
    return {} if model.startswith("openai/gpt-oss") else {"max_completion_tokens": tokens}


def llm_check(text: str, rule: dict, model: str = DEFAULT_MODEL, client=None) -> CheckResult:
    """
    rule.question: the rule written as a yes/no question for the model.
    rule.known_terms: terms that are never a problem, so a fail that is only about them becomes a pass.
    """
    truncated = len(text) > MAX_CHARS
    prompt = PROMPT.format(question=rule.get("question", rule.get("title", "")), text=text[:MAX_CHARS])
    try:
        client = client or default_client(model)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
            **token_cap(model),
        )
        content = response.choices[0].message.content
    except Exception as e:  # no API key, rate limit, model retired, model file missing, ...
        return CheckResult.from_rule(rule, SKIP, message=f"AI check skipped: {e}")

    try:
        answer = json.loads(content or "", strict=False)  # the local model may put a line break inside a quote
    except json.JSONDecodeError:
        answer = None
    if not isinstance(answer, dict):
        return CheckResult.from_rule(rule, WARN, message="The AI gave an unreadable answer. Check this rule by hand.")

    status = VERDICTS.get(str(answer.get("verdict", "")).lower(), WARN)
    message = str(answer.get("reason") or "").strip()
    if status == FAIL and only_known_terms(rule.get("known_terms") or [], message, str(answer.get("quote") or "")):
        status, message = PASS, "The AI only named terms that are on the known terms list."
    if truncated:
        message += f" (Only the first {MAX_CHARS} characters were checked.)"
    quote = str(answer.get("quote") or "").strip()
    where = f'"{quote[:80]}"' if quote and status != PASS else ""
    return CheckResult.from_rule(rule, status, where=where, message=message)
