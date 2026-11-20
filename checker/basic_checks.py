"""
Checks done with plain Python: fast, free and always give the same answer.
Each check takes (text, rule) and returns a CheckResult. Register new ones in CHECKS.
"""

import re

from checker.result import FAIL, PASS, WARN, CheckResult

# (name, pattern, status). Known token formats are a FAIL; "password: ..." style lines are only a WARN
SECRET_PATTERNS = [
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), FAIL),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), FAIL),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), FAIL),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), FAIL),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), FAIL),
    ("Private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), FAIL),
    (
        "Password or key value",
        re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?[^\s'\"]{6,}"),
        WARN,
    ),
]


def _normalize_heading(line: str) -> str:
    # "## 1. Done:", "**Done**", "Done:" -> "done"
    line = re.sub(r"^#+\s*", "", line.strip())
    line = re.sub(r"^\d+[.)]\s*", "", line)
    line = line.strip("*_ ").rstrip(":").strip("*_ ")
    return line.lower()


def _content_lines(text: str):
    """
    Yields (line_number, line), skipping code blocks and tables so they don't count as prose.
    """
    in_code = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.strip().startswith("|"):
            continue
        yield number, line


def required_sections(text: str, rule: dict) -> CheckResult:
    """
    rule.sections: list of section names. An item can also be a list of accepted alternatives,
    e.g. ["Blockers", "Issues"].
    """
    lines = [_normalize_heading(line) for line in text.splitlines()]
    missing = []
    for section in rule.get("sections", []):
        names = [section] if isinstance(section, str) else section
        found = any(
            line == name.lower() or line.startswith(name.lower() + ":") for line in lines for name in names
        )
        if not found:
            missing.append(" / ".join(names))
    if missing:
        return CheckResult.from_rule(rule, FAIL, message=f"Missing section(s): {', '.join(missing)}. Add a heading for each.")
    return CheckResult.from_rule(rule, PASS)


def no_secrets(text: str, rule: dict) -> CheckResult:
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for name, pattern, status in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append((number, name, status))
                break
    if not hits:
        return CheckResult.from_rule(rule, PASS)
    # The secret itself is never repeated in the report
    status = FAIL if any(status == FAIL for _, _, status in hits) else WARN
    where = ", ".join(f"line {number}" for number, _, _ in hits[:5])
    kinds = sorted({name for _, name, _ in hits})
    return CheckResult.from_rule(rule, status, where=where, message=f"Looks like: {', '.join(kinds)}. Remove it before sharing.")


def word_count(text: str, rule: dict) -> CheckResult:
    """
    rule.min / rule.max: allowed number of words (both optional).
    """
    words = len(text.split())
    minimum, maximum = rule.get("min"), rule.get("max")
    if minimum is not None and words < minimum:
        return CheckResult.from_rule(rule, FAIL, message=f"{words} words; at least {minimum} expected. Add more detail.")
    if maximum is not None and words > maximum:
        return CheckResult.from_rule(rule, FAIL, message=f"{words} words; at most {maximum} allowed. Shorten it.")
    return CheckResult.from_rule(rule, PASS, message=f"{words} words")


def long_sentences(text: str, rule: dict) -> CheckResult:
    """
    rule.max_words: longest allowed sentence (default 35). Long sentences are a WARN, not a FAIL.
    """
    limit = rule.get("max_words", 35)
    long_ones = []
    for number, line in _content_lines(text):
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if len(sentence.split()) > limit:
                long_ones.append(number)
    if not long_ones:
        return CheckResult.from_rule(rule, PASS)
    where = ", ".join(f"line {n}" for n in sorted(set(long_ones))[:5])
    return CheckResult.from_rule(
        rule, WARN, where=where, message=f"{len(long_ones)} sentence(s) longer than {limit} words. Split them."
    )


def forbidden_phrases(text: str, rule: dict) -> CheckResult:
    """
    rule.phrases: words that must not appear (case-insensitive), e.g. TODO, TBD.
    """
    phrases = rule.get("phrases", [])
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for phrase in phrases:
            if re.search(rf"(?i)\b{re.escape(phrase)}\b", line):
                hits.append((number, phrase))
    if not hits:
        return CheckResult.from_rule(rule, PASS)
    where = ", ".join(f"line {number}" for number, _ in hits[:5])
    found = sorted({phrase for _, phrase in hits})
    return CheckResult.from_rule(rule, FAIL, where=where, message=f"Found: {', '.join(found)}. Replace with real content.")


CHECKS = {
    "required_sections": required_sections,
    "no_secrets": no_secrets,
    "word_count": word_count,
    "long_sentences": long_sentences,
    "forbidden_phrases": forbidden_phrases,
}
