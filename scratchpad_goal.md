# Goal Implementation Plan

## Phase 1: Data Sources & Backend (Scrapers & Connectors)
- [ ] Open-Meteo Weather: Add humidity, pressure, daily forecasts
- [ ] Open-Meteo Flood: Fetch river_discharge, min, max, mean
- [ ] TN AgriNet Reservoir: Scrape https://www.tnagrisnet.tn.gov.in/ARS/acrs_apc_dashboard/reservoirs/
- [ ] GDELT DOC 2.0: Add fallback news fetcher
- [ ] TNPCB Water Quality: Hardcode the latest public classification for Bhavani River as a fallback.
- [ ] Update SQLite schema to handle the new parameters and data availability modes.

## Phase 2: UI Foundation & CSS
- [ ] Add `DATA MODE` selector logic to `st.session_state`.
- [ ] Implement Water Bubble CSS animation in `style.css`.
- [ ] Update Glassmorphism properties to `rgba(15,30,39,0.68)`, `blur(18px)`.
- [ ] Enforce typography (Inter) and contrast ratios.

## Phase 3: Mission Control Page
- [ ] Top Right Data Mode selector & Last updated timestamp.
- [ ] Four Hazard Cards with source reason and data mode.
- [ ] Reservoir Status table (Level, Storage %, Inflow, Outflow, Net flow, YoY).
- [ ] OSM Map with 60% width layout and NASA GIBS / OSM base layers.

## Phase 4: Environmental Intelligence Page
- [ ] Weather UI (3 large cards + Extra metrics).
- [ ] Reservoir Detail.
- [ ] Water Quality Detail (table).
- [ ] Satellite Page / NASA GIBS.
- [ ] News categorization (LATEST, RECENT, HISTORICAL) and GDELT fallback.

## Phase 5: AI Analyst & Risk
- [ ] Risk breakdown (NOT SCORED handling).
- [ ] Collapsible PUBLIC DATA SOURCES reference panel.

## Phase 6: Tests & Verification
- [ ] Write integration tests.
- [ ] Verify Definition of Done.
