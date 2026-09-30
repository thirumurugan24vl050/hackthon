"""
HYDRO MIND — Central Configuration
All settings are driven by environment variables with sensible defaults.
"""

import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "hydromind.db"
MODELS_DIR = BASE_DIR / "ml" / "artifacts"

# ─── Application ─────────────────────────────────────────
APP_NAME = "HYDRO MIND"
APP_SUBTITLE = "AI Environmental Intelligence Platform"
APP_VERSION = "1.0.0"
SECRET_KEY = os.getenv("SECRET_KEY", "hydromind-dev-key-change-in-prod")

# ─── Location ────────────────────────────────────────────
PRIMARY_LAT = 11.47083
PRIMARY_LNG = 77.11389
TIMEZONE = "Asia/Kolkata"

# ─── Open-Meteo (Weather) ────────────────────────────────
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_TIMEOUT = 15  # seconds

# ─── Google News RSS ─────────────────────────────────────
GOOGLE_NEWS_ENABLED = os.getenv("GOOGLE_NEWS_ENABLED", "true").lower() == "true"
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
GOOGLE_NEWS_REFRESH_MINUTES = int(os.getenv("GOOGLE_NEWS_REFRESH_MINUTES", "5"))
GOOGLE_NEWS_TIMEOUT = 15  # seconds
GOOGLE_NEWS_MAX_ITEMS = 30

# ─── Google Earth Engine (Satellite) ─────────────────────
GEE_SERVICE_ACCOUNT = os.getenv("GEE_SERVICE_ACCOUNT", "")
GEE_ENABLED = bool(GEE_SERVICE_ACCOUNT)

# ─── AI Provider ─────────────────────────────────────────
AI_PROVIDER = os.getenv("AI_PROVIDER", "")  # Empty = offline deterministic mode

# ─── UI Refresh ──────────────────────────────────────────
UI_REFRESH_SECONDS = 60
NEW_BADGE_DURATION_MINUTES = 30

# ─── Data Freshness Windows ──────────────────────────────
STALE_THRESHOLD_HOURS = {
    "weather": 1,
    "hydrology": 6,
    "water_quality": 24,
    "satellite": 120,  # 5 days (Sentinel-2 revisit)
    "news": 1,
}
