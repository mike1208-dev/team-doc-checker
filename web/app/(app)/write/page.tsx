"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Checked, type MySettings, type RuleResult, type Written } from "@/lib/api";
import { copyReport } from "@/lib/copy";
import { useSession } from "@/lib/session";
import { Questions, answersAsNotes } from "@/components/Questions";
import { RuleList } from "@/components/RuleList";
import { Spinner } from "@/components/Spinner";

const SAMPLE = `issue 95 fix booking list shows the wrong date, pr 102 merged
issue 96 feat send an email when the password is reset, pr 101 in review
practiced the project presentation
today: issue 97 chore add validation to the password reset form
blocker: waiting for QA validation on staging`;

const today = () => new Date().toLocaleDateString("sv"); // YYYY-MM-DD in this computer's time zone

type Rendered = { text: string; html: string; slack: string };

type Field = "reviewer" | "day" | "done" | "plan" | "repo" | "greeting";
const REPO = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/; // as REPO in api/main.py

// What a person was doing in each team, so switching teams or pages loses nothing. Kept in memory only:
// reloading the page starts again from empty
type Draft = { notes: string; asked: Written | null; answers: Record<string, string>; written: Written | null; checked: Checked | null; text: string; rendered: Rendered | null };
const drafts = new Map<string, Draft>();

// The AI rules that look at the same thing as a question (as SAME_POINT in views/points.py)
const SAME_POINT: Record<string, string> = { status_or_result: "What is the status", concrete_tasks: "What exactly", terms_explained: "A reader who", real_blockers: "Do you have any blockers" };

// The AI rules ran when the notes were checked, so writing with the answers doesn't run them again. A rule that failed
// passes now when the answers solved its question
function withEarlierRules(result: Written, earlier: Written): Written {
  const solved = (id: string) => id in SAME_POINT && earlier.points.some((point) => point.startsWith(SAME_POINT[id])) && !result.points.some((point) => point.startsWith(SAME_POINT[id]));
  const before = (rule: RuleResult) => {
    const old = earlier.rules.find((other) => other.id === rule.id) ?? rule;
    return old.status !== "PASS" && old.status !== "SKIP" && solved(rule.id) ? { ...old, status: "PASS" as const } : old;
  };
  const rules = result.rules.map((rule) => (rule.status === "SKIP" ? before(rule) : rule));
  const run = rules.filter((rule) => rule.status !== "SKIP");
  const notRun = rules.length - run.length;
  const summary = `${run.filter((rule) => rule.status === "PASS").length} of ${run.length} rules passed` + (notRun ? `, ${notRun} not checked` : "");
  return { ...result, rules, summary };
}

