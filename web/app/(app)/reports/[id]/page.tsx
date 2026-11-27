"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Report } from "@/lib/api";
import { copyReport } from "@/lib/copy";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    api<Report>(`/reports/${id}`).then(setReport).catch((e) => setError(e.message));
  }, [id]);

  async function copy() {
    if (!report) return;
    const copied = await copyReport(report);
    setToast(copied ? "Copied. Paste it into Slack." : "This browser didn't allow copying.");
    setTimeout(() => setToast(""), 3000);
  }

  return (
    <>
      <div className="row between">
        <div>
          <h1>{report ? `Report of ${report.day}` : "Report"}</h1>
          {report && <p className="soft">{report.team} · saved {report.created_at.slice(0, 16)} UTC</p>}
        </div>
        <div className="row">
          <Link href="/reports" className="btn">← My reports</Link>
          {report && <button className="btn main" onClick={copy}>Copy for Slack</button>}
        </div>
      </div>
      {error && <p className="notice bad">{error}</p>}
      {report && (
        <>
          <div className="card preview" dangerouslySetInnerHTML={{ __html: report.html }} />
          {report.notes && (
            <details className="card">
              <summary>Your notes</summary>
              <pre style={{ whiteSpace: "pre-wrap", margin: "10px 0 0", font: "inherit" }}>{report.notes}</pre>
            </details>
          )}
        </>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </>
  );
}
