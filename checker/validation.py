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
    "forbidden_phrases": "phrases",
    "must_contain": "phrases",
    "pattern": "pattern",
    "llm": "question",
}


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
        option = REQUIRED_OPTIONS.get(check)
        if option and not rule.get(option):
            problems.append(f"{label}: '{option}' is required.")
        if check == "pattern" and rule.get("pattern"):
            try:
                re.compile(rule["pattern"])
            except re.error as e:
                problems.append(f"{label}: the pattern is not a valid regular expression ({e}).")
        if check == "word_count" and rule.get("min") and rule.get("max") and rule["min"] > rule["max"]:
            problems.append(f"{label}: minimum is larger than maximum.")
    return problems
