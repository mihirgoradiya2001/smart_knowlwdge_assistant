import os
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
import contextvars
from typing import Optional
import hashlib

from fastapi import Request
from starlette.responses import Response

from utils.jwt import verify_access_token

# Context variables for correlation and user identity
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)
user_id_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("user_id", default=None)


class ContextFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		record.correlation_id = correlation_id_ctx.get()
		record.user_id = user_id_ctx.get()
		return True


class JsonFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:
		payload = {
			"timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
			"level": record.levelname,
			"logger": record.name,
			"message": record.getMessage(),
			"correlation_id": getattr(record, "correlation_id", None),
			"user_id": getattr(record, "user_id", None),
		}
		# Optional common fields if set as attributes on the record
		for key in ("path", "method", "status_code", "latency_ms", "client_host", "error"):
			val = getattr(record, key, None)
			if val is not None:
				payload[key] = val
		if record.exc_info:
			payload["exc_info"] = self.formatException(record.exc_info)
		return json.dumps(payload, ensure_ascii=False)


def _make_rotating_file_handler(path: Path, level: int) -> logging.Handler:
	path.parent.mkdir(parents=True, exist_ok=True)
	handler = TimedRotatingFileHandler(path, when="midnight", backupCount=int(os.getenv("LOG_BACKUP_COUNT", "7")), utc=True)
	handler.setLevel(level)
	handler.setFormatter(JsonFormatter())
	handler.addFilter(ContextFilter())
	return handler


def init_logging():
	"""Initialize application logging with console + rotating file handlers."""
	log_dir = Path(os.getenv("LOG_DIR", "logs"))
	level_name = os.getenv("LOG_LEVEL", "INFO").upper()
	level = getattr(logging, level_name, logging.INFO)

	root = logging.getLogger()
	root.setLevel(level)

	# Remove existing handlers to avoid duplicates on reload
	for h in list(root.handlers):
		root.removeHandler(h)

	# Console handler (still JSON for consistency)
	console = logging.StreamHandler()
	console.setLevel(level)
	console.setFormatter(JsonFormatter())
	console.addFilter(ContextFilter())
	root.addHandler(console)

	# File handlers
	app_log = _make_rotating_file_handler(log_dir / "app.log", level)
	error_log = _make_rotating_file_handler(log_dir / "error.log", logging.ERROR)
	root.addHandler(app_log)
	root.addHandler(error_log)

	logging.getLogger(__name__).info("Logging initialized")


def install_request_logging(app):
	"""Attach request logging middleware to the FastAPI app."""
	logger = logging.getLogger("request")

	@app.middleware("http")
	async def _log_middleware(request: Request, call_next):
		# Correlation ID from headers if provided; otherwise generate
		corr = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
		if not corr:
			corr = os.urandom(8).hex()
		correlation_id_ctx.set(corr)

		# Best-effort parse of user id from Authorization to enrich logs
		auth_header = request.headers.get("Authorization")
		user_id_ctx.set(None)
		if auth_header:
			raw = auth_header.split(" ", 1)[1] if " " in auth_header else auth_header
			payload = verify_access_token(raw)
			if payload and "id" in payload:
				try:
					user_id_ctx.set(int(payload["id"]))
				except Exception:
					user_id_ctx.set(None)

		start = datetime.utcnow()
		try:
			response: Response = await call_next(request)
			latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
			logger.info(
				"request_completed",
				extra={
					"path": request.url.path,
					"method": request.method,
					"status_code": response.status_code,
					"latency_ms": latency_ms,
					"client_host": request.client.host if request.client else None,
				},
			)
			return response
		except Exception as exc:
			latency_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
			logger.error(
				"request_failed",
				exc_info=True,
				extra={
					"path": request.url.path,
					"method": request.method,
					"status_code": 500,
					"latency_ms": latency_ms,
					"client_host": request.client.host if request.client else None,
				},
			)
			raise
		finally:
			# Clear context to avoid bleeding into other requests
			correlation_id_ctx.set(None)
			user_id_ctx.set(None)


def init_worker_logging():
	"""Initialize logging for Celery workers with a dedicated rotating file."""
	log_dir = Path(os.getenv("LOG_DIR", "logs"))
	level_name = os.getenv("LOG_LEVEL", "INFO").upper()
	level = getattr(logging, level_name, logging.INFO)

	logger = logging.getLogger("celery")
	logger.setLevel(level)

	# Avoid duplicate handlers on worker autoreload
	for h in list(logger.handlers):
		logger.removeHandler(h)

	handler = _make_rotating_file_handler(log_dir / "tasks.log", level)
	logger.addHandler(handler)
	logger.propagate = True

	logger.info("Celery worker logging initialized")


def mask_email(email: str) -> str:
	try:
		local, domain = email.split("@", 1)
		if len(local) <= 1:
			masked_local = "*"
		else:
			masked_local = local[0] + "*" * (len(local) - 1)
		return f"{masked_local}@{domain}"
	except Exception:
		return "***@***"


def hash_text(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8")).hexdigest() 