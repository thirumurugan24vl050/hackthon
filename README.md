# HYDRO MIND
**AI Environmental Intelligence Platform**
Bhavanisagar Dam & Lower Bhavani River, Erode, Tamil Nadu

HYDRO MIND is a production-grade Python/Streamlit intelligence platform that aggregates official water data, live weather readings, satellite proxies, and Google News intelligence to generate deterministic risk scores. It strictly enforces a "Real Data Only" philosophy.

## Features
- **Real-Time Data Orchestration:** Connects to Open-Meteo for live localized weather arrays.
- **News Intelligence Layer:** Queries and parses Google News RSS to find and corroborate environmental events in the region.
- **Strict Data Hierarchy:** News is discovery; Official sources are authority; Sensor endpoints are measurements. Never reverses this hierarchy.
- **Automated Risk Engine:** Cross-references telemetry with intelligence to evaluate 4 critical hazards (Water Stress, Flood, Quality, Runoff) and emits active alerts.
- **AI Environmental Analyst:** A deterministic AI agent that answers queries using only verified telemetry, while strictly refusing drinking-water safety certification.
- **Streamlit Command Center:** A sleek, industrial dark-themed UI that clearly delineates `LIVE`, `UNAVAILABLE`, and `HISTORICAL` provenance.

## Installation
The project uses `uv` for dependency management.

```bash
uv venv
uv pip install -r requirements.txt
# Or run with uv directly
```

## Running the Architecture
### 1. The Backend Orchestrator
The orchestrator drives data ingestion, anomaly detection, and the risk engine. 
Run this separately (e.g. on a cron job):
```bash
$env:PYTHONPATH="."
uv run python scripts/orchestrator.py
```

### 2. The Frontend UI
Run the Streamlit application:
```bash
uv run streamlit run ui/app.py
```

## Testing
Run the pytest suite to verify safety constraints and connector behavior:
```bash
$env:PYTHONPATH="."
uv run pytest tests/
```

## Data Philosophy
This platform **never** invents data. If an official sensor is offline, the system marks the module as `UNAVAILABLE`. No "virtual simulations" are rendered. Environmental safety cannot be certified without physical lab testing.
