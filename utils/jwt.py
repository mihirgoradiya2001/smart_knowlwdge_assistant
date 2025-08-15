import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
import requests
from typing import Optional
import logging

# FastAPI imports for dependency-based auth
from fastapi import Header, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET", "your_jwt_secret_here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_indexes/")

http_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("auth")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception as err:  # broad to log actual cause
        logger.warning("JWT verification failed: %s", str(err))
        return None


# Example usage in tasks/celery_tasks.py and routers/rag.py

def get_faiss_index_path(doc_id):
    return os.path.join(FAISS_INDEX_PATH, f"{doc_id}.index")


def get_chunks_path(doc_id):
    return os.path.join(FAISS_INDEX_PATH, f"{doc_id}_chunks.txt")


def query_gemini_llm(question, context):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}"}
    payload = {
        "contents": [
            {"parts": [{"text": f"Context: {context}\nQuestion: {question}"}]}
        ]
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return "Error: Unable to get response from Gemini"


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    Authorization: Optional[str] = Header(None, include_in_schema=False),
) -> int:
    """
    FastAPI dependency to extract and validate the current user id from a Bearer token.
    Prefer standard HTTP Bearer auth (works with Swagger Authorize button).
    Also falls back to raw Authorization header if provided.
    Returns 401 when header is missing/invalid.
    """
    token: Optional[str] = None

    if credentials and credentials.scheme and credentials.credentials:
        if credentials.scheme.lower() == "bearer":
            creds = credentials.credentials.strip()
            token = creds.split(" ", 1)[1].strip() if creds.lower().startswith("bearer ") else creds
    elif Authorization:
        raw = Authorization.strip()
        token = raw.split(" ", 1)[1].strip() if raw.lower().startswith("bearer ") else raw

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    payload = verify_access_token(token)
    if not payload or "id" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return int(payload["id"])