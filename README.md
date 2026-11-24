# ZeeChecker: Daily Report Checker

Live app: https://zeecheck.streamlit.app

Checks a daily report against the team's rules and gives a report: ✅ passed · ❌ failed · ⚠️ please look · ⏭️ skipped, with where the
problem is and how to fix it.

- **Input:** paste text, or upload `.md`, `.pdf`, `.docx` (or `.txt`)
- **Output:** a report in the browser, downloadable as `.md` or `.csv`
- **AI:** [Groq](https://console.groq.com) cloud API (free tier; reports are sent to Groq for the AI
  checks), or a small model that runs inside the app (reports aren't sent to an AI service)
- **Version 1:** daily reports in English. Issue/PR descriptions, work plans and Japanese come later.

- **Rules:** stored in a Supabase database and edited on the **Manage rules** page (forms, AI import
  from a rule document, history with restore). Without a database, the example rules in `rules/*.yaml`
  are used (read-only).

## How it works

```
daily report ──► read as text ──► run each daily report rule ──► report
                                    ├─ plain Python checks (fast, exact)
                                    └─ AI checks (meaning): Groq or the local model

rules: Supabase database (editable in the app)  ──fallback──►  rules/*.yaml (read-only examples)
```

| Path | Purpose |
|---|---|
| `app.py` | Entry point: page navigation |
| `views/check.py` | **Check daily report** page |
| `views/manage_rules.py` | **Manage rules** page (editors only) |
| `rules/*.yaml` | Example styles: fallback when there's no database, and the starting rules for a new one |
| `supabase/migrations/` | Database tables and the history trigger |
| `checker/store.py` | Reads and saves styles: Supabase, or the YAML files |
| `checker/validation.py` | Checks a style is valid before it's saved |
| `checker/rule_import.py` | Drafts rules from a rule document with the AI |
| `checker/loader.py` | Reads md / txt / pdf / docx into text |
| `checker/styles.py` | Loads the rule files; guesses the style |
| `checker/basic_checks.py` | Rule checks in plain Python |
| `checker/llm_checks.py` | Rule checks by the AI |
| `checker/local_model.py` | Runs a small model inside the app |
| `checker/report.py` | Runs all rules; builds the summary, table and Markdown report |
| `tests/` | pytest tests (no API key or network needed) |

## Setup (Windows, PowerShell)

```powershell
cd team-doc-checker
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Add your Groq key: create a free key at https://console.groq.com/keys, then

```powershell
Copy-Item .env.example .env
notepad .env
```

and put it after `GROQ_API_KEY=`. Never commit `.env` or share the key.

## Run

```powershell
streamlit run app.py
```

Open http://localhost:8501, paste or upload a daily report and click **Check daily report**.

## Daily report rules

| Rule | Checked by | A report passes when… |
|---|---|---|
| `has_sections` | code | It has Yesterday (or Weekend), Today, and Blockers / Notes |
| `tags_reviewer` | code | It tags the reviewer at the top |
| `has_hours` | code | It gives hours for both Yesterday (spent) and Today (planned) |
| `concrete_tasks` | AI | Each task says what was done or will be done |
| `status_or_result` | AI | Each finished task has a status or result |
| `overall_progress` | code | Blockers / Notes has a line such as `Overall: 60% done. Payment is left.` |
| `clear_and_short` | AI | It is easy to read, with no repeated lines or needless detail |
| `terms_explained` | AI | New, advanced or internal terms are explained (common software terms, such as PR or API, need no explanation) |
| `real_blockers` | AI | Blockers are stated clearly, or "None" when there are none |

If the database still has the old example rules: **Manage rules** → Daily report → **Use the built-in rules**.

Without a Groq key or a local model, the code rules still work: AI rules show ⏭️ skipped, or turn off
**Use AI checks** in the sidebar.

## Deployment

The app runs on [Streamlit Community Cloud](https://share.streamlit.io) at https://zeecheck.streamlit.app.

- **Python version:** 3.11 (Advanced settings)
- **Secrets** (App settings → Secrets), the cloud version of `.env`:
  ```toml
  GROQ_API_KEY = "gsk_..."
  SUPABASE_URL = "https://<project-ref>.supabase.co"
  SUPABASE_KEY = "sb_secret_..."
  EDITOR_PASSWORD = "..."
  ```
- Every push to the deployed branch redeploys the app automatically.
- Invite teammates in App settings → Sharing.

## Rule database (Supabase)

1. Create a project at https://supabase.com.
2. Open **SQL Editor**, paste the contents of `supabase/migrations/20261120000000_rule_store.sql` and
   click **Run**. It creates the `styles` and `style_history` tables. It's safe to run again.
3. Add to `.env` (local) or Streamlit **Secrets** (deployed):
   ```toml
   SUPABASE_URL = "https://<project-ref>.supabase.co"    # Project Settings -> Data API
   SUPABASE_KEY = "sb_secret_..."                        # Project Settings -> API Keys -> Secret keys
   EDITOR_PASSWORD = "choose-a-password"
   ```
   The secret key only lives on the server; the tables have row level security with no policies, so
   nobody can reach them with the public key.
4. Open **Manage rules**, unlock with the editor password, and click **Load the example rules** (or
   create styles from scratch).

## Managing rules

On the **Manage rules** page (editor password required):

- **Edit styles:** create, edit or delete styles and their rules with forms; test the rules on a sample
  document before saving. Changes apply to checks right away; no redeploy.
- **Import from rule document:** upload or paste a written rule document; the AI drafts a style for you
  to review, test and save.
- **History:** every save or delete keeps the previous version; restore any of them.

Without a database, styles come from `rules/*.yaml`. A style file looks like this:

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
| `no_secrets` | none | ❌ for API keys/tokens, ⚠️ for `password: ...` lines. If any is found, the text isn't sent to Groq |
| `word_count` | `min`, `max` | ❌ if too short or too long |
| `long_sentences` | `max_words` (default 35) | ⚠️ for sentences that are too long |
| `forbidden_phrases` | `phrases`: e.g. `["TODO", "TBD"]` | ❌ if any appears |
| `must_contain` | `phrases`: text that must appear | ❌ if any is missing |
| `pattern` | `pattern` (regular expression), `must`: `match` / `not_match`, `label` | ❌ if missing (or found, with `not_match`) |
| `mention_at_top` | `lines` (default 3) | ❌ if nobody is tagged with @ in the first lines |
| `working_hours` | `sections`: same shape as in `required_sections` | ❌ if a section gives no hours |
| `labelled_line` | `sections`: same shape as in `required_sections`; `labels`: accepted labels, e.g. `["Overall"]` | ❌ if none of the sections has a line such as `Overall: 60% done` |
| `llm` | `question`: the rule as a yes/no question; `known_terms` (optional): a fail that is only about these terms becomes a pass | ✅ / ❌ / ⚠️ from the AI |

Use plain checks wherever possible; use `llm` only for rules that need understanding.

## Choosing a model

Pick the model from the dropdown in the app's sidebar, or in the rule test on **Manage rules**. The local
model is the default when it's set up (see below). The Groq models come from `.env` / Secrets, so no code
change is needed when Groq retires or adds models:

```toml
GROQ_MODEL = "qwen/qwen3.8-27b"                                              # default Groq model
GROQ_MODELS = "qwen/qwen3.8-27b,openai/gpt-oss-20b,openai/gpt-oss-120b"      # dropdown list
```

Available models: https://console.groq.com/docs/models

## Local model

A small model can run inside the app (CPU, `llama-cpp-python`). When it's set in `.env` / Secrets, it is
first in the model list and used by default. If it can't run, its checks are skipped; they are never sent to Groq instead.

```toml
LOCAL_MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"    # Hugging Face repository
LOCAL_MODEL_FILE = "qwen2.5-0.5b-instruct-q8_0.gguf"    # about 0.7 GB
LOCAL_MODEL_LABEL = "Qwen2.5-0.5B (untrained)"          # name in the model list
HF_TOKEN = ""                                           # only for a private repository
```

This example is the untrained model, for testing hosting. Use the trained model's repository and file later.

## Tests

```powershell
python -m pytest -v
```

## Roadmap

1. Test the untrained model in a separate deployed app (memory and time per report)
2. Generate training examples from the rules and fine-tune the model
3. Score the untrained and trained models on labelled real reports
   (target: **≥ 80% of rule breaks found, < 2 false alarms per report**)
4. Add Issue/PR descriptions and work plans

Real reports are private: keep them in `data/` (git-ignored), never in this public repository.
