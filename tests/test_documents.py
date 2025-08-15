import io
import os
from fastapi.testclient import TestClient
from conftest import register_and_login


def test_upload_requires_auth(app_client: TestClient):
	resp = app_client.post("/documents/upload", files={"file": ("a.txt", b"hi")})
	assert resp.status_code in (401, 403)


def test_upload_unsupported_extension(app_client: TestClient):
	token = register_and_login(app_client)
	headers = {"Authorization": f"Bearer {token}"}
	resp = app_client.post("/documents/upload", headers=headers, files={"file": ("a.docx", b"hi")})
	assert resp.status_code == 400
	assert resp.json()["message"] == "Unsupported file format"


def test_upload_too_large(app_client: TestClient, monkeypatch):
	# Force small max size
	os.environ["MAX_UPLOAD_MB"] = "0"
	token = register_and_login(app_client)
	headers = {"Authorization": f"Bearer {token}"}
	big_content = b"x" * (1024 * 1024)  # 1 MB
	resp = app_client.post("/documents/upload", headers=headers, files={"file": ("a.txt", big_content)})
	assert resp.status_code == 400
	assert "File too large" in resp.json()["message"]


def test_upload_success_triggers_task(app_client: TestClient):
	# Ensure reasonable size limit for this test
	os.environ["MAX_UPLOAD_MB"] = "25"
	token = register_and_login(app_client)
	headers = {"Authorization": f"Bearer {token}"}
	resp = app_client.post("/documents/upload", headers=headers, files={"file": ("a.txt", b"Hello world")})
	assert resp.status_code == 201
	payload = resp.json()["data"]
	assert payload["status"] == "pending"
	assert payload["id"] == 1 