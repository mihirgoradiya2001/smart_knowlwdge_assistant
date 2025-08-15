import os
import shutil
import tempfile
import importlib
import pytest
from fastapi.testclient import TestClient
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def temp_dirs():
	base = tempfile.mkdtemp(prefix="ska_tests_")
	faiss_dir = os.path.join(base, "faiss")
	state_dir = os.path.join(base, "state")
	logs_dir = os.path.join(base, "logs")
	os.makedirs(faiss_dir, exist_ok=True)
	os.makedirs(state_dir, exist_ok=True)
	os.makedirs(logs_dir, exist_ok=True)
	yield {"base": base, "faiss": faiss_dir, "state": state_dir, "logs": logs_dir}
	shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(scope="session")
def app_client(temp_dirs):
	# Set env before importing app
	os.environ["FAISS_INDEX_PATH"] = temp_dirs["faiss"]
	os.environ["STATE_DIR"] = temp_dirs["state"]
	os.environ["LOG_DIR"] = temp_dirs["logs"]
	os.environ["JWT_SECRET"] = "test_secret"
	os.environ["FREE_DAILY_QUESTION_LIMIT"] = "20"
	os.environ["USE_FAKE_EMBEDDINGS"] = "1"
	# Import app fresh
	import main as main_module
	importlib.reload(main_module)
	app = main_module.app
	client = TestClient(app)
	return client


@pytest.fixture(autouse=True)
def reset_in_memory_stores(temp_dirs):
	# Clear in-memory fake DBs and counters between tests
	from routers import auth as auth_router
	from routers import documents as documents_router
	# Reset users
	auth_router.fake_users_db.clear()
	# Reset docs
	documents_router.fake_documents_db.clear()
	documents_router.doc_id_counter = 1
	# Also clear state (history/usage) and faiss dirs to avoid cross-test contamination
	for path in (temp_dirs["state"], temp_dirs["faiss"]):
		for root, dirs, files in os.walk(path):
			for name in files:
				try:
					os.unlink(os.path.join(root, name))
				except FileNotFoundError:
					pass
	yield


def register_and_login(client: TestClient, email: str = "user@example.com", password: str = "Passw0rd!") -> str:
	resp = client.post("/auth/register", json={"email": email, "password": password})
	assert resp.status_code in (200, 201)
	resp = client.post("/auth/login", json={"email": email, "password": password})
	assert resp.status_code == 200, resp.text
	return resp.json()["data"]["access_token"] 