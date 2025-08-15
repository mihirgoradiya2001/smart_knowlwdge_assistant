from fastapi import APIRouter, Query, Security
from datetime import date
from typing import Optional

from utils.jwt import get_current_user_id
from utils.response import api_response
from utils.history import list_history
import logging

router = APIRouter(prefix="/history", tags=["history"])
logger = logging.getLogger("api.history")


@router.get("")
def get_history(
	user_id: int = Security(get_current_user_id),
	for_date: Optional[date] = Query(None, description="Filter by date (YYYY-MM-DD, UTC), defaults to today (UTC)"),
	offset: int = Query(0, ge=0, description="Pagination offset; 0 means start from most recent"),
	limit: int = Query(20, ge=1, le=100),
):
	"""Return the user's question history for a given UTC date (most recent first)."""
	items, total, resolved_date = list_history(user_id, for_date, offset, limit)
	logger.info("history_listed", extra={"user_id": user_id, "date": resolved_date, "returned": len(items), "total": total, "offset": offset, "limit": limit})
	return api_response(
		data={
			"items": items,
			"total": total,
			"date": resolved_date,
			"offset": offset,
			"limit": limit,
		},
		message="History fetched successfully.",
		status_code=200,
	) 