import json
from types import SimpleNamespace

import pytest

from checker.basic_checks import CHECKS
from checker.loader import read_document
from checker.report import run_checks, summary, to_markdown
from checker.result import FAIL, PASS, SKIP, WARN
from checker.styles import Style, guess_style, load_styles

DAILY_REPORT = """# Daily report
## Done
- Fixed the login bug on the settings page.
## Next
- Write tests for the login flow.
## Blockers
- None.
"""


class FakeClient:
    """Stands in for groq.Groq so tests don't need an API key or network."""

    def __init__(self, content=None, error=None):
        self.content, self.error = content, error
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture(scope="module")
def styles():
    return load_styles()


def test_every_rule_file_loads_and_uses_known_checks(styles):
    assert {"daily_report", "issue_pr", "work_plan"} <= set(styles)
    for style in styles.values():
        assert style.rules, f"{style.id} has no rules"
        for rule in style.rules:
            assert "id" in rule, f"{style.id}: rule without id"
            assert rule.get("check") in {*CHECKS, "llm"}, f"{style.id}/{rule['id']}: unknown check"
            if rule["check"] == "llm":
                assert rule.get("question"), f"{style.id}/{rule['id']}: llm rule needs a question"


def test_guess_style(styles):
    assert guess_style(DAILY_REPORT, styles).id == "daily_report"
    assert guess_style("## Changes\n- x\n## Testing\nCloses #12", styles).id == "issue_pr"
    assert guess_style("hello world", styles) is None


def test_run_checks_without_ai(styles):
    results = run_checks(DAILY_REPORT, styles["daily_report"], use_llm=False)
    by_id = {r.rule_id: r for r in results}
    assert by_id["has_sections"].status == PASS
    assert by_id["specific"].status == SKIP
    assert summary(results).endswith("(1 skipped)")


@pytest.mark.parametrize(
    "client, expected",
    [
        (FakeClient(json.dumps({"verdict": "pass", "reason": "ok", "quote": ""})), PASS),
        (FakeClient(json.dumps({"verdict": "fail", "reason": "vague", "quote": "worked on stuff"})), FAIL),
        (FakeClient(json.dumps({"verdict": "unsure", "reason": "?", "quote": ""})), WARN),
        (FakeClient("not json"), WARN),
        (FakeClient(error=ConnectionError("Groq is unreachable")), SKIP),
    ],
)
def test_llm_rule_results(client, expected):
    style = Style(id="t", name="Test", rules=[{"id": "clear", "check": "llm", "question": "Is it clear?"}])
    [result] = run_checks("Some text.", style, client=client)
    assert result.status == expected


def test_unknown_check_is_skipped_not_crashed():
    style = Style(id="t", name="Test", rules=[{"id": "x", "check": "spellcheck"}])
    [result] = run_checks("text", style, use_llm=False)
    assert result.status == SKIP


def test_markdown_report():
    style = Style(id="t", name="Test", rules=[{"id": "p", "check": "forbidden_phrases", "phrases": ["TBD"]}])
    report = to_markdown(run_checks("a | b TBD", style), "Test", "doc.md")
    assert "# Check report: doc.md" in report
    assert "0 / 1 rules passed" in report


def test_read_markdown_and_unsupported():
    assert read_document("a.md", "﻿# Title".encode("utf-8")) == "# Title"
    with pytest.raises(ValueError):
        read_document("a.xlsx", b"")


def test_read_docx_keeps_headings():
    docx = pytest.importorskip("docx")
    import io

    document = docx.Document()
    document.add_heading("Done", level=2)
    document.add_paragraph("Fixed the login bug.")
    buffer = io.BytesIO()
    document.save(buffer)
    assert read_document("a.docx", buffer.getvalue()) == "## Done\nFixed the login bug."


def test_llm_check_asks_groq_for_json():
    client = FakeClient(json.dumps({"verdict": "pass", "reason": "ok", "quote": ""}))
    style = Style(id="t", name="Test", rules=[{"id": "clear", "check": "llm", "question": "Is it clear?"}])
    run_checks("Some text.", style, model="m", client=client)
    assert client.calls[0]["model"] == "m"
    assert client.calls[0]["response_format"] == {"type": "json_object"}


def test_missing_groq_package_or_key_is_skipped(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    style = Style(id="t", name="Test", rules=[{"id": "clear", "check": "llm", "question": "Is it clear?"}])
    [result] = run_checks("Some text.", style)
    assert result.status == SKIP
