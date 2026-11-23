"""
Step 1: writes made-up daily reports with Groq, from the rules only (no real reports are used or sent).

For each AI rule it asks for pairs: a good report, and the same report changed to break that one rule. A
second model then checks both. Run it again to continue after a stop or a Groq limit.

    python -m training.generate_examples --pairs 1     # quick try: 1 pair per rule
    python -m training.generate_examples               # about 25 pairs per rule
"""

import argparse
import json
import random
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # before checker.llm_checks reads GROQ_MODEL

from checker.llm_checks import llm_check  # noqa: E402
from checker.result import FAIL, PASS, SKIP  # noqa: E402
from checker.styles import load_styles  # noqa: E402

OUTPUT = Path("data/training/pairs.jsonl")
WRITER = "openai/gpt-oss-120b"
JUDGE = "qwen/qwen3.8-27b"  # must differ from the writer, or it only agrees with itself

# Different ways to break each rule, so the model doesn't learn just one
BREAKS = {
    "concrete_tasks": [
        "one finished task is vague about what was done",
        "one task for today is vague about what will be done",
        "most tasks only name a page or feature, without saying what changed",
    ],
    "status_or_result": [
        "one finished task has no status, PR number, link, check mark or other result",
        "none of the finished tasks has a status, PR number, link, check mark or other result",
    ],
    "overall_progress": ["nothing says how far the overall work is or what is left, only separate small tasks"],
    "clear_and_short": [
        "several lines repeat the same thing in almost the same words",
        "one task has far too much needless detail",
        "a long, confusing sentence makes it hard to see what was done",
    ],
    "terms_explained": [
        "it uses an uncommon abbreviation without explaining it",
        "it uses an unclear internal name or code word without explaining it",
    ],
    "real_blockers": [
        "Blockers says 'None', but a task mentions a problem that stops the work",
        "the blocker is too vague to act on",
    ],
}
NEEDS_NO_QUOTE = {"overall_progress"}  # broken by something missing, so there is nothing to quote

RAW_CODES = re.compile(r"\\n|U[0-9a-fA-F]{8}|\\u[0-9a-fA-F]{4}")

ROLES = ["frontend engineer", "backend engineer", "QA engineer", "mobile engineer", "data engineer", "designer", "project manager", "trainee engineer"]
TOPICS = ["an online shop", "a booking system", "a hospital records app", "a payroll tool", "a language learning app",
          "a delivery tracker", "a chat feature", "a reporting dashboard", "a school website", "an inventory system"]
LENGTHS = ["short (2-3 tasks)", "medium (4-6 tasks)", "long (7-9 tasks)"]
LAYOUTS = ["Markdown headings and bullets", "Slack style with emoji section titles and nested bullets", "plain text with simple dashes"]
FIRST_SECTIONS = ["Yesterday", "Weekend"]

PROMPT = """You write realistic, made-up daily work reports to train a checker.

Rule: {question}

Write two reports:
- "good" follows the rule.
- "broken" is the same report, changed only as much as needed to break the rule like this: {how}.

Writer: {role}. Work: {topic}. Length: {length}. Layout: {layout}.
Use the sections {first}, Today and Blockers. Today is the plan, so don't write finished work there.
Keep the formatting (bold, emoji, bullets) the same in both reports. Use invented names only, and no real companies, links or passwords.
Don't mention the rule, copy the examples in it, or say that a report is good or broken. Break it in a way that fits the topic.

Answer only with JSON in exactly this format:
{{"good": "the full good report", "good_reason": "one short sentence on why it follows the rule", "broken": "the full broken report", "broken_reason": "one short sentence on how it breaks the rule", "broken_quote": "the exact text in the broken report that breaks the rule{no_quote}"}}"""


def make_prompt(rule: dict, attempt: int) -> str:
    rng = random.Random(f"{rule['id']}-{attempt}")  # the same attempt always gets the same settings
    return PROMPT.format(
        question=rule["question"],
        how=rng.choice(BREAKS[rule["id"]]),
        role=rng.choice(ROLES),
        topic=rng.choice(TOPICS),
        length=rng.choice(LENGTHS),
        layout=rng.choice(LAYOUTS),
        first=rng.choice(FIRST_SECTIONS),
        no_quote="; here an empty string, because something is missing" if rule["id"] in NEEDS_NO_QUOTE else "",
    )


def formatting_changed(good: str, broken: str) -> bool:
    """
    Whether a line lost or gained bold, which would teach the model that formatting decides the verdict.
    """
    plain = {line.replace("*", "").strip(): line.strip() for line in good.splitlines()}
    lines = {line.replace("*", "").strip(): line.strip() for line in broken.splitlines()}
    return any(key in plain and plain[key].count("*") != line.count("*") for key, line in lines.items())


