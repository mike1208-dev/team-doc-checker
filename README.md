# ZeeCheck: Team Document Checker

Live app: https://zeecheck.streamlit.app

Checks a team document (daily report, Issue/PR description, project or work plan, ...) against the
team's rules and gives a report: ✅ passed · ❌ failed · ⚠️ please look · ⏭️ skipped, with where the
problem is and how to fix it.

- **Input:** paste text, or upload `.md`, `.pdf`, `.docx` (or `.txt`)
- **Output:** a report in the browser, downloadable as `.md` or `.csv`
- **AI:** [Groq](https://console.groq.com) cloud API (free tier, nothing to download). Documents are
  sent to Groq for the AI checks.

- **Rules:** stored in a Supabase database and edited on the **Manage rules** page (forms, AI import
  from a rule document, history with restore). Without a database, the example rules in `rules/*.yaml`
  are used (read-only).

## How it works

```
document ──► read as text ──► pick style (chosen or auto-detected) ──► run each rule in rules/<style>.yaml
                                                                         ├─ plain Python checks (fast, exact)
                                                                         └─ AI checks via Groq (meaning)
                                                                     ──► report

rules: Supabase database (editable in the app)  ──fallback──►  rules/*.yaml (read-only examples)
```

| Path | Purpose |
|---|---|
| `app.py` | Entry point: page navigation |
| `views/check.py` | **Check document** page |
| `views/manage_rules.py` | **Manage rules** page (editors only) |
| `rules/*.yaml` | Example styles: fallback when there's no database, and the starting rules for a new one |
| `supabase/migrations/` | Database tables and the history trigger |
| `checker/store.py` | Reads and saves styles: Supabase, or the YAML files |
| `checker/validation.py` | Checks a style is valid before it's saved |
| `checker/rule_import.py` | Drafts rules from a rule document with the AI |
| `checker/loader.py` | Reads md / txt / pdf / docx into text |
| `checker/styles.py` | Loads the rule files; guesses the style |
| `checker/basic_checks.py` | Rule checks in plain Python |
| `checker/llm_checks.py` | Rule checks by the AI (Groq) |
| `checker/report.py` | Runs all rules; builds the summary, table and Markdown report |
| `eval/docs/` | Real team documents for measuring accuracy (coming) |
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

Open http://localhost:8501, paste or upload a document, choose the style (or leave "Auto-detect")
and click **Check document**.

Without a Groq key, the rule-based checks still work: AI rules show ⏭️ skipped, or turn off
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
| `no_secrets` | none | ❌ for API keys/tokens, ⚠️ for `password: ...` lines |
| `word_count` | `min`, `max` | ❌ if too short or too long |
| `long_sentences` | `max_words` (default 35) | ⚠️ for sentences that are too long |
| `forbidden_phrases` | `phrases`: e.g. `["TODO", "TBD"]` | ❌ if any appears |
| `must_contain` | `phrases`: text that must appear | ❌ if any is missing |
| `pattern` | `pattern` (regular expression), `must`: `match` / `not_match`, `label` | ❌ if missing (or found, with `not_match`) |
| `llm` | `question`: the rule as a yes/no question | ✅ / ❌ / ⚠️ from the AI |

Use plain checks wherever possible; use `llm` only for rules that need understanding.

## Choosing a model

Pick the model from the dropdown in the app's sidebar. The list and the default come from `.env` /
Secrets, so no code change is needed when Groq retires or adds models:

```toml
GROQ_MODEL = "qwen/qwen3.8-27b"                                              # default
GROQ_MODELS = "qwen/qwen3.8-27b,openai/gpt-oss-20b,openai/gpt-oss-120b"      # dropdown list
```

Available models: https://console.groq.com/docs/models

## Tests

```powershell
python -m pytest -v
```

## Roadmap

1. Import the team's real rule documents on the Manage rules page
2. Collect 10–20 real documents in `eval/docs/` and label which rules each one breaks
3. `eval/evaluate.py`: measure the tool against the labels
   (target: **≥ 80% of rule breaks found, < 2 false alarms per document**)
4. Compare plain checks only vs different Groq models
