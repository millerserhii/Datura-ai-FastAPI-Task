# pylint: disable=unused-import
import logging

from celery import Celery

from src.config import settings


logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "tasks",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 5,  # 5 minutes
    worker_hijack_root_logger=False,
    broker_connection_retry_on_startup=True,
)

try:
    from src.tasks import blockchain_tasks, sentiment_tasks  # noqa

    logger.info("Celery worker initialized")
except ImportError:
    logger.warning("Task modules not found. Will be imported when created.")
