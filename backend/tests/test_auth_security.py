from fastapi.testclient import TestClient
from app.main import app
from app.auth import hash_password, verify_password

client = TestClient(app)

def test_password_hashing():
    digest = hash_password("very-long-demo-password")
    assert digest != "very-long-demo-password"
    assert verify_password("very-long-demo-password", digest)
    assert not verify_password("incorrect-password", digest)

def test_me_requires_authentication():
    response = client.get("/auth/me")
    assert response.status_code == 401

def test_participant_creation_requires_authentication():
    response = client.post("/participants", json={
        "full_name": "Example", "email": "example@example.test",
        "password": "long-example-password", "role": "guest"})
    assert response.status_code == 401

def test_loft_verification_requires_authentication():
    response = client.post("/lofts/00000000-0000-0000-0000-000000000001/verify")
    assert response.status_code == 401
