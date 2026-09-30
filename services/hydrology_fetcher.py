"""
HYDRO MIND — Official Hydrology Fetcher
Attempts to pull data from official sources (TN AgriNet) and models (Open-Meteo Flood).
Returns gracefully if APIs are unavailable or require login.
"""

from typing import Dict, Any
from config.thresholds import RESERVOIR_THRESHOLDS
import requests
from datetime import datetime, timezone
import json

def fetch_reservoir_status() -> Dict[str, Any]:
    """
    Attempts to fetch live reservoir status from Tamil Nadu AgriNet dashboard.
    Gracefully handles login walls or connection failures by returning UNAVAILABLE.
    """
    url = "https://www.tnagrisnet.tn.gov.in/ARS/acrs_apc_dashboard/reservoirs/"
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            html = response.text
            # If the page asks for officer login, it's not publicly accessible
            if "Officer Login" in html or "ars-login-page" in html:
                return _unavailable("TN AgriNet Reservoirs page currently behind authentication.")
            
            # Use regex to find Bhavanisagar data since bs4 is not available
            # We are looking for something like:
            # <td>Bhavanisagar</td><td>...</td><td>...</td><td>LEVEL</td><td>STORAGE</td><td>INFLOW</td><td>OUTFLOW</td>
            import re
            row_pattern = r"Bhavanisagar.*?<tr.*?</tr"
            match = re.search(row_pattern, html, re.IGNORECASE | re.DOTALL)
            if not match:
                # alternative pattern
                match = re.search(r"Bhavani.*?<tr.*?</tr", html, re.IGNORECASE | re.DOTALL)
                
            if match:
                row_html = match.group(0)
                tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.IGNORECASE | re.DOTALL)
                tds = [re.sub(r"<[^>]+>", "", t).strip() for t in tds]
                
                if len(tds) >= 8:
                    try:
                        level = float(tds[3].replace(',', ''))
                        storage = float(tds[4].replace(',', ''))
                        inflow = float(tds[5].replace(',', ''))
                        outflow = float(tds[6].replace(',', ''))
                        
                        return {
                            "status": "LIVE" if level > 0 else "PUBLIC_LATEST",
                            "reason": "Scraped from TN AgriNet public dashboard",
                            "level_ft": level,
                            "storage_mcft": storage,
                            "inflow_cusecs": inflow,
                            "outflow_cusecs": outflow,
                            "capacity_mcft": RESERVOIR_THRESHOLDS["gross_capacity_mcft"],
                            "frl_ft": RESERVOIR_THRESHOLDS["full_reservoir_level_ft"],
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        }
                    except ValueError:
                        return _unavailable("Table format changed on TN AgriNet.")
                else:
                    return _unavailable("Table format changed on TN AgriNet.")
            else:
                return _unavailable("Bhavanisagar not found on public dashboard.")
        else:
            return _unavailable(f"HTTP {response.status_code} from TN AgriNet.")
    except Exception as e:
        return _unavailable(f"Connection failed: {str(e)}")


def fetch_open_meteo_flood(lat=11.47083, lon=77.11389) -> Dict[str, Any]:
    """
    Fetches model river discharge data from Open-Meteo Flood API.
    """
    url = f"https://flood-api.open-meteo.com/v1/flood?latitude={lat}&longitude={lon}&daily=river_discharge,river_discharge_mean,river_discharge_max,river_discharge_min&forecast_days=3"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            daily = data.get("daily", {})
            discharge = daily.get("river_discharge", [])
            mean = daily.get("river_discharge_mean", [])
            mx = daily.get("river_discharge_max", [])
            mn = daily.get("river_discharge_min", [])
            
            if discharge and len(discharge) > 0:
                return {
                    "status": "MODEL_GUIDANCE",
                    "reason": "Open-Meteo Global Flood Model",
                    "discharge_m3s": discharge[0],
                    "mean_m3s": mean[0] if mean else None,
                    "max_m3s": mx[0] if mx else None,
                    "min_m3s": mn[0] if mn else None,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            return _unavailable("No daily data in flood response.")
        return _unavailable(f"HTTP {response.status_code} from Flood API")
    except Exception as e:
        return _unavailable(f"Flood API connection failed: {str(e)}")

def _unavailable(reason: str) -> Dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "reason": reason,
        "level_ft": None,
        "storage_mcft": None,
        "inflow_cusecs": None,
        "outflow_cusecs": None,
        "discharge_m3s": None,
        "capacity_mcft": RESERVOIR_THRESHOLDS["gross_capacity_mcft"],
        "frl_ft": RESERVOIR_THRESHOLDS["full_reservoir_level_ft"]
    }
