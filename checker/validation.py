"""
Checks that a style is safe to save: rules edited in the app must not break the checker.
"""

import re

from checker.basic_checks import CHECKS
from checker.styles import Style

CHECK_TYPES = [*CHECKS, "llm"]
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")
REQUIRED_OPTIONS = {
    "required_sections": "sections",
    "working_hours": "sections",
    "labelled_line": "sections",
    "forbidden_phrases": "phrases",
    "must_contain": "phrases",
    "pattern": "pattern",
    "llm": "question",
}
NUMBER_OPTIONS = {  # option: smallest allowed value
    "word_count": {"min": 0, "max": 0},
    "long_sentences": {"max_words": 5},
    "mention_at_top": {"lines": 1},
}
TEXT_OPTIONS = {"pattern": ("pattern", "label"), "llm": ("question",)}


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_list_of_text(value, alternatives: bool = False) -> bool:
    return isinstance(value, list) and all(
        _is_text(item) or (alternatives and bool(item) and _is_list_of_text(item)) for item in value
    )


def _is_number(value, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _option_problems(rule: dict) -> list[str]:
    check, problems = rule["check"], []
    if rule.get("title") and not _is_text(rule["title"]):
        problems.append("the title must be text.")
    required = REQUIRED_OPTIONS.get(check)
    if required and not rule.get(required):
        problems.append(f"'{required}' is required.")
    elif required in ("sections", "phrases") and not _is_list_of_text(rule[required], alternatives=required == "sections"):
        problems.append(f"'{required}' must be a list of text.")
    for option in TEXT_OPTIONS.get(check, ()):
        if rule.get(option) and not _is_text(rule[option]):
            problems.append(f"'{option}' must be text.")
    if check == "labelled_line" and not (rule.get("labels") and _is_list_of_text(rule["labels"])):
        problems.append("'labels' must be a list of text.")
    if rule.get("known_terms") and not _is_list_of_text(rule["known_terms"]):
        problems.append("'known_terms' must be a list of text.")
    numbers = NUMBER_OPTIONS.get(check, {})
    wrong = [option for option, minimum in numbers.items() if option in rule and not _is_number(rule[option], minimum)]
    problems += [f"'{option}' must be a whole number, {numbers[option]} or more." for option in wrong]
    if check == "word_count" and not wrong and rule.get("min") and rule.get("max") and rule["min"] > rule["max"]:
        problems.append("minimum is larger than maximum.")
    if check == "pattern" and _is_text(rule.get("pattern")):
        try:
            re.compile(rule["pattern"])
        except re.error as e:
            problems.append(f"the pattern is not a valid regular expression ({e}).")
    return problems


def validate_style(style: Style) -> list[str]:
    """
    Returns a list of problems in plain English; an empty list means the style is fine.
    """
    problems = []
    if not ID_PATTERN.match(style.id or ""):
        problems.append("Style ID must use lowercase letters, numbers, - or _ (e.g. daily_report).")
    if not str(style.name).strip():
        problems.append("Style name is required.")
    if not style.rules:
        problems.append("Add at least one rule.")

    seen = set()
    for number, rule in enumerate(style.rules, start=1):
        label = f"Rule {number} ({rule.get('title') or rule.get('id') or 'untitled'})"
        rule_id = str(rule.get("id", ""))
        if not ID_PATTERN.match(rule_id):
            problems.append(f"{label}: ID must use lowercase letters, numbers, - or _.")
        elif rule_id in seen:
            problems.append(f"{label}: ID '{rule_id}' is used twice.")
        seen.add(rule_id)

        check = rule.get("check")
        if check not in CHECK_TYPES:
            problems.append(f"{label}: unknown check type '{check}'.")
            continue
        problems += [f"{label}: {problem}" for problem in _option_problems(rule)]
    return problems
