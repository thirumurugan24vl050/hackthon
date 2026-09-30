"""
HYDRO MIND — Main Streamlit Application
"""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import folium
import streamlit.components.v1 as components

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from config.settings import APP_NAME, APP_SUBTITLE, APP_VERSION
from config.locations import BHAVANISAGAR_DAM
from database.db import execute_query, init_db
from agent.agent import HydroAgent
from scripts.orchestrator import run_pipeline

# --- Page Config ---
st.set_page_config(
    page_title=APP_NAME,
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Design Rules Applied ---
st.markdown("""
    <style>
    .stApp {
        background-color: #071017;
        color: #c9d1d9;
    }
    h1, h2, h3 {
        color: #f0f6fc;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
    }
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    .metric-card {
        background-color: rgba(15,30,39,0.72);
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin-bottom: 20px;
    }
    .status-badge {
        font-size: 0.8em;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .status-live { background-color: #238636; color: #ffffff; }
    .status-unavail { background-color: #30363d; color: #8b949e; }
    
    .risk-NORMAL { color: #3fb950; font-weight: bold; }
    .risk-WATCH { color: #d29922; font-weight: bold; }
    .risk-ELEVATED { color: #f0883e; font-weight: bold; }
    .risk-HIGH { color: #da3633; font-weight: bold; }
    .risk-CRITICAL { color: #b62324; font-weight: bold; }
    
    .news-item { margin-bottom: 10px; }
    .news-official { color: #36D6E8; font-weight: bold; font-size: 0.8em; border: 1px solid #36D6E8; padding: 2px 4px; border-radius: 4px; }
    .news-secondary { color: #8b949e; font-weight: bold; font-size: 0.8em; border: 1px solid #8b949e; padding: 2px 4px; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)


def fetch_dashboard_data(news_limit=20):
    """Fetch all necessary data from the SQLite database."""
    init_db()
    
    try:
        check = execute_query("SELECT COUNT(*) as count FROM observations")
        if check and check[0]['count'] == 0:
            with st.spinner("Initializing system and fetching live intelligence..."):
                run_pipeline()
    except Exception:
        pass
        
    hydro_data = {"status": "UNAVAILABLE", "level": "--", "storage": "--", "inflow": "--", "outflow": "--"}
    
    weather_rows = execute_query(
        "SELECT parameter, value, unit, timestamp_ist, status FROM observations WHERE source = 'Open-Meteo' ORDER BY id DESC LIMIT 4"
    )
    weather_data = {"status": "UNAVAILABLE", "temp": "--", "precip": "--", "wind": "--"}
    if weather_rows:
        weather_data["status"] = "LIVE"
        for row in weather_rows:
            if row["parameter"] == "temperature_2m": weather_data["temp"] = f"{row['value']} {row['unit']}"
            if row["parameter"] == "precipitation": weather_data["precip"] = f"{row['value']} {row['unit']}"
            if row["parameter"] == "wind_speed_10m": weather_data["wind"] = f"{row['value']} {row['unit']}"
            
    wqi_data = {"status": "UNAVAILABLE"}
    runoff_data = {"status": "UNAVAILABLE"}
    
    news = execute_query(
        f"SELECT title, url, publisher, source_type, published_at_utc as time FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT {news_limit}"
    )
    
    alerts = execute_query(
        "SELECT hazard_category, severity, message FROM alerts WHERE is_active = 1 ORDER BY created_at DESC"
    )
    
    return hydro_data, weather_data, wqi_data, runoff_data, news, alerts

def render_sidebar():
    with st.sidebar:
        st.title(f"💧 {APP_NAME}")
        st.caption("AI Environmental Intelligence Platform")
        
        st.divider()
        page = st.radio(
            "NAVIGATION",
            ["Mission Control", "Environmental Intelligence", "AI Analyst & Risk"],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.markdown("### Data Health")
        st.markdown("✅ **Weather:** Open-Meteo (LIVE)")
        st.markdown("✅ **Intelligence:** Google News (LIVE)")
        st.markdown("⚠️ **Hydrology:** CWC/TN-WRD (UNAVAILABLE)")
        st.markdown("⚠️ **Water Quality:** CPCB (UNAVAILABLE)")
        
        st.divider()
        if st.button("Refresh Dashboard"):
            st.rerun()
            
        return page

def render_hazard_card(title, status_text, value, baseline_text, risk_class):
    badge_class = "status-live" if status_text == "LIVE" else "status-unavail"
    html = f"""
    <div class="metric-card">
        <h4>{title}</h4>
        <span class="status-badge {badge_class}">{status_text}</span>
        <h2 class="risk-{risk_class}">{value}</h2>
        <p style="font-size: 0.8em; color: #8b949e;">{baseline_text}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def page_mission_control(hydro, weather, wqi, runoff, news, alerts):
    st.title("Mission Control")
    st.caption("High-level overview of Bhavanisagar Dam and the Lower Bhavani River.")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_hazard_card("WATER STRESS", hydro["status"], hydro["storage"], "Baseline: 32.8 TMC (Capacity)", "NORMAL")
    with col2:
        render_hazard_card("FLOOD/SURPLUS", hydro["status"], hydro["inflow"], "Threshold: >20,000 cusecs", "NORMAL")
    with col3:
        render_hazard_card("WATER QUALITY", wqi["status"], "--", "Threshold: >50 WQI", "NORMAL")
    with col4:
        r_risk = "NORMAL"
        r_val = "--"
        if weather["status"] == "LIVE":
            r_val = f"{weather['precip']} Precip"
            for a in alerts:
                if a["severity"] in ["ELEVATED", "HIGH", "CRITICAL"]:
                    r_risk = a["severity"]
                    r_val = "ELEVATED RISK"
        render_hazard_card("RUNOFF/POLLUTION", weather["status"], r_val, "Signals: Precip + Corroborated News", r_risk)

    st.divider()
    
    colA, colB = st.columns([2, 1])
    with colA:
        st.markdown("### Location Map")
        m = folium.Map(location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], zoom_start=11, tiles="OpenStreetMap")
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup=str(BHAVANISAGAR_DAM['name']),
            tooltip=str(BHAVANISAGAR_DAM['name'])
        ).add_to(m)
        components.html(m._repr_html_(), height=400)

    with colB:
        st.markdown("### Latest Environmental Updates")
        for item in news[:5]:
            badge = "news-official" if item["source_type"] == "OFFICIAL" else "news-secondary"
            st.markdown(
                f"""
                <div class="news-item">
                    <span class="{badge}">{item['source_type']}</span> <span style="font-size: 0.8em; color: #8b949e;">{item['time'][:16]}</span><br>
                    <a href="{item['url']}" target="_blank" style="color: #c9d1d9; text-decoration: none;"><b>{item['title']}</b></a><br>
                    <span style="font-size: 0.9em; color: #8b949e;">{item['publisher']}</span>
                </div>
                """, unsafe_allow_html=True
            )

