import json
from types import SimpleNamespace

import pandas as pd
import pytest

from checker.llm_checks import PROMPT, token_cap
from training.evaluate import run, scores
from training.generate_examples import BREAKS, JUDGE, WRITER, StopRun, ai_rules, generate, make_prompt, problem_with, read_rows
from training.prepare_dataset import prepare, split, to_examples

PAIR = {
    "good": "Yesterday\n- Added the reset form (Merged)",
    "good_reason": "The task is concrete.",
    "broken": "Yesterday\n- Worked on the form (Merged)",
    "broken_reason": "It doesn't say what changed.",
    "broken_quote": "Worked on the form",
}


class FakeGroq:
    """Writes PAIR, and judges reports with the given verdicts."""

    def __init__(self, good="pass", broken="fail", pair=PAIR):
        self.pair, self.verdicts, self.calls = pair, {PAIR["good"]: good, PAIR["broken"]: broken}, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages, **_):
        self.calls.append(model)
        if model == WRITER:
            content = json.dumps(self.pair)
        else:
            verdict = next(v for text, v in self.verdicts.items() if text in messages[0]["content"])
            if verdict == "limit":
                raise ConnectionError("rate limit")
            content = json.dumps({"verdict": verdict, "reason": "", "quote": ""})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


RULE = {"id": "concrete_tasks", "check": "llm", "question": "Is each task concrete?"}


def test_every_ai_rule_has_ways_to_break_it():
    assert {rule["id"] for rule in ai_rules()} == set(BREAKS)
    assert WRITER != JUDGE
    for rule in ai_rules():
        assert rule["question"] in make_prompt(rule, 1)
        assert make_prompt(rule, 1) == make_prompt(rule, 1)


@pytest.mark.parametrize(
    "change, expected",
    [
        ({}, ""),
        ({"good": ""}, "missing"),
        ({"broken": PAIR["good"]}, "same"),
        ({"broken_quote": ""}, "no quote"),
        ({"broken_quote": "not there"}, "isn't in"),
        ({"broken_quote": None}, "missing"),
        ({"good": "Yesterday\\n- Added the reset form"}, "raw codes"),
        ({"good": "U0001F4C5 Yesterday"}, "raw codes"),
        ({"good": "**Yesterday**\n- Added the reset form (Merged)"}, "formatting"),
    ],
)
def test_problem_with(change, expected):
    problem = problem_with({**PAIR, **change})
    assert expected in problem and bool(problem) == bool(expected)


def test_generate_keeps_agreed_pairs_and_continues(tmp_path):
    path = tmp_path / "pairs.jsonl"
    generate([RULE], 2, FakeGroq(), path)
    assert [row["kept"] for row in read_rows(path)] == [True, True]
    generate([RULE], 3, client := FakeGroq(), path)
    assert len(read_rows(path)) == 3
    assert client.calls.count(WRITER) == 1
    assert [row["attempt"] for row in read_rows(path)] == [1, 2, 3]


def test_generate_drops_pairs_the_judge_disagrees_with_and_gives_up(tmp_path):
    path = tmp_path / "pairs.jsonl"
    generate([RULE], 1, FakeGroq(broken="pass"), path)
    rows = read_rows(path)
    assert len(rows) == 3 and not any(row["kept"] for row in rows)


def test_generate_records_the_writer(tmp_path):
    path = tmp_path / "pairs.jsonl"
    generate([RULE], 1, FakeGroq(), path)
    assert read_rows(path)[0]["writer"] == WRITER


def test_a_limit_stops_the_run_instead_of_counting_as_disagreement(tmp_path):
    path = tmp_path / "pairs.jsonl"
    with pytest.raises(StopRun):
        generate([RULE], 1, FakeGroq(good="limit"), path)
    assert read_rows(path) == []


def make_rows(count, rule_id="concrete_tasks"):
    return [{**PAIR, "rule_id": rule_id, "question": RULE["question"], "attempt": i, "kept": True} for i in range(1, count + 1)]


def test_examples_use_the_apps_prompt():
    good, broken = to_examples(make_rows(1)[0])
    assert good["prompt"][0]["content"] == PROMPT.format(question=RULE["question"], text=PAIR["good"])
    assert json.loads(broken["completion"][0]["content"]) == {
        "verdict": "fail", "reason": PAIR["broken_reason"], "quote": PAIR["broken_quote"]
    }


def test_split_keeps_every_rule_in_both_parts():
    train, val = split(make_rows(20) + make_rows(20, "real_blockers"))
    assert len(train) == 36 and len(val) == 4
    assert {row["rule_id"] for row in val} == {"concrete_tasks", "real_blockers"}


def test_prepare_writes_files_and_respects_rejected_pairs(tmp_path):
    rows = make_rows(10) + [{**make_rows(1)[0], "attempt": 99, "kept": False}]
    (tmp_path / "pairs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert prepare(tmp_path) == {"train": 18, "val": 2}
    train, val = read_rows(tmp_path / "train.jsonl"), read_rows(tmp_path / "val.jsonl")
    pair_of = lambda e: e["report_id"].rsplit("-", 1)[0]  # noqa: E731
    assert not {pair_of(e) for e in train} & {pair_of(e) for e in val}
    assert len(pd.read_csv(tmp_path / "review.csv")) == 5

    (tmp_path / "rejected.txt").write_text("concrete_tasks-1\nconcrete_tasks-2\n", encoding="utf-8")
    assert sum(prepare(tmp_path).values()) == 16


def test_only_models_that_think_first_have_no_answer_cap():
    assert token_cap(JUDGE) == {"max_completion_tokens": 300}
    assert token_cap(WRITER) == {}


def test_scores():
    results = pd.DataFrame(
        [
            ("a", "r1", "fail", "fail"),
            ("a", "r2", "fail", "unsure"),
            ("b", "r1", "pass", "fail"),
            ("b", "r2", "pass", "pass"),
        ],
        columns=["report_id", "rule_id", "label", "verdict"],
    ).assign(seconds=1.0)
    s = scores(results)
    assert s["rule breaks found"] == 0.5
    assert s["false alarms"] == 1 and s["false alarms per report"] == 0.5
    assert s["accuracy"] == 0.5 and s["unsure"] == 1


def test_run_stops_when_the_model_cannot_answer():
    example = {"report_id": "a", "rule_id": "r", "question": "q", "text": PAIR["good"], "label": "pass"}
    assert run([example], JUDGE, FakeGroq()).verdict.tolist() == ["pass"]
    with pytest.raises(SystemExit):
        run([example], JUDGE, FakeGroq(good="limit"))
