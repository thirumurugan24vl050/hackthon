import pytest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from ui.app import fetch_dashboard_data, _get_badge_class
from database.db import execute_query, init_db

def test_not_scored_state():
    hydro, weather, wqi, news, alerts = fetch_dashboard_data()
    assert hydro["status"] == "UNAVAILABLE"
    assert hydro["storage"] == "NOT SCORED"
    assert wqi["status"] == "UNAVAILABLE"
    assert wqi["score"] == "NOT SCORED"
    assert _get_badge_class("NOT SCORED") == "badge-unavail"

def test_weather_live_implies_value():
    hydro, weather, wqi, news, alerts = fetch_dashboard_data()
    if weather["status"] == "LIVE":
        assert weather["precip"] != "--" or weather["temp"] != "--" or weather["wind"] != "--"

def test_alert_deduplication():
    # Insert duplicate alerts manually
    execute_query("INSERT INTO alerts (hazard_category, severity, message, evidence, is_active, created_at) VALUES ('TEST', 'HIGH', 'Test Alert', 'Ev1', 1, '2026-09-30')", commit=True)
    execute_query("INSERT INTO alerts (hazard_category, severity, message, evidence, is_active, created_at) VALUES ('TEST', 'HIGH', 'Test Alert', 'Ev1', 1, '2026-09-30')", commit=True)
    
    hydro, weather, wqi, news, alerts = fetch_dashboard_data()
    
    # We should only see "Test Alert" once
    count = sum(1 for a in alerts if a['message'] == 'Test Alert')
    assert count <= 1
    
    # Clean up
    execute_query("DELETE FROM alerts WHERE hazard_category = 'TEST'", commit=True)

def test_news_deduplication():
    # Insert duplicate news manually
    execute_query("INSERT INTO news_items (id, title, url, publisher, source_domain, source_type, status, published_at_utc, fetched_at_utc, category, first_seen_at_utc, last_seen_at_utc) VALUES ('test1', 'Test News', 'http://test.com/1', 'Pub', 'test.com', 'SECONDARY', 'ACTIVE', '2026-09-30', '2026-09-30', 'TEST', '2026-09-30', '2026-09-30')", commit=True)
    execute_query("INSERT INTO news_items (id, title, url, publisher, source_domain, source_type, status, published_at_utc, fetched_at_utc, category, first_seen_at_utc, last_seen_at_utc) VALUES ('test2', 'Test News', 'http://test.com/2', 'Pub', 'test.com', 'SECONDARY', 'ACTIVE', '2026-09-30', '2026-09-30', 'TEST', '2026-09-30', '2026-09-30')", commit=True)
    
    hydro, weather, wqi, news, alerts = fetch_dashboard_data()
    
    count = sum(1 for n in news if n['title'] == 'Test News')
    assert count <= 1
    
    execute_query("DELETE FROM news_items WHERE category = 'TEST'", commit=True)

def test_no_external_event_alerts():
    # Insert a generic external event
    execute_query("INSERT INTO alerts (hazard_category, severity, message, evidence, is_active, created_at) VALUES ('TEST2', 'HIGH', 'ELEVATED risk detected due to EXTERNAL EVENT.', 'Ev', 1, '2026-09-30')", commit=True)
    
    hydro, weather, wqi, news, alerts = fetch_dashboard_data()
    
    # Should be filtered out
    count = sum(1 for a in alerts if "EXTERNAL EVENT" in a['message'])
    assert count == 0
    
    execute_query("DELETE FROM alerts WHERE hazard_category = 'TEST2'", commit=True)
