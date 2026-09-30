"""
HYDRO MIND — AI Agent Tools
Provides deterministic access to database records for the AI agent.
"""
from typing import List, Dict, Any
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from database.db import execute_query

def get_reservoir_status() -> Dict[str, Any]:
    """Retrieves the latest reservoir status from the observations table."""
    # Since we are mocking unavailability for hydrology, we return UNAVAILABLE.
    return {
        "status": "UNAVAILABLE",
        "reason": "Official sources endpoints unavailable."
    }

def get_water_quality() -> Dict[str, Any]:
    """Retrieves the latest water quality indices."""
    return {
        "status": "UNAVAILABLE",
        "reason": "No live water quality data source exists."
    }

def get_weather() -> Dict[str, Any]:
    """Retrieves latest weather observations."""
    rows = execute_query(
        "SELECT parameter, value, unit, timestamp_ist, status FROM observations WHERE source = 'Open-Meteo' ORDER BY id DESC LIMIT 4"
    )
    if not rows:
        return {"status": "UNAVAILABLE", "reason": "No weather data found."}
    
    data = {"status": "LIVE", "timestamp": rows[0]["timestamp_ist"]}
    for row in rows:
        data[row["parameter"]] = f"{row['value']} {row['unit']}"
    return data

def get_alerts() -> List[Dict[str, Any]]:
    """Retrieves all active alerts."""
    rows = execute_query(
        "SELECT hazard_category, severity, message, evidence FROM alerts WHERE is_active = 1 ORDER BY created_at DESC"
    )
    return rows

def get_recent_news(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the most recent active news items."""
    rows = execute_query(
        f"SELECT title, publisher, source_domain, published_at_utc as time, category, verification_status FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT {limit}"
    )
    return rows
