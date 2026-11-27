# ZeeNote

**Rough notes in, a daily report your team can trust out.**

ZeeNote turns a team member's rough notes into a daily report in the team's format. It checks every fact against the notes,
asks about anything that is missing or doubtful, and never makes things up. Its core is **our own trained AI**: a small model
trained to sort notes into the parts of a report, so the notes can stay inside the company and there is no daily limit.

> The code still uses the old name, ZeeChecker, in a few places. They will be renamed.

## Status

| Part | State |
| --- | --- |
| Write a report from notes: fact check, questions, preview, copy for Slack, `.md` download | Working |
| 8 report rules: 3 checked by code, 5 by AI | Working |
| Manage the rules (database, history, import from a rule document) | Working, button turned off for now |
| Made-up training notes with known answers, scoring, Colab training notebook | Working |
| Our own trained model | Not trained yet. Today the app uses a cloud AI ([Groq](https://console.groq.com)) |
| **Web app v1** (`api/` + `web/`): sample accounts, write a report, My reports, each team's template and rules | First version, sample sign-in only |
| Real accounts, teams and people pages, our own AI page, the ZeeNote console | Planned, shown only in the product mockup |

## How it works

```
rough notes ──► AI sorts them into fields ──► code checks every field ──► code writes the report
                (tasks, statuses, PRs,        against the notes;          in the team's format,
                 plans, blockers)             doubtful points become       then checks the rules
                                              questions
```

**The main rule:** the AI only sorts the notes. Code writes the report, so the format is always the same, and a status, link or
number that the notes don't support is left out or asked about.

### Example

Notes:

```text
issue 95 fix booking list shows the wrong date, pr 102 merged
practiced the project presentation
today: issue 97 chore add validation to the password reset form
blocker: waiting for QA validation on staging
```

Report:

```text
✅ Yesterday (7 hours)
    issue-95 ― [FIX] Booking list shows the wrong date
        https://github.com/acme/app/pull/102 ― Merged
    Practiced the project presentation
🎯 Today (7 hours)
    issue-97 ― [CHORE] Add validation to the password reset form
🚧 Blockers / 📝 Notes
    Waiting for QA validation on staging
```

Question: What is the status of "Practiced the project presentation"?

## Our own AI

The model has one job: rough notes in, the parts of a report out, as JSON. A small model can learn one job well, and it can run on
our own server.

1. **Training data:** code makes rough notes from fields that it chose first, so every answer is known and no AI writes them.
   Typos, mixed order, emojis, missing parts and Japanese words are added on purpose. Every answer is checked with the app's
   own fact check, and the test notes never share subjects or details with the training notes.
2. **Training:** a LoRA fine-tune of Qwen2.5-1.5B-Instruct in Google Colab (free T4 GPU).
3. **Scoring:** the same app code scores the model before and after training: tasks found, right fields, invented tasks, and
   reports with a wrong fact and no warning.
4. **Later:** with a team's permission, the reports it confirms become new training examples. A new version is used only if it
   scores better.

| Goal | Value |
| --- | --- |
| Reports with a wrong fact and no warning | At most 2 of 100 |
| Right fields | Within 5 points of the best cloud model |
| Time per report on our own server | Under 30 seconds |

## Project layout

| Path | Purpose |
| --- | --- |
| `api/` | **Web app v1** backend (FastAPI): sign-in, teams, templates and rules, writing and saving reports. SQLite in `data/zeenote.db` |
| `web/` | **Web app v1** front end (Next.js): Sign in, Write report, My reports, Template and rules |
| `app.py` | Streamlit app entry point: pages and header |
| `views/write.py` | **Write daily report** page |
| `views/manage_rules.py` | **Manage rules** page (editors only) |
| `views/design.py`, `views/design.css`, `views/points.py`, `views/shared.py` | Layout, colors, the points to check, shared helpers |
| `checker/writer.py` | Asks the AI for the fields, checks them against the notes, and writes the report |
| `checker/statuses.py` | Finds which statuses and PR or issue numbers the notes support |
| `checker/markup.py` | The report's Markdown as HTML (preview) and in Slack's format (copy) |
| `checker/report.py`, `checker/basic_checks.py`, `checker/llm_checks.py` | Runs the rules: by code and by AI |
| `checker/store.py`, `checker/validation.py`, `checker/rule_import.py`, `checker/styles.py` | Rule database, rule checks, rule import |
| `checker/local_model.py`, `checker/loader.py` | A model inside the app (GGUF), reading md / txt / pdf / docx |
| `rules/*.yaml` | Built-in rules, used without a database |
| `supabase/migrations/` | Database tables for the rules |
| `training/make_notes.py` | Makes the training, validation and test notes |
| `training/score_notes.py` | Scores a model on the test notes |
| `training/notes_lora.ipynb` | Colab notebook: score, train, score again, make the model file |
| `training/generate_examples.py`, `evaluate.py`, `prepare_dataset.py`, `zeechecker_lora.ipynb` | The earlier training for the rule checks |
| `tests/` | pytest tests, with stand-ins for the AI. No API key or network needed |

## Setup (Windows, PowerShell)

```powershell
git clone https://github.com/mike1208-dev/zee-note.git
cd zee-note
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put a Groq key after `GROQ_API_KEY=` (free key: https://console.groq.com/keys). **Never commit `.env` or share a key.**

## Run

```powershell
streamlit run app.py
```

Open http://localhost:8501, write your notes and the settings, and click **Write daily report**.

**Groq's free plan** allows about 200,000 tokens per model per day. A report with its rule check uses about 4,300, so about 45
reports a day per model, shared by everyone with the same key. If the limit is used up, choose another model in Settings.

## Run the web app (v1)

It has two parts, each in its own PowerShell window. Install once:

```powershell
pip install -r requirements.txt   # adds FastAPI and Uvicorn
cd web
npm install
```

Then start the API (window 1, in the repo folder, with `.venv` on) and the web app (window 2):

```powershell
uvicorn api.main:app --reload
```

```powershell
cd web
npm run dev
```

Open http://localhost:3000 and sign in with a sample account. The password of every one is `zeenote`:

| Account | Role | Sees |
| --- | --- | --- |
| `dan@zeenote.ai` | Company Owner (Dan) | Template and rules of every team, and the company name |
| `illia@zeenote.ai` | Team Manager (Illia) of the Cova, Commity and AI-Training teams | Write report, My reports, Template and rules |
| `mike@zeenote.ai` | Team Member (Mike) of the Cova and AI-Training teams | Write report, My reports |
| `admin@zeenote.ai` | ZeeNote Admin | The ZeeNote overview: numbers of each company, never its reports |

The sample company is made the first time the API starts. To start again from nothing, stop the API and delete
`data/zeenote.db`. The sign-in is for trying the app only: there are no real passwords yet.

### Share it with teammates for a trial

A [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)
gives the app on this computer a public `https://….trycloudflare.com` address. It works only while this computer and the
three windows are on, and the address changes each time the tunnel starts.

1. Put a long password after `ZEENOTE_PASSWORD=` in `.env`. Every sample account uses it.
2. Start the API without `--reload`, and the web app as a production build:
   ```cmd
   .venv\Scripts\python -m uvicorn api.main:app
   ```
   ```cmd
   cd web
   npm run build
   npm start
   ```
3. Start the tunnel in a third window and send the `https://….trycloudflare.com` address it prints:
   ```cmd
   cloudflared tunnel --url http://localhost:3000
   ```

Send each teammate the password privately. The sign-in page lists the sample emails through the link too, but not where
the password is set. Everything teammates write goes to Groq with the key in `.env`, and they share its daily limit.

## Tests

```powershell
python -m pytest -q
```

## Training

1. Open `training/notes_lora.ipynb` in Google Colab and choose **Runtime → Change runtime type → T4 GPU**.
2. Run the cells from top to bottom. The notebook makes the notes itself, so nothing has to be uploaded.
3. To make the notes on your computer instead: `python -m training.make_notes` (written to `data/notes/`).
4. To score a model: `python -m training.score_notes --name <name> --gguf <model file>`, or `--groq <model>`.

Only made-up notes may be sent to a cloud AI. Real reports stay on your computer and in private Colab sessions.

## Report rules

| Rule | Checked by | A report passes when… |
| --- | --- | --- |
| `has_sections` | code | It has Yesterday (or Weekend), Today, and Blockers / Notes |
| `tags_reviewer` | code | It tags the reviewer at the top |
| `has_hours` | code | It gives hours for both Yesterday and Today |
| `concrete_tasks` | AI | Each task says what was done or will be done |
| `status_or_result` | AI | Each finished task has a status or result |
| `clear_and_short` | AI | It is easy to read, with no repeated lines or needless detail |
| `terms_explained` | AI | New, advanced or internal terms are explained |
| `real_blockers` | AI | Blockers are stated clearly, or "None" when there are none |

Editors can change the rules on the **Manage rules** page, if a Supabase database is set in `.env`
(`SUPABASE_URL`, `SUPABASE_KEY`, `EDITOR_PASSWORD`). Run `supabase/migrations/20261120000000_rule_store.sql` once in the
database's SQL Editor to create its tables. Without a database, `rules/*.yaml` is used.

## Models

The cloud models come from `.env`, so no code change is needed when Groq adds or retires a model:

```toml
GROQ_MODEL = "qwen/qwen3.8-27b"                                          # default
GROQ_MODELS = "qwen/qwen3.8-27b,openai/gpt-oss-20b,openai/gpt-oss-120b"  # the list in Settings
```

A model file (GGUF) can also run inside the app, for the rule test on **Manage rules**: set `LOCAL_MODEL_REPO` and
`LOCAL_MODEL_FILE`, or `LOCAL_MODEL_PATH`. See `.env.example`.

## Privacy

- Notes and reports are sent to Groq while the cloud AI is used. The page says so.
- Real reports and notes are private: keep them in `data/` (ignored by Git), never in this public repository.
- Text that looks like a key or a password is not sent to the AI.

## Contributing

- Start each piece of work from a GitHub issue, on a branch named `feature/<issue-number>-short-description`, made from the
  freshly pulled base branch.
- Commit messages: `type: short summary`, such as `feat: add the team feed` or `fix: keep the date after another page`.
  Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `style`, `chore`, `ci`, `revert`.
- Rebase on the base branch before pushing, and use `--force-with-lease`, never plain `--force`.
- Never push directly to the base branch: every change goes through a pull request with `Closes #<issue>`.
- Run the tests before opening a pull request.
