"""
Runs the Streamlit pages headlessly with an in-memory database, so UI errors show up in tests.
"""

import pytest
from streamlit.testing.v1 import AppTest

import checker.store
from checker.store import YamlStore
from checker.styles import Style


class MemoryStore:
    editable = True
    label = "test database"

    def __init__(self):
        self.styles, self.rows = {}, []

    def list_styles(self):
        return dict(self.styles)

    def save_style(self, style, editor):
        if style.id in self.styles:
            self.rows.insert(0, {**self.styles[style.id].to_dict(), "style_id": style.id, "history_id": len(self.rows) + 1,
                                 "action": "update", "archived_at": "2026-11-20T10:00:00", "updated_by": editor})
        self.styles[style.id] = Style.from_dict(style.to_dict())

    def delete_style(self, style_id):
        self.styles.pop(style_id)

    def history(self, limit=50):
        return self.rows

    def restore(self, row, editor):
        self.save_style(Style.from_dict({**row, "id": row["style_id"]}), editor)


@pytest.fixture
def memory_store(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(checker.store, "get_store", lambda: store)
    monkeypatch.setenv("EDITOR_PASSWORD", "secret")
    return store


def test_check_page_runs_rule_checks(monkeypatch):
    monkeypatch.setattr(checker.store, "get_store", lambda: YamlStore())
    at = AppTest.from_file("../views/check.py", default_timeout=30).run()
    at.sidebar.toggle[0].set_value(False).run()
    next(b for b in at.button if b.label == "Try an example").click().run()
    next(b for b in at.button if b.label == "Check daily report").click().run()
    assert not at.exception
    # The example has all sections and tags the reviewer, but gives no hours for Today
    assert [m.value for m in at.metric] == ["2", "1", "0", "6"]
    assert any("2 / 3 rules passed" in m.value for m in at.markdown)

    # A new check that can't run must not leave the old result on the page
    at.text_area[0].input("").run()
    next(b for b in at.button if b.label == "Check daily report").click().run()
    assert at.warning and not at.metric


def test_check_page_offers_the_local_model_only_when_configured(monkeypatch):
    monkeypatch.setattr(checker.store, "get_store", lambda: YamlStore())
    for name in ("LOCAL_MODEL_PATH", "LOCAL_MODEL_REPO", "LOCAL_MODEL_FILE"):
        monkeypatch.delenv(name, raising=False)
    at = AppTest.from_file("../views/check.py", default_timeout=30).run()
    options = list(at.sidebar.selectbox[0].options)
    assert all(option.startswith("Groq") for option in options)

    monkeypatch.setenv("LOCAL_MODEL_PATH", "model.gguf")
    monkeypatch.setenv("LOCAL_MODEL_LABEL", "Test model")
    at = AppTest.from_file("../views/check.py", default_timeout=30).run()
    assert list(at.sidebar.selectbox[0].options) == [*options, "Test model"]


def test_manage_page_needs_the_password(memory_store):
    at = AppTest.from_file("../views/manage_rules.py", default_timeout=30).run()
    assert not at.exception
    at.text_input[0].input("wrong")
    at.text_input[1].input("Mike")
    at.button[0].click().run()
    assert any("Wrong password" in e.value for e in at.error)


def test_manage_page_loads_examples_edits_and_restores(memory_store):
    at = AppTest.from_file("../views/manage_rules.py", default_timeout=30).run()
    at.text_input[0].input("secret")
    at.text_input[1].input("Mike")
    at.button[0].click().run()
    assert not at.exception

    # Empty database -> load the example rules
    next(b for b in at.button if b.label.startswith("Load the example rules")).click().run()
    assert set(memory_store.styles) == {"daily_report", "issue_pr", "work_plan"}

    # Open a style, rename it and save
    at.selectbox(key="style_choice").set_value("daily_report").run()
    name_box = next(t for t in at.text_input if t.label == "Name")
    name_box.input("Daily report v2").run()
    next(b for b in at.button if b.label == "💾 Save style").click().run()
    assert not at.exception
    assert memory_store.styles["daily_report"].name == "Daily report v2"
    assert memory_store.rows[0]["name"] == "Daily report"  # old version kept in history

    # Restore the old version from History
    next(b for b in at.button if b.label == "↩️ Restore this version").click().run()
    assert memory_store.styles["daily_report"].name == "Daily report"


def test_manage_page_replaces_old_rules_with_the_built_in_ones(memory_store):
    memory_store.styles["daily_report"] = Style(id="daily_report", name="Old", rules=[{"id": "old", "check": "no_secrets"}])
    at = AppTest.from_file("../views/manage_rules.py", default_timeout=30).run()
    at.text_input[0].input("secret")
    at.text_input[1].input("Mike")
    at.button[0].click().run()
    at.selectbox(key="style_choice").set_value("daily_report").run()
    next(b for b in at.button if b.label == "Yes, replace them").click().run()
    assert not at.exception
    assert len(memory_store.styles["daily_report"].rules) == 9
    assert memory_store.rows[0]["name"] == "Old"


def test_manage_page_creates_a_new_style(memory_store):
    at = AppTest.from_file("../views/manage_rules.py", default_timeout=30).run()
    at.text_input[0].input("secret")
    at.text_input[1].input("Mike")
    at.button[0].click().run()

    next(t for t in at.text_input if t.label == "Name").input("Meeting notes").run()
    next(b for b in at.button if b.label == "➕ Add rule").click().run()  # first type in the list: required_sections
    next(t for t in at.text_input if t.label == "Title (shown in the report)").input("Has attendees").run()
    next(t for t in at.text_area if t.label.startswith("Sections")).input("Attendees\nAction items / Next steps").run()
    next(b for b in at.button if b.label == "💾 Save style").click().run()
    assert not at.exception, at.exception
    saved = memory_store.styles["meeting_notes"]
    assert saved.rules[0]["sections"] == ["Attendees", ["Action items", "Next steps"]]
    assert "_uid" not in saved.rules[0]
