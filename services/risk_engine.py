"""
HYDRO MIND - Risk Assessment Engine
Evaluates telemetry vs thresholds and corroborates with intelligence layer.
"""

import json
import datetime
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
    
    # Four Independent Hazards
    hazards = {
        "Water Stress": {"score": None, "status": "NOT_SCORED", "band": "NORMAL", "contributors": [], "data_availability": "UNAVAILABLE"},
        "Flood / Surplus": {"score": None, "status": "NOT_SCORED", "band": "NORMAL", "contributors": [], "data_availability": "UNAVAILABLE"},
        "Water Quality": {"score": None, "status": "NOT_SCORED", "band": "NORMAL", "contributors": [], "data_availability": "UNAVAILABLE"},
        "Runoff / Pollution": {"score": None, "status": "NOT_SCORED", "band": "NORMAL", "contributors": [], "data_availability": "UNAVAILABLE"}
    }
    
    # 2. Check Weather
    if weather.get("status") == "LIVE":
        precip = weather.get("precipitation", 0.0)
        hazards["Flood / Surplus"]["data_availability"] = "PARTIAL"
        hazards["Runoff / Pollution"]["data_availability"] = "PARTIAL"
        if precip > 20.0:
            hazards["Flood / Surplus"]["score"] = 60
            hazards["Flood / Surplus"]["status"] = "SCORED"
            hazards["Flood / Surplus"]["band"] = "ELEVATED"
            hazards["Flood / Surplus"]["contributors"].append(f"Heavy rainfall detected: {precip} mm")
            
            hazards["Runoff / Pollution"]["score"] = 55
            hazards["Runoff / Pollution"]["status"] = "SCORED"
            hazards["Runoff / Pollution"]["band"] = "WATCH"
            hazards["Runoff / Pollution"]["contributors"].append(f"Heavy rainfall detected: {precip} mm")
    
    # 3. Check News Events (Discovery Layer)
    for event in news_events:
        cat = (event.get("category") or "").lower()
        evidence_str = f"News event: {event.get('title')}"
        severity = "ELEVATED" if event.get("corroboration_status") == "CORROBORATED" else "WATCH"
        
        target_hazard = None
        if "flood" in cat or "surplus" in cat or "release" in cat:
            target_hazard = "Flood / Surplus"
        elif "pollution" in cat or "quality" in cat:
            target_hazard = "Water Quality"
        elif "stress" in cat or "drought" in cat or "storage" in cat:
            target_hazard = "Water Stress"
            
        if target_hazard:
            h = hazards[target_hazard]
            if h["status"] == "NOT_SCORED" or (severity == "ELEVATED" and h["band"] != "ELEVATED"):
                h["status"] = "SCORED"
                h["score"] = 65 if severity == "ELEVATED" else 40
                h["band"] = severity
                h["contributors"].append(evidence_str)
            else:
                if evidence_str not in h["contributors"]:
                    h["contributors"].append(evidence_str)

    # 4. Generate deduplicated Alerts
    active_alerts = execute_query("SELECT hazard_category, message FROM alerts WHERE is_active = 1")
    existing = set((a["hazard_category"], a["message"]) for a in active_alerts)

    for hazard_name, data in hazards.items():
        if data["band"] in ["ELEVATED", "HIGH", "CRITICAL"]:
            evidence = json.dumps(data["contributors"])
            message = f"Possible {hazard_name.lower()} event"
            
            if (hazard_name, message) not in existing:
                execute_query(
                    '''
                    INSERT INTO alerts (hazard_category, severity, message, evidence, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (hazard_name, data["band"], message, evidence, 1),
                    commit=True
                )
                
    return hazards
