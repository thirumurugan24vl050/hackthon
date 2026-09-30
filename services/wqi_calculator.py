"""
HYDRO MIND — Water Quality Index (WQI) Calculator
"""
from typing import Dict, Any, Optional
from config.thresholds import WQ_THRESHOLDS

def calculate_wqi(parameters: Dict[str, float]) -> Dict[str, Any]:
    """
    Calculates a basic WQI score based on available parameters.
    Currently returns UNAVAILABLE since no live water quality data source exists.
    """
    # For now, we enforce UNAVAILABLE as there is no source.
    # We will build out the logic for when data is present (e.g. from manual entry).
    if not parameters:
        return {
            "status": "UNAVAILABLE",
            "score": None,
            "category": "UNKNOWN",
            "risk": "UNKNOWN"
        }
        
    # Placeholder for actual calculation
    return {
        "status": "LIVE",
        "score": 0.0,
        "category": "UNKNOWN",
        "risk": "UNKNOWN"
    }
