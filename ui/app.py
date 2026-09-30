"""
HYDRO MIND - Main Streamlit Application
"""
import sys
from pathlib import Path
import json
import streamlit as st
import folium
import streamlit.components.v1 as components

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from config.settings import APP_NAME, APP_SUBTITLE
from config.locations import BHAVANISAGAR_DAM
from database.db import execute_query, init_db
from scripts.orchestrator import run_pipeline
from agent.agent import HydroAgent
import threading

# --- Page Config ---
st.set_page_config(
    page_title=APP_NAME,
    page_icon="📡",
    layout="wide"
)

# Load CSS
css_path = BASE_DIR / "ui" / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Data Fetching
@st.cache_data(ttl=60)
def fetch_dashboard_data(news_limit=20):
    hydro_data = {"status": "UNAVAILABLE", "storage": "NOT SCORED"}
    wqi_data = {"status": "UNAVAILABLE", "score": "NOT SCORED"}
    
    # Weather
    w_rows = execute_query(
        "SELECT parameter, value, status FROM observations WHERE source = 'Open-Meteo' ORDER BY timestamp_utc DESC LIMIT 10"
    )
    weather_data = {"status": "UNAVAILABLE", "precip": "--", "temp": "--", "wind": "--"}
    if w_rows:
        weather_data["status"] = w_rows[0]["status"]
        for r in w_rows:
            if r["parameter"] == "precipitation": weather_data["precip"] = r["value"]
            elif r["parameter"] == "temperature_2m": weather_data["temp"] = r["value"]
            elif r["parameter"] == "wind_speed_10m": weather_data["wind"] = r["value"]
            
    # News
    news = execute_query(
        f"SELECT title, url, publisher, source_type, published_at_utc as time, category FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT {news_limit}"
    )
    
    # Alerts
    alerts = execute_query(
        "SELECT hazard_category, severity, message, evidence FROM alerts WHERE is_active = 1 ORDER BY created_at DESC LIMIT 10"
    )
    
    return hydro_data, weather_data, wqi_data, news, alerts

def render_sidebar():
    with st.sidebar:
        st.markdown(f"<div style='margin-bottom: 24px;'><span style='font-size: 20px; font-weight: 700; color: #EAEAEA; letter-spacing: -0.05em;'>// {APP_NAME}</span><br><span style='font-size: 11px; color: #666; font-family: monospace;'>{APP_SUBTITLE}</span></div>", unsafe_allow_html=True)
        
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: #666; margin-bottom: 8px; letter-spacing: 0.1em;'>[ OP_MODES ]</div>", unsafe_allow_html=True)
        if st.button("> MISSION_CONTROL", use_container_width=True): st.session_state.page = "Mission Control"
        
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: #666; margin-top: 16px; margin-bottom: 8px; letter-spacing: 0.1em;'>[ INTEL_FEEDS ]</div>", unsafe_allow_html=True)
        if st.button("> ENV_INTELLIGENCE", use_container_width=True): st.session_state.page = "Environmental Intelligence"
        
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: #666; margin-top: 16px; margin-bottom: 8px; letter-spacing: 0.1em;'>[ TACTICAL ]</div>", unsafe_allow_html=True)
        if st.button("> AI_RISK_ANALYST", use_container_width=True): st.session_state.page = "AI Analyst & Risk"
        
        st.divider()
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: #666; margin-bottom: 12px; letter-spacing: 0.1em;'>[ SYS_HEALTH ]</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 12px; font-family: monospace;'>WX_SAT <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 12px; font-family: monospace; margin-top: 8px;'>INTEL_NET <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 12px; font-family: monospace; margin-top: 8px;'>HYDRO_SENSORS <span class='status-badge badge-unavail' style='float:right'>UNAVAIL</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 12px; font-family: monospace; margin-top: 8px;'>WQ_NODE <span class='status-badge badge-unavail' style='float:right'>UNAVAIL</span></div>", unsafe_allow_html=True)
        
        st.divider()
        if st.button("EXECUTE_REFRESH", use_container_width=True):
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
    if s == "UNAVAILABLE" or s == "NOT SCORED": return "badge-unavail"
    if s == "OFFICIAL": return "badge-official"
    if s == "SECONDARY": return "badge-secondary"
    return "badge-unavail"

