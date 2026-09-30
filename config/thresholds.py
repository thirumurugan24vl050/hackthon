"""
HYDRO MIND — Environmental Thresholds
Thresholds are clearly separated into PROTOTYPE/ASSUMED and OFFICIAL.
Never present assumed thresholds as regulatory standards.

References:
- IS 10500:2012 (Drinking Water Standards)
- CPCB/TNPCB Category B Classification
- CWC Flood Alerting Guidelines
- Tamil Nadu AgriNet Published FRL/Capacity data
"""

# ─── Reservoir Hydrology ─────────────────────────────────
RESERVOIR_THRESHOLDS = {
    # Elevation in feet
    "full_reservoir_level_ft": 105.0,       # TN AgriNet / CWC
    "dead_storage_level_ft": 30.0,          # Assumed/Prototype
    "surplus_trigger_level_ft": 102.0,      # Assumed/Prototype
    "minimum_draw_down_ft": 40.0,           # Assumed/Prototype

    # Capacity in MCft
    "gross_capacity_mcft": 32800.0,         # TN AgriNet (32.8 TMC)

    # Storage percentage thresholds
    "low_storage_pct": 20,                  # Below = Water Stress WATCH
    "critical_storage_pct": 10,             # Below = Water Stress HIGH
    "high_storage_pct": 85,                 # Above = Flood/Surplus WATCH
    "near_full_pct": 95,                    # Above = Flood/Surplus ELEVATED

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
        "ideal_saturated": 14.6,            # mg/L at 0C
        "standard_min": 5.0,                # mg/L (Class B/C limit)
        "critical_min": 3.0,                # Below = severe
    },
    "turbidity": {
        "standard_max": 5.0,                # NTU
        "critical_max": 25.0,               # Above = severe
    },
    "tds": {
        "standard_max": 500.0,              # mg/L
        "critical_max": 2000.0,
    },
    "conductivity": {
        "standard_max": 400.0,              # µS/cm
        "critical_max": 1000.0,
    },
    "bod": {
        "standard_max": 3.0,                # mg/L
        "critical_max": 6.0,
    },
    "cod": {
        "standard_max": 10.0,               # mg/L
        "critical_max": 25.0,
    },
    "nitrate": {
        "standard_max": 45.0,               # mg/L as NO3
        "critical_max": 100.0,
    },
    "source_status": "PROTOTYPE - Based on standard methodology (Not location-specific regulatory limits)"
}

# ─── Weather Anomalies ───────────────────────────────────
WEATHER_THRESHOLDS = {
    "heavy_rainfall_24h_mm": 30.0,
    "extreme_heat_c": 40.0,
    "source_status": "ASSUMED"
}

# ─── Flood Model Thresholds ──────────────────────────────
FLOOD_THRESHOLDS = {
    "discharge_normal_max_m3s": 50,         # Below = NORMAL
    "discharge_watch_m3s": 100,             # Above = WATCH
    "discharge_elevated_m3s": 200,          # Above = ELEVATED
    "discharge_critical_m3s": 500,          # Above = HIGH/CRITICAL
    "precipitation_watch_mm": 20,           # Above = Runoff WATCH
    "precipitation_elevated_mm": 40,        # Above = Flood WATCH
    "precipitation_critical_mm": 80,        # Above = Flood ELEVATED
}

# ─── Runoff / Pollution Signal Thresholds ─────────────────
RUNOFF_THRESHOLDS = {
    "min_signals_for_watch": 1,
    "min_signals_for_elevated": 3,
    "min_signals_for_high": 4,
}
