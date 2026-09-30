"""
HYDRO MIND — Source Registry
Tracks the verification status and health of all external data sources.
"""

from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class DataSource:
    name: str
    type: str # 'API', 'SCRAPE', 'RSS', 'MANUAL_CSV'
    status: str # 'CONFIRMED WORKING', 'CONFIRMED UNAVAILABLE', 'UNVERIFIED'
    last_check_utc: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None

# Populated from Phase 0 Verification
SOURCES: Dict[str, DataSource] = {
    "OPEN_METEO": DataSource(
        name="Open-Meteo",
        type="API",
        status="CONFIRMED WORKING",
        url="https://api.open-meteo.com/v1/forecast",
        notes="Provides current and hourly weather for Bhavanisagar coordinates."
    ),
    "GOOGLE_NEWS": DataSource(
        name="Google News RSS",
        type="RSS",
        status="CONFIRMED WORKING",
        url="https://news.google.com/rss/search",
        notes="Provides discovery layer for environmental news."
    ),
    "INDIA_WRIS": DataSource(
        name="India-WRIS",
        type="API/WEB",
        status="CONFIRMED UNAVAILABLE",
        url="https://indiawris.gov.in/wiki/doku.php?id=bhavanisagar",
        notes="No specific Bhavanisagar wiki page. API requires institutional access."
    ),
    "CWC_RESERVOIR": DataSource(
        name="CWC Reservoir Storage",
        type="WEB",
        status="CONFIRMED UNAVAILABLE",
        url="https://cwc.gov.in/reservoir-storage",
        notes="Returns 404 Not Found."
    ),
    "CPCB_NWMP": DataSource(
        name="CPCB NWMP Data",
        type="WEB",
        status="CONFIRMED UNAVAILABLE",
        url="https://cpcb.nic.in/nwmp-data/",
        notes="Behind JS/Form interface. No public REST API."
    ),
    "TN_WRD": DataSource(
        name="TN WRD Dam Details",
        type="WEB",
        status="CONFIRMED UNAVAILABLE",
        url="https://wrd.tn.gov.in/dam-details",
        notes="SSL Certificate expired/invalid."
    ),
    "TN_AGRI": DataSource(
        name="TN Agriculture Dam Details",
        type="WEB",
        status="CONFIRMED UNAVAILABLE",
        url="https://tnagriculture.in/DamDetails",
        notes="Returns 404 Not Found. Main site is a budget page."
    )
}

def get_source_status(source_id: str) -> Optional[DataSource]:
    return SOURCES.get(source_id)