def render_hazard_card(title, data_status, score_val, band, reason):
    b_class = _get_badge_class(data_status)
    s_class = _get_sev_class(band) if data_status != "UNAVAILABLE" and data_status != "NOT SCORED" else ""
    val_display = score_val if (data_status != "UNAVAILABLE" and data_status != "NOT SCORED") else "NOT SCORED"
    
    html = f'''
    <div class="metric-card">
        <h4>{title} <span class="status-badge {b_class}" style="float:right">{data_status}</span></h4>
        <h2 class="{s_class}">{val_display}</h2>
        <div class="baseline">{reason}</div>
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def page_mission_control(hydro, weather, wqi, news, alerts):
    st.markdown("<div class='eyebrow'>// HYDRO_MIND_CORE_OPS</div>", unsafe_allow_html=True)
    st.markdown("<h1>MISSION CONTROL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>MACRO-LEVEL TELEMETRY: BHAVANISAGAR RESERVOIR // LOWER BHAVANI SECTOR</div>", unsafe_allow_html=True)
    
    # Evaluate Hazards based on fetched data
    # (In a real app, this would read from the DB's latest risk evaluation)
    # For now, we mock the hazard read based on alerts and weather
    run_score = "NOT SCORED"
    run_status = "NOT SCORED"
    run_band = "NORMAL"
    run_reason = "No precipitation or news anomaly detected"
    
    if weather["status"] == "LIVE" and weather["precip"] != "--" and float(weather["precip"]) > 20.0:
        run_score = "55"
        run_status = "SCORED"
        run_band = "WATCH"
        run_reason = f"Heavy rainfall detected: {weather['precip']} mm"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_hazard_card("WATER STRESS", "UNAVAILABLE", "--", "NORMAL", "No official hydrology data available")
    with col2:
        render_hazard_card("FLOOD / SURPLUS", "UNAVAILABLE", "--", "NORMAL", "No official inflow data available")
    with col3:
        render_hazard_card("WATER QUALITY", "UNAVAILABLE", "--", "NORMAL", "No current observation")
    with col4:
        render_hazard_card("RUNOFF / POLLUTION", run_status, run_score, run_band, run_reason)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Reservoir Status
    st.markdown("<h3>[ RESERVOIR_STATUS_MATRIX ]</h3>", unsafe_allow_html=True)
    st.markdown('''
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: #333; border: 1px solid #333;">
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">LEVEL</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">--</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">STORAGE</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">--</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">INFLOW</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">--</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">OUTFLOW</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">--</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">24H_LEVEL</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">--</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    
    colA, colB = st.columns([2, 1])
    with colA:
        st.markdown("<h3>[ GEO_SPATIAL_FEED ]</h3>", unsafe_allow_html=True)
        m = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=14, tiles="CartoDB dark_matter")
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup=str(BHAVANISAGAR_DAM['name']),
            tooltip="Bhavanisagar Dam - Reservoir/River Context"
        ).add_to(m)
        components.html(m._repr_html_(), height=450)

    with colB:
        st.markdown("<h3>[ ACTIVE_ALERTS ]</h3>", unsafe_allow_html=True)
        if alerts:
            for item in alerts[:3]:
                st.error(f"**{item['severity']}**: {item['message']}")
        else:
            st.success("> SYSTEM LOG: No active environmental alerts.")
            
        st.markdown("<h3 style='margin-top:24px;'>[ LATEST_LOGS ]</h3>", unsafe_allow_html=True)
        for item in news[:4]:
            badge = _get_badge_class(item["source_type"])
            st.markdown(
                f'''
                <div class="news-item">
                    <span class="status-badge {badge}">{item['source_type']}</span> <span style="font-size: 11px; color: #666; float:right;">{item['time'][:16]}</span><br>
                    <div style="margin-top: 12px;"><a href="{item['url']}" target="_blank" style="color: #EAEAEA; text-decoration: none; font-weight: 700; font-size: 14px; line-height: 1.4;">{item['title']}</a></div>
                    <div style="font-size: 11px; color: #888; font-family: monospace; margin-top: 8px;">> SOURCE: {item['publisher']}</div>
                </div>
                ''', unsafe_allow_html=True
            )

