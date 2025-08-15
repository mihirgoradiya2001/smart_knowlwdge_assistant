from fastapi import APIRouter, HTTPException, Query, Depends, Security
from utils.response import api_response
import faiss
import numpy as np
from langchain.embeddings import HuggingFaceEmbeddings
import os
from utils.jwt import get_current_user_id
from utils.history import append_history_entry, enforce_daily_limit
from datetime import datetime
import logging
from utils.logging_config import hash_text

router = APIRouter(prefix="/rag", tags=["rag"])
logger = logging.getLogger("api.rag")

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_indexes/")
USE_FAKE_EMBEDDINGS = os.getenv("USE_FAKE_EMBEDDINGS", "0") == "1"


def load_faiss_index(doc_id):
    faiss_path = os.path.join(FAISS_INDEX_PATH, f"{doc_id}.index")
    if not os.path.exists(faiss_path):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return faiss.read_index(faiss_path)


def get_chunks_for_doc(doc_id):
    chunks_path = os.path.join(FAISS_INDEX_PATH, f"{doc_id}_chunks.txt")
    if not os.path.exists(chunks_path):
        return []
    with open(chunks_path, "r", encoding="utf-8") as f:
        # ensure empty lines do not create empty chunks
        content = f.read().strip()
        if not content:
            return []
        return [c for c in content.split("\n---\n") if c.strip()]


def _make_query_vector(question: str, target_dim: int) -> np.ndarray:
    if USE_FAKE_EMBEDDINGS:
        # Deterministic pseudo-embedding for tests: seeded random of target_dim
        seed = int(hash_text(question), 16) % (2**31 - 1)
        rng = np.random.RandomState(seed)
        vec = rng.rand(target_dim).astype("float32")
        return vec
    # Use real embeddings and resize if needed
    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    qv = np.array(embedder.embed_query(question)).astype("float32")
    if qv.shape[0] == target_dim:
        return qv
    if qv.shape[0] > target_dim:
        return qv[:target_dim]
    # pad with zeros
    padded = np.zeros((target_dim,), dtype="float32")
    padded[: qv.shape[0]] = qv
    return padded


def get_relevant_context(question, doc_id, top_k=3):
    index = load_faiss_index(doc_id)
    dim = getattr(index, "d", None)
    if dim is None:
        # Fallback for other index types; attempt to infer from first vector length if possible
        dim = index.d
    question_vec = _make_query_vector(question, dim)
    D, I = index.search(np.expand_dims(question_vec, axis=0), top_k)
    chunks = get_chunks_for_doc(doc_id)
    return [chunks[i] for i in I[0] if 0 <= i < len(chunks)], I[0].tolist()


def query_local_llm(question, context):
    # Placeholder: deterministic stub to keep API functional without external keys
    preview = context[:200].replace("\n", " ") if context else ""
    return f"This is a stubbed answer for: '{question}'. Context preview: '{preview}...'"


@router.post("/ask")
def ask_question(
    doc_id: int = Query(..., gt=0),
    question: str = Query(..., min_length=3),
    user_id: int = Security(get_current_user_id),
):
    # Enforce free daily limit per user (read from env at request time for testability)
    daily_limit = int(os.getenv("FREE_DAILY_QUESTION_LIMIT", "20"))
    enforce_daily_limit(user_id, daily_limit)

    q_hash = hash_text(question)
    context_chunks, indices = get_relevant_context(question, doc_id)
    logger.info("retrieval_done", extra={"doc_id": doc_id, "chunks": len(context_chunks), "indices": indices, "question_hash": q_hash})

    if not context_chunks:
        return api_response(data=[], message="No relevant context found.", status_code=404)

    context = "\n".join(context_chunks)
    answer = query_local_llm(question, context)
    logger.info("answer_generated", extra={"doc_id": doc_id, "question_hash": q_hash, "context_len": len(context)})

    # Append to history (store only preview to keep files small)
    entry = {
        "user_id": user_id,
        "doc_id": doc_id,
        "question": question,
        "answer": answer,
        "context_preview": context[:300],
        "top_k": 3,
        "chunk_indices": indices,
    }
    append_history_entry(user_id, entry)

    return api_response(
        data={"answer": answer, "context": context_chunks},
        message="Answer generated successfully.",
        status_code=200,
    )