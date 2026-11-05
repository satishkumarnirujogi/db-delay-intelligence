"""All environment variables in one place. Locally they come from .env, in Actions from secrets."""
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULTS = {
    "DB_BASE_URL": "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1",
    "PG_PORT": "5432",
    "PG_DB": "postgres",
}


def env(name: str) -> str:
    """Read a required variable; fail loudly instead of calling an API with an empty key."""
    value = os.getenv(name) or DEFAULTS.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable {name} (see .env.example)")
    return value
