"""
Checks that need understanding ("Is it clear?", "Does the summary match?"), answered by an LLM: through
Groq's cloud API (free tier, needs GROQ_API_KEY) or a small model inside the app (see local_model.py).
"""

import json
import os

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

PROMPT = """You are reviewing a team document against ONE rule.

Rule: {question}

Document:
\"\"\"
{text}
\"\"\"

Answer only with JSON in exactly this format:
{{"verdict": "pass" | "fail" | "unsure", "reason": "one short sentence", "quote": "the exact text that breaks the rule, or an empty string"}}"""

VERDICTS = {"pass": PASS, "fail": FAIL}


def default_client(model: str = DEFAULT_MODEL):
    if model == local_model.MODEL_ID:
        return local_model.get_client()
    from groq import Groq

    return Groq()  # reads GROQ_API_KEY


def llm_check(text: str, rule: dict, model: str = DEFAULT_MODEL, client=None) -> CheckResult:
    """
    rule.question: the rule written as a yes/no question for the model.
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
        )
        answer = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return CheckResult.from_rule(rule, WARN, message="The AI gave an unreadable answer. Check this rule by hand.")
    except Exception as e:  # no API key, rate limit, model retired, model file missing, ...
        return CheckResult.from_rule(rule, SKIP, message=f"AI check skipped: {e}")

    status = VERDICTS.get(str(answer.get("verdict", "")).lower(), WARN)
    message = str(answer.get("reason", "")).strip()
    if truncated:
        message += f" (Only the first {MAX_CHARS} characters were checked.)"
    quote = str(answer.get("quote", "")).strip()
    where = f'"{quote[:80]}"' if quote and status != PASS else ""
    return CheckResult.from_rule(rule, status, where=where, message=message)
