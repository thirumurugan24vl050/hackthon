"""
HYDRO MIND — Environmental Thresholds
Thresholds are clearly separated into PROTOTYPE/ASSUMED and OFFICIAL.
Never present assumed thresholds as regulatory standards.
"""

# ─── Reservoir Hydrology ─────────────────────────────────
RESERVOIR_THRESHOLDS = {
    # Elevation in feet
    "full_reservoir_level_ft": 105.0, # Assumed/Prototype (Need to verify exact FRL for Bhavanisagar, often 105ft)
    "dead_storage_level_ft": 30.0,    # Assumed/Prototype
    "surplus_trigger_level_ft": 102.0, # Assumed/Prototype
    
    # Capacity in MCft
    "gross_capacity_mcft": 32800.0,   # Assumed/Prototype (Approx 32.8 TMC)
    "source_status": "ASSUMED - Prototype Defaults"
}

# ─── Water Quality (WQI) ─────────────────────────────────
# Standard ideal and permissible values (IS 10500 / CPCB / WHO derived)
WQ_THRESHOLDS = {
    "ph": {
        "ideal": 7.0,
        "min_permissible": 6.5,
        "max_permissible": 8.5
    },
    "do": {
        "ideal_saturated": 14.6, # mg/L at 0C, typically ~8-9 at 25C. Using index baseline.
        "standard_min": 5.0      # mg/L (Class B/C limit)
    },
    "turbidity": {
        "standard_max": 5.0      # NTU
    },
    "tds": {
        "standard_max": 500.0    # mg/L
    },
    "bod": {
        "standard_max": 3.0      # mg/L
    },
    "cod": {
        "standard_max": 10.0     # mg/L (Custom strict threshold for river, IS 10500 doesn't strictly define COD for drinking, typically < 20 for discharge)
    },
    "source_status": "PROTOTYPE - Based on standard methodology (Not location-specific regulatory limits)"
}

# ─── Weather Anomalies ───────────────────────────────────
WEATHER_THRESHOLDS = {
    "heavy_rainfall_24h_mm": 30.0,
    "extreme_heat_c": 40.0,
    "source_status": "ASSUMED"
}
