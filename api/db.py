"""
The ZeeNote database: people, teams, each team's template and rules, each person's report settings, saved reports and sign-ins. SQLite for the first
version, so nothing needs to be set up. The sample company is added the first time.
"""

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

from checker.store import YamlStore
from checker.writer import GREETING, Layout

DB_PATH = Path(os.getenv("ZEENOTE_DB", Path(__file__).resolve().parent.parent / "data" / "zeenote.db"))
# The first version has no real sign-in: every sample account uses this password. Set your own in .env before sharing the app
FAKE_PASSWORD = os.getenv("ZEENOTE_PASSWORD") or "zeenote"

SCHEMA = """
-- owner: the company's owner. admin: ZeeNote's own staff, who see numbers but never a company's reports
create table if not exists users (email text primary key, name text not null, owner integer not null default 0, admin integer not null default 0);
create table if not exists teams (id integer primary key, name text not null unique);
create table if not exists members (
    team_id integer not null references teams(id), email text not null references users(email),
    role text not null check (role in ('Manager', 'Member')), primary key (team_id, email)
);
create table if not exists templates (team_id integer primary key references teams(id), data text not null, updated_at text, updated_by text);
-- what each person last used for a team's reports: reviewer, hours, repo link, greeting
create table if not exists settings (email text not null references users(email), team_id integer not null references teams(id), data text not null, primary key (email, team_id));
create table if not exists reports (
    id integer primary key, email text not null references users(email), team_id integer not null references teams(id),
    day text not null, notes text not null, text text not null, created_at text not null default (datetime('now'))
);
-- the one company of the first version; its owner can rename it
create table if not exists company (id integer primary key check (id = 1), name text not null);
create table if not exists sessions (token text primary key, email text not null references users(email), created_at text not null default (datetime('now')));
"""

COMPANY = "ZeeSpires"  # the sample company's first name
SAMPLE = 4  # raised when the sample people or teams change, so an older database starts again
# name: (email, owner, admin). Illia manages three teams, and Mike works in two of them. The Support Team has its own manager
USERS = {
    "Dan": ("dan@zeenote.ai", 1, 0),
    "Illia": ("illia@zeenote.ai", 0, 0),
    "Mike": ("mike@zeenote.ai", 0, 0),
    "Lina": ("lina@zeenote.ai", 0, 0),
    "Noah": ("noah@zeenote.ai", 0, 0),
    "Yuki": ("yuki@zeenote.ai", 0, 0),
    "Leo": ("leo@zeenote.ai", 0, 0),
    "Admin": ("admin@zeenote.ai", 0, 1),
}
TEAMS = {
    "Cova Team": [("Illia", "Manager"), ("Mike", "Member"), ("Lina", "Member")],
    "Commity Team": [("Illia", "Manager"), ("Noah", "Member")],
    "AI-Training Team": [("Illia", "Manager"), ("Mike", "Member"), ("Noah", "Member")],
    "Support Team": [("Yuki", "Manager"), ("Leo", "Member")],
}


def default_template() -> dict:
    """
    What a new team starts with: the built-in daily report rules, all turned on, and the usual format.
    """
    return {"rules": [{**rule, "enabled": True} for rule in YamlStore().list_styles()["daily_report"].rules], "layout": asdict(Layout())}


DEFAULT_REPO = "https://github.com/mike1208-dev/zee-note"


def default_settings(reviewer: str = "") -> dict:
    """
    A person's first report settings for a team. They change them on Write report, and the next report starts from those.
    """
    return {"reviewer": reviewer, "first_section": "Yesterday", "done_hours": 8.0, "plan_hours": 8.0, "repo": DEFAULT_REPO, "greeting": GREETING}


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("pragma foreign_keys = on")
    return db


def setup(path: Path = DB_PATH) -> None:
    with connect(path) as db:
        if db.execute("pragma table_info(users)").fetchone() and db.execute("pragma user_version").fetchone()[0] < SAMPLE:
            # an older sample company, with other people or teams: start again
            names = ("sessions", "reports", "settings", "templates", "members", "teams", "users")
            db.executescript("".join(f"drop table if exists {name};" for name in names))
        db.executescript(SCHEMA)
        db.execute(f"pragma user_version = {SAMPLE}")
        db.execute("insert or ignore into company (id, name) values (1, ?)", (COMPANY,))
        # one report a person, team and day: a report copied again replaces that day's one. Copies saved twice before
        # this rule keep only the newest
        db.execute("delete from reports where id not in (select max(id) from reports group by email, team_id, day)")
        db.execute("create unique index if not exists one_report_a_day on reports (email, team_id, day)")
        if db.execute("select count(*) from users").fetchone()[0]:
            return
        db.executemany("insert into users (email, name, owner, admin) values (?, ?, ?, ?)", [(email, name, owner, admin) for name, (email, owner, admin) in USERS.items()])
        for name, people in TEAMS.items():
            team_id = db.execute("insert into teams (name) values (?)", (name,)).lastrowid
            db.executemany("insert into members values (?, ?, ?)", [(team_id, USERS[who][0], role) for who, role in people])
            db.execute("insert into templates (team_id, data) values (?, ?)", (team_id, json.dumps(default_template())))
