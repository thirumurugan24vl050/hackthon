import pytest
from services.risk_engine import evaluate_risk

def test_risk_missing_data():
    weather = {"status": "UNAVAILABLE"}
    hydrology = {"status": "UNAVAILABLE"}
    wqi = {"status": "UNAVAILABLE"}
    news = []
    
    result = evaluate_risk(hydrology, weather, wqi, news)
    assert result["Water Stress"]["status"] == "NOT_SCORED"
    assert result["Water Stress"]["score"] is None
    assert result["Flood / Surplus"]["status"] == "NOT_SCORED"

def test_weather_live_mismatch():
    weather = {"status": "LIVE", "precipitation": 25.0}
    hydrology = {"status": "UNAVAILABLE"}
    wqi = {"status": "UNAVAILABLE"}
    news = []
    
    result = evaluate_risk(hydrology, weather, wqi, news)
    assert result["Flood / Surplus"]["status"] == "SCORED"
    assert result["Flood / Surplus"]["band"] == "ELEVATED"
    assert result["Runoff / Pollution"]["status"] == "SCORED"
