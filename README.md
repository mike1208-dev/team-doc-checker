# Team Document Checker

Checks a team document (daily report, Issue/PR description, project or work plan, ...) against the
team's rules and gives a report: ✅ passed · ❌ failed · ⚠️ please look · ⏭️ skipped, with where the
problem is and how to fix it.

- **Input:** paste text, or upload `.md`, `.pdf`, `.docx` (or `.txt`)
- **Output:** a report in the browser, downloadable as `.md` or `.csv`
- **AI:** [Groq](https://console.groq.com) (cloud, free tier, nothing to download) by default, or a local
  [Ollama](https://ollama.com) model (no API key, documents never leave the machine). Switch in the sidebar
  or with `LLM_PROVIDER`.

> **Status:** the rule files in `rules/` are **examples**. They will be replaced with the team's real
> rules.

## How it works

```
document ──► read as text ──► pick style (chosen or auto-detected) ──► run each rule in rules/<style>.yaml
                                                                         ├─ plain Python checks (fast, exact)
                                                                         └─ AI checks via Groq or Ollama (meaning)
                                                                     ──► report
```

| Path | Purpose |
|---|---|
| `app.py` | Streamlit web page |
| `rules/*.yaml` | One file per document style: its rules |
| `checker/loader.py` | Reads md / txt / pdf / docx into text |
| `checker/styles.py` | Loads the rule files; guesses the style |
| `checker/basic_checks.py` | Rule checks in plain Python |
| `checker/llm_checks.py` | Rule checks by the AI (Groq or Ollama) |
| `checker/report.py` | Runs all rules; builds the summary, table and Markdown report |
| `eval/docs/` | Real team documents for measuring accuracy (coming) |
| `tests/` | pytest tests (no Ollama needed) |

## Setup (Windows, PowerShell)

```powershell
cd team-doc-checker
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Set up the AI provider:

```powershell
Copy-Item .env.example .env
notepad .env
```

- **Groq (default):** create a free key at https://console.groq.com/keys and put it after
  `GROQ_API_KEY=` in `.env`. Nothing to download. Never commit `.env` or share the key.
- **Ollama (optional, fully local):** set `LLM_PROVIDER=ollama` and download a model once with
  `ollama pull qwen2.5:1.5b`.

## Run

```powershell
streamlit run app.py
```

Open http://localhost:8501, paste or upload a document, choose the style (or leave "Auto-detect")
and click **Check document**.

Without an AI provider, the rule-based checks still work: AI rules show ⏭️ skipped, or turn off
**Use AI checks** in the sidebar.

### Share with the team (one shared machine)

Run it on one PC and let teammates open it in their browser. They install nothing.

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Teammates open `http://<that-PC's-IP>:8501` (find the IP with `ipconfig`, "IPv4 Address").
They must be on the same network or VPN, and Windows Firewall must allow port 8501 (Windows asks
the first time; choose **Private networks**).

## Adding a new document style

Add one file to `rules/`, e.g. `rules/meeting_notes.yaml`. No code changes; restart the app.

```yaml
name: Meeting notes
description: Decisions and action items from a meeting.
detect: ["meeting notes", "attendees", "action items"]   # words used by Auto-detect

rules:
  - id: has_sections
    title: Has Attendees / Decisions / Action items
    check: required_sections
    sections:
      - "Attendees"
      - ["Decisions", "Outcomes"]          # a list = any of these names is accepted
      - "Action items"
  - id: owners
    title: Every action item has an owner
    check: llm
    question: "Does every action item name a person responsible for it?"
```

### Check types

| `check` | Options | Result |
|---|---|---|
| `required_sections` | `sections`: names (or lists of alternative names) | ❌ if any is missing |
| `no_secrets` | none | ❌ for API keys/tokens, ⚠️ for `password: ...` lines |
| `word_count` | `min`, `max` | ❌ if too short or too long |
| `long_sentences` | `max_words` (default 35) | ⚠️ for sentences that are too long |
| `forbidden_phrases` | `phrases`: e.g. `["TODO", "TBD"]` | ❌ if any appears |
| `llm` | `question`: the rule as a yes/no question | ✅ / ❌ / ⚠️ from the AI |

Use plain checks wherever possible; use `llm` only for rules that need understanding.

## Choosing a model

Set the model in the app's sidebar, or with `GROQ_MODEL` / `OLLAMA_MODEL` in `.env`.

**Groq** (default `qwen/qwen3.8-27b`; `openai/gpt-oss-20b` and `openai/gpt-oss-120b` also tested): any chat model listed at https://console.groq.com/docs/models.
Model names change over time; if a model is retired, pick another from that page.

**Ollama:**

| Model | Download | Notes |
|---|---|---|
| `qwen2.5:1.5b` | ~1 GB | Default. Fast, fine for development |
| `qwen2.5:3b` | ~1.9 GB | Better answers; fits a 4 GB GPU |
| `qwen2.5:7b` | ~4.7 GB | Best quality; slower on a 4 GB GPU |

## Tests

```powershell
python -m pytest -v
```

## Roadmap

1. Replace the example rules with the team's real rules
2. Collect 10–20 real documents in `eval/docs/` and label which rules each one breaks
3. `eval/evaluate.py`: measure the tool against the labels
   (target: **≥ 80% of rule breaks found, < 2 false alarms per document**)
4. Compare plain checks only vs Groq models vs local Ollama models
