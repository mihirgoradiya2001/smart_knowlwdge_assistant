from pydantic import BaseModel
from typing import Optional

class Document(BaseModel):
    id: int
    filename: str
    owner_id: int
    status: str  # e.g., "pending", "processing", "indexed"
    error: Optional[str] = None