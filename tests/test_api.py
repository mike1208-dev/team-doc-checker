from datetime import date

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api import db, main  # noqa: E402
from checker.writer import Draft, Task  # noqa: E402

DAY = "2026-11-27"


@pytest.fixture
def client(tmp_path):
    return TestClient(main.create_app(tmp_path / "test.db"))


def sign_in(client, who: str) -> dict:
    email = dict(db.USERS)[who.capitalize()][0] if who.capitalize() in db.USERS else f"{who}@zeenote.ai"
    token = client.post("/api/login", json={"email": email, "password": db.FAKE_PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def team_id(client, headers, name: str) -> int:
    return next(team["id"] for team in client.get("/api/me", headers=headers).json()["teams"] if team["name"] == name)


@pytest.fixture
def no_ai(monkeypatch):
    """
    The AI's sorting of the notes, without calling Groq.
    """

    def extract(notes, day: date, first_section: str):
        return Draft(done=[Task("Fixed the login page", status="Merged")], plans=[Task("Write the tests")], no_blockers=True, notes=notes)

    monkeypatch.setattr(main, "extract", extract)


def test_wrong_password_and_no_token(client):
    assert client.post("/api/login", json={"email": "mike@zeenote.ai", "password": "wrong"}).status_code == 401
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_teams_of_each_role(client):
    owner = client.get("/api/me", headers=sign_in(client, "dan")).json()
    assert owner["owner"] and [team["role"] for team in owner["teams"]] == ["Owner"] * 4
    illia = client.get("/api/me", headers=sign_in(client, "illia")).json()
    assert [(team["name"], team["role"]) for team in illia["teams"]] == [("Cova Team", "Manager"), ("Commity Team", "Manager"), ("AI-Training Team", "Manager")]
    token = client.post("/api/login", json={"email": " Mike@ZeeNote.ai", "password": db.FAKE_PASSWORD}).json()["token"]  # not case sensitive
    mike = client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert [(team["name"], team["role"]) for team in mike["teams"]] == [("Cova Team", "Member"), ("AI-Training Team", "Member")]


def test_admin_sees_numbers_only(client, no_ai):
    admin = sign_in(client, "admin")
    me = client.get("/api/me", headers=admin).json()
    assert me["admin"] and not me["owner"] and me["teams"] == []
    mike = sign_in(client, "mike")
    app_team = team_id(client, mike, "Cova Team")
    client.post("/api/reports", headers=mike, json={"team_id": app_team, "day": DAY, "text": "- **Today**"})
    company = client.get("/api/console", headers=admin).json()["companies"][0]
    assert (company["name"], company["owner"], company["people"], company["teams"], company["reports"]) == ("ZeeSpires", "Dan", 7, 4, 1)
    assert client.get(f"/api/teams/{app_team}/template", headers=admin).status_code == 403
    assert client.get("/api/console", headers=sign_in(client, "dan")).status_code == 403


def test_old_sample_starts_again(tmp_path):
    path = tmp_path / "old.db"
    with db.connect(path) as old:
        old.execute("create table users (email text primary key, name text not null, owner integer not null default 0)")
        old.execute("insert into users values ('dan@acme.example', 'Ava', 1)")
    db.setup(path)
    with db.connect(path) as new:
        assert new.execute("select email from users where owner = 1").fetchone()[0] == "dan@zeenote.ai"


def test_copies_saved_twice_before_keep_the_newest(tmp_path):
    path = tmp_path / "copies.db"
    db.setup(path)
    with db.connect(path) as old:
        old.execute("drop index one_report_a_day")  # as before the rule
        old.executemany("insert into reports (email, team_id, day, notes, text) values ('mike@zeenote.ai', 1, ?, '', ?)",
                        [(DAY, "first"), (DAY, "newest"), ("2026-11-26", "other day")])
    db.setup(path)
    with db.connect(path) as new:
        assert [row[0] for row in new.execute("select text from reports order by day")] == ["other day", "newest"]


def test_logout(client):
    headers = sign_in(client, "mike")
    client.post("/api/logout", headers=headers)
    assert client.get("/api/me", headers=headers).status_code == 401


def test_first_settings(client):
    mike, illia = sign_in(client, "mike"), sign_in(client, "illia")
    web = team_id(client, mike, "AI-Training Team")
    assert client.get(f"/api/teams/{web}/settings", headers=mike).json() == db.default_settings("Illia")
    assert client.get(f"/api/teams/{web}/settings", headers=illia).json()["reviewer"] == ""  # not himself
    assert client.get(f"/api/teams/{web}/settings", headers=sign_in(client, "leo")).status_code == 403


def test_write_uses_and_keeps_my_settings(client, no_ai):
    mike = sign_in(client, "mike")
    web, app_team = team_id(client, mike, "AI-Training Team"), team_id(client, mike, "Cova Team")
    body = {"team_id": web, "notes": "fixed the login page, merged", "day": DAY, "done_hours": 7, "plan_hours": 8, "reviewer": "@Mina ",
            "repo": "https://github.com/acme/web/", "greeting": "Hello team.", "check_ai": False}
    result = client.post("/api/reports/write", headers=mike, json=body).json()
    assert result["text"].startswith("@Mina  \nHello team.")
    assert "Fixed the login page ― **Merged**" in result["text"] and "(7 hours)" in result["text"]
    assert "<strong>" in result["html"] and '"ops"' in result["slack"]
    assert "rules passed" in result["summary"]
    kept = client.get(f"/api/teams/{web}/settings", headers=mike).json()
    assert (kept["reviewer"], kept["repo"], kept["greeting"], kept["done_hours"]) == ("Mina", "https://github.com/acme/web", "Hello team.", 7)
    assert client.get(f"/api/teams/{app_team}/settings", headers=mike).json()["reviewer"] == "Illia"  # each team has its own
    client.post("/api/reports/write", headers=mike, json={**body, "repo": "", "greeting": ""})
    kept = client.get(f"/api/teams/{web}/settings", headers=mike).json()
    assert (kept["repo"], kept["greeting"]) == (db.DEFAULT_REPO, db.GREETING)  # an empty one gets its default back

    wrong = client.post("/api/reports/write", headers=mike, json={**body, "repo": "github.com/acme"})
    assert wrong.status_code == 422 and "repo link" in wrong.json()["detail"]


def test_answers_join_the_notes(client, no_ai):
    mike = sign_in(client, "mike")
    body = {"team_id": team_id(client, mike, "Cova Team"), "notes": "fixed the login page \n", "day": DAY, "check_ai": False,
            "answers": ["pr 30 is merged", " ", " QA means testing "]}
    result = client.post("/api/reports/write", headers=mike, json=body).json()
    assert result["notes"] == "fixed the login page\npr 30 is merged\nQA means testing"


def test_writer_errors_are_messages(client, monkeypatch):
    mike = sign_in(client, "mike")
    body = {"team_id": team_id(client, mike, "Cova Team"), "notes": " ", "day": DAY, "check_ai": False}
    response = client.post("/api/reports/write", headers=mike, json=body)
    assert response.status_code == 422 and response.json()["detail"] == "Please write some notes first."


def test_only_team_people_write_and_the_owner_doesnt(client, no_ai):
    leo = sign_in(client, "leo")
    app_team = team_id(client, sign_in(client, "mike"), "Cova Team")
    body = {"team_id": app_team, "notes": "fixed it", "day": DAY, "check_ai": False}
    assert client.post("/api/reports/write", headers=leo, json=body).status_code == 403
    assert client.post("/api/reports/write", headers=sign_in(client, "dan"), json=body).status_code == 403
    assert client.post("/api/reports", headers=leo, json={"team_id": app_team, "day": DAY, "text": "x"}).status_code == 403


def test_saved_reports_are_only_mine(client):
    mike, lina = sign_in(client, "mike"), sign_in(client, "lina")
    app_team = team_id(client, mike, "Cova Team")
    report_id = client.post("/api/reports", headers=mike, json={"team_id": app_team, "day": DAY, "notes": "n", "text": "- **Today**"}).json()["id"]
    assert [row["id"] for row in client.get("/api/reports", headers=mike).json()] == [report_id]
    assert client.get("/api/reports", headers=lina).json() == []
    assert client.get(f"/api/reports/{report_id}", headers=lina).status_code == 404
    report = client.get(f"/api/reports/{report_id}", headers=mike).json()
    assert report["team"] == "Cova Team" and "<strong>Today</strong>" in report["html"]
    assert client.post("/api/reports", headers=mike, json={"team_id": app_team, "day": DAY, "text": "  "}).status_code == 422
    again = client.post("/api/reports", headers=mike, json={"team_id": app_team, "day": DAY, "notes": "n2", "text": "- **Today** fixed"}).json()
    assert again == {"id": report_id, "replaced": True}  # the same day's report is replaced, not added
    assert len(client.get("/api/reports", headers=mike).json()) == 1 and "fixed" in client.get(f"/api/reports/{report_id}", headers=mike).json()["text"]
    assert client.delete(f"/api/reports/{report_id}", headers=lina).status_code == 404  # only my own
    assert client.delete(f"/api/reports/{report_id}", headers=mike).status_code == 200
    assert client.get("/api/reports", headers=mike).json() == []


def test_who_can_change_the_template(client):
    illia, mike, yuki, dan = (sign_in(client, who) for who in ("illia", "mike", "yuki", "dan"))
    app_team, support = team_id(client, dan, "Cova Team"), team_id(client, dan, "AI-Training Team")
    data = client.get(f"/api/teams/{app_team}/template", headers=mike).json()
    assert data["can_edit"] is False and len(data["rules"]) == 8
    assert client.put(f"/api/teams/{app_team}/template", headers=mike, json=data).status_code == 403
    assert client.put(f"/api/teams/{app_team}/template", headers=yuki, json=data).status_code == 403
    assert client.get(f"/api/teams/{support}/template", headers=sign_in(client, "lina")).status_code == 403  # not in the team
    rules = [{**rule, "title": "Has the parts"} if rule["id"] == "has_sections" else rule for rule in data["rules"]]
    saved = client.put(f"/api/teams/{app_team}/template", headers=dan, json={**data, "rules": rules}).json()
    assert saved["rules"][0]["title"] == "Has the parts" and saved["updated_by"] == "Dan" and saved["can_edit"]
    assert client.get("/api/teams/999/template", headers=dan).status_code == 404


def test_rules_turned_off_new_and_wrong(client):
    illia = sign_in(client, "illia")
    app_team = team_id(client, illia, "Cova Team")
    data = client.get(f"/api/teams/{app_team}/template", headers=illia).json()
    rules = [{**rule, "enabled": rule["id"] == "has_sections"} for rule in data["rules"]]
    rules.append({"id": "", "check": "llm", "title": "Names the client", "question": "Does it name the client?", "enabled": True})
    saved = client.put(f"/api/teams/{app_team}/template", headers=illia, json={**data, "rules": rules}).json()
    assert saved["rules"][-1]["id"] == "custom_names_the_client"
    result = client.post("/api/reports/check", headers=illia, json={"team_id": app_team, "text": "- **Today**", "check_ai": False}).json()
    assert [rule["title"] for rule in result["rules"]] == ["Has Yesterday / Today / Blockers sections", "Names the client"]
    assert any(point.startswith("Has Yesterday") for point in result["points"])

    no_question = [*data["rules"], {"id": "", "check": "llm", "title": "Empty", "enabled": True}]
    assert client.put(f"/api/teams/{app_team}/template", headers=illia, json={**data, "rules": no_question}).status_code == 422


def test_reset(client):
    illia = sign_in(client, "illia")
    app_team = team_id(client, illia, "Cova Team")
    data = client.get(f"/api/teams/{app_team}/template", headers=illia).json()
    client.put(f"/api/teams/{app_team}/template", headers=illia, json={"rules": data["rules"][:1]})
    reset = client.post(f"/api/teams/{app_team}/template/reset", headers=illia).json()
    assert reset["rules"] == db.default_template()["rules"]


def test_a_team_format_is_used_checked_and_reset(client, no_ai):
    illia, mike = sign_in(client, "illia"), sign_in(client, "mike")
    cova = team_id(client, illia, "Cova Team")
    data = client.get(f"/api/teams/{cova}/template", headers=illia).json()
    assert data["layout"]["done"] == "Yesterday" and data["layout"]["icons"] is True
    layout = {**data["layout"], "done": "Done", "today": "Plan", "icons": False}
    assert client.put(f"/api/teams/{cova}/template", headers=illia, json={**data, "layout": layout}).json()["layout"]["done"] == "Done"
    body = {"team_id": cova, "notes": "fixed the login page, merged", "day": DAY, "done_hours": 7, "plan_hours": 8, "reviewer": "Illia",
            "repo": "", "greeting": "Hi", "check_ai": False}
    result = client.post("/api/reports/write", headers=mike, json=body).json()
    assert "**Done** (7 hours)" in result["text"] and ":dart:" not in result["text"]
    assert {rule["id"]: rule["status"] for rule in result["rules"]}["has_sections"] == "PASS"  # the rule follows the names

    for wrong in ({"done": " "}, {"done": "plan"}, {"today": "**Plan**"}):  # empty, the same as another, markup
        response = client.put(f"/api/teams/{cova}/template", headers=illia, json={**data, "layout": {**layout, **wrong}})
        assert response.status_code == 422
    preview = client.post("/api/template/preview", headers=mike, json={"done": "Shipped"}).json()
    assert "Shipped" in preview["html"]
    assert client.post(f"/api/teams/{cova}/template/reset", headers=illia).json()["layout"]["done"] == "Yesterday"


def test_only_the_owner_renames_the_company(client):
    dan, illia, admin = sign_in(client, "dan"), sign_in(client, "illia"), sign_in(client, "admin")
    assert client.get("/api/me", headers=illia).json()["company"] == "ZeeSpires"
    for someone in (illia, admin):
        assert client.put("/api/company", headers=someone, json={"name": "Other"}).status_code == 403
    assert client.put("/api/company", headers=dan, json={"name": "  "}).status_code == 422
    assert client.put("/api/company", headers=dan, json={"name": " ZeeSpires   Labs "}).json() == {"name": "ZeeSpires Labs"}
    assert client.get("/api/me", headers=illia).json()["company"] == "ZeeSpires Labs"
    assert client.get("/api/console", headers=admin).json()["companies"][0]["name"] == "ZeeSpires Labs"
