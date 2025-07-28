from dotenv import load_dotenv
import os
from typing import TypeVar

T = TypeVar("T")
load_dotenv()

def get_env(name: str, default=None, required=False, cast=str):
    raw_value = os.getenv(name, str(default) if default is not None else None)
    if required and raw_value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    try:
        return cast(raw_value)
    except (ValueError, TypeError):
        raise ValueError(f"Environment variable {name} must be of type {cast.__name__}")

# Example: "0 30 3 * * *" → 3:30 AM daily
SCHEDULE_CRON = get_env("SCHEDULE_CRON", default="*/1 * * * *")  # default: every minute
