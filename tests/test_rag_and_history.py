import os
import faiss
import numpy as np
from fastapi.testclient import TestClient
from conftest import register_and_login
from utils.history import clear_daily_cache, _get_usage_file
from utils.jwt import verify_access_token


def create_dummy_index_and_chunks(base_path: str, doc_id: int):
	# Create minimal FAISS index and chunks for testing retrieval
	os.makedirs(base_path, exist_ok=True)
	chunks_path = os.path.join(base_path, f"{doc_id}_chunks.txt")
	with open(chunks_path, "w", encoding="utf-8") as f:
		f.write("Chunk one\n---\nChunk two\n---\nChunk three")
	# 2D vectors: 3 chunks x 5 dims
	index = faiss.IndexFlatL2(5)
	vecs = np.stack([
		np.ones(5, dtype="float32"),
		2 * np.ones(5, dtype="float32"),
		3 * np.ones(5, dtype="float32"),
	]).astype("float32")
	index.add(vecs)
	faiss.write_index(index, os.path.join(base_path, f"{doc_id}.index"))


def test_rag_ask_without_index_returns_404(app_client: TestClient):
	token = register_and_login(app_client)
	headers = {"Authorization": f"Bearer {token}"}
	resp = app_client.post("/rag/ask", headers=headers, params={"doc_id": 999, "question": "Hello?"})
	assert resp.status_code == 404


def test_rag_ask_success_and_history(app_client: TestClient):
	# Prepare dummy index
	faiss_dir = os.environ["FAISS_INDEX_PATH"]
	create_dummy_index_and_chunks(faiss_dir, doc_id=1)
	# Auth
	token = register_and_login(app_client)
	headers = {"Authorization": f"Bearer {token}"}
	# Ask
	resp = app_client.post("/rag/ask", headers=headers, params={"doc_id": 1, "question": "What is inside?"})
	assert resp.status_code == 200
	data = resp.json()["data"]
	assert "answer" in data and "context" in data
	# History
	hist = app_client.get("/history", headers=headers)
	assert hist.status_code == 200
	body = hist.json()["data"]
	assert body["total"] >= 1
	assert len(body["items"]) >= 1


def test_daily_limit_enforced(app_client: TestClient, monkeypatch):
	# Lower the limit for this test
	os.environ["FREE_DAILY_QUESTION_LIMIT"] = "1"
	faiss_dir = os.environ["FAISS_INDEX_PATH"]
	create_dummy_index_and_chunks(faiss_dir, doc_id=2)
	# Auth
	email = "limit@example.com"
	token = register_and_login(app_client, email=email)
	headers = {"Authorization": f"Bearer {token}"}
	# Get actual user_id from token
	payload = verify_access_token(token)
	user_id = payload["id"]
	# Ensure clean usage state across all mechanisms
	clear_daily_cache()
	state_dir = os.environ["STATE_DIR"]
	for root, dirs, files in os.walk(state_dir):
		for name in files:
			try:
				os.unlink(os.path.join(root, name))
			except FileNotFoundError:
				pass
	# Verify clean state by checking count_today
	from utils.history import count_today
	count_before = count_today(user_id)
	assert count_before == 0, f"Expected 0 usage for user {user_id}, got {count_before}"
	# First question succeeds
	resp1 = app_client.post("/rag/ask", headers=headers, params={"doc_id": 2, "question": "Hi?"})
	assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}: {resp1.text}"
	# Second question blocked
	resp2 = app_client.post("/rag/ask", headers=headers, params={"doc_id": 2, "question": "Again?"})
	assert resp2.status_code == 429 