"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { PageHead } from "@/components/Shell";
import { Spinner } from "@/components/Spinner";

type Company = { id: number; name: string; owner: string; people: number; teams: number; reports: number; reports_today: number };
type NewCompany = { name: string; owner_name: string; owner_email: string };
const EMPTY: NewCompany = { name: "", owner_name: "", owner_email: "" };

// ZeeNote's own overview: every company, in numbers only, never a company's reports or notes
export default function ConsolePage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<NewCompany>(EMPTY);
  const [problems, setProblems] = useState<Partial<NewCompany>>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const [toast, setToast] = useState("");

  const load = () => api<{ companies: Company[] }>("/console").then((data) => setCompanies(data.companies)).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    const found: Partial<NewCompany> = {
      name: form.name.trim() ? undefined : "Write the company's name.",
      owner_name: form.owner_name.trim() ? undefined : "Write the owner's name.",
      owner_email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.owner_email.trim()) ? undefined : "Write the owner's email, such as nora@northwind.ai.",
    };
    setProblems(found);
    const first = (Object.keys(found) as (keyof NewCompany)[]).find((key) => found[key]);
    if (first) {
      document.getElementById(`new-${first}`)?.focus();
      return;
    }
    setBusy(true);
    setFormError("");
    try {
      const created = await api<{ name: string }>("/companies", { body: form });
      await load();
      setForm(EMPTY);
      setAdding(false);
      setToast(`${created.name} is added. Its owner signs in with the shared password.`);
      setTimeout(() => setToast(""), 4000);
    } catch (e) {
      setFormError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = (key: keyof NewCompany, label: string, placeholder: string) => (
    <label>
      <span>{label}</span>
      <input id={`new-${key}`} value={form[key]} placeholder={placeholder} disabled={busy}
        onChange={(event) => { setForm({ ...form, [key]: event.target.value }); setProblems({ ...problems, [key]: undefined }); }}
        aria-invalid={Boolean(problems[key])} aria-describedby={problems[key] ? `new-${key}-problem` : undefined} />
      {problems[key] && <span id={`new-${key}-problem`} className="field-problem">{problems[key]}</span>}
    </label>
  );

  const total = (key: keyof Company) => (companies ?? []).reduce((sum, company) => sum + Number(company[key]), 0);
  return (
    <>
      <PageHead title="Overview" sub="Every company that uses ZeeNote. Staff see numbers, never a company's reports.">
        {!adding && (
          <button className="btn main" onClick={() => setAdding(true)}>
            <Icon name="building" size={14} /> Add company
          </button>
        )}
      </PageHead>
      <main className="content">
        {error && <p className="notice bad">{error}</p>}
        {!companies && !error && <div className="empty"><Spinner />Loading the companies…</div>}
        {adding && (
          <form className="card flush" onSubmit={add} noValidate>
            <div className="card-head">
              <div>
                <h2>Add a company</h2>
                <p className="soft small">The owner signs in with their email and the shared password, then sets up the company.</p>
              </div>
            </div>
            <div className="card-body">
              {field("name", "Company name", "e.g. Northwind")}
              <div className="cols2">
                {field("owner_name", "Owner's name", "e.g. Nora")}
                {field("owner_email", "Owner's email", "e.g. nora@northwind.ai")}
              </div>
              {formError && <p className="notice bad row" role="alert" style={{ gap: 8 }}><Icon name="alert" size={15} /> {formError}</p>}
            </div>
            <div className="card-foot">
              <button type="button" className="btn ghost" onClick={() => { setAdding(false); setProblems({}); setFormError(""); }} disabled={busy}>
                Cancel
              </button>
              <button className="btn main" disabled={busy}>{busy ? "Adding…" : "Add company"}</button>
            </div>
          </form>
        )}
        {companies && (
          <>
            <div className="cols4">
              {([["Companies", companies.length], ["People", total("people")], ["Reports", total("reports")], ["Reports today", total("reports_today")]] as const).map(([label, value]) => (
                <div key={label} className="card">
                  <p className="soft small">{label}</p>
                  <p style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-.01em" }}>{value}</p>
                </div>
              ))}
            </div>
            <div className="card flush scroll">
              <table className="companies">
                <thead>
                  <tr><th>Company</th><th>Owner</th><th>People</th><th>Teams</th><th>Reports</th><th>Today</th></tr>
                </thead>
                <tbody>
                  {companies.map((company) => (
                    <tr key={company.id}>
                      <td>
                        <span className="row" style={{ gap: 10 }}>
                          <span className="team-mark" aria-hidden="true">{company.name[0]}</span>
                          <b style={{ fontWeight: 500 }}>{company.name}</b>
                        </span>
                      </td>
                      <td>{company.owner || <span className="faint">None</span>}</td>
                      <td>{company.people}</td>
                      <td>{company.teams}</td>
                      <td>{company.reports}</td>
                      <td>{company.reports_today}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
      {toast && <div className="toast" role="status"><Icon name="check" size={15} />{toast}</div>}
    </>
  );
}
