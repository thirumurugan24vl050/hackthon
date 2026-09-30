"""
HYDRO MIND - Main Streamlit Application
"""
import sys
from pathlib import Path
import json
import streamlit as st
import folium
import streamlit.components.v1 as components
import threading
from datetime import datetime, timezone, timedelta

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from config.settings import APP_NAME, APP_SUBTITLE
from config.locations import BHAVANISAGAR_DAM
from database.db import execute_query, init_db
from scripts.orchestrator import run_pipeline
from agent.agent import HydroAgent

# --- Page Config ---
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# HTML for water bubble background
def inject_water_bubbles():
    html = """
    <div class="bubble-container">
        <div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>
        <div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>
        <div class="bubble"></div><div class="bubble"></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# Load CSS
css_path = BASE_DIR / "ui" / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Data Fetching
@st.cache_data(ttl=60)
def fetch_dashboard_data(news_limit=30, mode="LIVE"):
    # If mode is DEMO_SNAPSHOT, return mock data
    if mode == "DEMO_SNAPSHOT":
        return get_demo_snapshot_data(news_limit)

    # 1. Hydrology (Reservoir + Flood)
    hydro_data = {"status": "UNAVAILABLE", "reason": "No data", "level_ft": "--", "storage_mcft": "--", "inflow_cusecs": "--", "outflow_cusecs": "--", "capacity_mcft": 32800, "storage_pct": "--", "discharge_m3s": "--", "flood_status": "UNAVAILABLE"}
    
    # Try fetching latest hydrology observations
    h_rows = execute_query(
        "SELECT parameter, value, status, timestamp_ist, source FROM observations WHERE station_id = ? AND source IN ('TN AgriNet', 'Open-Meteo') ORDER BY timestamp_utc DESC LIMIT 20",
        (BHAVANISAGAR_DAM["id"],)
    )
    if h_rows:
        h_vals = {}
        for r in h_rows:
            if r["parameter"] not in h_vals:
                h_vals[r["parameter"]] = r
        
        if "level_ft" in h_vals:
            hydro_data["level_ft"] = h_vals["level_ft"]["value"]
            hydro_data["status"] = h_vals["level_ft"]["status"]
            hydro_data["reason"] = f"Scraped from {h_vals['level_ft']['source']}"
            hydro_data["last_updated"] = h_vals["level_ft"]["timestamp_ist"]
        if "storage_mcft" in h_vals:
            hydro_data["storage_mcft"] = h_vals["storage_mcft"]["value"]
            if hydro_data["storage_mcft"] != "--" and hydro_data["capacity_mcft"] > 0:
                hydro_data["storage_pct"] = round((float(hydro_data["storage_mcft"]) / hydro_data["capacity_mcft"]) * 100, 2)
        if "inflow_cusecs" in h_vals: hydro_data["inflow_cusecs"] = h_vals["inflow_cusecs"]["value"]
        if "outflow_cusecs" in h_vals: hydro_data["outflow_cusecs"] = h_vals["outflow_cusecs"]["value"]
        if "discharge_m3s" in h_vals: 
            hydro_data["discharge_m3s"] = h_vals["discharge_m3s"]["value"]
            hydro_data["flood_status"] = h_vals["discharge_m3s"]["status"]

    # 2. Water Quality
    # In live system without telemetry, we only have PUBLIC_LATEST classification.
    wqi_data = {
        "status": "PUBLIC_LATEST",
        "station": "Bhavani Sagar",
        "class": "Category 'B' (Outdoor Bathing Organized)",
        "report_period": "2023-2024",
        "source": "TNPCB",
        "category": "B",
        "risk": "NORMAL",
        "score": "NOT SCORED"
    }

    # 3. Weather
    w_rows = execute_query(
        "SELECT parameter, value, status, timestamp_ist FROM observations WHERE source = 'Open-Meteo' ORDER BY timestamp_utc DESC LIMIT 20"
    )
    weather_data = {"status": "UNAVAILABLE", "precip": "--", "temp": "--", "wind": "--", "humidity": "--", "pressure": "--"}
    if w_rows:
        has_values = False
        for r in w_rows:
            if r["parameter"] == "precipitation" and r["value"] != "--" and weather_data["precip"] == "--": 
                weather_data["precip"] = r["value"]
                has_values = True
            elif r["parameter"] == "temperature_2m" and r["value"] != "--" and weather_data["temp"] == "--": 
                weather_data["temp"] = r["value"]
                has_values = True
            elif r["parameter"] == "wind_speed_10m" and r["value"] != "--" and weather_data["wind"] == "--": 
                weather_data["wind"] = r["value"]
                has_values = True
            elif r["parameter"] == "relative_humidity_2m" and r["value"] != "--" and weather_data["humidity"] == "--": 
                weather_data["humidity"] = r["value"]
            elif r["parameter"] == "surface_pressure" and r["value"] != "--" and weather_data["pressure"] == "--": 
                weather_data["pressure"] = r["value"]
            
            if "last_updated" not in weather_data and has_values:
                weather_data["last_updated"] = r["timestamp_ist"]
        
        weather_data["status"] = "LIVE" if has_values else "UNAVAILABLE"
            
    # 4. News
    raw_news = execute_query(
        "SELECT title, url, publisher, source_type, published_at_utc as time, category FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT 150"
    )
    
    news = []
    seen_urls = set()
    seen_titles = set()
    
    if raw_news:
        for item in raw_news:
            url_norm = item['url'].lower().strip()
            title_norm = f"{item['publisher']}_{item['title']}".lower().strip()
            if url_norm not in seen_urls and title_norm not in seen_titles:
                seen_urls.add(url_norm)
                seen_titles.add(title_norm)
                news.append(item)
                if len(news) >= news_limit:
                    break
    
    # 5. Alerts
    raw_alerts = execute_query(
        "SELECT hazard_category, severity, message, evidence, created_at FROM alerts WHERE is_active = 1 ORDER BY created_at DESC LIMIT 50"
    )
    
    alerts = []
    seen_alerts = set()
    if raw_alerts:
        for item in raw_alerts:
            if "EXTERNAL EVENT" in item["message"] or "EXTERNAL EVENT" in item["evidence"]:
                continue
            alert_key = f"{item['hazard_category']}_{item['message']}"
            if alert_key not in seen_alerts:
                seen_alerts.add(alert_key)
                alerts.append(item)
                if len(alerts) >= 10:
                    break
    
    return hydro_data, weather_data, wqi_data, news, alerts

def get_demo_snapshot_data(news_limit):
    """Returns static DEMO snapshot data."""
    hydro = {
        "status": "DEMO_SNAPSHOT", "reason": "Demo Snapshot Mode",
        "level_ft": 53.02, "storage_mcft": 5198, "inflow_cusecs": 58, "outflow_cusecs": 555,
        "capacity_mcft": 32800, "storage_pct": 15.85, "discharge_m3s": 15.2, "flood_status": "DEMO_SNAPSHOT",
        "last_updated": "2026-07-06T12:00:00Z"
    }
    weather = {
        "status": "DEMO_SNAPSHOT", "precip": 12.5, "temp": 28.4, "wind": 14.2, "humidity": 75, "pressure": 1008.2, "last_updated": "2026-07-06T12:00:00Z"
    }
    wqi = {
        "status": "DEMO_SNAPSHOT", "station": "Bhavani Sagar", "class": "Category 'B'", "report_period": "2023-2024", "source": "TNPCB", "category": "B", "risk": "NORMAL", "score": "NOT SCORED"
    }
    news = [
        {"title": "Bhavanisagar dam water level stands at 53 feet", "publisher": "The Hindu", "url": "#", "source_type": "SECONDARY", "time": datetime.now(timezone.utc).isoformat(), "category": "ENVIRONMENTAL"}
    ]
    alerts = [
        {"hazard_category": "RUNOFF / POLLUTION", "severity": "WATCH", "message": "Heavy rainfall expected to increase inflow.", "evidence": "['Forecast: 12.5mm']", "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    return hydro, weather, wqi, news, alerts

def render_sidebar():
    with st.sidebar:
        st.markdown(f"<div style='margin-bottom: 24px;'><span style='font-size: 20px; font-weight: 800; color: #F8FAFC; letter-spacing: -0.05em;'>{APP_NAME}</span><br><span style='font-size: 13px; color: #94A3B8;'>{APP_SUBTITLE}</span></div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 1px; background: rgba(148,163,184,0.14); margin-bottom: 24px;'></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='eyebrow'>Monitor</div>", unsafe_allow_html=True)
        if st.button("Mission Control", use_container_width=True): st.session_state.page = "Mission Control"
        
        st.markdown("<div class='eyebrow' style='margin-top: 16px;'>Intelligence</div>", unsafe_allow_html=True)
        if st.button("Environmental Intelligence", use_container_width=True): st.session_state.page = "Environmental Intelligence"
        
        st.markdown("<div class='eyebrow' style='margin-top: 16px;'>Analysis</div>", unsafe_allow_html=True)
        if st.button("AI Analyst & Risk", use_container_width=True): st.session_state.page = "AI Analyst & Risk"
        
        st.markdown("<div style='height: 1px; background: rgba(148,163,184,0.14); margin: 24px 0;'></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='eyebrow'>Data Health</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-bottom: 8px;'>Weather <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-bottom: 8px;'>Intelligence <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-bottom: 8px;'>Hydrology <span class='status-badge badge-unavail' style='float:right'>UNAVAILABLE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-bottom: 24px;'>Water Quality <span class='status-badge badge-unavail' style='float:right'>UNAVAILABLE</span></div>", unsafe_allow_html=True)
        
        if st.button("Refresh", use_container_width=True):
            st.rerun()

def _get_sev_class(severity):
    s = severity.upper()
    if s == "NORMAL": return "sev-normal"
    if s == "WATCH": return "sev-watch"
    if s == "ELEVATED": return "sev-elevated"
    if s in ["HIGH", "CRITICAL"]: return "sev-critical"
    return ""

def _get_badge_class(status):
    s = status.upper()
    if s == "LIVE": return "badge-live"
    if s == "SCORED": return "badge-scored"
    if s == "ACTIVE": return "badge-active"
    if s == "UNAVAILABLE" or s == "NOT SCORED": return "badge-unavail"
    if s == "OFFICIAL": return "badge-official"
    if s == "SECONDARY": return "badge-secondary"
    return "badge-unavail"

def render_hazard_card(title, data_status, score_val, band, reason):
    b_class = _get_badge_class(data_status)
    s_class = _get_sev_class(band) if data_status not in ["UNAVAILABLE", "NOT SCORED"] else ""
    val_display = score_val if data_status not in ["UNAVAILABLE", "NOT SCORED"] else "NOT SCORED"
    
    html = f'''
    <div class="metric-card">
        <h4>{title} <span class="status-badge {b_class}" style="float:right">{data_status}</span></h4>
        <h2 class="{s_class}">{val_display}</h2>
        <div class="baseline">{reason}</div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def render_top_bar(hydro, weather, wqi):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Determine aggregate health for top indicator
    aggregate_live = any(x["status"] == "LIVE" for x in [weather, hydro])
    
    mode = st.session_state.data_mode
    mode_label = "LIVE" if aggregate_live and mode == "LIVE" else mode.replace("_", " ")
    badge = "badge-live" if mode_label == "LIVE" else ("badge-official" if mode == "PUBLIC_LATEST" else "badge-secondary")
    
    col1, col2 = st.columns([7, 3])
    with col1:
        st.markdown(f'''
        <div style="display: flex; align-items: center; padding-bottom: 24px;">
            <span style="font-weight: 700; color: #F8FAFC; font-size: 20px;">HYDRO MIND</span> 
            <span style="color: #94A3B8; margin-left: 8px;">| Bhavanisagar Dam • Erode, Tamil Nadu</span>
        </div>
        ''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''
        <div style="text-align: right; font-size: 13px; color: #94A3B8; padding-bottom: 24px;">
            <span class="status-badge {badge}" style="margin-right: 12px;">{mode_label}</span> Last updated: {now_str}
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('<div style="border-bottom: 1px solid rgba(148,163,184,0.14); margin-bottom: 24px; margin-top: -16px;"></div>', unsafe_allow_html=True)

def page_mission_control(hydro, weather, wqi, news, alerts):
    render_top_bar(hydro, weather, wqi)
    st.markdown("<div class='eyebrow'>ENVIRONMENTAL OPERATIONS</div>", unsafe_allow_html=True)
    st.markdown("<h1>MISSION CONTROL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>High-level environmental overview of Bhavanisagar Dam and the Lower Bhavani River.</div>", unsafe_allow_html=True)
    
    run_score = "NOT SCORED"
    run_status = "NOT SCORED"
    run_band = "NORMAL"
    run_reason = "No precipitation or news anomaly detected"
    
    if weather["status"] != "UNAVAILABLE" and weather["precip"] != "--" and float(weather["precip"]) > 20.0:
        run_score = "55 / 100"
        run_status = "SCORED"
        run_band = "WATCH"
        run_reason = f"Heavy rainfall detected: {weather['precip']} mm"
        
    water_stress_status = "NOT SCORED"
    water_stress_score = "--"
    water_stress_band = "NORMAL"
    water_stress_reason = "Missing reservoir capacity metric"
    if hydro["status"] != "UNAVAILABLE" and hydro.get("storage_pct") != "--":
        water_stress_status = "SCORED"
        if hydro["storage_pct"] < 20:
            water_stress_score = "75 / 100"
            water_stress_band = "ELEVATED"
            water_stress_reason = f"Storage critically low ({hydro['storage_pct']}%)"
        else:
            water_stress_score = "20 / 100"
            water_stress_band = "NORMAL"
            water_stress_reason = f"Storage nominal ({hydro['storage_pct']}%)"
            
    flood_status = "NOT SCORED"
    flood_score = "--"
    flood_band = "NORMAL"
    flood_reason = "No official telemetry"
    if hydro["flood_status"] != "UNAVAILABLE" and hydro.get("discharge_m3s") != "--":
        flood_status = "SCORED"
        val = float(hydro["discharge_m3s"])
        if val > 100:
            flood_score = "60 / 100"
            flood_band = "WATCH"
            flood_reason = f"Model discharge {val} m³/s"
        else:
            flood_score = "10 / 100"
            flood_band = "NORMAL"
            flood_reason = f"Model discharge {val} m³/s"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_hazard_card("Water Stress", water_stress_status, water_stress_score, water_stress_band, water_stress_reason)
    with col2:
        render_hazard_card("Flood / Surplus", flood_status, flood_score, flood_band, flood_reason)
    with col3:
        render_hazard_card("Water Quality", wqi["status"], wqi["score"], wqi["risk"], f"Class {wqi['category']} ({wqi['report_period']})")
    with col4:
        render_hazard_card("Runoff / Pollution", run_status, run_score, run_band, run_reason)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    st.markdown("<h3>Reservoir Status</h3>", unsafe_allow_html=True)
    h_level = f"{hydro['level_ft']} ft" if hydro['level_ft'] != "--" else "N/A"
    h_storage = f"{hydro['storage_mcft']} MCft" if hydro['storage_mcft'] != "--" else "N/A"
    h_inflow = f"{hydro['inflow_cusecs']} cusecs" if hydro['inflow_cusecs'] != "--" else "N/A"
    h_outflow = f"{hydro['outflow_cusecs']} cusecs" if hydro['outflow_cusecs'] != "--" else "N/A"
    h_net = "N/A"
    if hydro['inflow_cusecs'] != "--" and hydro['outflow_cusecs'] != "--":
        h_net = f"{float(hydro['inflow_cusecs']) - float(hydro['outflow_cusecs'])} cusecs"
    
    h_badge = _get_badge_class(hydro['status'])
    
    st.markdown(f'''
    <div class="matrix-grid">
        <div class="matrix-cell"><div class="matrix-label">LEVEL</div><div class="matrix-value" style="color: #F8FAFC;">{h_level}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {h_badge}">{hydro['status']}</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">STORAGE</div><div class="matrix-value" style="color: #F8FAFC;">{h_storage}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {h_badge}">{hydro['status']}</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">INFLOW</div><div class="matrix-value" style="color: #F8FAFC;">{h_inflow}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {h_badge}">{hydro['status']}</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">OUTFLOW</div><div class="matrix-value" style="color: #F8FAFC;">{h_outflow}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {h_badge}">{hydro['status']}</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">NET FLOW</div><div class="matrix-value" style="color: #F8FAFC;">{h_net}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {h_badge}">{hydro['status']}</span></div></div>
    </div>
    ''', unsafe_allow_html=True)
    if hydro['status'] != "UNAVAILABLE":
        st.markdown(f"<div style='font-size: 12px; color: #94A3B8; margin-top: 8px;'>Source: {hydro['reason']} (Updated: {hydro.get('last_updated', 'Unknown')})</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    
    colA, colB = st.columns([6, 4])
    with colA:
        st.markdown("<h3>Environmental Map</h3>", unsafe_allow_html=True)
        m = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=13, tiles="OpenStreetMap")
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup=str(BHAVANISAGAR_DAM['name']),
            tooltip="Bhavanisagar Dam"
        ).add_to(m)
        components.html(m._repr_html_(), height=450)
        st.markdown("<div style='font-size:11px; color:#94A3B8; text-align:right;'>© OpenStreetMap contributors</div>", unsafe_allow_html=True)

    with colB:
        st.markdown("<h3>Recent Activity</h3>", unsafe_allow_html=True)
        logs_html = ""
        if not alerts and weather['status'] == "UNAVAILABLE" and hydro['status'] == "UNAVAILABLE":
            logs_html = "<li>No new environmental events since last refresh.</li>"
        else:
            if weather['status'] != "UNAVAILABLE": logs_html += "<li>Weather telemetry refreshed successfully.</li>"
            if hydro['status'] != "UNAVAILABLE": logs_html += "<li>Reservoir status updated from official sources.</li>"
            if alerts: logs_html += f"<li>{len(alerts)} alerts generated in current evaluation window.</li>"
            
        st.markdown(f"""
        <div class="panel">
            <ul style="color: #CBD5E1; font-size: 14px; line-height: 1.8; margin: 0; padding-left: 20px;">
                {logs_html}
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h3 style='margin-top:24px;'>Active Alerts</h3>", unsafe_allow_html=True)
        if alerts:
            for item in alerts[:3]:
                st.error(f"**{item['severity']}**: {item['message']}")
        else:
            st.markdown("""
            <div class="panel" style="text-align: center; color: #94A3B8;">
                <div style="margin-bottom: 8px;">✅</div>
                <div style="font-weight: 600;">NO ACTIVE ENVIRONMENTAL ALERTS</div>
                <div style="font-size: 13px;">All monitored conditions are currently below configured alert criteria.</div>
            </div>
            """, unsafe_allow_html=True)

