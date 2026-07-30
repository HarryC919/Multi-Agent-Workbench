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


# ------------------------------------------------------------------
# Markdown skill CRUD (Phase 3 round 2)
# ------------------------------------------------------------------


def _patch_skills_dir(monkeypatch, tmp_path):
    """Point the router's skills_md dir at a tmp path so tests don't touch real files."""
    monkeypatch.setattr("app.routers.skills._skills_dir", lambda: tmp_path)
    # Reload from the (empty) tmp dir to clear any real .md skills first.
    from app.skills.registry import reload_markdown_skills

    reload_markdown_skills(tmp_path)
    return tmp_path


def test_md_crud_create_list_get_update_delete(monkeypatch, tmp_path):
    """Full lifecycle: create -> list contains -> get source -> update -> delete."""
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)

    # Create
    resp = client.post("/api/skills/md", json={
        "name": "my_skill",
        "description": "A test skill",
        "content": "You are a test assistant.",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "my_skill"

    # List contains it with source=markdown
    resp = client.get("/api/skills")
    item = next(s for s in resp.json()["skills"] if s["name"] == "my_skill")
    assert item["source"] == "markdown"
    assert item["description"] == "A test skill"

    # Get source
    resp = client.get("/api/skills/md/my_skill")
    assert resp.status_code == 200
    src = resp.json()
    assert src["name"] == "my_skill"
    assert src["description"] == "A test skill"
    assert "test assistant" in src["content"]

    # Update
    resp = client.put("/api/skills/md/my_skill", json={
        "description": "Updated desc",
        "content": "You are an updated assistant.",
    })
    assert resp.status_code == 200
    # Verify update took effect
    resp = client.get("/api/skills/md/my_skill")
    assert resp.json()["description"] == "Updated desc"
    assert "updated assistant" in resp.json()["content"]

    # Delete
    resp = client.delete("/api/skills/md/my_skill")
    assert resp.status_code == 200
    # Verify gone
    resp = client.get("/api/skills/md/my_skill")
    assert resp.status_code == 404


def test_md_create_invalid_name_rejected(monkeypatch, tmp_path):
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)
    for bad in ["1starts_with_digit", "has space", "has/slash", "..", "has.dot", ""]:
        resp = client.post("/api/skills/md", json={"name": bad, "description": "", "content": "x"})
        assert resp.status_code == 400, f"expected 400 for {bad!r}"


def test_md_create_duplicate_name_rejected(monkeypatch, tmp_path):
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)
    # Duplicate with a Python skill name.
    resp = client.post("/api/skills/md", json={"name": "echo", "description": "", "content": "x"})
    assert resp.status_code == 400
    # Duplicate with an existing md skill.
    client.post("/api/skills/md", json={"name": "dup", "description": "", "content": "x"})
    resp = client.post("/api/skills/md", json={"name": "dup", "description": "", "content": "x"})
    assert resp.status_code == 400


def test_md_delete_python_skill_rejected(monkeypatch, tmp_path):
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)
    resp = client.delete("/api/skills/md/echo")
    assert resp.status_code == 400
    assert "built-in" in resp.json()["detail"].lower()


def test_md_get_nonexistent_returns_404(monkeypatch, tmp_path):
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)
    resp = client.get("/api/skills/md/does_not_exist")
    assert resp.status_code == 404


def test_md_update_preserves_description_when_none(monkeypatch, tmp_path):
    """PUT with description=None keeps the existing description."""
    _patch_skills_dir(monkeypatch, tmp_path)
    client = TestClient(app)
    client.post("/api/skills/md", json={
        "name": "keep_desc",
        "description": "Original desc",
        "content": "Original content",
    })
    resp = client.put("/api/skills/md/keep_desc", json={"description": None, "content": "New content"})
    assert resp.status_code == 200
    resp = client.get("/api/skills/md/keep_desc")
    assert resp.json()["description"] == "Original desc"
    assert resp.json()["content"] == "New content"