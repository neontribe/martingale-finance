from dotenv import load_dotenv
import os

load_dotenv()

def get_env(name: str, default=None, required=False, cast=str):
    raw_value = os.getenv(name, str(default) if default is not None else None)
    if required and raw_value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    try:
        return cast(raw_value)
    except (ValueError, TypeError):
        raise ValueError(f"Environment variable {name} must be of type {cast.__name__}")

ENV=get_env("ENV", default="development")
# Example: "0 30 3 * * *" → 3:30 AM daily
# default: every minute
SCHEDULE_CRON = get_env("SCHEDULE_CRON", default="*/1 * * * *")
# Bearer token for accessing protected API
API_BEARER_TOKEN = get_env("API_BEARER_TOKEN", required=True)
# Optional: REST endpoint to call
API_URL = get_env("API_URL", required=True)