def problem_with(pair: dict, rule_id: str) -> str:
    """
    Why a pair can't be used, or an empty string if it's fine.
    """
    for key in ("good", "good_reason", "broken", "broken_reason"):
        if not isinstance(pair.get(key), str) or not pair[key].strip():
            return f"'{key}' is missing"
    if not isinstance(pair.get("broken_quote"), str):
        return "'broken_quote' is missing"
    if pair["good"].strip() == pair["broken"].strip():
        return "both reports are the same"
    if RAW_CODES.search(pair["good"] + pair["broken"]):
        return "it has raw codes instead of line breaks or emoji"
    if formatting_changed(pair["good"], pair["broken"]):
        return "the formatting changed too"
    quote = pair["broken_quote"].strip()
    if not quote and rule_id not in NEEDS_NO_QUOTE:
        return "there is no quote"
    if quote and quote not in pair["broken"]:
        return "the quote isn't in the broken report"
    return ""


class StopRun(Exception):
    pass


def judge_pair(pair: dict, rule: dict, client) -> dict:
    statuses = {}
    for key in ("good", "broken"):
        result = llm_check(pair[key], rule, model=JUDGE, client=client)
        if result.status == SKIP:  # a limit or connection problem, not an opinion
            raise StopRun(result.message)
        statuses[key] = result.status
    return statuses


def make_pair(rule: dict, attempt: int, client, writer: str = WRITER) -> dict:
    from groq import APIError, BadRequestError

    row = {"rule_id": rule["id"], "question": rule["question"], "attempt": attempt, "writer": writer}
    try:
        response = client.chat.completions.create(
            model=writer,
            messages=[{"role": "user", "content": make_prompt(rule, attempt)}],
            temperature=0.9,
            response_format={"type": "json_object"},
        )
        pair = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, BadRequestError) as e:  # Groq answers 400 when the model's JSON is broken
        if isinstance(e, BadRequestError) and "json" not in str(e).lower():
            raise StopRun(str(e)) from e
        return {**row, "kept": False, "why": "the answer isn't valid JSON"}
    except APIError as e:
        raise StopRun(str(e)) from e

    if not isinstance(pair, dict):
        return {**row, "kept": False, "why": "the answer isn't a JSON object"}
    if rule["id"] in NEEDS_NO_QUOTE:
        pair["broken_quote"] = ""
    row.update({key: pair.get(key) for key in ("good", "good_reason", "broken", "broken_reason", "broken_quote")})
    if why := problem_with(pair, rule["id"]):
        return {**row, "kept": False, "why": why}
    statuses = judge_pair(pair, rule, client)
    agreed = statuses == {"good": PASS, "broken": FAIL}
    return {**row, "judge": statuses, "kept": agreed, "why": "" if agreed else "the second model disagrees"}


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def generate(rules: list[dict], pairs: int, client, path: Path = OUTPUT, writer: str = WRITER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_rows(path)
    for rule in rules:
        mine = [row for row in rows if row["rule_id"] == rule["id"]]
        kept = sum(row["kept"] for row in mine)
        attempt = max((row["attempt"] for row in mine), default=0)
        while kept < pairs and attempt < pairs * 3:  # give up on a rule the models can't agree on
            attempt += 1
            row = make_pair(rule, attempt, client, writer)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += row["kept"]
            print(f"{rule['id']}: {kept}/{pairs}" + (f" (dropped: {row['why']})" if row["why"] else ""), flush=True)
        if kept < pairs:
            print(f"{rule['id']}: stopped at {kept}/{pairs} after {attempt} tries. Make the rule clearer.")


def ai_rules() -> list[dict]:
    return [rule for rule in load_styles()["daily_report"].rules if rule["check"] == "llm"]


if __name__ == "__main__":
    from groq import Groq

    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=25, help="good/broken pairs to keep per rule")
    parser.add_argument("--writer", default=WRITER, help="Groq model that writes the reports")
    parser.add_argument("--rule", help="only this rule, e.g. real_blockers")
    args = parser.parse_args()
    if args.writer == JUDGE:
        raise SystemExit("The writer must differ from the judge.")
    rules = [rule for rule in ai_rules() if args.rule in (None, rule["id"])]
    try:
        generate(rules, args.pairs, Groq(max_retries=8), writer=args.writer)
    except StopRun as e:
        raise SystemExit(f"Stopped: {e}\nEverything so far is saved. Run the same command again to continue.")
