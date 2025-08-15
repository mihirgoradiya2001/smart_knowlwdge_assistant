from celery import Celery
import os
from utils.logging_config import init_worker_logging

CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "smart_knowledge_assistant",
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL,
    include=["tasks.celery_tasks"]  # <-- Add this line!
)

# Initialize logging for worker
init_worker_logging()