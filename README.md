# ZeeChecker: Daily Report Writer and Checker

Live app: https://zeecheck.streamlit.app

Turns plain notes into a daily report in the team's format, checks it against the team's rules, and asks about
anything that is missing or doubtful.

- **Input:** plain notes, and settings such as the reviewer, the date and the hours
- **Output:** a report to edit, copy to Slack or download as `.md`
- **AI:** [Groq](https://console.groq.com) cloud API. The notes and the report are sent to Groq. The AI only sorts the
  notes into fields; code checks every field against the notes and writes the report
- **Version 2:** daily reports in English

- **Rules:** stored in a Supabase database and edited on the **Manage rules** page (forms, AI import
  from a rule document, history with restore). Without a database, the example rules in `rules/*.yaml`
  are used (read-only).

## How it works

```
plain notes ──► AI sorts them into fields ──► code checks the fields against the notes ──► code writes the report
                                                                                        └──► rules: 3 by code, 5 by AI

rules: Supabase database (editable in the app)  ──fallback──►  rules/*.yaml (read-only examples)
```

| Path | Purpose |
|---|---|
| `app.py` | Entry point: page navigation |
| `views/write.py` | **Write daily report** page (v2): plain notes in, a report in the team's template out |
| `views/design.py`, `views/design.css` | The header, colors and layout |
| `views/points.py` | The points to check, each only once |
| `views/manage_rules.py` | **Manage rules** page (editors only; its button is turned off for now) |
| `rules/*.yaml` | Example styles: fallback when there's no database, and the starting rules for a new one |
| `supabase/migrations/` | Database tables and the history trigger |
| `checker/store.py` | Reads and saves styles: Supabase, or the YAML files |
| `checker/validation.py` | Checks a style is valid before it's saved |
| `checker/rule_import.py` | Drafts rules from a rule document with the AI |
| `checker/loader.py` | Reads md / txt / pdf / docx into text |
| `checker/styles.py` | Loads the rule files |
| `checker/basic_checks.py` | Rule checks in plain Python |
| `checker/llm_checks.py` | Rule checks by the AI |
| `checker/local_model.py` | Runs a small model inside the app |
| `checker/writer.py` | Sorts plain notes into fields with the AI, checks them against the notes, and writes the report |
| `checker/markup.py` | Turns the report's Markdown into HTML (preview) and Slack's format (copy) |
| `checker/statuses.py` | Finds which statuses the notes support |
| `checker/report.py` | Runs all rules; builds the summary and the table |
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

Open http://localhost:8501, write your notes and the settings, and click **Write daily report**.

## Daily report rules

| Rule | Checked by | A report passes when… |
|---|---|---|
| `has_sections` | code | It has Yesterday (or Weekend), Today, and Blockers / Notes |
| `tags_reviewer` | code | It tags the reviewer at the top |
| `has_hours` | code | It gives hours for both Yesterday (spent) and Today (planned) |
| `concrete_tasks` | AI | Each task says what was done or will be done |
| `status_or_result` | AI | Each finished task has a status or result |
| `clear_and_short` | AI | It is easy to read, with no repeated lines or needless detail |
| `terms_explained` | AI | New, advanced or internal terms are explained (common software terms, such as PR or API, need no explanation) |
| `real_blockers` | AI | Blockers are stated clearly, or "None" when there are none |

If the database only has the old example rules, the built-in rules are used.

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
detect: ["meeting notes", "attendees", "action items"]   # not used now

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
| `llm` | `question`: the rule as a yes/no question; `known_terms` (optional): a fail that is only about these terms becomes a pass | ✅ / ❌ / ⚠️ from the AI |

Use plain checks wherever possible; use `llm` only for rules that need understanding.

## Choosing a model

Pick the model in Settings, or in the rule test on **Manage rules**. The Groq models come from `.env` / Secrets, so no code
change is needed when Groq retires or adds models:

```toml
GROQ_MODEL = "qwen/qwen3.8-27b"                                              # default Groq model
GROQ_MODELS = "qwen/qwen3.8-27b,openai/gpt-oss-20b,openai/gpt-oss-120b"      # dropdown list
```

Available models: https://console.groq.com/docs/models

## Local model

A small model can run inside the app (CPU, `llama-cpp-python`) for the rule test on **Manage rules**. When it's set in
`.env` / Secrets, it is first in that model list. If it can't run, its checks are skipped; they are never sent to Groq instead.

```toml
LOCAL_MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"    # Hugging Face repository
LOCAL_MODEL_FILE = "qwen2.5-0.5b-instruct-q8_0.gguf"    # about 0.7 GB
LOCAL_MODEL_LABEL = "Qwen2.5-0.5B (untrained)"          # name in the model list
HF_TOKEN = ""                                           # only for a private repository
```

This example is an untrained model.

## Tests

```powershell
python -m pytest -v
```

## Roadmap

1. Check all AI rules in one request, to use less of Groq's free limit
2. Collect the team's feedback on the written reports
3. Add Issue/PR descriptions and work plans

Real reports are private: keep them in `data/` (git-ignored), never in this public repository.
