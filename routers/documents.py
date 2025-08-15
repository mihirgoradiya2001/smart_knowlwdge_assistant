from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Security
from models.document import Document
from utils.response import api_response
from typing import Dict
import os
from tasks.celery_tasks import process_document_task
from utils.jwt import get_current_user_id
import logging

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("api.documents")

# In-memory document store for demo
fake_documents_db: Dict[int, dict] = {}
doc_id_counter = 1

SUPPORTED_FORMATS = ["pdf", "txt", "md"]


def _get_max_upload_mb() -> int:
	try:
		return int(os.getenv("MAX_UPLOAD_MB", "25"))
	except Exception:
		return 25


def validate_file_extension(filename: str):
	ext = filename.split(".")[-1].lower()
	if ext not in SUPPORTED_FORMATS:
		logger.warning("upload_unsupported_extension", extra={"file_name": filename, "ext": ext})
		raise HTTPException(status_code=400, detail="Unsupported file format")
	return ext


def validate_file_upload(file: UploadFile, max_mb: int):
	# Best-effort MIME check
	allowed_mimes = {
		"pdf": ["application/pdf"],
		"txt": ["text/plain"],
		"md": ["text/markdown", "text/plain"],
	}
	ext = validate_file_extension(file.filename)
	if file.content_type and file.content_type not in sum(allowed_mimes.values(), []):
		# Allow some providers to send generic text/plain for md
		if not (ext in ("txt", "md") and file.content_type == "text/plain"):
			logger.warning("upload_unsupported_mime", extra={"file_name": file.filename, "mime": file.content_type})
			raise HTTPException(status_code=400, detail="Unsupported MIME type")
	# Note: FastAPI UploadFile does not expose size before reading; enforce via content length header if present
	return ext


@router.post("/upload")
async def upload_document(
	file: UploadFile = File(...),
	user_id: int = Security(get_current_user_id),
):
	ext = validate_file_upload(file, _get_max_upload_mb())
	global doc_id_counter
	doc_id = doc_id_counter
	doc_id_counter += 1

	# Save file locally (for demo; use cloud storage in production)
	os.makedirs("uploads", exist_ok=True)
	save_path = f"uploads/{doc_id}_{file.filename}"

	# Read and size-check the content
	content = await file.read()
	size_bytes = len(content)
	limit_mb = _get_max_upload_mb()
	size_mb = size_bytes / (1024 * 1024)
	if size_mb > limit_mb:
		logger.warning("upload_too_large", extra={"doc_id": doc_id, "file_name": file.filename, "size_mb": round(size_mb, 2)})
		raise HTTPException(status_code=400, detail=f"File too large. Max {limit_mb}MB allowed")

	with open(save_path, "wb") as f:
		f.write(content)

	# Add to fake DB
	fake_documents_db[doc_id] = {
		"id": doc_id,
		"filename": file.filename,
		"owner_id": user_id,
		"status": "pending",
		"error": None,
	}

	# Trigger async embedding job with Celery
	process_document_task.delay(doc_id, save_path)

	logger.info(
		"upload_accepted",
		extra={
			"doc_id": doc_id,
			"user_id": user_id,
			"file_name": file.filename,
			"ext": ext,
			"mime": file.content_type,
			"size_bytes": size_bytes,
		},
	)

	return api_response(
		data=Document(id=doc_id, filename=file.filename, owner_id=user_id, status="pending").model_dump(),
		message="File uploaded successfully. Embedding job triggered.",
		status_code=201,
	)