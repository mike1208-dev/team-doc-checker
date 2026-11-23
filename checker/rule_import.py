"""
Drafts a document style (name, auto-detect words, rules) from a team's written rule document, using
Groq. The draft is always reviewed by an editor before it is saved.
"""

import json

from checker import llm_checks
from checker.styles import Style, slugify

MAX_CHARS = 12000

PROMPT = """You turn a team's written rules for one kind of document into rules for an automatic checker.

Check types you can use:
- required_sections: the document must have these section headings. Options: "sections": list of names; an item can be a list of accepted alternatives, e.g. ["Blockers", "Issues"].
- no_secrets: no API keys or passwords. No options.
- word_count: length limits. Options: "min" and/or "max" (numbers).
- long_sentences: warn about very long sentences. Options: "max_words" (number).
- forbidden_phrases: words that must not appear. Options: "phrases": list.
- must_contain: text that must appear. Options: "phrases": list.
- pattern: a regular expression that must (or must not) appear. Options: "pattern", "must": "match" or "not_match", "label": what it means.
- llm: a rule that needs understanding, asked as a yes/no question where "yes" means the rule is followed. Options: "question".

Prefer the simple check types; use llm only when a rule needs understanding.
Every rule needs "id" (lowercase letters, numbers and underscores), "title" (short, plain English) and "check".

Rule document:
\"\"\"
{text}
\"\"\"

Answer only with JSON in this format:
{{"name": "...", "description": "one sentence", "detect": ["words that suggest a document is this kind"], "rules": [{{"id": "...", "title": "...", "check": "...", "...options": "..."}}]}}"""


def draft_style(text: str, model: str = llm_checks.DEFAULT_MODEL, client=None) -> Style:
    client = client or llm_checks.default_client()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(text=text[:MAX_CHARS])}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    return Style.from_dict({**data, "id": slugify(data.get("name", "")) or "new_style"})
