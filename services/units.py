"""
HYDRO MIND — Unit Conversion Utilities
Internal storage is standard/metric, UI can request conversions.
"""

def feet_to_meters(feet: float) -> float:
    return feet * 0.3048

def meters_to_feet(meters: float) -> float:
    return meters / 0.3048

def cusecs_to_cumecs(cusecs: float) -> float:
    """Cubic feet per second to cubic meters per second"""
    return cusecs * 0.0283168

def cumecs_to_cusecs(cumecs: float) -> float:
    return cumecs / 0.0283168

def mcft_to_cubic_meters(mcft: float) -> float:
    """Million cubic feet to cubic meters"""
    return mcft * 28316.8

def cubic_meters_to_mcft(cumecs: float) -> float:
    return cumecs / 28316.8
