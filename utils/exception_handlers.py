import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Any, Dict

from utils.response import api_response

logger = logging.getLogger("api.errors")


def install_exception_handlers(app: FastAPI) -> None:
	@app.exception_handler(HTTPException)
	async def http_exception_handler(request: Request, exc: HTTPException):
		# Do not log sensitive details; rely on request middleware for stack traces when needed
		logger.warning(
			"http_exception",
			extra={
				"path": request.url.path,
				"method": request.method,
				"status_code": exc.status_code,
			}
		)
		return api_response(data=None, message=str(exc.detail or "HTTP error"), status_code=exc.status_code)

	@app.exception_handler(RequestValidationError)
	async def validation_exception_handler(request: Request, exc: RequestValidationError):
		errors = exc.errors()
		logger.warning(
			"validation_error",
			extra={
				"path": request.url.path,
				"method": request.method,
				"status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
				"error_count": len(errors),
			}
		)
		content: Dict[str, Any] = {"errors": errors}
		return JSONResponse(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			content={
				"data": content,
				"message": "Validation error",
				"status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
			},
		)

	@app.exception_handler(Exception)
	async def generic_exception_handler(request: Request, exc: Exception):
		# Do not expose internal details to clients
		logger.error(
			"unhandled_exception",
			exc_info=True,
			extra={
				"path": request.url.path,
				"method": request.method,
				"status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
			}
		)
		return api_response(data=None, message="Internal server error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR) 