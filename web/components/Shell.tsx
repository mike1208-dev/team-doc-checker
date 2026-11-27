"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { pagesOf, roleName, useSession } from "@/lib/session";

export function Shell({ children }: { children: React.ReactNode }) {
  const { me, team, teams, chooseTeam, signOut } = useSession();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const pages = pagesOf(me);
  const groups = [...new Set(pages.map((page) => page.group))];
  // the owner chooses a team only where the page is about one team; the others in several teams on every page
  const picker = teams.length > 1 && (!me.owner || path.startsWith("/templates"));

  return (
    <div className="shell">
      <nav className={`side ${open ? "open" : ""}`} aria-label="Menu">
        <div className="brand">
          <img src="/zeenote-mark.png" alt="" /> ZeeNote
        </div>
        {groups.map((group) => (
          <div key={group} className="stack" style={{ gap: 4 }}>
            <div className="group">{group}</div>
            {pages.filter((page) => page.group === group).map((page) => (
              <Link key={page.href} href={page.href} className="nav" aria-current={path.startsWith(page.href) ? "page" : undefined} onClick={() => setOpen(false)}>
                <span aria-hidden="true">{page.icon}</span> {page.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
      <div>
        <header className="top">
          <button className="btn sm menu-button" onClick={() => setOpen(!open)} aria-expanded={open}>
            ☰ Menu
          </button>
          {picker && (
            <label className="row" style={{ fontWeight: 400 }}>
              Team
              <select value={team?.id} onChange={(event) => chooseTeam(Number(event.target.value))}>
                {teams.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="me">
            <span className="avatar" aria-hidden="true">{me.name[0]}</span>
            <span>
              <b>{me.name}</b> <span className="soft small">· {roleName(me)}</span>
            </span>
          </div>
          <button className="btn sm" onClick={signOut}>
            Sign out
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
