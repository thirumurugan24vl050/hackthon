"""
HYDRO MIND - Main Data Orchestrator
Runs all live connectors, evaluates risk, and updates the database.
"""
import sys
from pathlib import Path
import time
import json

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from services.weather_fetcher import fetch_current_weather
from services.hydrology_fetcher import fetch_reservoir_status
from services.wqi_calculator import calculate_wqi
from services.news_fetcher import run_all_fetches
from services.risk_engine import evaluate_risk
from database.db import execute_query

def run_pipeline():
    print("--- Starting HYDRO MIND Orchestration Pipeline ---")
    
    print("1. Fetching Weather Data...")
    weather = fetch_current_weather()
    print(f"Weather Status: {weather.get('status')}")
    
    print("2. Fetching Hydrology Data...")
    hydrology = fetch_reservoir_status()
    print(f"Hydrology Status: {hydrology.get('status')} - {hydrology.get('reason')}")
    
    print("3. Fetching Water Quality Data...")
    wqi = calculate_wqi({})
    print(f"WQI Status: {wqi.get('status')}")
    
    print("4. Fetching News Intelligence (Google News)...")
    # Fetching news takes time, so we just run the active fetcher
    news_events = run_all_fetches()
    print(f"News Events Fetched: {len(news_events)}")
    
    print("5. Evaluating Risk...")
    # Fetch active news from DB for risk evaluation
    recent_news = execute_query(
        "SELECT title, category, 'CORROBORATED' as corroboration_status FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT 5"
    )
    
    risk_assessment = evaluate_risk(hydrology, weather, wqi, recent_news)
    print("Risk Assessment Complete. Output hazards:", json.dumps(risk_assessment, indent=2))
        
    print("--- Pipeline Execution Complete ---")

if __name__ == "__main__":
    run_pipeline()
