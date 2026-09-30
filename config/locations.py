"""
HYDRO MIND — Locations and Spatial Configurations
"""

# Primary Monitoring Station
BHAVANISAGAR_DAM = {
    "id": "ST-Bhavanisagar-01",
    "name": "Bhavanisagar Dam",
    "type": "RESERVOIR",
    "latitude": 11.47083,
    "longitude": 77.11389,
    "elevation_m": 255.0  # Approx surface elevation MSL
}

# Downstream River Monitoring point (for water quality/runoff if distinct)
LOWER_BHAVANI_RIVER = {
    "id": "ST-LowerBhavani-01",
    "name": "Lower Bhavani River (Sathyamangalam Segment)",
    "type": "RIVER",
    "latitude": 11.50000, 
    "longitude": 77.20000
}

ALL_STATIONS = [BHAVANISAGAR_DAM, LOWER_BHAVANI_RIVER]

# ─── Sentinel-2 AOI Geometry (GeoJSON style) ───
BHAVANISAGAR_AOI_POLYGON = [
    [77.08, 11.45],
    [77.14, 11.45],
    [77.14, 11.49],
    [77.08, 11.49],
    [77.08, 11.45]
]
