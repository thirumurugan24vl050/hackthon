import pytest
from services.weather_fetcher import fetch_current_weather
from services.hydrology_fetcher import fetch_reservoir_status

def test_weather_fetcher_integration():
    """Tests if the live weather fetcher returns data correctly or gracefully degrades."""
    data = fetch_current_weather()
    assert "status" in data
    assert data["status"] in ["LIVE", "UNAVAILABLE"]

def test_hydrology_degradation():
    """Tests if hydrology correctly falls back to UNAVAILABLE as per spec."""
    data = fetch_reservoir_status()
    assert data["status"] == "UNAVAILABLE"
    assert "reason" in data
