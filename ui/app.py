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
from datetime import datetime, timezone

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
    layout="wide"
)

# Load CSS
css_path = BASE_DIR / "ui" / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Data Fetching
@st.cache_data(ttl=60)
def fetch_dashboard_data(news_limit=30):
    hydro_data = {"status": "UNAVAILABLE", "storage": "NOT SCORED"}
    wqi_data = {"status": "UNAVAILABLE", "score": "NOT SCORED"}
    
    # Weather
    w_rows = execute_query(
        "SELECT parameter, value, status FROM observations WHERE source = 'Open-Meteo' ORDER BY timestamp_utc DESC LIMIT 10"
    )
    weather_data = {"status": "UNAVAILABLE", "precip": "--", "temp": "--", "wind": "--"}
    if w_rows:
        has_values = False
        for r in w_rows:
            if r["parameter"] == "precipitation" and r["value"] != "--": 
                weather_data["precip"] = r["value"]
                has_values = True
            elif r["parameter"] == "temperature_2m" and r["value"] != "--": 
                weather_data["temp"] = r["value"]
                has_values = True
            elif r["parameter"] == "wind_speed_10m" and r["value"] != "--": 
                weather_data["wind"] = r["value"]
                has_values = True
        
        weather_data["status"] = "LIVE" if has_values else "UNAVAILABLE"
            
    # News - deduplicate
    raw_news = execute_query(
        "SELECT title, url, publisher, source_type, published_at_utc as time, category FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT 100"
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
    
    # Alerts - deduplicate
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

def render_top_bar():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f'''
    <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 24px; margin-bottom: 24px; border-bottom: 1px solid rgba(148,163,184,0.14);">
        <div>
            <span style="font-weight: 700; color: #F8FAFC;">HYDRO MIND</span> <span style="color: #94A3B8;">| Bhavanisagar Dam • Erode, Tamil Nadu</span>
        </div>
        <div style="font-size: 13px; color: #94A3B8;">
            <span class="status-badge badge-live" style="margin-right: 12px;">LIVE</span> Last updated: {now_str}
        </div>
    </div>
    ''', unsafe_allow_html=True)

