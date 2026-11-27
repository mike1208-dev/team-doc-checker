"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { pagesOf, roleName, useSession } from "@/lib/session";
import { Icon } from "@/components/Icon";
import { Select } from "@/components/Select";
import { ThemeSwitch } from "@/components/ThemeSwitch";

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
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <nav className={`side ${open ? "open" : ""}`} aria-label="Menu">
        <div className="brand">
          <img src="/zeenote-mark.png" alt="" />
          <span style={{ minWidth: 0 }}>
            ZeeNote
            {!me.admin && <span className="company-name">{me.company}</span>}
          </span>
        </div>
        {picker ? (
          <div className="switcher">
            <Select label="Team" value={String(team?.id ?? "")} onChange={(id) => chooseTeam(Number(id))}
              options={teams.map((item) => ({ value: String(item.id), label: item.name }))}
              leading={<span className="team-mark" aria-hidden="true">{team?.name[0]}</span>} />
          </div>
        ) : (
          team && !me.owner && (
            <div className="switcher single">
              <span className="team-mark" aria-hidden="true">{team.name[0]}</span> {team.name}
            </div>
          )
        )}
        {groups.map((group) => (
          <div key={group} style={{ display: "grid", gap: 2 }}>
            <div className="group">{group}</div>
            {pages.filter((page) => page.group === group).map((page) => (
              <Link key={page.href} href={page.href} className="nav" aria-current={path.startsWith(page.href) ? "page" : undefined} onClick={() => setOpen(false)}>
                <Icon name={page.icon} /> {page.label}
              </Link>
            ))}
          </div>
        ))}
        <div style={{ marginTop: "auto" }}>
          <ThemeSwitch />
        </div>
        <div className="side-foot" style={{ marginTop: 0 }}>
          <span className="avatar" aria-hidden="true">{me.name[0]}</span>
          <span className="who">
            <b>{me.name}</b>
            <span>{roleName(me)}</span>
          </span>
          <button className="btn ghost icon" onClick={signOut} aria-label="Sign out" title="Sign out">
            <Icon name="logout" />
          </button>
        </div>
      </nav>
      <div className="panel">
        <div className="mobile-bar">
          <button className="btn icon" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Menu">
            <Icon name="menu" />
          </button>
          <span className="brand" style={{ padding: 0 }}>
            <img src="/zeenote-mark.png" alt="" /> ZeeNote
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}

// The title row of a page, with its actions on the right, above the page's content
export function PageHead({ title, sub, children }: { title: string; sub?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {children && <div className="row">{children}</div>}
    </header>
  );
}
