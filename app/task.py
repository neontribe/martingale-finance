import requests
import logging
from app import config

logger = logging.getLogger(__name__)

def scheduled_task():
    logger.info("Scheduled task started.")

    headers = {
        "Authorization": f"Bearer {config.API_BEARER_TOKEN}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(config.API_URL, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return

    try:
        data = response.json()
        logger.info(f"API response received and parsed: {data}")
    except ValueError as e:
        logger.error(f"Response is not valid JSON: {e}")
