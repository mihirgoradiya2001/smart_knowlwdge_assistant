from fastapi.testclient import TestClient
from conftest import register_and_login


def test_register_and_login_success(app_client: TestClient):
	# Register and login returns token
	token = register_and_login(app_client)
	assert isinstance(token, str) and len(token) > 10


def test_login_invalid_credentials(app_client: TestClient):
	# Register
	app_client.post("/auth/register", json={"email": "a@b.com", "password": "x"})
	# Wrong password
	resp = app_client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
	assert resp.status_code == 401
	assert resp.json()["message"] == "Invalid credentials" 