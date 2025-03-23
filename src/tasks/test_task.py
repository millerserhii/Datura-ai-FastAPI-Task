import logging

from src.tasks.worker import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="test_task")
def test_task():
    logger.info("Executing test task")
    return True