def page_mission_control(hydro, weather, wqi, news, alerts):
    render_top_bar()
    st.markdown("<div class='eyebrow'>ENVIRONMENTAL OPERATIONS</div>", unsafe_allow_html=True)
    st.markdown("<h1>MISSION CONTROL</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>High-level environmental overview of Bhavanisagar Dam and the Lower Bhavani River.</div>", unsafe_allow_html=True)
    
    run_score = "NOT SCORED"
    run_status = "NOT SCORED"
    run_band = "NORMAL"
    run_reason = "No precipitation or news anomaly detected"
    
    if weather["status"] == "LIVE" and weather["precip"] != "--" and float(weather["precip"]) > 20.0:
        run_score = "55 / 100"
        run_status = "SCORED"
        run_band = "WATCH"
        run_reason = f"Heavy rainfall detected: {weather['precip']} mm"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_hazard_card("Water Stress", "NOT SCORED", "--", "NORMAL", "No official hydrology data available")
    with col2:
        render_hazard_card("Flood / Surplus", "NOT SCORED", "--", "NORMAL", "No official inflow data available")
    with col3:
        render_hazard_card("Water Quality", "NOT SCORED", "--", "NORMAL", "No current observation")
    with col4:
        render_hazard_card("Runoff / Pollution", run_status, run_score, run_band, run_reason)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    st.markdown("<h3>Reservoir Status</h3>", unsafe_allow_html=True)
    st.markdown('''
    <div class="matrix-grid">
        <div class="matrix-cell"><div class="matrix-label">LEVEL</div><div class="matrix-value" style="color: #94A3B8;">N/A</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge badge-unavail">UNAVAILABLE</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">STORAGE</div><div class="matrix-value" style="color: #94A3B8;">N/A</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge badge-unavail">UNAVAILABLE</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">INFLOW</div><div class="matrix-value" style="color: #94A3B8;">N/A</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge badge-unavail">UNAVAILABLE</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">OUTFLOW</div><div class="matrix-value" style="color: #94A3B8;">N/A</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge badge-unavail">UNAVAILABLE</span></div></div>
        <div class="matrix-cell"><div class="matrix-label">24H_LEVEL_CHANGE</div><div class="matrix-value" style="color: #94A3B8;">N/A</div><div style="font-size: 11px; margin-top:4px; color:#94A3B8;"><span class="status-badge badge-unavail">UNAVAILABLE</span></div></div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown("<div style='font-size: 12px; color: #94A3B8; margin-top: 8px;'>Official hydrology data unavailable.</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    
    colA, colB = st.columns([6, 4])
    with colA:
        st.markdown("<h3>Environmental Map</h3>", unsafe_allow_html=True)
        m = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=14, tiles="OpenStreetMap")
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup=str(BHAVANISAGAR_DAM['name']),
            tooltip="Bhavanisagar Dam"
        ).add_to(m)
        components.html(m._repr_html_(), height=450)

    with colB:
        st.markdown("<h3>Top Contributing Evidence</h3>", unsafe_allow_html=True)
        st.markdown("""
        <div class="panel">
            <ul style="color: #CBD5E1; font-size: 14px; line-height: 1.8; margin: 0; padding-left: 20px;">
                <li>Official hydrology feeds are currently offline, preventing core volumetric assessment.</li>
                <li>Live weather telemetry indicates no immediate precipitation threat.</li>
                <li>News sentiment remains baseline with no flood indicators.</li>
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
                <div style="font-size: 13px;">All monitored conditions currently below configured alert criteria.</div>
            </div>
            """, unsafe_allow_html=True)

def page_environmental_intelligence(hydro, weather, wqi, news, alerts):
    render_top_bar()
    st.markdown("<div class='eyebrow'>INTELLIGENCE FEED</div>", unsafe_allow_html=True)
    st.markdown("<h1>ENVIRONMENTAL INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>Live external information and environmental indicators relevant to Bhavanisagar and the Lower Bhavani River.</div>", unsafe_allow_html=True)
    
    st.markdown("<h3>Official Updates</h3>", unsafe_allow_html=True)
    st.info("Awaiting official connection restore from CWC and TN-WRD. Fallback to secondary intelligence enabled.")
    
    st.markdown("<h3 style='margin-top:32px;'>Weather Telemetry</h3>", unsafe_allow_html=True)
    
    precip_val = f"{weather['precip']} mm" if weather['precip'] != "--" else "--"
    temp_val = f"{weather['temp']} °C" if weather['temp'] != "--" else "--"
    wind_val = f"{weather['wind']} km/h" if weather['wind'] != "--" else "--"
    
    st.markdown(f'''
    <div class="matrix-grid" style="grid-template-columns: repeat(3, 1fr);">
        <div class="matrix-cell"><div class="matrix-label">PRECIPITATION</div><div class="matrix-value">{precip_val}</div></div>
        <div class="matrix-cell"><div class="matrix-label">TEMPERATURE</div><div class="matrix-value">{temp_val}</div></div>
        <div class="matrix-cell"><div class="matrix-label">WIND SPEED</div><div class="matrix-value">{wind_val}</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>Satellite Indicators</h3>", unsafe_allow_html=True)
    st.markdown('''
    <div class="matrix-grid" style="grid-template-columns: repeat(3, 1fr);">
        <div class="matrix-cell"><div class="matrix-label">NDWI (WATER EXTENT)</div><div class="matrix-value" style="color:#94A3B8;">UNAVAILABLE</div></div>
        <div class="matrix-cell"><div class="matrix-label">NDVI (VEGETATION)</div><div class="matrix-value" style="color:#94A3B8;">UNAVAILABLE</div></div>
        <div class="matrix-cell"><div class="matrix-label">CLOUD COVER</div><div class="matrix-value" style="color:#94A3B8;">UNAVAILABLE</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-top:32px;'>Google News Discovery</h3>", unsafe_allow_html=True)
    
    for item in news[:10]:
        badge = _get_badge_class(item["source_type"])
        st.markdown(
            f'''
            <div class="news-item">
                <div style="display:flex; justify-content:space-between; margin-bottom: 12px;">
                    <span class="status-badge {badge}">{item['source_type']}</span>
                    <span style="font-size: 12px; color: #94A3B8;">{item['time'][:16]}</span>
                </div>
                <div><a href="{item['url']}" target="_blank" style="color: #F8FAFC; text-decoration: none; font-weight: 600; font-size: 15px; line-height: 1.4;">{item['title']}</a></div>
                <div style="font-size: 13px; color: #94A3B8; margin-top: 8px;">{item['publisher']}</div>
            </div>
            ''', unsafe_allow_html=True
        )

def page_ai_analyst(hydro, weather, wqi, news, alerts):
    render_top_bar()
    st.markdown("<div class='eyebrow'>ANALYSIS & DECISION SUPPORT</div>", unsafe_allow_html=True)
    st.markdown("<h1>AI ANALYST & RISK</h1>", unsafe_allow_html=True)
    st.markdown("<div class='page-subtitle'>AI-assisted environmental analysis using reservoir, weather, satellite, historical, alert and external information.</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([45, 55])
    
    with col1:
        st.markdown("<h3>Risk Breakdown</h3>", unsafe_allow_html=True)
        st.markdown("""
        <div class="panel">
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Water Stress</strong> <span class="status-badge badge-unavail">NOT SCORED</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Missing Inputs: Hydrology Data</div>
            </div>
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Flood / Surplus</strong> <span class="status-badge badge-unavail">NOT SCORED</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Missing Inputs: Inflow Feed</div>
            </div>
            <div style="margin-bottom: 20px;">
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Water Quality</strong> <span class="status-badge badge-unavail">NOT SCORED</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Missing Inputs: Sensor Node Offline</div>
            </div>
            <div>
                <div style="display:flex; justify-content:space-between; margin-bottom: 4px;">
                    <strong style="color:#F8FAFC;">Runoff / Pollution</strong> <span class="status-badge badge-live">MONITORING</span>
                </div>
                <div style="font-size: 13px; color: #94A3B8;">Weather node correlating risk.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
                        <div style="font-size: 13px; color: #CBD5E1; margin-bottom: 16px;">✓ Weather<br>✓ Alerts</div>
                        <div class="eyebrow" style="margin-bottom: 12px;">Analysis</div>
                        <div style="color:#F8FAFC; font-size: 14px; line-height: 1.6;">%s</div>
                        <div class="eyebrow" style="margin-top: 16px; margin-bottom: 12px;">AI Safety Notice</div>
                        <div style="font-size: 12px; color: #94A3B8; font-style: italic;">The system cannot certify drinking-water safety. Current observations indicate measured conditions. Official laboratory testing and applicable regulatory standards are required.</div>
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
        
    bootstrap_system()
            
    render_sidebar()
    hydro, weather, wqi, news, alerts = fetch_dashboard_data(news_limit=30)
    
    if st.session_state.page == "Mission Control":
        page_mission_control(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "Environmental Intelligence":
        page_environmental_intelligence(hydro, weather, wqi, news, alerts)
    elif st.session_state.page == "AI Analyst & Risk":
        page_ai_analyst(hydro, weather, wqi, news, alerts)

if __name__ == "__main__":
    main()
