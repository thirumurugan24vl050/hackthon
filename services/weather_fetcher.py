"""
HYDRO MIND — Open-Meteo Weather Service
Fetches real-time and forecast weather data for Bhavanisagar.
"""

import requests
from datetime import datetime, timezone
from config.settings import OPEN_METEO_BASE, OPEN_METEO_TIMEOUT
from config.locations import BHAVANISAGAR_DAM
from database.db import execute_query

def fetch_current_weather():
    """Fetches current weather for Bhavanisagar Dam and stores it in the DB."""
    params = {
        "latitude": BHAVANISAGAR_DAM["latitude"],
        "longitude": BHAVANISAGAR_DAM["longitude"],
        "current": ["temperature_2m", "precipitation", "weather_code", "wind_speed_10m"],
        "timezone": "Asia/Kolkata"
    }
    
    try:
        response = requests.get(OPEN_METEO_BASE, params=params, timeout=OPEN_METEO_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        if "current" in data:
            current_data = data["current"]
            # Save to database
            now_utc = datetime.now(timezone.utc).isoformat()
            now_ist = current_data.get("time") # Open-Meteo returns local time if timezone passed
            
            queries = [
                ("temperature_2m", current_data.get("temperature_2m"), "C"),
                ("precipitation", current_data.get("precipitation"), "mm"),
                ("wind_speed_10m", current_data.get("wind_speed_10m"), "km/h")
            ]
            
            for param, val, unit in queries:
                execute_query(
                    """
                    INSERT INTO observations 
                    (station_id, parameter, value, unit, source, timestamp_utc, timestamp_ist, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (BHAVANISAGAR_DAM["id"], param, val, unit, "Open-Meteo", now_utc, now_ist, "LIVE"),
                    commit=True
                )
            
            return {
                "status": "LIVE",
                "temperature_2m": current_data.get("temperature_2m"),
                "precipitation": current_data.get("precipitation"),
                "wind_speed_10m": current_data.get("wind_speed_10m"),
                "timestamp_ist": now_ist
            }
        return {"status": "UNAVAILABLE", "reason": "No current data in response"}
    except Exception as e:
        return {"status": "UNAVAILABLE", "reason": str(e)}
