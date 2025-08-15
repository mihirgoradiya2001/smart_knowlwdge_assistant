from pydantic import BaseModel
from typing import Any, List, Optional

class APIResponse(BaseModel):
    data: Any
    message: str
    status_code: int