"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Company = { name: string; owner: string; people: number; teams: number; reports: number; reports_today: number };

// ZeeNote's own overview: numbers only, never a company's reports or notes
export default function ConsolePage() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ companies: Company[] }>("/console").then((data) => setCompanies(data.companies)).catch((e) => setError(e.message));
  }, []);

  const total = (key: keyof Company) => (companies ?? []).reduce((sum, company) => sum + Number(company[key]), 0);
  return (
    <>
      <div>
        <h1>Overview</h1>
        <p className="soft">Every company that uses ZeeNote. Staff see numbers, never a company&apos;s reports.</p>
      </div>
      {error && <p className="notice bad">{error}</p>}
      {!companies && !error && <p className="soft">Loading…</p>}
      {companies && (
        <>
          <div className="cols4">
            {([["Companies", companies.length], ["People", total("people")], ["Reports", total("reports")], ["Reports today", total("reports_today")]] as const).map(([label, value]) => (
              <div key={label} className="card">
                <p className="soft small">{label}</p>
                <p style={{ fontSize: 28, fontWeight: 700 }}>{value}</p>
              </div>
            ))}
          </div>
          <div className="card scroll">
            <table>
              <thead>
                <tr><th>Company</th><th>Owner</th><th>People</th><th>Teams</th><th>Reports</th></tr>
              </thead>
              <tbody>
                {companies.map((company) => (
                  <tr key={company.name}>
                    <td><b>{company.name}</b></td><td>{company.owner}</td><td>{company.people}</td><td>{company.teams}</td><td>{company.reports}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