export default function WritePage() {
  const { me, team } = useSession();
  const [notes, setNotes] = useState("");
  const [day, setDay] = useState(today);
  const [firstSection, setFirstSection] = useState<"Yesterday" | "Weekend">("Yesterday");
  const [hours, setHours] = useState<[string, string]>(["", ""]);
  const [mine, setMine] = useState({ reviewer: "", repo: "", greeting: "" });
  const [busy, setBusy] = useState<"" | "checking" | "writing">("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [asked, setAsked] = useState<Written | null>(null); // the check of the notes, while its questions are open
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draftOf, setDraftOf] = useState(""); // the team whose draft the page shows
  const [written, setWritten] = useState<Written | null>(null);
  const [checked, setChecked] = useState<Checked | null>(null);
  const [text, setText] = useState("");
  const [rendered, setRendered] = useState<Rendered | null>(null);
  const [tab, setTab] = useState<"preview" | "markdown">("preview");
  const [toast, setToast] = useState("");
  const [problems, setProblems] = useState<Partial<Record<Field, string>>>({});

  // Each team's report starts from what this person used last time
  useEffect(() => {
    if (!team) return;
    api<MySettings>(`/teams/${team.id}/settings`)
      .then((data) => {
        setFirstSection(data.first_section);
        setHours([data.done_hours?.toString() ?? "", data.plan_hours?.toString() ?? ""]);
        setMine({ reviewer: data.reviewer, repo: data.repo, greeting: data.greeting });
      })
      .catch((e) => setError(e.message));
    const key = `zeenote-draft-${me.email}-${team.id}`;
    const saved = drafts.get(key);
    setNotes(saved?.notes ?? "");
    setAsked(saved?.asked ?? null);
    setAnswers(saved?.answers ?? {});
    setWritten(saved?.written ?? null);
    setChecked(saved?.checked ?? null);
    setText(saved?.text ?? "");
    setRendered(saved?.rendered ?? null);
    setTab("preview");
    setError("");
    setDraftOf(key);
  }, [team, me.email]);

  // Saved only once the team's own draft is shown, so one team's work is never kept as another's
  useEffect(() => {
    if (team && draftOf === `zeenote-draft-${me.email}-${team.id}`) drafts.set(draftOf, { notes, asked, answers, written, checked, text, rendered });
  }, [team, me.email, draftOf, notes, asked, answers, written, checked, text, rendered]);

  // The preview follows the edits, a moment after typing stops
  useEffect(() => {
    if (!written || rendered?.text === text) return;
    const timer = setTimeout(() => {
      api<{ html: string; slack: string }>("/render", { body: { text } }).then((data) => setRendered({ text, ...data })).catch(() => {});
    }, 400);
    return () => clearTimeout(timer);
  }, [text, written, rendered]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!team) return <p className="soft">You aren't in a team yet. Ask your company's owner to add you.</p>;

  const writing = busy !== "";

  // The questions stay open, so an answer can be changed and the report written again
  function show(result: Written) {
    setWritten(result);
    setChecked(result);
    setText(result.text);
    setRendered({ text: result.text, html: result.html, slack: result.slack });
    setTab("preview");
  }

  // The settings are checked here, so each problem shows under its own field
  function settingsOk(): boolean {
    const hoursProblem = (value: string) => (value === "" || Number(value) < 0 || Number(value) > 24 ? "Write the hours." : "");
    const found: Partial<Record<Field, string>> = {
      reviewer: mine.reviewer.trim() ? "" : "Write who checks your report.",
      day: day ? "" : "Pick the date of the report.",
      done: hoursProblem(hours[0]),
      plan: hoursProblem(hours[1]),
      repo: !mine.repo.trim() ? "Write your GitHub repo link." : REPO.test(mine.repo.trim()) ? "" : "Write a link such as https://github.com/acme/app.",
      greeting: mine.greeting.trim() ? "" : "Write a greeting.",
    };
    const open = Object.fromEntries(Object.entries(found).filter(([, problem]) => problem));
    setProblems(open);
    const first = Object.keys(open)[0];
    if (first) document.getElementById(`field-${first}`)?.focus();
    return !first;
  }

  const clear = (name: Field) => problems[name] && setProblems({ ...problems, [name]: "" });
  const field = (name: Field) => ({ id: `field-${name}`, "aria-invalid": Boolean(problems[name]), "aria-describedby": problems[name] ? `problem-${name}` : undefined });
  const problem = (name: Field) => problems[name] && <span id={`problem-${name}`} className="field-problem">{problems[name]}</span>;

  async function writeReport(answered: string[], check_ai: boolean) {
    const number = (value: string) => (value === "" ? null : Number(value));
    return api<Written>("/reports/write", {
      body: { team_id: team!.id, notes, answers: answered, day, first_section: firstSection, done_hours: number(hours[0]), plan_hours: number(hours[1]), ...mine, check_ai },
    });
  }

  // First the notes are checked. With nothing to ask, the report is ready; otherwise the questions come first
  async function checkNotes(event: React.FormEvent) {
    event.preventDefault();
    if (!settingsOk()) return;
    setBusy("checking");
    setError("");
    setWritten(null);
    setChecked(null);
    try {
      const result = await writeReport([], true);
      if (JSON.stringify(result.asks) !== JSON.stringify(asked?.asks)) setAnswers({}); // the same questions keep their answers
      setAsked(result.points.length ? result : null);
      if (!result.points.length) show(result);
      else
        setTimeout(() => {
          const card = document.getElementById("questions");
          card?.scrollIntoView({ behavior: "smooth", block: "start" });
          card?.querySelector<HTMLElement>("input, select")?.focus({ preventScroll: true });
        });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function writeWithAnswers() {
    if (!settingsOk()) return;
    setBusy("writing");
    setError("");
    setWritten(null);
    setChecked(null);
    try {
      show(withEarlierRules(await writeReport(answersAsNotes(asked!.asks, answers), false), asked!));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function checkAgain() {
    setChecking(true);
    try {
      setChecked(await api<Checked>("/reports/check", { body: { team_id: team!.id, text, questions: written!.questions } }));
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setChecking(false);
    }
  }

  async function copyAndSave() {
    // copy first, while the click still allows it, then save
    const fresh = rendered?.text === text ? rendered : null;
    const copied = await copyReport({ text, html: fresh?.html, slack: fresh?.slack });
    try {
      await api("/reports", { body: { team_id: team!.id, day, notes: written!.notes, text } }); // with the answers
      setToast(copied ? "Copied. Paste it into Slack. It's saved in My reports." : "Saved in My reports, but this browser didn't allow copying. Copy it from the Markdown tab.");
    } catch (e) {
      setToast(`${copied ? "Copied" : "Not copied"}, but not saved: ${(e as Error).message}`);
    }
  }

  const edited = written !== null && text !== written.text;
  const toFill = /\[add (?:your tasks|your blockers, or None|the title)\]/.test(text);

  return (
    <>
      <div className="row between">
        <div>
          <h1>Write report</h1>
          <p className="soft">
            <b>{team.name}</b> · Write rough notes. ZeeNote writes the report in your team&apos;s format.
          </p>
        </div>
      </div>

      <form className="write" onSubmit={checkNotes} noValidate>
        <div className="stack" style={{ gap: 18 }}>
          <div className="card stack">
            <div>
              <h2>Your notes</h2>
              <p className="soft small">What you did, what you&apos;ll do, and any blockers. Any order is fine. Don&apos;t write keys or passwords: the notes are sent to an AI service.</p>
            </div>
            <textarea rows={8} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="e.g. fixed issue 95, pr 102 merged…" disabled={writing} aria-label="Your notes" />
            <div className="row between">
              <button type="button" className="btn" onClick={() => setNotes(SAMPLE)} disabled={writing}>
                Use sample notes
              </button>
              <button className="btn main" disabled={writing || !notes.trim()}>
                {busy === "checking" ? "Checking…" : "Check notes"}
              </button>
            </div>
          </div>

          {/* the notes stay editable: Check notes again asks again */}
          {asked && (
            <Questions asks={asked.asks} answers={answers} onAnswer={(key, value) => setAnswers({ ...answers, [key]: value })} open={checked?.asks ?? null}
              disabled={writing} writing={busy === "writing"} onWrite={writeWithAnswers} />
          )}
        </div>

        <div className="card stack">
          <div>
            <h2>Settings</h2>
            <p className="soft small">All fields are required. ZeeNote remembers them for your next report.</p>
          </div>
          <label>
            <span>Reviewer (tagged at the top)</span>
            <input {...field("reviewer")} value={mine.reviewer} onChange={(event) => { setMine({ ...mine, reviewer: event.target.value }); clear("reviewer"); }} placeholder="e.g. Sam" disabled={writing} />
            {problem("reviewer")}
          </label>
          <label>
            <span>Date</span>
            <input {...field("day")} type="date" value={day} onChange={(event) => { setDay(event.target.value); clear("day"); }} disabled={writing} />
            {problem("day")}
          </label>
          <label>
            <span>First section</span>
            <select value={firstSection} onChange={(event) => setFirstSection(event.target.value as "Yesterday" | "Weekend")} disabled={writing}>
              <option>Yesterday</option>
              <option>Weekend</option>
            </select>
          </label>
          <div className="cols2">
            {(["done", "plan"] as const).map((name, i) => (
              <label key={name}>
                <span>{i === 0 ? firstSection : "Today"} (hours)</span>
                <input {...field(name)} type="number" min={0} max={24} step={0.5} value={hours[i]} disabled={writing}
                  onChange={(event) => { setHours(i === 0 ? [event.target.value, hours[1]] : [hours[0], event.target.value]); clear(name); }} />
                {problem(name)}
              </label>
            ))}
          </div>
          <label>
            <span>GitHub repo link</span>
            <input {...field("repo")} value={mine.repo} onChange={(event) => { setMine({ ...mine, repo: event.target.value }); clear("repo"); }} placeholder="https://github.com/acme/app" disabled={writing} />
            {problem("repo")}
          </label>
          <label>
            <span>Greeting</span>
            <textarea {...field("greeting")} rows={2} value={mine.greeting} onChange={(event) => { setMine({ ...mine, greeting: event.target.value }); clear("greeting"); }} disabled={writing} />
            {problem("greeting")}
          </label>
        </div>
      </form>

      <section className="card stack" aria-live="polite">
        <div>
          <h2>Your daily report</h2>
          <p className="soft small">Check it, edit if needed, and copy it to Slack.</p>
        </div>
        {error && <p className="notice bad" role="alert">{error}</p>}
        {busy === "checking" && <div className="empty"><Spinner />Checking your notes…</div>}
        {busy === "writing" && <div className="empty"><Spinner />Writing your daily report…</div>}
        {!writing && !written && !error && (
          <div className="empty">
            {asked ? (
              <>Answer the questions above, then click <b>Write report</b>.</>
            ) : (
              <>Write your notes and click <b>Check notes</b>. ZeeNote asks about anything missing, then writes the report here.</>
            )}
          </div>
        )}
        {written && checked && (
          <>
            {/* with the questions open, they show what is still open; edits checked again show it here */}
            {!asked && checked.points.length > 0 && (
              <div className="notice">
                <p>
                  <b>{checked.points.length} point{checked.points.length === 1 ? " is" : "s are"} still open</b>: fix them in the Markdown tab, or copy it as it is.
                </p>
                <ul className="points">
                  {checked.points.map((point) => <li key={point}>{point}</li>)}
                </ul>
              </div>
            )}
            <div className="tabs" role="tablist">
              {(["preview", "markdown"] as const).map((name) => (
                <button key={name} type="button" role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>
                  {name === "preview" ? "Preview" : "Markdown (edit)"}
                </button>
              ))}
            </div>
            {tab === "preview" ? (
              <div className="preview" dangerouslySetInnerHTML={{ __html: rendered?.html ?? "" }} />
            ) : (
              <textarea rows={18} value={text} onChange={(event) => setText(event.target.value)} aria-label="Daily report in Markdown" style={{ fontFamily: "ui-monospace, monospace", fontSize: 14 }} />
            )}
            {toFill && <p className="error">Fill in the parts in [brackets] before you post it.</p>}
            <details>
              <summary className="soft">{checked.summary}</summary>
              <RuleList rules={checked.rules} />
            </details>
            <div className="row between">
              <button type="button" className="btn" onClick={checkAgain} disabled={checking || !edited}>
                {checking ? "Checking…" : "Check again"}
              </button>
              <button type="button" className="btn main" onClick={copyAndSave}>
                Copy for Slack
              </button>
            </div>
          </>
        )}
      </section>
      <p className="soft small">
        Every report you copy is saved in <Link href="/reports">My reports</Link>.
      </p>
      {toast && <div className="toast" role="status">{toast}</div>}
    </>
  );
}
