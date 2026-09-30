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

# --- Page Config ---
st.set_page_config(
    page_title=APP_NAME,
    page_icon="??",
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
        st.markdown(f"<div style='margin-bottom: 24px;'><span style='font-size: 20px; font-weight: 800; color: #F8FAFC; letter-spacing: -0.02em;'>?? {APP_NAME}</span><br><span style='font-size: 11px; color: #94A3B8;'>{APP_SUBTITLE}</span></div>", unsafe_allow_html=True)
        
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94A3B8; margin-bottom: 8px;'>MONITOR</div>", unsafe_allow_html=True)
        if st.button("? Mission Control", use_container_width=True): st.session_state.page = "Mission Control"
        
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94A3B8; margin-top: 16px; margin-bottom: 8px;'>INTELLIGENCE</div>", unsafe_allow_html=True)
        if st.button("? Environmental Intelligence", use_container_width=True): st.session_state.page = "Environmental Intelligence"
        
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94A3B8; margin-top: 16px; margin-bottom: 8px;'>ANALYSIS</div>", unsafe_allow_html=True)
        if st.button("? AI Analyst & Risk", use_container_width=True): st.session_state.page = "AI Analyst & Risk"
        
        st.divider()
        st.markdown("<div style='font-size: 11px; font-weight: 700; color: #94A3B8; margin-bottom: 12px;'>DATA HEALTH</div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px;'>Weather <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-top: 8px;'>Intelligence <span class='status-badge badge-live' style='float:right'>LIVE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-top: 8px;'>Hydrology <span class='status-badge badge-unavail' style='float:right'>UNAVAILABLE</span></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 13px; margin-top: 8px;'>Water Quality <span class='status-badge badge-unavail' style='float:right'>UNAVAILABLE</span></div>", unsafe_allow_html=True)
        
        st.divider()
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
    st.markdown("<div class='eyebrow'>HYDRO MIND / ENVIRONMENTAL OPERATIONS</div>", unsafe_allow_html=True)
    st.markdown("<h1>MISSION CONTROL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>High-level overview of Bhavanisagar Dam and the Lower Bhavani River.</div>", unsafe_allow_html=True)
    
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
    st.markdown("<h3>Reservoir Status</h3>", unsafe_allow_html=True)
    r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns(5)
    r_col1.metric("LEVEL", "--", delta=None, help="UNAVAILABLE")
    r_col2.metric("STORAGE", "--")
    r_col3.metric("INFLOW", "--")
    r_col4.metric("OUTFLOW", "--")
    r_col5.metric("24H LEVEL", "--")

    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    
    colA, colB = st.columns([2, 1])
    with colA:
        st.markdown("<h3>Environmental Map</h3>", unsafe_allow_html=True)
        m = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=14, tiles="CartoDB dark_matter")
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup=str(BHAVANISAGAR_DAM['name']),
            tooltip="Bhavanisagar Dam - Reservoir/River Context"
        ).add_to(m)
        components.html(m._repr_html_(), height=450)

    with colB:
        st.markdown("<h3>Active Alerts</h3>", unsafe_allow_html=True)
        if alerts:
            for item in alerts[:3]:
                st.error(f"**{item['severity']}**: {item['message']}")
        else:
            st.success("No active environmental alerts.")
            
        st.markdown("<h3 style='margin-top:24px;'>Latest Environmental Updates</h3>", unsafe_allow_html=True)
        for item in news[:4]:
            badge = _get_badge_class(item["source_type"])
            st.markdown(
                f'''
                <div class="news-item">
                    <span class="status-badge {badge}">{item['source_type']}</span> <span style="font-size: 11px; color: #8b949e; float:right;">{item['time'][:16]}</span><br>
                    <div style="margin-top: 8px;"><a href="{item['url']}" target="_blank" style="color: #F8FAFC; text-decoration: none; font-weight: 600; font-size: 13px;">{item['title']}</a></div>
                    <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">{item['publisher']}</div>
                </div>
                ''', unsafe_allow_html=True
            )