def page_environmental_intelligence(hydro, weather, wqi, news, alerts):
    st.markdown("<div class='eyebrow'>// INTEL_FEEDS</div>", unsafe_allow_html=True)
    st.markdown("<h1>ENVIRONMENTAL INTEL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>RAW FEED: EXTERNAL SIGNALS AND DECENTRALIZED DATA NODES</div>", unsafe_allow_html=True)
    
    st.markdown("<h3>[ OFFICIAL_UPDATES ]</h3>", unsafe_allow_html=True)
    st.info("> LOG: Awaiting official connection restore from CWC and TN-WRD. Fallback to secondary intelligence enabled.")
    
    st.markdown("<h3 style='margin-top:32px;'>[ WX_TELEMETRY ]</h3>", unsafe_allow_html=True)
    
    precip_val = f"{weather['precip']} mm" if weather['precip'] != "--" else "--"
    temp_val = f"{weather['temp']} °C" if weather['temp'] != "--" else "--"
    wind_val = f"{weather['wind']} km/h" if weather['wind'] != "--" else "--"
    
    st.markdown(f'''
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: #333; border: 1px solid #333;">
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">PRECIPITATION</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">{precip_val}</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">TEMPERATURE</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">{temp_val}</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">WIND_SPEED</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">{wind_val}</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>[ SATELLITE_INDICATORS // SENTINEL-2 ]</h3>", unsafe_allow_html=True)
    st.markdown('''
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: #333; border: 1px solid #333;">
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">NDWI_(WATER_EXTENT)</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">UNAVAIL</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">NDVI_(VEGETATION)</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">UNAVAIL</div></div>
        <div style="background: #0A0A0A; padding: 12px;"><div style="font-size: 10px; color:#888;">CLOUD_COVER</div><div style="font-family: monospace; font-size: 20px; font-weight: 700; color:#EAEAEA; margin-top: 4px;">UNAVAIL</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>[ SIGNAL_DISCOVERY ]</h3>", unsafe_allow_html=True)
    
    for item in news[:10]:
        badge = _get_badge_class(item["source_type"])
        st.markdown(
            f'''
            <div class="news-item">
                <span class="status-badge {badge}">{item['source_type']}</span> <span style="font-size: 11px; color: #666; float:right;">{item['time'][:16]}</span><br>
                <div style="margin-top: 12px;"><a href="{item['url']}" target="_blank" style="color: #EAEAEA; text-decoration: none; font-weight: 700; font-size: 14px; line-height: 1.4;">{item['title']}</a></div>
                <div style="font-size: 11px; color: #888; font-family: monospace; margin-top: 8px;">> SOURCE: {item['publisher']}</div>
            </div>
            ''', unsafe_allow_html=True
        )

def page_ai_analyst(hydro, weather, wqi, news, alerts):
    st.markdown("<div class='eyebrow'>// TACTICAL_ANALYSIS</div>", unsafe_allow_html=True)
    st.markdown("<h1>AI ANALYST & RISK</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>AUTOMATED THREAT DETECTION AND INTERROGATION INTERFACE</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([45, 55])
    
    with col1:
        st.markdown("<h3>Risk Breakdown</h3>", unsafe_allow_html=True)
        st.markdown("""
        <div class="panel">
            <p style="font-family: monospace; font-size: 12px; margin: 0 0 16px 0;"><strong>[ WATER_STRESS ]</strong> <span class="status-badge badge-unavail" style="float:right;">ERR_NO_DATA</span><br><span style="color:#666;">> Awaiting official telemetry.</span></p>
            <p style="font-family: monospace; font-size: 12px; margin: 0 0 16px 0;"><strong>[ FLOOD_SURPLUS ]</strong> <span class="status-badge badge-unavail" style="float:right;">ERR_NO_DATA</span><br><span style="color:#666;">> Awaiting official inflow feed.</span></p>
            <p style="font-family: monospace; font-size: 12px; margin: 0 0 16px 0;"><strong>[ WATER_QUALITY ]</strong> <span class="status-badge badge-unavail" style="float:right;">ERR_NO_DATA</span><br><span style="color:#666;">> Node offline.</span></p>
            <p style="font-family: monospace; font-size: 12px; margin: 0 0 0px 0;"><strong>[ RUNOFF_POLLUTION ]</strong> <span class="status-badge badge-live" style="float:right;">ACTIVE</span><br><span style="color:#4AF626;">> Weather node correlating risk.</span></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h3>Active Alerts</h3>", unsafe_allow_html=True)
        if alerts:
            for alert in alerts:
                sev_class = _get_sev_class(alert['severity'])
                try:
                    ev_list = json.loads(alert['evidence'])
                    ev_str = "<br>".join(f"? {e}" for e in ev_list)
                except:
                    ev_str = alert['evidence']
                
                st.markdown(f"""
                <div class="panel" style="border-left: 4px solid var(--{sev_class.replace('sev-', '')}, #FF2A2A);">
                    <div style="font-size: 11px; font-weight: 700; font-family: monospace; color: #FF2A2A; margin-bottom: 4px;">[ {alert['severity']} ]</div>
                    <div style="font-weight: 700; color: #EAEAEA; margin-bottom: 8px;">{alert['message']}</div>
                    <div style="font-size: 11px; font-family: monospace; color: #888;">{ev_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("> SYSTEM LOG: No active anomalies detected.")
            
    with col2:
        st.markdown("<h3>AI TACTICAL INTERROGATION</h3>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 11px; color: #4AF626; font-family: monospace; margin-bottom: 16px;'>[ NODE ONLINE : AWAITING INPUT ]</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='font-size: 10px; font-weight: 700; color: #666; margin-bottom: 8px; letter-spacing: 0.1em;'>[ AVAILABLE_VECTORS ]</div>", unsafe_allow_html=True)
        st.markdown("<span style='font-family: monospace; font-size: 12px; color: #888;'>WSS_DB | OPEN_METEO | G-NEWS_API | GEE_S2</span>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        user_input = st.text_input("QUERY", label_visibility="collapsed", placeholder=">>> ENTER COMMAND OR QUERY...")
        if st.button("EXECUTE", type="primary"):
            if user_input:
                agent = HydroAgent()
                with st.spinner("Processing telemetry..."):
                    response = agent.process_query(user_input)
                    st.markdown(f"<div class='panel' style='color:#EAEAEA; font-family: monospace; font-size: 13px; line-height: 1.6;'>{response}</div>", unsafe_allow_html=True)

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
        
    bootstrap_system()
            
    render_sidebar()
    hydro, weather, wqi, news, alerts = fetch_dashboard_data(news_limit=20)
    
    if st.session_state.page == "Mission Control":
        page_mission_control(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "Environmental Intelligence":
        page_environmental_intelligence(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "AI Analyst & Risk":
        page_ai_analyst(hydro, weather, wqi, news, alerts)

if __name__ == "__main__":
    main()