def page_environmental_intelligence(hydro, weather, wqi, news, alerts):
    render_top_bar(hydro, weather, wqi)
    st.markdown("<div class='eyebrow'>INTELLIGENCE FEED</div>", unsafe_allow_html=True)
    st.markdown("<h1>ENVIRONMENTAL INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>Public environmental evidence, weather telemetry, satellite imagery and external information.</div>", unsafe_allow_html=True)
    
    st.markdown("<h3>Water Quality</h3>", unsafe_allow_html=True)
    w_badge = _get_badge_class(wqi['status'])
    st.markdown(f'''
    <div class="panel">
        <div style="display:flex; justify-content:space-between; margin-bottom: 12px;">
            <span style="font-size: 11px; font-weight:700; color:#36D6E8;">LATEST PUBLISHED CLASSIFICATION</span>
            <span class="status-badge {w_badge}">{wqi['status']}</span>
        </div>
        <table style="width: 100%; text-align: left; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid rgba(148,163,184,0.14);">
                <th style="padding: 8px;">Parameter</th><th style="padding: 8px;">Value</th><th style="padding: 8px;">Unit</th><th style="padding: 8px;">Sample Date</th><th style="padding: 8px;">Source</th>
            </tr>
            <tr>
                <td style="padding: 8px;">Classification</td><td style="padding: 8px;">{wqi.get("class", "N/A")}</td><td style="padding: 8px;">-</td><td style="padding: 8px;">{wqi.get("report_period", "N/A")}</td><td style="padding: 8px;">TNPCB</td>
            </tr>
            <tr>
                <td style="padding: 8px;">pH</td><td style="padding: 8px;">N/A</td><td style="padding: 8px;">-</td><td style="padding: 8px;">N/A</td><td style="padding: 8px;">-</td>
            </tr>
            <tr>
                <td style="padding: 8px;">DO</td><td style="padding: 8px;">N/A</td><td style="padding: 8px;">mg/L</td><td style="padding: 8px;">N/A</td><td style="padding: 8px;">-</td>
            </tr>
        </table>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>Weather Telemetry</h3>", unsafe_allow_html=True)
    
    precip_val = f"{weather['precip']} mm" if weather['precip'] != "--" else "--"
    temp_val = f"{weather['temp']} °C" if weather['temp'] != "--" else "--"
    wind_val = f"{weather['wind']} km/h" if weather['wind'] != "--" else "--"
    
    wb = _get_badge_class(weather["status"])
    st.markdown(f'''
    <div class="matrix-grid" style="grid-template-columns: repeat(3, 1fr);">
        <div class="matrix-cell"><div class="matrix-label">PRECIPITATION</div><div class="matrix-value">{precip_val}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {wb}">{weather["status"]}</span> Source: Open-Meteo</div></div>
        <div class="matrix-cell"><div class="matrix-label">TEMPERATURE</div><div class="matrix-value">{temp_val}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {wb}">{weather["status"]}</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">WIND SPEED</div><div class="matrix-value">{wind_val}</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge {wb}">{weather["status"]}</span></div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>Satellite Observation</h3>", unsafe_allow_html=True)
    st.markdown('''
    <div style="display:flex; justify-content:space-between; margin-bottom: 12px; margin-top: 12px;">
        <span style="font-size: 11px; font-weight:700; color:#36D6E8;">NASA GIBS SATELLITE IMAGERY</span>
        <span class="status-badge badge-live">AVAILABLE</span>
    </div>
    ''', unsafe_allow_html=True)
    
    colS1, colS2 = st.columns([7, 3])
    with colS1:
        # Use Folium to render a map centered on Bhavanisagar with NASA GIBS layer
        m_sat = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=11, tiles=None)
        
        # NASA GIBS True Color
        folium.TileLayer(
            tiles='https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/current/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg',
            attr='NASA EOSDIS GIBS',
            name='NASA GIBS True Color',
            overlay=True
        ).add_to(m_sat)
        
        components.html(m_sat._repr_html_(), height=400)
    with colS2:
        st.markdown('''
        <div class="panel" style="height: 100%;">
            <div style="margin-bottom: 16px;">
                <div class="matrix-label">NDWI (WATER EXTENT)</div>
                <div class="matrix-value" style="color:#94A3B8;">N/A</div>
            </div>
            <div style="margin-bottom: 16px;">
                <div class="matrix-label">MNDWI</div>
                <div class="matrix-value" style="color:#94A3B8;">N/A</div>
            </div>
            <div>
                <div class="matrix-label">SOURCE</div>
                <div class="matrix-value" style="color:#94A3B8; font-size:16px;">NASA GIBS</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>News Discovery</h3>", unsafe_allow_html=True)
    
    for item in news[:10]:
        badge = _get_badge_class(item["source_type"])
        # Freshness determination
        try:
            pub_dt = datetime.fromisoformat(item['time'].replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
            if age_hours <= 12: freshness = "LATEST"
            elif age_hours <= 168: freshness = "RECENT"
            else: freshness = "HISTORICAL"
        except:
            freshness = "UNKNOWN"
            
        st.markdown(
            f'''
            <div class="news-item">
                <div style="display:flex; justify-content:space-between; margin-bottom: 12px;">
                    <div><span class="status-badge {badge}">{item['source_type']}</span> <span style="font-size: 12px; color:#36D6E8; margin-left:8px; font-weight:600;">{freshness}</span></div>
                    <span style="font-size: 12px; color: #94A3B8;">{item['time'][:16]}</span>
                </div>
                <div><a href="{item['url']}" target="_blank" style="color: #F8FAFC; text-decoration: none; font-weight: 600; font-size: 15px; line-height: 1.4;">{item['title']}</a></div>
                <div style="font-size: 13px; color: #94A3B8; margin-top: 8px;">{item['publisher']}</div>
            </div>
            ''', unsafe_allow_html=True
        )

def page_ai_analyst(hydro, weather, wqi, news, alerts):
    render_top_bar(hydro, weather, wqi)
    st.markdown("<div class='eyebrow'>ANALYSIS & DECISION SUPPORT</div>", unsafe_allow_html=True)
    st.markdown("<h1>AI ANALYST & RISK</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>AI-assisted environmental analysis using reservoir, weather, satellite, historical, alert and external information.</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([45, 55])
    
    with col1:
        st.markdown("<h3>Risk Breakdown</h3>", unsafe_allow_html=True)
        
        ws_badge = _get_badge_class("SCORED") if hydro["status"] != "UNAVAILABLE" else _get_badge_class("UNAVAILABLE")
        ws_status = "SCORED" if hydro["status"] != "UNAVAILABLE" else "NOT SCORED"
        
        fs_badge = _get_badge_class("SCORED") if hydro["flood_status"] != "UNAVAILABLE" else _get_badge_class("UNAVAILABLE")
        fs_status = "SCORED" if hydro["flood_status"] != "UNAVAILABLE" else "NOT SCORED"
        
        wq_badge = _get_badge_class("UNAVAILABLE") # We don't score water quality risk purely on historical category
        
        run_badge = _get_badge_class("LIVE")
        
        st.markdown(f"""
        <div class="panel">
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Water Stress</strong> <span class="status-badge {ws_badge}">{ws_status}</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Contributors: Reservoir Storage, Inflow</div>
            </div>
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Flood / Surplus</strong> <span class="status-badge {fs_badge}">{fs_status}</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Contributors: River Discharge Model</div>
            </div>
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Water Quality</strong> <span class="status-badge {wq_badge}">NOT SCORED</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Data Limitations: Live telemetry offline</div>
            </div>
            <div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Runoff / Pollution</strong> <span class="status-badge {run_badge}">MONITORING</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Contributors: Weather, Satellite Anomaly</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("PUBLIC DATA SOURCES"):
            st.markdown("""
            - **Open-Meteo**: Weather + flood model
            - **Tamil Nadu AgriNet**: Reservoir public data
            - **TNPCB**: Water quality reports
            - **NASA GIBS**: Satellite imagery
            - **OpenStreetMap**: Map basemap
            - **Google News / GDELT**: News discovery
            """)
        
        st.markdown("<h3>Active Alerts</h3>", unsafe_allow_html=True)
        if alerts:
            for alert in alerts:
                sev_class = _get_sev_class(alert['severity'])
                try:
                    ev_list = json.loads(alert['evidence'])
                    ev_str = "<br>".join(f"• {e}" for e in ev_list)
                except:
                    ev_str = alert['evidence']
                
                st.markdown(f"""
                <div class="panel" style="border-left: 4px solid var(--{sev_class.replace('sev-', '')}, #EF4444);">
                    <div style="font-size: 11px; font-weight: 700; color: #EF4444; margin-bottom: 4px;">{alert['severity']}</div>
                    <div style="font-weight: 600; color: #F8FAFC; margin-bottom: 8px;">{alert['message']}</div>
                    <div style="font-size: 13px; color: #94A3B8;">{ev_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="panel" style="text-align: center; color: #94A3B8;">
                <div style="font-size: 24px; margin-bottom: 8px;">✅</div>
                <div style="font-weight: 600;">NO ACTIVE ALERTS</div>
            </div>
            """, unsafe_allow_html=True)
            
    with col2:
        st.markdown("<h3>AI Environmental Analyst</h3>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; color: #34D399; margin-bottom: 16px;'><span class='status-badge badge-live'>READY</span></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='eyebrow'>Available Tools</div>", unsafe_allow_html=True)
        st.markdown("<span style='font-size: 13px; color: #94A3B8;'>Reservoir • Weather • Satellite • History • News • Alerts</span>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        user_input = st.text_input("Query", label_visibility="collapsed", placeholder="Ask about the current environmental state...")
        
        if st.button("Analyze", type="primary"):
            if user_input:
                agent = HydroAgent()
                with st.spinner("Analyzing..."):
                    response = agent.process_query(user_input)
                    st.markdown("""
                    <div class="panel" style="background-color: rgba(54, 214, 232, 0.05); border-color: rgba(54, 214, 232, 0.2);">
                        <div class="eyebrow" style="margin-bottom: 12px;">Tools Used</div>
                        <div style="font-size: 13px; color: #CBD5E1; margin-bottom: 16px;">✓ Reservoir<br>✓ Weather<br>✓ Satellite<br>✓ History<br>✓ News<br>✓ Alerts</div>
                        <div class="eyebrow" style="margin-bottom: 12px;">Analysis</div>
                        <div style="color:#F8FAFC; font-size: 14px; line-height: 1.6;">%s</div>
                        <div class="eyebrow" style="margin-top: 16px; margin-bottom: 12px;">Data Limitations</div>
                        <div style="font-size: 12px; color: #94A3B8; font-style: italic;">The AI can only cite values returned from current tools. It does not invent missing telemetry points.</div>
                    </div>
                    """ % response.replace('\n', '<br>'), unsafe_allow_html=True)

@st.cache_resource
def bootstrap_system():
    init_db()
    def background_task():
        try:
            check = execute_query("SELECT COUNT(*) as count FROM observations")
            if not check or check[0]['count'] == 0:
                run_pipeline()
        except Exception:
            run_pipeline()
            
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()
    return True

def main():
    if "page" not in st.session_state:
        st.session_state.page = "Mission Control"
        
    if "data_mode" not in st.session_state:
        st.session_state.data_mode = "LIVE"
        
    bootstrap_system()
    inject_water_bubbles()
    
    with st.sidebar:
        st.markdown("<div class='eyebrow'>DATA MODE</div>", unsafe_allow_html=True)
        st.session_state.data_mode = st.radio(
            "Data Availability", 
            ["LIVE", "PUBLIC_LATEST", "DEMO_SNAPSHOT"], 
            label_visibility="collapsed"
        )
            
    render_sidebar()
    hydro, weather, wqi, news, alerts = fetch_dashboard_data(news_limit=30, mode=st.session_state.data_mode)
    
    if st.session_state.page == "Mission Control":
        page_mission_control(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "Environmental Intelligence":
        page_environmental_intelligence(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "AI Analyst & Risk":
        page_ai_analyst(hydro, weather, wqi, news, alerts)

if __name__ == "__main__":
    main()
