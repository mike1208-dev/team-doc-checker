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
    email = {"ava": "owner@zeenote.com", "sam": "manager@zeenote.com", "kai": "member@zeenote.com"}.get(who, f"{who}@zeenote.com")
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
    assert client.post("/api/login", json={"email": "member@zeenote.com", "password": "wrong"}).status_code == 401
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_teams_of_each_role(client):
    owner = client.get("/api/me", headers=sign_in(client, "ava")).json()
    assert owner["owner"] and [team["role"] for team in owner["teams"]] == ["Owner"] * 3
    sam = client.get("/api/me", headers=sign_in(client, "sam")).json()
    assert [(team["name"], team["role"]) for team in sam["teams"]] == [("App team", "Manager"), ("Web team", "Manager")]
    token = client.post("/api/login", json={"email": " Member@ZeeNote.com", "password": db.FAKE_PASSWORD}).json()["token"]  # not case sensitive
    kai = client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert [(team["name"], team["role"]) for team in kai["teams"]] == [("App team", "Member"), ("Web team", "Member")]


def test_admin_sees_numbers_only(client, no_ai):
    admin = sign_in(client, "admin")
    me = client.get("/api/me", headers=admin).json()
    assert me["admin"] and not me["owner"] and me["teams"] == []
    kai = sign_in(client, "kai")
    app_team = team_id(client, kai, "App team")
    client.post("/api/reports", headers=kai, json={"team_id": app_team, "day": DAY, "text": "- **Today**"})
    company = client.get("/api/console", headers=admin).json()["companies"][0]
    assert (company["name"], company["owner"], company["people"], company["teams"], company["reports"]) == ("Acme Inc.", "Ava", 7, 3, 1)
    assert client.get(f"/api/teams/{app_team}/template", headers=admin).status_code == 403
    assert client.get("/api/console", headers=sign_in(client, "ava")).status_code == 403


def test_old_sample_starts_again(tmp_path):
    path = tmp_path / "old.db"
    with db.connect(path) as old:
        old.execute("create table users (email text primary key, name text not null, owner integer not null default 0)")
        old.execute("insert into users values ('ava@acme.example', 'Ava', 1)")
    db.setup(path)
    with db.connect(path) as new:
        assert new.execute("select email from users where owner = 1").fetchone()[0] == "owner@zeenote.com"


def test_logout(client):
    headers = sign_in(client, "kai")
    client.post("/api/logout", headers=headers)
    assert client.get("/api/me", headers=headers).status_code == 401


def test_first_settings(client):
    kai, sam = sign_in(client, "kai"), sign_in(client, "sam")
    web = team_id(client, kai, "Web team")
    assert client.get(f"/api/teams/{web}/settings", headers=kai).json() == db.default_settings("Sam")
    assert client.get(f"/api/teams/{web}/settings", headers=sam).json()["reviewer"] == ""  # not himself
    assert client.get(f"/api/teams/{web}/settings", headers=sign_in(client, "leo")).status_code == 403


def test_write_uses_and_keeps_my_settings(client, no_ai):
    kai = sign_in(client, "kai")
    web, app_team = team_id(client, kai, "Web team"), team_id(client, kai, "App team")
    body = {"team_id": web, "notes": "fixed the login page, merged", "day": DAY, "done_hours": 7, "plan_hours": 8, "reviewer": "@Mina ",
            "repo": "https://github.com/acme/web/", "greeting": "Hello team.", "check_ai": False}
    result = client.post("/api/reports/write", headers=kai, json=body).json()
    assert result["text"].startswith("@Mina  \nHello team.")
    assert "Fixed the login page ― **Merged**" in result["text"] and "(7 hours)" in result["text"]
    assert "<strong>" in result["html"] and '"ops"' in result["slack"]
    assert "rules passed" in result["summary"]
    kept = client.get(f"/api/teams/{web}/settings", headers=kai).json()
    assert (kept["reviewer"], kept["repo"], kept["greeting"], kept["done_hours"]) == ("Mina", "https://github.com/acme/web", "Hello team.", 7)
    assert client.get(f"/api/teams/{app_team}/settings", headers=kai).json()["reviewer"] == "Sam"  # each team has its own
    client.post("/api/reports/write", headers=kai, json={**body, "repo": "", "greeting": ""})
    kept = client.get(f"/api/teams/{web}/settings", headers=kai).json()
    assert (kept["repo"], kept["greeting"]) == (db.DEFAULT_REPO, db.GREETING)  # an empty one gets its default back

    wrong = client.post("/api/reports/write", headers=kai, json={**body, "repo": "github.com/acme"})
    assert wrong.status_code == 422 and "repo link" in wrong.json()["detail"]


