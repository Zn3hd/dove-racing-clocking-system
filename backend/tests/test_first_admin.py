"""Disabled bootstrap must reject requests without consulting the database."""
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.mark.parametrize("configured,supplied", [
    (None, None),
    ("short", "short"),
    ("x" * 64, None),
    ("x" * 64, "wrong-secret"),
    ("x" * 64, "invalid-\u00e9-secret"),
])
def test_bootstrap_rejects_before_database(monkeypatch, configured, supplied):
    if configured is None:
        monkeypatch.delenv("ADMIN_BOOTSTRAP_SECRET", raising=False)
    else:
        monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", configured)

    def forbidden_database():
        pytest.fail("Unauthorized bootstrap opened the database")

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = forbidden_database
    try:
        # HTTPX uses ASCII strings for headers; bytes exercise unexpected input.
        headers = {b"x-setup-secret": supplied.encode("utf-8")} if supplied else {}
        response = TestClient(app).post("/setup/first-admin", headers=headers, json={
            "full_name": "Test Chairman", "email": "chairman@example.test",
            "password": "test-password-for-bootstrap",
        })
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