def page_environmental_intelligence(hydro, weather, wqi, runoff, news, alerts):
    st.title("Environmental Intelligence")
    st.caption("Deep dive into source data, verified news, and satellite telemetry.")
    
    st.markdown("### 🟢 Official Updates")
    st.info("Awaiting official connection restore from CWC and TN-WRD. Fallback to secondary intelligence enabled.")
    
    st.markdown("### ☁️ Weather Telemetry")
    w_col1, w_col2, w_col3 = st.columns(3)
    w_col1.metric("Precipitation", weather["precip"])
    w_col2.metric("Temperature", weather["temp"])
    w_col3.metric("Wind Speed", weather["wind"])
    
    st.divider()
    
    st.markdown("### 🛰️ Satellite Indices (Sentinel-2)")
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("NDWI (Water Extent)", "UNAVAILABLE", help="Requires Earth Engine API")
    s_col2.metric("NDVI (Vegetation)", "UNAVAILABLE")
    s_col3.metric("Cloud Cover", "UNAVAILABLE")
    
    st.divider()
    
    st.markdown("### 📰 Google News Discovery")
    filter_type = st.radio("Filter", ["All", "Official", "Weather", "Reservoir", "Water"], horizontal=True)
    
    # Simple frontend filter mock
    filtered_news = news
    if filter_type != "All":
        pass # In a full app, implement filtering logic here
        
    for item in filtered_news[:10]:
        badge = "news-official" if item["source_type"] == "OFFICIAL" else "news-secondary"
        st.markdown(
            f"""
            <div class="news-item" style="background-color: rgba(15,30,39,0.5); padding: 10px; border-radius: 5px;">
                <span class="{badge}">{item['source_type']}</span> <span style="font-size: 0.8em; color: #8b949e;">{item['time'][:16]}</span><br>
                <a href="{item['url']}" target="_blank" style="color: #c9d1d9; text-decoration: none;"><b>{item['title']}</b></a><br>
                <span style="font-size: 0.9em; color: #8b949e;">{item['publisher']}</span>
            </div>
            """, unsafe_allow_html=True
        )

def page_ai_analyst(hydro, weather, wqi, runoff, news, alerts):
    st.title("AI Analyst & Risk")
    st.caption("Automated risk analysis and natural language interrogation.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Active Alerts")
        if alerts:
            for alert in alerts:
                st.error(f"**{alert['severity']}**: {alert['message']}")
        else:
            st.success("No active environmental alerts detected in the database.")
            
        st.markdown("### Risk Breakdown")
        st.markdown("""
        * **Water Stress:** 0/100 (No Official Data)
        * **Flood/Surplus:** Evaluated via Weather/News
        * **Water Quality:** 0/100 (No Official Data)
        * **Runoff/Pollution:** Linked to Precipitation
        """)
        
    with col2:
        st.markdown("### AI Environmental Analyst")
        st.markdown("Tools Available: `Reservoir`, `Weather`, `Satellite`, `History`, `Alerts`")
        
        user_input = st.text_input("Ask a question about the current environmental state:")
        if user_input:
            agent = HydroAgent()
            with st.spinner("Agent is analyzing tools and building evidence..."):
                response = agent.process_query(user_input)
                st.info(response)

def main():
    page = render_sidebar()
    hydro, weather, wqi, runoff, news, alerts = fetch_dashboard_data(news_limit=20)
    
    if page == "Mission Control":
        page_mission_control(hydro, weather, wqi, runoff, news, alerts)
    elif page == "Environmental Intelligence":
        page_environmental_intelligence(hydro, weather, wqi, runoff, news, alerts)
    elif page == "AI Analyst & Risk":
        page_ai_analyst(hydro, weather, wqi, runoff, news, alerts)

if __name__ == "__main__":
    main()
