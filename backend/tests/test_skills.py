from fastapi.testclient import TestClient

from main import app


def test_list_skills_includes_echo_and_current_time():
    client = TestClient(app)
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body["skills"]}
    assert {"echo", "current_time", "web_search"}.issubset(names)
    for item in body["skills"]:
        assert item["description"]
        assert "source" in item
        assert item["source"] in ("python", "markdown")


def test_invoke_echo_returns_input_verbatim():
    client = TestClient(app)
    resp = client.post("/api/skills/echo", json={"input": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["skill"] == "echo"
    assert body["output"] == "hello"
    assert body["metadata"]["length"] == 5


def test_invoke_echo_upper_flag():
    client = TestClient(app)
    resp = client.post("/api/skills/echo", json={"input": "hi", "args": {"upper": True}})
    assert resp.json()["output"] == "HI"


def test_invoke_skill_with_empty_body_is_allowed():
    client = TestClient(app)
    resp = client.post("/api/skills/echo")
    assert resp.status_code == 200
    assert resp.json()["output"] == ""


def test_invoke_current_time_returns_iso():
    client = TestClient(app)
    resp = client.post("/api/skills/current_time")
    body = resp.json()
    assert body["status"] == "ok"
    assert "T" in body["output"]
    assert body["metadata"]["utc"] == body["output"]


def test_invoke_unknown_skill_returns_error_envelope():
    client = TestClient(app)
    resp = client.post("/api/skills/does_not_exist", json={"input": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert body["skill"] == "does_not_exist"
    assert body["message"]
    assert body["output"] is None