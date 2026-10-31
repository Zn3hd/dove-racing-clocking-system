"""Same-origin dashboard delivery and API boundary checks."""
from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_assets_and_security_headers():
    with TestClient(app) as client:
        redirect = client.get("/", follow_redirects=False)
        assert redirect.status_code == 307
        assert redirect.headers["location"] == "/dashboard/"
        for path, content_type in [("/dashboard/", "text/html"),
                                   ("/dashboard/app.js", "javascript"),
                                   ("/dashboard/scan.html", "text/html"),
                                   ("/dashboard/scan.js", "javascript"),
                                   ("/dashboard/qr-core.js", "javascript"),
                                   ("/dashboard/vendor/jsQR.js", "javascript"),
                                   ("/dashboard/styles.css", "text/css")]:
            response = client.get(path)
            assert response.status_code == 200
            assert content_type in response.headers["content-type"]
            assert response.headers["cache-control"] == "no-store"
            assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
            assert response.headers["x-content-type-options"] == "nosniff"
            assert 'camera=(self)' in response.headers['permissions-policy']
        assert client.get("/dashboard/../.env").status_code == 404
        assert client.get("/health").status_code == 200


def test_dashboard_does_not_bypass_api_authentication(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1/dove_test")
    with TestClient(app) as client:
        assert client.get("/dashboard/").status_code == 200
        for path in ("/clubs", "/participants", "/lofts", "/pigeons"):
            assert client.get(path).status_code == 401
