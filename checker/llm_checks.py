"""
Checks that need understanding ("Is it clear?", "Does the summary match?"), answered by an LLM.

Two providers:
- groq:   Groq's cloud API. Free tier, needs GROQ_API_KEY, nothing to download.
- ollama: a local Ollama model. No API key, documents never leave the machine.
"""

import json
import os

from checker.result import FAIL, PASS, SKIP, WARN, CheckResult

PROVIDERS = ("groq", "ollama")
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
DEFAULT_MODELS = {
    "groq": os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
    "ollama": os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b"),
}
MAX_CHARS = 8000  # small models lose track of very long input

PROMPT = """You are reviewing a team document against ONE rule.

Rule: {question}

Document:
\"\"\"
{text}
\"\"\"

Answer only with JSON in exactly this format:
{{"verdict": "pass" | "fail" | "unsure", "reason": "one short sentence", "quote": "the exact text that breaks the rule, or an empty string"}}"""

VERDICTS = {"pass": PASS, "fail": FAIL}


class GroqClient:
    """
    Wraps the Groq SDK so it answers like ollama.Client.chat, letting llm_check use either one.
    """

    def __init__(self, client=None):
        if client is None:
            from groq import Groq

            client = Groq()  # reads GROQ_API_KEY
        self._client = client

    def chat(self, model, messages, format=None, options=None):
        kwargs = {"model": model, "messages": messages, "temperature": (options or {}).get("temperature", 0)}
        if format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        response = self._client.chat.completions.create(**kwargs)
        return {"message": {"content": response.choices[0].message.content}}


def _default_client(provider: str):
    if provider == "groq":
        return GroqClient()
    if provider == "ollama":
        import ollama

        return ollama.Client()  # uses OLLAMA_HOST, or http://localhost:11434
    raise ValueError(f"Unknown LLM provider '{provider}'. Use one of: {', '.join(PROVIDERS)}")


def llm_check(
    text: str, rule: dict, provider: str = DEFAULT_PROVIDER, model: str | None = None, client=None
) -> CheckResult:
    """
    rule.question: the rule written as a yes/no question for the model.
    """
    truncated = len(text) > MAX_CHARS
    prompt = PROMPT.format(question=rule.get("question", rule.get("title", "")), text=text[:MAX_CHARS])
    try:
        client = client or _default_client(provider)
        response = client.chat(
            model=model or DEFAULT_MODELS[provider],
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0},
        )
        answer = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return CheckResult.from_rule(rule, WARN, message="The AI gave an unreadable answer. Check this rule by hand.")
    except Exception as e:  # no API key, rate limit, Ollama not running, model not pulled, ...
        return CheckResult.from_rule(rule, SKIP, message=f"AI check skipped: {e}")

    status = VERDICTS.get(str(answer.get("verdict", "")).lower(), WARN)
    message = str(answer.get("reason", "")).strip()
    if truncated:
        message += f" (Only the first {MAX_CHARS} characters were checked.)"
    quote = str(answer.get("quote", "")).strip()
    where = f'"{quote[:80]}"' if quote and status != PASS else ""
    return CheckResult.from_rule(rule, status, where=where, message=message)
