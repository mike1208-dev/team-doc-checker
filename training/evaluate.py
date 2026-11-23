"""
Step 4: scores a model on labelled rule checks, through the same code as the app.

    python -m training.evaluate data/training/val.jsonl --name untrained
    python -m training.evaluate data/training/val.jsonl --name groq --model qwen/qwen3.8-27b

Each line of the file needs report_id, rule_id, question, text and label ("pass" or "fail"). The default model
is the local one (LOCAL_MODEL_* in .env), so nothing is sent anywhere. Never use a Groq model on real reports
unless the team has approved it.
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # before checker.llm_checks reads GROQ_MODEL

from checker import local_model  # noqa: E402
from checker.llm_checks import llm_check  # noqa: E402
from checker.result import FAIL, PASS, SKIP  # noqa: E402

RESULTS = Path("data/results")
VERDICTS = {PASS: "pass", FAIL: "fail"}  # anything else is "unsure" (also when the answer is unreadable)


def run(examples: list[dict], model: str, client=None) -> pd.DataFrame:
    rows = []
    for number, example in enumerate(examples, start=1):
        started = time.perf_counter()
        rule = {"id": example["rule_id"], "check": "llm", "question": example["question"]}
        result = llm_check(example["text"], rule, model=model, client=client)
        if result.status == SKIP:
            raise SystemExit(f"Stopped, nothing was scored: {result.message}")
        rows.append(
            {
                "report_id": example["report_id"],
                "rule_id": example["rule_id"],
                "label": example["label"],
                "verdict": VERDICTS.get(result.status, "unsure"),
                "message": result.message,
                "seconds": time.perf_counter() - started,
            }
        )
        print(f"{number}/{len(examples)}", end="\r", flush=True)
    return pd.DataFrame(rows)


def scores(results: pd.DataFrame) -> dict:
    """
    "unsure" is never counted as correct: it isn't a found rule break, and it isn't a pass.
    """
    breaks = results[results.label == "fail"]
    good = results[results.label == "pass"]
    false_alarms = int((good.verdict == "fail").sum())
    return {
        "checks": len(results),
        "rule breaks": len(breaks),
        "rule breaks found": (breaks.verdict == "fail").mean() if len(breaks) else None,
        "good checks": len(good),
        "false alarms": false_alarms,
        "false alarms per report": false_alarms / results.report_id.nunique(),
        "accuracy": (results.verdict == results.label).mean(),
        "unsure": int((results.verdict == "unsure").sum()),
        "seconds per check": results.seconds.mean(),
    }


def score_table(results: pd.DataFrame) -> pd.DataFrame:
    table = {"ALL": scores(results)}
    for rule_id, part in results.groupby("rule_id"):
        table[rule_id] = scores(part)
    return pd.DataFrame(table).T


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--name", required=True, help="name for the result files, e.g. untrained")
    parser.add_argument("--model", default=local_model.MODEL_ID)
    args = parser.parse_args()
    if args.model == local_model.MODEL_ID and not local_model.is_configured():
        raise SystemExit("Set LOCAL_MODEL_REPO and LOCAL_MODEL_FILE (or LOCAL_MODEL_PATH) in .env first.")

    examples = [json.loads(line) for line in args.file.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = run(examples, args.model)
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"{args.name}_{args.file.stem}"
    results.to_csv(RESULTS / f"{stem}_answers.csv", index=False, encoding="utf-8-sig")
    table = score_table(results)
    table.to_csv(RESULTS / f"{stem}_scores.csv", encoding="utf-8-sig")
    print(table.T.to_string())
