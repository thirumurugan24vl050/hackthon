"""
HYDRO MIND — Risk Assessment Engine
Evaluates telemetry vs thresholds and corroborates with intelligence layer.
"""

import json
from typing import Dict, Any, List
from database.db import execute_query

def evaluate_risk(
    hydrology: Dict[str, Any], 
    weather: Dict[str, Any], 
    wqi: Dict[str, Any], 
    news_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Determines overall risk based on hierarchy.
    """
    
    # 1. Start with NORMAL
    risk_level = "NORMAL"
    hazard_category = "NONE"
    reasons = []
    
    # 2. Check Weather (since hydrology/WQI are mostly UNAVAILABLE)
    if weather.get("status") == "LIVE":
        precip = weather.get("precipitation", 0.0)
        if precip > 20.0:
            risk_level = "ELEVATED"
            hazard_category = "HEAVY RAINFALL"
            reasons.append(f"High precipitation detected: {precip} mm")
            
    # 3. Check News Events (Discovery Layer)
    for event in news_events:
        if event.get("corroboration_status") == "CORROBORATED":
            if risk_level in ["NORMAL", "WATCH"]:
                risk_level = "ELEVATED"
                hazard_category = event.get("category") or "EXTERNAL EVENT"
                reasons.append(f"Corroborated news event: {event.get('title')}")
                
    # 4. Generate Alert if necessary
    if risk_level in ["ELEVATED", "HIGH", "CRITICAL"]:
        evidence = json.dumps(reasons)
        message = f"{risk_level} risk detected due to {hazard_category}."
        execute_query(
            """
            INSERT INTO alerts (hazard_category, severity, message, evidence, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hazard_category, risk_level, message, evidence, 1),
            commit=True
        )
                
    return {
        "risk_level": risk_level,
        "hazard_category": hazard_category,
        "reasons": reasons
    }
