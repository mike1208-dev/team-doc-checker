"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ReportRow } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function ReportsPage() {
  const { team, teams } = useSession();
  const [rows, setRows] = useState<ReportRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<ReportRow[]>("/reports").then(setRows).catch((e) => setError(e.message));
  }, []);

  // with several teams, the list shows the team chosen at the top
  const shown = (rows ?? []).filter((row) => teams.length < 2 || row.team_id === team?.id);
  return (
    <>
      <div>
        <h1>My reports</h1>
        <p className="soft">{teams.length > 1 && team ? <><b>{team.name}</b> · </> : null}Every report you copied for Slack, newest first.</p>
      </div>
      {error && <p className="notice bad">{error}</p>}
      {rows === null && !error && <p className="soft">Loading…</p>}
      {rows !== null && (
        <div className="card scroll">
          {shown.length === 0 ? (
            <div className="empty">
              No reports yet. <Link href="/write">Write your first one</Link>.
            </div>
          ) : (
            <table>
              <thead>
                <tr><th>Date</th><th>Team</th><th>Report</th></tr>
              </thead>
              <tbody>
                {shown.map((row) => (
                  <tr key={row.id}>
                    <td style={{ whiteSpace: "nowrap" }}><Link href={`/reports/${row.id}`}>{row.day}</Link></td>
                    <td style={{ whiteSpace: "nowrap" }}>{row.team}</td>
                    <td className="soft small">{row.text.replace(/[*:@]/g, "").replace(/\s+/g, " ").slice(0, 140)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </>
  );
}
