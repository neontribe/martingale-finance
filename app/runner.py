from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.tasks.task import scheduled_task
import time
import logging
from app import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_scheduler():
    scheduler = BackgroundScheduler()

    # Use a cron expression from env/config
    trigger = CronTrigger.from_crontab(config.SCHEDULE_CRON)

    scheduler.add_job(
        scheduled_task,
        trigger=trigger
    )

    scheduler.start()
    logger.info(f"Scheduler started with cron expression: '{config.SCHEDULE_CRON}'")

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