def page_environmental_intelligence(hydro, weather, wqi, news, alerts):
    st.markdown("<div class='eyebrow'>HYDRO MIND / INTELLIGENCE</div>", unsafe_allow_html=True)
    st.markdown("<h1>ENVIRONMENTAL INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>Live external and environmental evidence for Bhavanisagar</div>", unsafe_allow_html=True)
    
    st.markdown("<h3>Official Updates</h3>", unsafe_allow_html=True)
    st.info("Awaiting official connection restore from CWC and TN-WRD. Fallback to secondary intelligence enabled.")
    
    st.markdown("<h3 style='margin-top:32px;'>Weather Telemetry</h3>", unsafe_allow_html=True)
    w_col1, w_col2, w_col3 = st.columns(3)
    w_col1.metric("Precipitation", f"{weather['precip']} mm" if weather['precip'] != "--" else "--")
    w_col2.metric("Temperature", f"{weather['temp']} °C" if weather['temp'] != "--" else "--")
    w_col3.metric("Wind Speed", f"{weather['wind']} km/h" if weather['wind'] != "--" else "--")
    
    st.markdown("<h3 style='margin-top:32px;'>Satellite Indicators (Sentinel-2)</h3>", unsafe_allow_html=True)
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("NDWI (Water Extent)", "UNAVAILABLE", help="Requires Earth Engine API")
    s_col2.metric("NDVI (Vegetation)", "UNAVAILABLE")
    s_col3.metric("Cloud Cover", "UNAVAILABLE")
    
    st.markdown("<h3 style='margin-top:32px;'>Google News Discovery</h3>", unsafe_allow_html=True)
    
    for item in news[:10]:
        badge = _get_badge_class(item["source_type"])
        st.markdown(
            f'''
            <div class="news-item">
                <span class="status-badge {badge}">{item['source_type']}</span> <span style="font-size: 11px; color: #8b949e; float:right;">{item['time'][:16]}</span><br>
                <div style="margin-top: 8px;"><a href="{item['url']}" target="_blank" style="color: #F8FAFC; text-decoration: none; font-weight: 600; font-size: 13px;">{item['title']}</a></div>
                <div style="font-size: 11px; color: #94A3B8; margin-top: 4px;">{item['publisher']}</div>
            </div>
            ''', unsafe_allow_html=True
        )

def page_ai_analyst(hydro, weather, wqi, news, alerts):
    st.markdown("<div class='eyebrow'>HYDRO MIND / ANALYSIS</div>", unsafe_allow_html=True)
    st.markdown("<h1>AI ANALYST & RISK</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>Automated risk analysis and natural language interrogation.</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([45, 55])
    
    with col1:
        st.markdown("<h3>Risk Breakdown</h3>", unsafe_allow_html=True)
        st.markdown("""
        <div class="panel">
            <p><strong>Water Stress:</strong> <span class="status-badge badge-unavail">NOT SCORED</span><br><span style="color:#94A3B8; font-size:11px;">No official hydrology data available.</span></p>
            <p><strong>Flood / Surplus:</strong> <span class="status-badge badge-unavail">NOT SCORED</span><br><span style="color:#94A3B8; font-size:11px;">No official inflow data available.</span></p>
            <p><strong>Water Quality:</strong> <span class="status-badge badge-unavail">NOT SCORED</span><br><span style="color:#94A3B8; font-size:11px;">No current observation.</span></p>
            <p><strong>Runoff / Pollution:</strong> Evaluated via Weather/News</p>
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
                <div class="panel" style="border-left: 4px solid var(--{sev_class.replace('sev-', '')}, #FB923C);">
                    <div style="font-size: 11px; font-weight: 700; color: #FB923C; margin-bottom: 4px;">{alert['severity']}</div>
                    <div style="font-weight: 600; color: #F8FAFC; margin-bottom: 8px;">{alert['message']}</div>
                    <div style="font-size: 11px; color: #94A3B8;">{ev_str}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No active environmental alerts detected in the database.")
            
    with col2:
        st.markdown("<h3>AI ENVIRONMENTAL ANALYST</h3>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 11px; color: #34D399; margin-bottom: 16px;'>? READY</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='font-size: 11px; font-weight: 600; color: #94A3B8; margin-bottom: 8px;'>TOOLS AVAILABLE</div>", unsafe_allow_html=True)
        st.markdown("Reservoir Weather Satellite History Alerts News Official")
        
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        user_input = st.text_input("Ask about the current environmental state...", label_visibility="collapsed", placeholder="Ask about the current environmental state...")
        if st.button("Analyze", type="primary"):
            if user_input:
                agent = HydroAgent()
                with st.spinner("Agent is analyzing tools and building evidence..."):
                    response = agent.process_query(user_input)
                    st.markdown(f"<div class='panel' style='color:#F8FAFC;'>{response}</div>", unsafe_allow_html=True)

def main():
    if "page" not in st.session_state:
        st.session_state.page = "Mission Control"
        
    init_db()
    
    try:
        check = execute_query("SELECT COUNT(*) as count FROM observations")
        if not check or check[0]['count'] == 0:
            with st.spinner("Initializing system and fetching live intelligence..."):
                run_pipeline()
    except Exception:
        with st.spinner("Initializing system and fetching live intelligence..."):
            run_pipeline()
            
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
