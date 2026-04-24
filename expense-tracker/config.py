import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SPENDLY_SECRET_KEY", "dev-secret-key")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DATABASE_PATH = os.environ.get("SPENDLY_DATABASE_PATH", str(BASE_DIR / "expense_tracker.db"))
    PORT = int(os.environ.get("SPENDLY_PORT", "5001"))
    DEBUG = env_bool("SPENDLY_DEBUG", True)
    MAX_CONTENT_LENGTH = int(os.environ.get("SPENDLY_MAX_CONTENT_LENGTH", str(5 * 1024 * 1024)))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SPENDLY_SESSION_COOKIE_SECURE", False)
    BUDGET_ALERT_THRESHOLD = float(os.environ.get("SPENDLY_BUDGET_ALERT_THRESHOLD", "0.9"))
    CSV_MAX_IMPORT_ROWS = int(os.environ.get("SPENDLY_CSV_MAX_IMPORT_ROWS", "500"))
    DEMO_EMAIL = os.environ.get("SPENDLY_DEMO_EMAIL", "demo@spendly.com")
    DEMO_PASSWORD = os.environ.get("SPENDLY_DEMO_PASSWORD", "demo12345")
    ADMIN_EMAIL = os.environ.get("SPENDLY_ADMIN_EMAIL", "admin@spendly.com")
    ADMIN_PASSWORD = os.environ.get("SPENDLY_ADMIN_PASSWORD", "admin12345")
