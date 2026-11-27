"use client";

import { useEffect, useState } from "react";
import { api, type Rule, type SavedTemplate, type Template } from "@/lib/api";
import { useSession } from "@/lib/session";

const own = (rule: Rule) => rule.id === "" || rule.id.startsWith("custom_");

// Cleans what the form allows while typing, such as an empty line in the known terms
function forSaving(data: Template): Template {
  return {
    rules: data.rules.map((rule) => (rule.known_terms ? { ...rule, known_terms: rule.known_terms.map((term) => term.trim()).filter(Boolean) } : rule)),
  };
}

export default function TemplatesPage() {
  const { me, team } = useSession();
  const [saved, setSaved] = useState<SavedTemplate | null>(null);
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [newRule, setNewRule] = useState({ title: "", question: "" });

  function use(result: SavedTemplate) {
    setSaved(result);
    setRules(result.rules);
  }

  useEffect(() => {
    if (!team) return;
    setSaved(null);
    setRules(null);
    setError("");
    api<SavedTemplate>(`/teams/${team.id}/template`).then(use).catch((e) => setError(e.message));
  }, [team]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!team) return <p className="soft">There are no teams yet.</p>;

  async function save(path: string, body?: Template) {
    setBusy(true);
    setError("");
    try {
      use(await api<SavedTemplate>(path, { method: body ? "PUT" : "POST", body }));
      setToast(`Saved. New reports of the ${team!.name} use it now.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const editRule = (index: number, change: Partial<Rule>) => setRules(rules!.map((rule, i) => (i === index ? { ...rule, ...change } : rule)));
  const changed = rules !== null && saved !== null && JSON.stringify(forSaving({ rules }).rules) !== JSON.stringify(saved.rules);

  return (
    <>
      <div className="row between">
        <div>
          <h1>Template and rules</h1>
          <p className="soft">
            <b>{team.name}</b> · {me.owner ? "As the owner, you can change any team's rules." : "Every report of your team is checked against these."}
            {saved?.updated_by && ` Last changed by ${saved.updated_by}, ${saved.updated_at?.slice(0, 16)} UTC.`}
          </p>
        </div>
        {saved?.can_edit && rules && (
          <div className="row">
            <button className="btn" disabled={busy} onClick={() => confirm("Go back to ZeeNote's built-in rules? Your own rules are removed.") && save(`/teams/${team.id}/template/reset`)}>
              Reset to default
            </button>
            <button className="btn main" disabled={busy || !changed} onClick={() => save(`/teams/${team.id}/template`, forSaving({ rules }))}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        )}
      </div>
      {error && <p className="notice bad" role="alert">{error}</p>}
      {!rules && !error && <p className="soft">Loading…</p>}
      {rules && (
        <>
          <div className="card stack">
            <div>
              <h2>Template</h2>
              <p className="soft small">Every report of the team has these parts, in this order. Each person sets their reviewer, hours, repo link and greeting on Write report.</p>
            </div>
            <div className="preview small">
              <p>@reviewer</p>
              <p>greeting</p>
              <p>📅 <b>[date]</b></p>
              <ul>
                <li>✅ <b>Yesterday</b> or <b>Weekend</b> (hours): what was done, with PR links and statuses</li>
                <li>🎯 <b>Today</b> (hours): the plans</li>
                <li>🚧 <b>Blockers</b> / 📝 <b>Notes</b></li>
              </ul>
            </div>
          </div>

          <fieldset disabled={!saved?.can_edit || busy} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }} className="stack">
            <div className="row between">
              <h2>Rules</h2>
              <span className="tag off">{rules.filter((rule) => rule.enabled).length} of {rules.length} on</span>
            </div>
            <p className="soft small" style={{ marginTop: -8 }}>Every report is checked against the rules that are on. Code checks are always quick; AI checks ask the AI one question each.</p>
            {rules.map((rule, i) => (
              <div key={i} className={`rule card ${rule.enabled ? "" : "off"}`}>
                <div className="row between">
                  <label className="check grow">
                    <input type="checkbox" checked={rule.enabled} onChange={(event) => editRule(i, { enabled: event.target.checked })} />
                    <input value={rule.title} onChange={(event) => editRule(i, { title: event.target.value })} aria-label="Rule title" style={{ fontWeight: 600 }} />
                  </label>
                  <span className={`tag ${rule.check === "llm" ? "" : "off"}`}>{rule.check === "llm" ? "AI check" : "Code check"}</span>
                  {own(rule) && (
                    <button type="button" className="btn sm" onClick={() => setRules(rules.filter((_, j) => j !== i))}>
                      Delete
                    </button>
                  )}
                </div>
                {rule.check === "llm" && (
                  <label>
                    Question for the AI
                    <textarea rows={2} value={rule.question ?? ""} onChange={(event) => editRule(i, { question: event.target.value })} />
                  </label>
                )}
                {rule.known_terms && (
                  <label>
                    Terms that need no explanation (one per line)
                    <textarea rows={4} value={rule.known_terms.join("\n")} onChange={(event) => editRule(i, { known_terms: event.target.value.split("\n") })} />
                  </label>
                )}
              </div>
            ))}
            <form
              className="card stack"
              onSubmit={(event) => {
                event.preventDefault();
                setRules([...rules, { id: "", check: "llm", title: newRule.title.trim(), question: newRule.question.trim(), enabled: true }]);
                setNewRule({ title: "", question: "" });
              }}
            >
              <h2>Add your own rule</h2>
              <p className="soft small">Write a yes-or-no question. The AI asks it of every report. Save to keep it.</p>
              <label>
                Title
                <input value={newRule.title} onChange={(event) => setNewRule({ ...newRule, title: event.target.value })} placeholder="e.g. Names the client for client work" required />
              </label>
              <label>
                Question for the AI
                <textarea rows={2} value={newRule.question} onChange={(event) => setNewRule({ ...newRule, question: event.target.value })} placeholder="e.g. Does each client task name the client?" required />
              </label>
              <div>
                <button className="btn">Add rule</button>
              </div>
            </form>
          </fieldset>
        </>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </>
  );
}
