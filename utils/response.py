from fastapi.responses import JSONResponse
from models.response import APIResponse


def api_response(data=None, message="Success", status_code=200):
	return JSONResponse(
		status_code=status_code,
		content=APIResponse(data=data, message=message, status_code=status_code).model_dump()
	)