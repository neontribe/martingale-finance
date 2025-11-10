import logging
from app import config
from app.tasks import task

# Force test config
config.ENV = "testing"

def test_scheduled_task_with_mock_env(caplog):
    """Test scheduled_task using internal ENV == 'testing' logic (no requests)."""
    caplog.set_level(logging.INFO)
    task.scheduled_task()