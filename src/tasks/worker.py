# pylint: disable=unused-import
import logging
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

from src.config import settings


print("==== WORKER MODULE LOADING ====")


logger = logging.getLogger(__name__)
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

# Explicitly format the Redis URL to ensure proper authentication
redis_password = settings.REDIS_PASSWORD.get_secret_value()
redis_broker_url = (
    f"redis://:{redis_password}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
)
redis_backend_url = (
    f"redis://:{redis_password}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
)

logger.info(
    f"Configuring Celery with Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}"
)

# Create Celery app with explicit Redis URL protocol
celery_app = Celery(
    "tasks",
    broker=redis_broker_url,
    backend=redis_backend_url,
)

# Configure Celery
celery_app.conf.update(
    broker_transport="redis",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 5,  # 5 minutes
    worker_hijack_root_logger=False,
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        "visibility_timeout": 3600,  # 1 hour
    },
)

# Import task modules
try:
    from src.tasks import blockchain_tasks, test_task  # noqa

    logger.info("Celery worker initialized with tasks")
except ImportError:
    logger.warning("Task modules not found. Will be imported when created.")