def test_answers_join_the_notes(client, no_ai):
    kai = sign_in(client, "kai")
    body = {"team_id": team_id(client, kai, "App team"), "notes": "fixed the login page \n", "day": DAY, "check_ai": False,
            "answers": ["pr 30 is merged", " ", " QA means testing "]}
    result = client.post("/api/reports/write", headers=kai, json=body).json()
    assert result["notes"] == "fixed the login page\npr 30 is merged\nQA means testing"


def test_writer_errors_are_messages(client, monkeypatch):
    kai = sign_in(client, "kai")
    body = {"team_id": team_id(client, kai, "App team"), "notes": " ", "day": DAY, "check_ai": False}
    response = client.post("/api/reports/write", headers=kai, json=body)
    assert response.status_code == 422 and response.json()["detail"] == "Please write some notes first."


def test_only_team_people_write_and_the_owner_doesnt(client, no_ai):
    leo = sign_in(client, "leo")
    app_team = team_id(client, sign_in(client, "kai"), "App team")
    body = {"team_id": app_team, "notes": "fixed it", "day": DAY, "check_ai": False}
    assert client.post("/api/reports/write", headers=leo, json=body).status_code == 403
    assert client.post("/api/reports/write", headers=sign_in(client, "ava"), json=body).status_code == 403
    assert client.post("/api/reports", headers=leo, json={"team_id": app_team, "day": DAY, "text": "x"}).status_code == 403


def test_saved_reports_are_only_mine(client):
    kai, lina = sign_in(client, "kai"), sign_in(client, "lina")
    app_team = team_id(client, kai, "App team")
    report_id = client.post("/api/reports", headers=kai, json={"team_id": app_team, "day": DAY, "notes": "n", "text": "- **Today**"}).json()["id"]
    assert [row["id"] for row in client.get("/api/reports", headers=kai).json()] == [report_id]
    assert client.get("/api/reports", headers=lina).json() == []
    assert client.get(f"/api/reports/{report_id}", headers=lina).status_code == 404
    report = client.get(f"/api/reports/{report_id}", headers=kai).json()
    assert report["team"] == "App team" and "<strong>Today</strong>" in report["html"]
    assert client.post("/api/reports", headers=kai, json={"team_id": app_team, "day": DAY, "text": "  "}).status_code == 422


def test_who_can_change_the_template(client):
    sam, kai, yuki, ava = (sign_in(client, who) for who in ("sam", "kai", "yuki", "ava"))
    app_team, support = team_id(client, ava, "App team"), team_id(client, ava, "Support team")
    data = client.get(f"/api/teams/{app_team}/template", headers=kai).json()
    assert data["can_edit"] is False and len(data["rules"]) == 8
    assert client.put(f"/api/teams/{app_team}/template", headers=kai, json=data).status_code == 403
    assert client.put(f"/api/teams/{app_team}/template", headers=yuki, json=data).status_code == 403
    assert client.get(f"/api/teams/{support}/template", headers=sam).status_code == 403
    rules = [{**rule, "title": "Has the parts"} if rule["id"] == "has_sections" else rule for rule in data["rules"]]
    saved = client.put(f"/api/teams/{app_team}/template", headers=ava, json={**data, "rules": rules}).json()
    assert saved["rules"][0]["title"] == "Has the parts" and saved["updated_by"] == "Ava" and saved["can_edit"]
    assert client.get("/api/teams/999/template", headers=ava).status_code == 404


def test_rules_turned_off_new_and_wrong(client):
    sam = sign_in(client, "sam")
    app_team = team_id(client, sam, "App team")
    data = client.get(f"/api/teams/{app_team}/template", headers=sam).json()
    rules = [{**rule, "enabled": rule["id"] == "has_sections"} for rule in data["rules"]]
    rules.append({"id": "", "check": "llm", "title": "Names the client", "question": "Does it name the client?", "enabled": True})
    saved = client.put(f"/api/teams/{app_team}/template", headers=sam, json={**data, "rules": rules}).json()
    assert saved["rules"][-1]["id"] == "custom_names_the_client"
    result = client.post("/api/reports/check", headers=sam, json={"team_id": app_team, "text": "- **Today**", "check_ai": False}).json()
    assert [rule["title"] for rule in result["rules"]] == ["Has Yesterday / Today / Blockers sections", "Names the client"]
    assert any(point.startswith("Has Yesterday") for point in result["points"])

    no_question = [*data["rules"], {"id": "", "check": "llm", "title": "Empty", "enabled": True}]
    assert client.put(f"/api/teams/{app_team}/template", headers=sam, json={**data, "rules": no_question}).status_code == 422


def test_reset(client):
    sam = sign_in(client, "sam")
    app_team = team_id(client, sam, "App team")
    data = client.get(f"/api/teams/{app_team}/template", headers=sam).json()
    client.put(f"/api/teams/{app_team}/template", headers=sam, json={"rules": data["rules"][:1]})
    reset = client.post(f"/api/teams/{app_team}/template/reset", headers=sam).json()
    assert reset["rules"] == db.default_template()["rules"]
