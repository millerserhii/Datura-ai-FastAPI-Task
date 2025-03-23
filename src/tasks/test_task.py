from src.tasks.worker import celery_app


@celery_app.task(name="test_task")
def test_task():
    print("Test task executed successfully!")
    return True
