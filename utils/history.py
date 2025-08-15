import os
import json
import uuid
import fcntl
from pathlib import Path
from datetime import datetime, date
from typing import List, Tuple, Optional, Dict

from fastapi import HTTPException, status
import logging

STATE_DIR = Path(os.getenv("STATE_DIR", "state")).resolve()
HISTORY_DIR = STATE_DIR / "history"
USAGE_DIR = STATE_DIR / "usage"
logger = logging.getLogger("api.history")

# In-process daily usage cache: {(user_id, YYYY-MM-DD): count}
_DAILY_CACHE: Dict[tuple, int] = {}


def clear_daily_cache() -> None:
	"""Clear in-process daily usage cache (useful for tests)."""
	_DAILY_CACHE.clear()


def _today_utc() -> date:
	return datetime.utcnow().date()


def _ensure_user_dir(user_id: int) -> Path:
	user_dir = HISTORY_DIR / str(user_id)
	user_dir.mkdir(parents=True, exist_ok=True)
	return user_dir


def _get_usage_file(user_id: int, for_date: Optional[date] = None) -> Path:
	if for_date is None:
		for_date = _today_utc()
	USAGE_DIR.mkdir(parents=True, exist_ok=True)
	return USAGE_DIR / f"{for_date.isoformat()}_{user_id}.count"


def _read_usage(user_id: int, for_date: Optional[date] = None) -> int:
	path = _get_usage_file(user_id, for_date)
	if not path.exists():
		return 0
	try:
		with open(path, "r", encoding="utf-8") as f:
			val = f.read().strip()
			return int(val or 0)
	except Exception:
		return 0


def _inc_usage(user_id: int, for_date: Optional[date] = None) -> None:
	path = _get_usage_file(user_id, for_date)
	# Atomic-ish increment using exclusive lock
	with open(path, "a+", encoding="utf-8") as f:
		fcntl.flock(f.fileno(), fcntl.LOCK_EX)
		f.seek(0)
		val = f.read().strip()
		count = int(val or 0)
		count += 1
		f.seek(0)
		f.truncate(0)
		f.write(str(count))
		fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def get_history_file(user_id: int, for_date: Optional[date] = None) -> Path:
	if for_date is None:
		for_date = _today_utc()
	user_dir = _ensure_user_dir(user_id)
	return user_dir / f"{for_date.isoformat()}.jsonl"


def append_history_entry(user_id: int, entry: Dict) -> str:
	"""
	Append a single JSON entry to the user's daily history file.
	Returns the generated entry id.
	"""
	entry_id = entry.get("id") or str(uuid.uuid4())
	entry["id"] = entry_id
	entry.setdefault("timestamp", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
	filepath = get_history_file(user_id, _today_utc())
	# Ensure parent dir exists
	filepath.parent.mkdir(parents=True, exist_ok=True)
	with open(filepath, "a", encoding="utf-8") as f:
		# Exclusive lock for writing
		fcntl.flock(f.fileno(), fcntl.LOCK_EX)
		f.write(json.dumps(entry, ensure_ascii=False) + "\n")
		fcntl.flock(f.fileno(), fcntl.LOCK_UN)
	# Update in-process cache and persistent counter
	key = (user_id, _today_utc().isoformat())
	_DAILY_CACHE[key] = _DAILY_CACHE.get(key, 0) + 1
	_inc_usage(user_id, _today_utc())
	return entry_id


def _read_all_lines(filepath: Path) -> List[str]:
	if not filepath.exists():
		return []
	with open(filepath, "r", encoding="utf-8") as f:
		# Shared lock for reading
		fcntl.flock(f.fileno(), fcntl.LOCK_SH)
		lines = f.readlines()
		fcntl.flock(f.fileno(), fcntl.LOCK_UN)
	return lines


def list_history(user_id: int, for_date: Optional[date] = None, offset: int = 0, limit: int = 20) -> Tuple[List[Dict], int, str]:
	filepath = get_history_file(user_id, for_date if for_date is not None else _today_utc())
	lines = _read_all_lines(filepath)
	total = len(lines)
	items: List[Dict] = []
	# Most recent first
	rev = reversed(lines)
	for idx, line in enumerate(rev):
		if idx < offset:
			continue
		if len(items) >= limit:
			break
		try:
			items.append(json.loads(line))
		except json.JSONDecodeError:
			# Skip malformed lines
			continue
	return items, total, filepath.name.replace(".jsonl", "")


def count_today(user_id: int) -> int:
	filepath = get_history_file(user_id, _today_utc())
	file_count = len(_read_all_lines(filepath))
	key = (user_id, _today_utc().isoformat())
	cached = _DAILY_CACHE.get(key, 0)
	usage = _read_usage(user_id, _today_utc())
	return max(file_count, cached, usage)


def enforce_daily_limit(user_id: int, daily_limit: int):
	used = count_today(user_id)
	if used >= daily_limit:
		logger.warning("daily_limit_exceeded", extra={"user_id": user_id, "limit": daily_limit, "used": used})
		raise HTTPException(
			status_code=status.HTTP_429_TOO_MANY_REQUESTS,
			detail=f"Daily question limit reached ({daily_limit}). Resets at UTC midnight.",
		) 