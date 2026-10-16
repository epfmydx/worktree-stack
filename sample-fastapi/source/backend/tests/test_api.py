"""Example API checks; database writes require the disposable CI contract."""
import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db import engine
from app.main import app
from app.routes.todos import TodoIn


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:
        yield client
        client.portal.call(engine.dispose)


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_exposes_todo_routes(client):
    schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/api/todos"]
    assert "post" in schema["paths"]["/api/todos"]
    assert "delete" in schema["paths"]["/api/todos/{todo_id}"]


@pytest.mark.parametrize("text", ["", "x" * 256])
def test_invalid_todo_schema(text):
    with pytest.raises(ValidationError):
        TodoIn(text=text)


@pytest.mark.database
def test_postgres_create_list_delete_and_missing_todo(client):
    target = urlparse(os.environ["DATABASE_URL"])
    assert os.environ.get("WORKTREE_STACK_CI") == "1", "Run DB checks with wt-test"
    assert target.hostname == "ci-postgres" and target.path == "/worktree_ci", "Disposable DB required"
    created = client.post("/api/todos", json={"text": "Disposable CI task"})
    assert created.status_code == 201
    todo = created.json()
    assert todo["text"] == "Disposable CI task"
    assert todo["done"] is False
    assert todo in client.get("/api/todos").json()
    assert client.delete(f"/api/todos/{todo['id']}").status_code == 204
    assert all(item["id"] != todo["id"] for item in client.get("/api/todos").json())
    assert client.delete(f"/api/todos/{todo['id']}").status_code == 404
