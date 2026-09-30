"""
HYDRO MIND — Official Hydrology Fetcher
Attempts to pull data from official sources. Currently returns UNAVAILABLE as per Phase 0 verification.
"""

from typing import Dict, Any
from config.thresholds import RESERVOIR_THRESHOLDS

def fetch_reservoir_status() -> Dict[str, Any]:
    """
    Attempts to fetch live reservoir status.
    Currently hardcoded to UNAVAILABLE due to lack of public APIs.
    """
    return {
        "status": "UNAVAILABLE",
        "reason": "Official sources (India-WRIS, CWC, TN WRD) endpoints unavailable.",
        "level_ft": None,
        "storage_mcft": None,
        "inflow_cusecs": None,
        "outflow_cusecs": None,
        "capacity_mcft": RESERVOIR_THRESHOLDS["gross_capacity_mcft"],
        "frl_ft": RESERVOIR_THRESHOLDS["full_reservoir_level_ft"]
    }
