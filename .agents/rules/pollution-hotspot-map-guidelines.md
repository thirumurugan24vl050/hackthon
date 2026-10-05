---
name: pollution-hotspot-map-guidelines
description: "Guidelines for implementing lightweight environmental map visualizations without fabricating measurements or relying on paid map providers."
---

# Rules for Pollution Hotspot Maps & Dashboard Integrity

## Map Provider & Performance
1. **Free & Keyless**: Always use completely free, keyless map providers (e.g., `folium.Map` + `OpenStreetMap`).
2. **No Paid APIs**: Never use CARTO, Mapbox, or Google Maps if they require tokens/API keys.
3. **Lightweight rendering**: Use `CircleMarker` or basic markers instead of heavy glowing overlays or full-scale heatmaps, especially when data is sparse.

## Data Integrity & Authenticity
1. **No Fake Data**: Never invent random pollution values or measurements. Always derive hotspot classifications from existing project signals (e.g., turbidity anomaly, low DO, heavy rainfall, satellite NDWI).
2. **Proper Terminology**: Do not claim satellite imagery directly "measures" pH, DO, BOD, or COD. Label them as "Evidence-based environmental indicators" or "Pollution Hotspot Risk."
3. **Data Provenance**: Preserve existing provenance. Never turn simulated/demo evidence into LIVE data, and always show the actual `last_updated` observation timestamp. Do not fabricate timestamps.

## Visualization Logic
1. **Evidence-based Classification**: Re-use the existing risk engine logic (e.g., `Runoff / Pollution` signals) rather than creating conflicting ML models.
   - Example Logic: `0-1 signals = LOW`, `2 = WATCH`, `3 = ELEVATED`, `4+ = HOTSPOT`.
2. **Clear UI Components**:
   - Always include the geographic context (e.g., Bhavanisagar Dam marker).
   - Clickable popups must cleanly list: Location, Risk Level, Evidence count, Confidence, Status ("Requires field verification"), and Last updated time.
   - Provide a simple floating HTML legend inside the map.

## UI/UX Continuity
1. **Do Not Redesign**: When instructed to replace a component, replace ONLY that component. Preserve all existing glassmorphism, fonts, spacing, animations, and the dual-language system (Tamil/English).
2. **Translation Consistency**: Add missing keys to the existing `ui/translations.py` dictionary. Do not implement a separate translation mechanism.
