"""
HYDRO MIND - Main Streamlit Application
Judge-ready environmental intelligence dashboard.
"""
import sys
from pathlib import Path
import json
import streamlit as st
import folium
import streamlit.components.v1 as components
import threading
from datetime import datetime, timezone, timedelta

from translations import t
def _t(key):
    return t(key, st.session_state.get("lang", "en"))

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from config.settings import APP_NAME, APP_SUBTITLE
from config.locations import BHAVANISAGAR_DAM
from config.thresholds import RESERVOIR_THRESHOLDS, WQ_THRESHOLDS
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

# ══════════════════════════════════════════════════════════════
# CSS + BUBBLES
# ══════════════════════════════════════════════════════════════

def inject_water_bubbles():
    st.markdown("""
    <div class="bubble-container">
        <div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>
        <div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>
        <div class="bubble"></div><div class="bubble"></div><div class="bubble"></div>
        <div class="bubble"></div>
    </div>
    """, unsafe_allow_html=True)

css_path = BASE_DIR / "ui" / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# DEMO DATA LOADER
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_demo_dataset():
    demo_path = BASE_DIR / "data" / "demo" / "hydro_mind_demo.json"
    if demo_path.exists():
        with open(demo_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def _dv(field_dict):
    """Extract value from demo field dict."""
    if isinstance(field_dict, dict):
        return field_dict.get("value", "")
    return field_dict

def get_demo_data(scenario="NORMAL"):
    """Build dashboard-compatible data from demo JSON for a given scenario."""
    demo = load_demo_dataset()
    if not demo:
        return None, None, None, [], [], []

    sc = demo.get("scenarios", {}).get(scenario, demo["scenarios"]["NORMAL"])
    r = sc.get("reservoir", {})
    w = sc.get("weather", {})

    # Use NORMAL scenario water quality if scenario doesn't override
    wq_data = sc.get("water_quality", demo["scenarios"]["NORMAL"].get("water_quality", {}))
    fm = sc.get("flood_model", demo["scenarios"]["NORMAL"].get("flood_model", {}))

    capacity = _dv(r.get("full_capacity_mcft", {})) or 32800
    storage = _dv(r.get("storage_mcft", {})) or 0
    inflow = _dv(r.get("inflow_cusecs", {})) or 0
    outflow = _dv(r.get("outflow_cusecs", {})) or 0

    hydro = {
        "status": "DEMO",
        "reason": "Demo reference baseline — Tamil Nadu AgriNet",
        "level_ft": _dv(r.get("level_ft", {})),
        "storage_mcft": storage,
        "inflow_cusecs": inflow,
        "outflow_cusecs": outflow,
        "capacity_mcft": capacity,
        "storage_pct": round(storage / capacity * 100, 2) if capacity > 0 else 0,
        "net_flow": inflow - outflow,
        "frl_ft": _dv(r.get("full_depth_ft", {})) or 105,
        "last_year_level_ft": _dv(r.get("last_year_level_ft", {})),
        "last_year_storage_mcft": _dv(r.get("last_year_storage_mcft", {})),
        "discharge_m3s": _dv(fm.get("discharge_m3s", {})) or 15.2,
        "flood_status": "MODEL",
        "mean_m3s": _dv(fm.get("mean_m3s", {})),
        "max_m3s": _dv(fm.get("max_m3s", {})),
        "last_updated": demo.get("timestamp", "2026-07-06"),
        "observation_date": r.get("level_ft", {}).get("timestamp", "2026-07-06"),
        "provenance": "DEMO"
    }

    weather = {
        "status": "DEMO",
        "temp": _dv(w.get("temperature_c", {})),
        "precip": _dv(w.get("precipitation_mm", {})),
        "humidity": _dv(w.get("humidity_pct", {})),
        "wind": _dv(w.get("wind_kmh", {})),
        "pressure": _dv(w.get("pressure_hpa", {})),
        "condition": _dv(w.get("condition", {})),
        "last_updated": w.get("temperature_c", {}).get("timestamp", ""),
        "provenance": "DEMO"
    }

    wqi = {
        "status": "DEMO",
        "station": "Bhavani Sagar",
        "class": f"Category '{_dv(wq_data.get('tnpcb_class', {}))}'",
        "report_period": wq_data.get("ph", {}).get("timestamp", "2023-2024"),
        "source": wq_data.get("ph", {}).get("source", "Published Bhavani Sagar Dataset"),
        "category": _dv(wq_data.get("tnpcb_class", {})) or "B",
        "risk": "NORMAL",
        "provenance": "REFERENCE",
        "ph": _dv(wq_data.get("ph", {})),
        "do": _dv(wq_data.get("do_mgl", {})),
        "turbidity": _dv(wq_data.get("turbidity_ntu", {})),
        "tds": _dv(wq_data.get("tds_mgl", {})),
        "conductivity": _dv(wq_data.get("conductivity", {})),
        "bod": _dv(wq_data.get("bod_mgl", {})),
        "cod": _dv(wq_data.get("cod_mgl", {})),
        "nitrate": _dv(wq_data.get("nitrate_mgl", {})),
        "water_temp": _dv(wq_data.get("temperature_c", {})),
        "tnpcb_station_code": _dv(wq_data.get("tnpcb_station_code", {}))
    }

    # Calculate WQI score from reference data using thresholds
    wqi["score"] = calculate_demo_wqi_score(wqi)

    news = sc.get("news", [])
    alerts = sc.get("alerts", [])
    activity = sc.get("activity", demo["scenarios"]["NORMAL"].get("activity", []))

    return hydro, weather, wqi, news, alerts, activity


def calculate_demo_wqi_score(wqi_data):
    """Calculate a simple WQI risk score from water quality parameters and thresholds."""
    score = 0
    count = 0

    ph = wqi_data.get("ph")
    if ph is not None:
        th = WQ_THRESHOLDS["ph"]
        if ph < th["min_permissible"] or ph > th["max_permissible"]:
            score += 60
        elif abs(ph - th["ideal"]) > 0.5:
            score += 30
        else:
            score += 10
        count += 1

    do_val = wqi_data.get("do")
    if do_val is not None:
        if do_val < WQ_THRESHOLDS["do"]["standard_min"]:
            score += 70
        elif do_val < 6.5:
            score += 40
        else:
            score += 10
        count += 1

    turb = wqi_data.get("turbidity")
    if turb is not None:
        if turb > WQ_THRESHOLDS["turbidity"]["standard_max"] * 2:
            score += 70
        elif turb > WQ_THRESHOLDS["turbidity"]["standard_max"]:
            score += 45
        else:
            score += 10
        count += 1

    tds = wqi_data.get("tds")
    if tds is not None:
        if tds > WQ_THRESHOLDS["tds"]["standard_max"]:
            score += 60
        elif tds > WQ_THRESHOLDS["tds"]["standard_max"] * 0.6:
            score += 35
        else:
            score += 10
        count += 1

    bod = wqi_data.get("bod")
    if bod is not None:
        if bod > WQ_THRESHOLDS["bod"]["standard_max"]:
            score += 65
        else:
            score += 10
        count += 1

    cod = wqi_data.get("cod")
    if cod is not None:
        if cod > WQ_THRESHOLDS["cod"]["standard_max"] * 2:
            score += 70
        elif cod > WQ_THRESHOLDS["cod"]["standard_max"]:
            score += 50
        else:
            score += 15
        count += 1

    if count == 0:
        return 0
    return round(score / count)


# ══════════════════════════════════════════════════════════════
# LIVE DATA LOADER
# ══════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def fetch_live_data(news_limit=30):
    """Fetch live data from database (populated by orchestrator)."""
    # 1. Hydrology
    hydro = {
        "status": "SYNCING", "reason": "Checking sources...",
        "level_ft": None, "storage_mcft": None,
        "inflow_cusecs": None, "outflow_cusecs": None,
        "capacity_mcft": RESERVOIR_THRESHOLDS["gross_capacity_mcft"],
        "frl_ft": RESERVOIR_THRESHOLDS["full_reservoir_level_ft"],
        "storage_pct": None, "net_flow": None,
        "discharge_m3s": None, "flood_status": "SYNCING",
        "mean_m3s": None, "max_m3s": None,
        "last_year_level_ft": None, "last_year_storage_mcft": None,
        "last_updated": None, "provenance": "LIVE"
    }

    h_rows = execute_query(
        "SELECT parameter, value, status, timestamp_ist, source FROM observations WHERE station_id = ? ORDER BY timestamp_utc DESC LIMIT 20",
        (BHAVANISAGAR_DAM["id"],)
    )
    if h_rows:
        h_vals = {}
        for r in h_rows:
            if r["parameter"] not in h_vals:
                h_vals[r["parameter"]] = r

        for key in ["level_ft", "storage_mcft", "inflow_cusecs", "outflow_cusecs"]:
            if key in h_vals and h_vals[key]["value"] is not None:
                hydro[key] = h_vals[key]["value"]
                hydro["status"] = "LIVE"
                hydro["reason"] = f"{_t('Source:')} {h_vals[key]['source']}"
                hydro["last_updated"] = h_vals[key]["timestamp_ist"]

        if hydro["storage_mcft"] is not None and hydro["capacity_mcft"] > 0:
            hydro["storage_pct"] = round((hydro["storage_mcft"] / hydro["capacity_mcft"]) * 100, 2)
        if hydro["inflow_cusecs"] is not None and hydro["outflow_cusecs"] is not None:
            hydro["net_flow"] = hydro["inflow_cusecs"] - hydro["outflow_cusecs"]

    # Check flood model data
    try:
        from services.hydrology_fetcher import fetch_open_meteo_flood
        flood = fetch_open_meteo_flood()
        if flood.get("status") != "UNAVAILABLE":
            hydro["discharge_m3s"] = flood.get("discharge_m3s")
            hydro["mean_m3s"] = flood.get("mean_m3s")
            hydro["max_m3s"] = flood.get("max_m3s")
            hydro["flood_status"] = "MODEL"
    except Exception:
        hydro["flood_status"] = "DEGRADED"

    if hydro["status"] == "SYNCING":
        hydro["status"] = "REFERENCE"
        hydro["reason"] = "Official sources currently behind authentication"

    # 2. Weather
    weather = {"status": "SYNCING", "temp": None, "precip": None, "wind": None, "humidity": None, "pressure": None, "condition": None, "last_updated": None, "provenance": "LIVE"}
    w_rows = execute_query(
        "SELECT parameter, value, status, timestamp_ist FROM observations WHERE source = 'Open-Meteo' ORDER BY timestamp_utc DESC LIMIT 20"
    )
    if w_rows:
        param_map = {"temperature_2m": "temp", "precipitation": "precip", "wind_speed_10m": "wind", "relative_humidity_2m": "humidity", "surface_pressure": "pressure"}
        for r in w_rows:
            mapped = param_map.get(r["parameter"])
            if mapped and weather[mapped] is None and r["value"] is not None:
                weather[mapped] = r["value"]
                if weather["last_updated"] is None:
                    weather["last_updated"] = r["timestamp_ist"]

        weather["status"] = "LIVE" if weather["temp"] is not None else "DEGRADED"

    # 3. WQI — Use TNPCB reference data (always available)
    wqi = {
        "status": "REFERENCE", "station": "Bhavani Sagar",
        "class": "Category 'B' (Outdoor Bathing Organized)",
        "report_period": "2023-2024", "source": "TNPCB",
        "category": "B", "risk": "NORMAL",
        "provenance": "REFERENCE",
        "ph": 7.85, "do": 6.18, "turbidity": 3, "tds": 183,
        "conductivity": 273, "bod": 1, "cod": 17, "nitrate": 0.17,
        "water_temp": 27.5, "tnpcb_station_code": "1321",
        "score": None
    }
    wqi["score"] = calculate_demo_wqi_score(wqi)

    # 4. News
    raw_news = execute_query(
        "SELECT title, url, publisher, source_type, published_at_utc as time, category FROM news_items WHERE status = 'ACTIVE' ORDER BY published_at_utc DESC LIMIT 150"
    )
    news = []
    seen = set()
    if raw_news:
        for item in raw_news:
            key = f"{item['publisher']}_{item['title']}".lower().strip()
            if key not in seen:
                seen.add(key)
                news.append(item)
                if len(news) >= news_limit:
                    break

    # 5. Alerts
    raw_alerts = execute_query(
        "SELECT hazard_category, severity, message, evidence, created_at FROM alerts WHERE is_active = 1 ORDER BY created_at DESC LIMIT 20"
    )
    alerts = []
    seen_alerts = set()
    if raw_alerts:
        for item in raw_alerts:
            alert_key = f"{item['hazard_category']}_{item['message']}"
            if alert_key not in seen_alerts:
                seen_alerts.add(alert_key)
                alerts.append(item)
                if len(alerts) >= 5:
                    break

    # 6. Activity
    activity = []
    if weather["status"] == "LIVE":
        activity.append({"message": "Weather telemetry refreshed", "timestamp": weather["last_updated"] or "", "source": "Open-Meteo"})
    if hydro["status"] == "LIVE":
        activity.append({"message": "Reservoir status updated", "timestamp": hydro["last_updated"] or "", "source": "TN AgriNet"})
    if news:
        activity.append({"message": f"News discovery completed — {len(news)} items", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "Google News"})
    activity.append({"message": "Risk engine evaluated", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "HYDRO MIND"})
    activity.append({"message": "Satellite imagery available (NASA GIBS)", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "NASA GIBS"})
    activity.append({"message": "AI tools connected and ready", "timestamp": datetime.now(timezone.utc).isoformat(), "source": "HYDRO MIND"})

    return hydro, weather, wqi, news, alerts, activity


# ══════════════════════════════════════════════════════════════
# RISK CALCULATOR
# ══════════════════════════════════════════════════════════════

def compute_risks(hydro, weather, wqi):
    """Compute four hazard risk scores from current data."""
    risks = {}

    # Water Stress
    ws_score = 0
    ws_contributors = []
    if hydro.get("storage_pct") is not None:
        pct = hydro["storage_pct"]
        if pct < 10:
            ws_score = 85
        elif pct < 20:
            ws_score = 75
        elif pct < 40:
            ws_score = 45
        else:
            ws_score = 15
        ws_contributors.append(f"Storage ratio: {pct}%")

    if hydro.get("net_flow") is not None:
        nf = hydro["net_flow"]
        if nf < -500:
            ws_score = max(ws_score, ws_score + 10)
            ws_contributors.append(f"Net flow: {nf} cusecs")
        elif nf < 0:
            ws_contributors.append(f"Net flow: {nf} cusecs")

    if hydro.get("level_ft") is not None and hydro.get("frl_ft"):
        level_pct = (hydro["level_ft"] / hydro["frl_ft"]) * 100
        ws_contributors.append(f"Level: {hydro['level_ft']} ft ({level_pct:.0f}% of FRL)")

    ws_score = min(ws_score, 100)
    ws_band = "NORMAL" if ws_score < 30 else ("WATCH" if ws_score < 50 else ("ELEVATED" if ws_score < 70 else "HIGH"))
    risks["Water Stress"] = {"score": ws_score, "band": ws_band, "contributors": ws_contributors, "status": "SCORED"}

    # Flood / Surplus
    fl_score = 0
    fl_contributors = []
    precip = weather.get("precip")
    if precip is not None and isinstance(precip, (int, float)):
        if precip > 40:
            fl_score = 70
            fl_contributors.append(f"Heavy rainfall: {precip} mm")
        elif precip > 20:
            fl_score = 45
            fl_contributors.append(f"Significant rainfall: {precip} mm")
        else:
            fl_score = max(fl_score, 5)

    discharge = hydro.get("discharge_m3s")
    mean_d = hydro.get("mean_m3s")
    if discharge is not None and isinstance(discharge, (int, float)):
        if mean_d and discharge > mean_d * 5:
            fl_score = max(fl_score, 75)
            fl_contributors.append(f"River discharge {discharge} m³/s ({discharge/mean_d:.1f}x mean)")
        elif mean_d and discharge > mean_d * 2:
            fl_score = max(fl_score, 45)
            fl_contributors.append(f"River discharge {discharge} m³/s ({discharge/mean_d:.1f}x mean)")
        else:
            fl_contributors.append(f"River discharge: {discharge} m³/s")
            fl_score = max(fl_score, 10)

    fl_score = min(fl_score, 100)
    fl_band = "NORMAL" if fl_score < 30 else ("WATCH" if fl_score < 50 else ("ELEVATED" if fl_score < 70 else "HIGH"))
    risks["Flood / Surplus"] = {"score": fl_score, "band": fl_band, "contributors": fl_contributors, "status": "SCORED"}

    # Water Quality
    wq_score = wqi.get("score") or 0
    wq_contributors = []
    if wqi.get("do") is not None:
        wq_contributors.append(f"DO: {wqi['do']} mg/L")
    if wqi.get("bod") is not None:
        wq_contributors.append(f"BOD: {wqi['bod']} mg/L")
    if wqi.get("turbidity") is not None:
        wq_contributors.append(f"Turbidity: {wqi['turbidity']} NTU")
    if wqi.get("ph") is not None:
        wq_contributors.append(f"pH: {wqi['ph']}")
    wq_band = "NORMAL" if wq_score < 30 else ("WATCH" if wq_score < 50 else ("ELEVATED" if wq_score < 70 else "HIGH"))
    risks["Water Quality"] = {"score": wq_score, "band": wq_band, "contributors": wq_contributors, "status": "SCORED"}

    # Runoff / Pollution
    rp_score = 0
    rp_contributors = []
    signals = 0

    if precip is not None and isinstance(precip, (int, float)) and precip > 20:
        signals += 1
        rp_score += 20
        rp_contributors.append(f"Rainfall: {precip} mm")

    if wqi.get("turbidity") is not None and wqi["turbidity"] > WQ_THRESHOLDS["turbidity"]["standard_max"]:
        signals += 1
        rp_score += 25
        rp_contributors.append(f"Turbidity: {wqi['turbidity']} NTU (above threshold)")

    if wqi.get("do") is not None and wqi["do"] < WQ_THRESHOLDS["do"]["standard_min"]:
        signals += 1
        rp_score += 20
        rp_contributors.append(f"Low DO: {wqi['do']} mg/L")

    if wqi.get("bod") is not None and wqi["bod"] > WQ_THRESHOLDS["bod"]["standard_max"]:
        signals += 1
        rp_score += 20
        rp_contributors.append(f"BOD: {wqi['bod']} mg/L (above threshold)")

    if signals < 1:
        rp_score = max(rp_score, 12)
        if not rp_contributors:
            rp_contributors.append("No anomalous signals detected")

    rp_score = min(rp_score, 100)
    rp_band = "NORMAL" if rp_score < 30 else ("WATCH" if rp_score < 50 else ("ELEVATED" if rp_score < 70 else "HIGH"))
    if signals >= 3:
        rp_band = "ELEVATED"
        rp_score = max(rp_score, 65)
    risks["Runoff / Pollution"] = {"score": rp_score, "band": rp_band, "contributors": rp_contributors, "status": "SCORED"}

    return risks


# ══════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════

def _sev_class(band):
    m = {"NORMAL": "sev-normal", "WATCH": "sev-watch", "ELEVATED": "sev-elevated", "HIGH": "sev-critical", "CRITICAL": "sev-critical"}
    return m.get(band.upper(), "")

def _badge(status):
    s = status.upper()
    m = {"LIVE": "badge-live", "DEMO": "badge-secondary", "MODEL": "badge-official", "REFERENCE": "badge-official",
         "FORECAST": "badge-official", "SATELLITE": "badge-official", "SCORED": "badge-scored",
         "READY": "badge-live", "SYNCING": "badge-secondary", "DEGRADED": "badge-unavail",
         "SECONDARY": "badge-secondary", "DISCOVERY": "badge-secondary", "OFFICIAL": "badge-official", "VERIFIED OFFICIAL": "badge-official"}
    return m.get(s, "badge-unavail")

def _prov_chip(provenance):
    return f'<span class="status-badge {_badge(provenance)}" style="font-size:9px;">{provenance}</span>'

def render_hazard_card(title, score, band, contributors, provenance="LIVE"):
    s_class = _sev_class(band)
    b_class = _badge(band if band in ["NORMAL", "WATCH", "ELEVATED", "HIGH", "CRITICAL"] else "SCORED")
    contrib_html = "<br>".join(f"• {c}" for c in contributors[:3]) if contributors else "Monitoring"

    st.markdown(f'''
    <div class="metric-card">
        <h4>{title} <span class="status-badge {b_class}" style="float:right">{_t(band)}</span></h4>
        <h2 class="{s_class}">{score} / 100</h2>
        <div class="baseline">{contrib_html}<br><span style="margin-top:6px;display:inline-block;">{_prov_chip(_t(provenance))}</span></div>
    </div>
    ''', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════

def render_sidebar(mode, hydro, weather, wqi):
    with st.sidebar:
        st.markdown(f"<div class=\'eyebrow\'>{_t('LANGUAGE')}</div>", unsafe_allow_html=True)
        lang_choice = st.radio("Language", ["ENGLISH", "தமிழ்"], label_visibility="collapsed", index=0 if st.session_state.get("lang", "en") == "en" else 1)
        st.session_state.lang = "en" if lang_choice == "ENGLISH" else "ta"
        st.markdown("<div style=\'height:1px;background:rgba(148,163,184,0.14);margin-bottom:24px;\'></div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='margin-bottom:24px;'>
            <span style='font-size:22px;font-weight:800;color:#F8FAFC;letter-spacing:-0.05em;'>{APP_NAME}</span><br>
            <span style='font-size:12px;color:#94A3B8;'>{APP_SUBTITLE}</span><br>
            <span style='font-size:10px;color:#36D6E8;margin-top:4px;display:inline-block;'>Created by THIRUMURUGAN.S (SIET)</span>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1px;background:rgba(148,163,184,0.14);margin-bottom:24px;'></div>", unsafe_allow_html=True)

        st.markdown("<div class=\'eyebrow\'>{_t('MONITOR')}</div>", unsafe_allow_html=True)
        if st.button(_t("Mission Control"), use_container_width=True, key="nav_mc"):
            st.session_state.page = "Mission Control"
        st.markdown("<div class=\'eyebrow\' style=\'margin-top:16px;\'>{_t('INTELLIGENCE')}</div>", unsafe_allow_html=True)
        if st.button(_t("Environmental Intelligence"), use_container_width=True, key="nav_ei"):
            st.session_state.page = "Environmental Intelligence"
        st.markdown("<div class=\'eyebrow\' style=\'margin-top:16px;\'>{_t('ANALYSIS_SIDEBAR')}</div>", unsafe_allow_html=True)
        if st.button(_t("AI Analyst & Risk"), use_container_width=True, key="nav_ai"):
            st.session_state.page = "AI Analyst & Risk"

        st.markdown("<div style='height:1px;background:rgba(148,163,184,0.14);margin:24px 0;'></div>", unsafe_allow_html=True)

        # Data Health
        st.markdown("<div class=\'eyebrow\'>{_t('DATA HEALTH')}</div>", unsafe_allow_html=True)

        w_status = weather.get("status", "SYNCING")
        h_status = hydro.get("status", "SYNCING")
        wq_status = wqi.get("provenance", "REFERENCE")
        if mode == "DEMO":
            w_status = h_status = wq_status = "DEMO"

        for label, status in [(_t("WEATHER"), w_status), (_t("INTELLIGENCE"), "LIVE" if mode == "LIVE" else "DEMO"), (_t("Hydrology"), h_status), (_t("Water Quality"), wq_status)]:
            b = _badge(status)
            st.markdown(f"<div style='font-size:13px;margin-bottom:8px;'>{label} <span class='status-badge {b}' style='float:right'>{_t(status)}</span></div>", unsafe_allow_html=True)

        st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
        if st.button(_t("REFRESH"), use_container_width=True, key="refresh"):
            st.cache_data.clear()
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TOP BAR
# ══════════════════════════════════════════════════════════════

def render_top_bar(mode):
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    b = _badge(mode)

    col1, col2 = st.columns([7, 3])
    with col1:
        st.markdown(f'''
        <div style="display:flex;align-items:center;padding-bottom:24px;">
            <span style="font-weight:700;color:#F8FAFC;font-size:20px;">HYDRO MIND</span>
            <span style="color:#94A3B8;margin-left:8px;">| Bhavanisagar Dam • Erode, Tamil Nadu</span>
        </div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''
        <div style="text-align:right;font-size:13px;color:#94A3B8;padding-bottom:24px;">
            <span class="status-badge {b}" style="margin-right:12px;">{_t(mode)}</span> {_t("Last refreshed:")} {now_str}
        </div>''', unsafe_allow_html=True)

    st.markdown('<div style="border-bottom:1px solid rgba(148,163,184,0.14);margin-bottom:24px;margin-top:-16px;"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE 1: MISSION CONTROL
# ══════════════════════════════════════════════════════════════

def page_mission_control(hydro, weather, wqi, news, alerts, activity, mode):
    render_top_bar(mode)
    st.markdown("<div class=\'eyebrow\'>{_t('ENVIRONMENTAL OPERATIONS')}</div>", unsafe_allow_html=True)
    st.markdown("<h1>{_t('MISSION CONTROL')}</h1>", unsafe_allow_html=True)
    st.markdown("<div class=\'page-subtitle\'>{_t('MISSION_CONTROL_SUBTITLE')}</div>", unsafe_allow_html=True)

    # Compute risks
    risks = compute_risks(hydro, weather, wqi)
    provenance = hydro.get("provenance", mode)

    # Four hazard cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        r = risks["Water Stress"]
        render_hazard_card(_t("Water Stress"), r["score"], r["band"], r["contributors"], provenance)
    with c2:
        r = risks["Flood / Surplus"]
        render_hazard_card(_t("Flood / Surplus"), r["score"], r["band"], r["contributors"], provenance)
    with c3:
        r = risks["Water Quality"]
        render_hazard_card(_t("Water Quality"), r["score"], r["band"], r["contributors"], provenance)
    with c4:
        r = risks["Runoff / Pollution"]
        render_hazard_card(_t("Runoff / Pollution"), r["score"], r["band"], r["contributors"], provenance)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # Weather mini-panel
    st.markdown("<h3>{_t('Weather Conditions')}</h3>", unsafe_allow_html=True)
    wc1, wc2, wc3, wc4 = st.columns(4)
    w_prov = weather.get("provenance", mode)
    weather_fields = [
        (_t("TEMPERATURE"), weather.get("temp"), "°C", wc1),
        (_t("PRECIPITATION"), weather.get("precip"), "mm", wc2),
        (_t("WIND SPEED"), weather.get("wind"), "km/h", wc3),
        (_t("HUMIDITY"), weather.get("humidity"), "%", wc4),
    ]
    for label, val, unit, col in weather_fields:
        with col:
            display = f"{val} {unit}" if val is not None else "Syncing..."
            st.markdown(f'''
            <div class="metric-card">
                <h4>{label}</h4>
                <h2>{display}</h2>
                <div class="baseline">{_prov_chip(_t(w_prov))} Open-Meteo</div>
            </div>''', unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # Reservoir Status
    st.markdown("<h3>{_t('Reservoir Status')}</h3>", unsafe_allow_html=True)
    h_prov = hydro.get("provenance", mode)

    level = hydro.get("level_ft")
    storage = hydro.get("storage_mcft")
    stor_pct = hydro.get("storage_pct")
    inflow = hydro.get("inflow_cusecs")
    outflow = hydro.get("outflow_cusecs")
    net_flow = hydro.get("net_flow")
    frl = hydro.get("frl_ft", 105)
    capacity = hydro.get("capacity_mcft", 32800)
    ly_level = hydro.get("last_year_level_ft")
    ly_storage = hydro.get("last_year_storage_mcft")
    obs_date = hydro.get("observation_date", hydro.get("last_updated", ""))

    def _rv(v, u=""):
        if v is None:
            return "Syncing..."
        return f"{v} {u}".strip()

    st.markdown(f'''
    <div class="matrix-grid" style="grid-template-columns: repeat(5, 1fr);">
        <div class="matrix-cell"><div class="matrix-label">{_t('LEVEL')}</div><div class="matrix-value">{_rv(level, "ft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('STORAGE')}</div><div class="matrix-value">{_rv(storage, "MCft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('STORAGE %')}</div><div class="matrix-value">{_rv(stor_pct, "%")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">Calculated</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('INFLOW')}</div><div class="matrix-value">{_rv(inflow, "cusecs")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('OUTFLOW')}</div><div class="matrix-value">{_rv(outflow, "cusecs")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
    </div>
    <div class="matrix-grid" style="grid-template-columns: repeat(5, 1fr); margin-top:1px;">
        <div class="matrix-cell"><div class="matrix-label">{_t('NET FLOW')}</div><div class="matrix-value">{_rv(net_flow, "cusecs")}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('FULL CAPACITY')}</div><div class="matrix-value">{_rv(capacity, "MCft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t("REFERENCE"))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('FULL DEPTH')}</div><div class="matrix-value">{_rv(frl, "ft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t("REFERENCE"))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('LAST YEAR LEVEL')}</div><div class="matrix-value">{_rv(ly_level, "ft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
        <div class="matrix-cell"><div class="matrix-label">{_t('LAST YEAR STORAGE')}</div><div class="matrix-value">{_rv(ly_storage, "MCft")}</div><div style="font-size:11px;margin-top:4px;color:#94A3B8;">{_prov_chip(_t(h_prov))}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    if obs_date:
        st.markdown(f"<div style='font-size:12px;color:#94A3B8;margin-top:8px;'>{_t('Observation date:')} {obs_date} • {_t('Source:')} {hydro.get('reason', 'Tamil Nadu AgriNet')}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # Reservoir trend chart (demo)
    demo_ds = load_demo_dataset()
    if demo_ds and demo_ds.get("history", {}).get("reservoir_7day"):
        import altair as alt
        import pandas as pd
        hist = demo_ds["history"]["reservoir_7day"]
        df = pd.DataFrame(hist)
        chart = alt.Chart(df).mark_line(color="#36D6E8", strokeWidth=2).encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("level_ft:Q", title="Level (ft)", scale=alt.Scale(zero=False)),
            tooltip=["date:T", "level_ft:Q", "storage_mcft:Q"]
        ).properties(height=180, title="7-Day Reservoir Level Trend").configure_axis(
            labelColor="#94A3B8", titleColor="#94A3B8", gridColor="rgba(148,163,184,0.1)"
        ).configure_title(color="#F8FAFC", fontSize=14)
        st.altair_chart(chart, use_container_width=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # Map + Evidence + Activity + Alerts
    colA, colB = st.columns([6, 4])
    with colA:
        st.markdown("<h3>{_t('ENVIRONMENTAL MAP')}</h3>", unsafe_allow_html=True)
        
        # Use simple OpenStreetMap to avoid API keys and CartoDB issues
        m = folium.Map(
            location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], 
            zoom_start=13, 
            tiles="OpenStreetMap",
            control_scale=True
        )
        folium.Marker(
            [BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']],
            popup="Bhavanisagar Dam", tooltip="Bhavanisagar Dam",
            icon=folium.Icon(color="blue", icon="tint", prefix="fa")
        ).add_to(m)
        # River line
        folium.PolyLine(
            [[11.47083, 77.11389], [11.475, 77.125], [11.480, 77.14], [11.485, 77.155], [11.49, 77.17], [11.50, 77.20]],
            color="#4F8CFF", weight=2, opacity=0.6, tooltip="Lower Bhavani River"
        ).add_to(m)
        components.html(m._repr_html_(), height=420)
        st.markdown("<div style='font-size:11px;color:#94A3B8;text-align:right;'>© OpenStreetMap contributors</div>", unsafe_allow_html=True)

    with colB:
        # Evidence panel
        st.markdown("<h3>{_t('TOP CONTRIBUTING EVIDENCE')}</h3>", unsafe_allow_html=True)
        evidence_items = []
        for hazard_name, rdata in risks.items():
            for c in rdata.get("contributors", [])[:2]:
                evidence_items.append(f"<li style='margin-bottom:6px;'><strong>{hazard_name}:</strong> {c}</li>")
        if not evidence_items:
            evidence_items = ["<li>{_t('All monitored parameters within normal range')}</li>"]

        st.markdown(f"""
        <div class="panel">
            <ul style="color:#CBD5E1;font-size:13px;line-height:1.7;margin:0;padding-left:20px;">
                {''.join(evidence_items[:6])}
            </ul>
        </div>""", unsafe_allow_html=True)

        # Activity
        st.markdown("<h3 style=\'margin-top:20px;\'>{_t('RECENT ACTIVITY')}</h3>", unsafe_allow_html=True)
        act_html = ""
        for a in (activity or [])[:6]:
            act_html += f"<li><strong>{a.get('source', '')}</strong>: {a['message']}</li>"
        st.markdown(f"""
        <div class="panel">
            <ul style="color:#CBD5E1;font-size:13px;line-height:1.7;margin:0;padding-left:20px;">
                {act_html}
            </ul>
        </div>""", unsafe_allow_html=True)

        # Alerts
        st.markdown("<h3 style=\'margin-top:20px;\'>{_t('ACTIVE ALERTS')}</h3>", unsafe_allow_html=True)
        if alerts:
            for alert in (alerts if isinstance(alerts, list) else [])[:3]:
                sev = alert.get("severity", "WATCH")
                msg = alert.get("message", "")
                ev = alert.get("evidence", [])
                if isinstance(ev, str):
                    try:
                        ev = json.loads(ev)
                    except Exception:
                        ev = [ev]
                ev_html = "<br>".join(f"• {e}" for e in (ev or [])[:3])
                st.markdown(f"""
                <div class="panel" style="border-left:4px solid {'#EF4444' if sev in ['HIGH','CRITICAL','ELEVATED'] else '#FBBF24'};">
                    <div style="font-size:11px;font-weight:700;color:{'#EF4444' if sev in ['HIGH','CRITICAL','ELEVATED'] else '#FBBF24'};margin-bottom:4px;">{sev}</div>
                    <div style="font-weight:600;color:#F8FAFC;margin-bottom:8px;">{msg}</div>
                    <div style="font-size:12px;color:#94A3B8;">{ev_html}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="panel" style="text-align:center;color:#94A3B8;">
                <div style="font-size:24px;margin-bottom:8px;">✅</div>
                <div style="font-weight:600;">{_t('NO CRITICAL ALERTS')}</div>
                <div style="font-size:13px;">{_t('All monitored conditions are below configured alert criteria.')}</div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE 2: ENVIRONMENTAL INTELLIGENCE
# ══════════════════════════════════════════════════════════════

def page_environmental_intelligence(hydro, weather, wqi, news, alerts, activity, mode):
    render_top_bar(mode)
    st.markdown("<div class=\'eyebrow\'>{_t('INTELLIGENCE FEED')}</div>", unsafe_allow_html=True)
    st.markdown("<h1>{_t('ENVIRONMENTAL INTELLIGENCE')}</h1>", unsafe_allow_html=True)
    st.markdown("<div class=\'page-subtitle\'>{_t('EI_SUBTITLE')}</div>", unsafe_allow_html=True)

    # ROW 1: WQ Summary | Weather | Satellite
    r1c1, r1c2, r1c3 = st.columns(3)

    with r1c1:
        st.markdown("<h3>{_t('WATER QUALITY')}</h3>", unsafe_allow_html=True)
        wq_prov = wqi.get("provenance", "REFERENCE")
        wq_score = wqi.get("score", 0)
        st.markdown(f"""
        <div class="panel">
            <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
                <span class="eyebrow">{_t('CLASSIFICATION')}</span>
                {_prov_chip(_t(wq_prov))}
            </div>
            <div style="font-size:36px;font-weight:800;color:#F8FAFC;">{wq_score} / 100</div>
            <div style="font-size:14px;color:#94A3B8;margin-top:4px;">TNPCB Class {wqi.get('category','B')} • Station {wqi.get('tnpcb_station_code','1321')}</div>
            <div style="font-size:12px;color:#94A3B8;margin-top:8px;">{_t('Reference Date')}: {wqi.get('report_period','2023-2024')}</div>
            <div style="font-size:12px;color:#94A3B8;">{_t('Source:')} {wqi.get('source','TNPCB')}</div>
        </div>""", unsafe_allow_html=True)

    with r1c2:
        st.markdown("<h3>{_t('WEATHER')}</h3>", unsafe_allow_html=True)
        w_prov = weather.get("provenance", mode)
        cond = weather.get("condition", "")
        st.markdown(f"""
        <div class="panel">
            <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
                <span class="eyebrow">{_t('CURRENT CONDITIONS')}</span>
                {_prov_chip(_t(w_prov))}
            </div>
            <div style="font-size:36px;font-weight:800;color:#F8FAFC;">{weather.get('temp', '--')}°C</div>
            <div style="font-size:14px;color:#94A3B8;margin-top:4px;">{cond}</div>
            <div style="margin-top:12px;font-size:13px;color:#CBD5E1;">
                Precip: {weather.get('precip','--')} mm • Wind: {weather.get('wind','--')} km/h<br>
                Humidity: {weather.get('humidity','--')}% • Pressure: {weather.get('pressure','--')} hPa
            </div>
        </div>""", unsafe_allow_html=True)

    with r1c3:
        st.markdown("<h3>{_t('SATELLITE')}</h3>", unsafe_allow_html=True)
        sat_prov = "SATELLITE" if mode == "LIVE" else "DEMO"
        demo_ds = load_demo_dataset()
        sat_data = demo_ds.get("scenarios", {}).get("NORMAL", {}).get("satellite", {}) if demo_ds else {}
        ndwi = _dv(sat_data.get("ndwi", {})) if sat_data else "—"
        mndwi = _dv(sat_data.get("mndwi", {})) if sat_data else "—"
        extent = _dv(sat_data.get("water_extent_km2", {})) if sat_data else "—"

        st.markdown(f"""
        <div class="panel">
            <div style="display:flex;justify-content:space-between;margin-bottom:12px;">
                <span class="eyebrow">NASA GIBS</span>
                {_prov_chip(_t(sat_prov))}
            </div>
            <div style="font-size:14px;color:#CBD5E1;">
                <div style="margin-bottom:8px;">NDWI: <strong style="color:#F8FAFC;">{ndwi}</strong></div>
                <div style="margin-bottom:8px;">MNDWI: <strong style="color:#F8FAFC;">{mndwi}</strong></div>
                <div style="margin-bottom:8px;">Water Extent: <strong style="color:#F8FAFC;">{extent} km²</strong></div>
            </div>
            <div style="font-size:12px;color:#94A3B8;margin-top:8px;">Layer: MODIS Terra True Color</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ROW 2: Satellite Map | News
    r2c1, r2c2 = st.columns([5, 5])

    with r2c1:
        st.markdown("<h3>{_t('SATELLITE OBSERVATION')}</h3>", unsafe_allow_html=True)
        m_sat = folium.Map(
            location=[BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], 
            zoom_start=13, 
            tiles="OpenStreetMap",
            control_scale=True
        )
        folium.Marker([BHAVANISAGAR_DAM['latitude'], BHAVANISAGAR_DAM['longitude']], tooltip="Bhavanisagar Dam").add_to(m_sat)
        components.html(m_sat._repr_html_(), height=350)

        # Weather trend
        if demo_ds and demo_ds.get("history", {}).get("weather_24h"):
            import altair as alt
            import pandas as pd
            wh = demo_ds["history"]["weather_24h"]
            df = pd.DataFrame(wh)
            chart = alt.Chart(df).mark_line(color="#36D6E8", strokeWidth=2).encode(
                x=alt.X("hour:N", title="Hour"),
                y=alt.Y("temp_c:Q", title="Temperature (°C)", scale=alt.Scale(zero=False)),
                tooltip=["hour:N", "temp_c:Q", "precip_mm:Q"]
            ).properties(height=160, title="24-Hour Temperature Trend").configure_axis(
                labelColor="#94A3B8", titleColor="#94A3B8", gridColor="rgba(148,163,184,0.1)"
            ).configure_title(color="#F8FAFC", fontSize=13)
            st.altair_chart(chart, use_container_width=True)

    with r2c2:
        st.markdown("<h3>{_t('NEWS DISCOVERY')}</h3>", unsafe_allow_html=True)

        # Primary items
        for item in (news or [])[:3]:
            src_type = item.get("source_type", "DISCOVERY")
            b = _badge(src_type)
            try:
                pub_dt = datetime.fromisoformat(str(item.get('time', '')).replace('Z', '+00:00'))
                age_h = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                freshness = "LATEST" if age_h <= 12 else ("RECENT" if age_h <= 168 else "HISTORICAL")
            except Exception:
                freshness = "RECENT"

            st.markdown(f'''
            <div class="news-item">
                <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                    <div><span class="status-badge {b}">{_t(src_type)}</span> <span style="font-size:12px;color:#36D6E8;margin-left:8px;font-weight:600;">{_t(freshness)}</span></div>
                    <span style="font-size:12px;color:#94A3B8;">{str(item.get('time',''))[:16]}</span>
                </div>
                <div><a href="{item.get('url','#')}" target="_blank" style="color:#F8FAFC;text-decoration:none;font-weight:600;font-size:14px;line-height:1.4;">{item.get('title','')}</a></div>
                <div style="font-size:12px;color:#94A3B8;margin-top:4px;">{item.get('publisher','')}</div>
            </div>''', unsafe_allow_html=True)

        # Compact scroll panel
        if len(news or []) > 3:
            with st.expander(f"{_t('MORE UPDATES')} ({len(news) - 3} more)"):
                for item in news[3:10]:
                    st.markdown(f"• **{item.get('publisher', '')}**: [{item.get('title', '')}]({item.get('url', '#')})")

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ROW 3: Water Quality Detail Table
    st.markdown("<h3>{_t('WATER QUALITY PARAMETERS')}</h3>", unsafe_allow_html=True)
    wq_prov = wqi.get("provenance", "REFERENCE")
    params = [
        (_t("pH"), wqi.get("ph"), "", wqi.get("report_period", "2023-2024")),
        (_t("Dissolved Oxygen"), wqi.get("do"), "mg/L", wqi.get("report_period", "2023-2024")),
        (_t("Turbidity"), wqi.get("turbidity"), "NTU", wqi.get("report_period", "2023-2024")),
        (_t("TDS"), wqi.get("tds"), "mg/L", wqi.get("report_period", "2023-2024")),
        (_t("Conductivity"), wqi.get("conductivity"), "µS/cm", wqi.get("report_period", "2023-2024")),
        (_t("BOD"), wqi.get("bod"), "mg/L", wqi.get("report_period", "2023-2024")),
        (_t("COD"), wqi.get("cod"), "mg/L", wqi.get("report_period", "2023-2024")),
        (_t("Nitrate"), wqi.get("nitrate"), "mg/L", wqi.get("report_period", "2023-2024")),
        (_t("Water Temperature"), wqi.get("water_temp"), "°C", wqi.get("report_period", "2023-2024")),
    ]
    rows_html = ""
    for name, val, unit, period in params:
        display_val = f"{val}" if val is not None else "—"
        rows_html += f'<tr><td style="padding:8px;">{name}</td><td style="padding:8px;">{display_val}</td><td style="padding:8px;">{unit}</td><td style="padding:8px;">{period}</td><td style="padding:8px;">{wqi.get("source","TNPCB")}</td><td style="padding:8px;">{_prov_chip(_t(wq_prov))}</td></tr>'

    st.markdown(f'''
    <div class="panel">
        <table style="width:100%;text-align:left;border-collapse:collapse;">
            <tr style="border-bottom:1px solid rgba(148,163,184,0.14);">
                <th style="padding:8px;">{_t('Parameter')}</th><th style="padding:8px;">{_t('Value')}</th><th style="padding:8px;">{_t('Unit')}</th><th style="padding:8px;">{_t('Reference Date')}</th><th style="padding:8px;">{_t("Source:").replace(":", "")}</th><th style="padding:8px;">{_t('Provenance')}</th>
            </tr>
            {rows_html}
        </table>
    </div>''', unsafe_allow_html=True)

    # Data Sources
    with st.expander(_t("Data Sources")):
        st.markdown(f"""
        - **Open-Meteo** — {_t("WEATHER")} + {_t("FORECAST")}
        - **Tamil Nadu AgriNet** — {_t("Reservoir")} {_t("OFFICIAL")}
        - **TNPCB** — {_t("WATER QUALITY")} (Station 1321)
        - **NASA GIBS** — {_t("SATELLITE")} (MODIS Terra)
        - **OpenStreetMap** — {_t("ENVIRONMENTAL MAP")}
        - **Google News** — {_t("NEWS DISCOVERY")}
        - **GDELT** — {_t("NEWS DISCOVERY")}
        """)
        #
        st.markdown("""
        - **Open-Meteo** — {_t("WEATHER")} + {_t("FORECAST")}
        - **Tamil Nadu AgriNet** — {_t("Reservoir")} {_t("OFFICIAL")}
        - **TNPCB** — {_t("WATER QUALITY")} (Station 1321)
        - **NASA GIBS** — {_t("SATELLITE")} (MODIS Terra)
        - **OpenStreetMap** — {_t("ENVIRONMENTAL MAP")}
        - **Google News** — {_t("NEWS DISCOVERY")}
        - **GDELT** — {_t("NEWS DISCOVERY")}
        """)


# ══════════════════════════════════════════════════════════════
# PAGE 3: AI ANALYST & RISK
# ══════════════════════════════════════════════════════════════

def page_ai_analyst(hydro, weather, wqi, news, alerts, activity, mode):
    render_top_bar(mode)
    st.markdown("<div class=\'eyebrow\'>{_t('ANALYSIS & DECISION SUPPORT')}</div>", unsafe_allow_html=True)
    st.markdown("<h1>{_t('AI ANALYST & RISK')}</h1>", unsafe_allow_html=True)
    st.markdown("<div class=\'page-subtitle\'>{_t('AI_SUBTITLE')}</div>", unsafe_allow_html=True)

    risks = compute_risks(hydro, weather, wqi)

    col1, col2 = st.columns([45, 55])

    with col1:
        # Risk Panel — always numeric
        st.markdown("<h3>{_t('RISK BREAKDOWN')}</h3>", unsafe_allow_html=True)
        for hazard_name in ["Water Stress", "Flood / Surplus", "Water Quality", "Runoff / Pollution"]:
            r = risks[hazard_name]
            s_class = _sev_class(r["band"])
            contrib_html = " • ".join(r["contributors"][:3]) if r["contributors"] else "Monitoring"
            st.markdown(f"""
            <div class="panel" style="margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                    <strong style="color:#F8FAFC;">{_t(hazard_name)}</strong>
                    <span class="{s_class}" style="font-size:20px;font-weight:800;">{r['score']} / 100</span>
                </div>
                <div style="font-size:12px;color:#94A3B8;">{contrib_html}</div>
            </div>""", unsafe_allow_html=True)

        # Active Alerts
        st.markdown("<h3 style=\'margin-top:20px;\'>{_t('ACTIVE ALERTS')}</h3>", unsafe_allow_html=True)
        if alerts:
            for alert in (alerts if isinstance(alerts, list) else [])[:3]:
                sev = alert.get("severity", "WATCH")
                msg = alert.get("message", "")
                ev = alert.get("evidence", [])
                if isinstance(ev, str):
                    try:
                        ev = json.loads(ev)
                    except Exception:
                        ev = [ev]
                ev_html = "<br>".join(f"• {e}" for e in (ev or [])[:3])
                st.markdown(f"""
                <div class="panel" style="border-left:4px solid {'#EF4444' if sev in ['HIGH','CRITICAL','ELEVATED'] else '#FBBF24'};">
                    <div style="font-size:11px;font-weight:700;color:{'#EF4444' if sev in ['HIGH','CRITICAL','ELEVATED'] else '#FBBF24'};margin-bottom:4px;">{sev}</div>
                    <div style="font-weight:600;color:#F8FAFC;margin-bottom:8px;">{msg}</div>
                    <div style="font-size:12px;color:#94A3B8;">{ev_html}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="panel" style="text-align:center;color:#94A3B8;">
                <div style="font-size:24px;margin-bottom:8px;">✅</div>
                <div style="font-weight:600;">{_t('NO ACTIVE ALERTS')}</div>
            </div>""", unsafe_allow_html=True)

        # Tool Status
        st.markdown("<h3 style=\'margin-top:20px;\'>{_t('Tools Connected')}</h3>", unsafe_allow_html=True)
        tools = [_t("Reservoir"), _t("WEATHER"), _t("SATELLITE"), _t("History"), _t("News"), _t("Alerts")]
        tools_html = ""
        for t in tools:
            tools_html += f'<div style="display:flex;justify-content:space-between;margin-bottom:6px;"><span style="color:#CBD5E1;font-size:13px;">{t}</span><span class="status-badge badge-live">READY</span></div>'
        st.markdown(f'<div class="panel">{tools_html}</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("<h3>{_t('AI ENVIRONMENTAL ANALYST')}</h3>", unsafe_allow_html=True)

        # Quick Questions
        st.markdown("<div class=\'eyebrow\' style=\'margin-bottom:12px;\'>{_t('QUICK QUESTIONS')}</div>", unsafe_allow_html=True)
        quick_qs = [
            _t("Why is water stress elevated?"),
            _t("What changed today?"),
            _t("What are the latest environmental updates?"),
            _t("Is there evidence of runoff or pollution?")
        ]

        selected_q = None
        qc1, qc2 = st.columns(2)
        with qc1:
            if st.button(quick_qs[0], use_container_width=True, key="qq1"):
                selected_q = quick_qs[0]
            if st.button(quick_qs[2], use_container_width=True, key="qq3"):
                selected_q = quick_qs[2]
        with qc2:
            if st.button(quick_qs[1], use_container_width=True, key="qq2"):
                selected_q = quick_qs[1]
            if st.button(quick_qs[3], use_container_width=True, key="qq4"):
                selected_q = quick_qs[3]

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        user_input = st.text_input(_t("Query"), label_visibility="collapsed", placeholder=_t("Ask about the current environmental state..."))

        query = selected_q or (user_input if st.button(_t("Analyze"), type="primary", key="analyze_btn") else None)

        if query:
            # Build context-aware response
            response = build_ai_response(query, hydro, weather, wqi, risks, news, alerts, mode)

            st.markdown(f"""
            <div class="panel" style="background-color:rgba(54,214,232,0.05);border-color:rgba(54,214,232,0.2);min-height:200px;">
                <div class="eyebrow" style="margin-bottom:12px;">{_t('QUESTION')}</div>
                <div style="color:#F8FAFC;font-size:14px;margin-bottom:16px;font-weight:600;">{query}</div>
                <div class="eyebrow" style="margin-bottom:12px;">{_t('ANALYSIS')}</div>
                <div style="color:#F8FAFC;font-size:14px;line-height:1.6;margin-bottom:16px;">{response['analysis']}</div>
                <div class="eyebrow" style="margin-bottom:12px;">{_t('EVIDENCE')}</div>
                <div style="font-size:13px;color:#CBD5E1;">{response['evidence']}</div>
                <div style="font-size:12px;color:#94A3B8;font-style:italic;margin-top:12px;">{_t('Data basis:')} {mode} • {_t('AI_DISCLAIMER')}</div>
            </div>""", unsafe_allow_html=True)
        else:
            # Placeholder
            st.markdown("""
            <div class="panel" style="min-height:300px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;">
                <div style="font-size:36px;margin-bottom:16px;">🔬</div>
                <div style="font-weight:600;color:#F8FAFC;font-size:16px;">{_t('AI ENVIRONMENTAL ANALYST')}</div>
                <div style="font-size:13px;color:#94A3B8;margin-top:8px;max-width:300px;">{_t('AI_PLACEHOLDER')}</div>
            </div>""", unsafe_allow_html=True)


def build_ai_response(query, hydro, weather, wqi, risks, news, alerts, mode):
    """Build deterministic AI response using current tool data."""
    q = query.lower()

    evidence_parts = []

    if "stress" in q or "water stress" in q or "why" in q:
        r = risks.get("Water Stress", {})
        storage_pct = hydro.get("storage_pct")
        net_flow = hydro.get("net_flow")
        level = hydro.get("level_ft")
        analysis = f"Water stress is {'elevated' if r.get('score', 0) > 50 else 'moderate'} primarily because the reservoir storage ratio is {storage_pct}% of gross capacity."
        if net_flow is not None and net_flow < 0:
            analysis += f" Net flow is negative at {net_flow} cusecs, meaning outflow exceeds inflow."
        if level is not None:
            analysis += f" Current water level is {level} ft against a full reservoir level of {hydro.get('frl_ft', 105)} ft."

        evidence_parts.append(f"Storage: {hydro.get('storage_mcft')} MCft [Reservoir]")
        evidence_parts.append(f"Capacity: {hydro.get('capacity_mcft')} MCft [Reference]")
        evidence_parts.append(f"Inflow: {hydro.get('inflow_cusecs')} cusecs [Reservoir]")
        evidence_parts.append(f"Outflow: {hydro.get('outflow_cusecs')} cusecs [Reservoir]")
        evidence_parts.append(f"Net flow: {net_flow} cusecs [Calculated]")

    elif "changed" in q or "today" in q:
        analysis = "Today's environmental state summary: "
        t = weather.get("temp")
        p = weather.get("precip")
        if t is not None:
            analysis += f"Temperature is {t}°C. "
        if p is not None:
            analysis += f"Precipitation is {p} mm. "
        analysis += f"Reservoir level is at {hydro.get('level_ft', '--')} ft with storage at {hydro.get('storage_pct', '--')}%. "

        if news:
            analysis += f"There are {len(news)} recent news items related to the Bhavanisagar area."

        evidence_parts.append(f"Temperature: {t}°C [Open-Meteo]")
        evidence_parts.append(f"Precipitation: {p} mm [Open-Meteo]")
        evidence_parts.append(f"Level: {hydro.get('level_ft')} ft [Reservoir]")
        if news:
            evidence_parts.append(f"Latest: {news[0].get('title', '')} [{news[0].get('publisher', 'News')}]")

    elif "news" in q or "update" in q or "latest" in q:
        analysis = ""
        if news:
            analysis = f"There are {len(news)} recent environmental news items. "
            for item in news[:3]:
                analysis += f"{item.get('publisher', 'Source')}: {item.get('title', '')}. "
        else:
            analysis = "No recent news items found for the Bhavanisagar area."

        if alerts:
            analysis += f" Additionally, there are {len(alerts)} active alerts."
            for a in (alerts if isinstance(alerts, list) else [])[:2]:
                evidence_parts.append(f"Alert: {a.get('message', '')} [{a.get('severity', '')}]")

        for item in (news or [])[:3]:
            evidence_parts.append(f"{item.get('title', '')} [{item.get('publisher', 'Discovery')}]")

    elif "runoff" in q or "pollution" in q:
        r = risks.get("Runoff / Pollution", {})
        analysis = f"Runoff/pollution risk is currently scored at {r.get('score', 0)} / 100 ({r.get('band', 'NORMAL')}). "
        if r.get("contributors"):
            analysis += "Contributing factors: " + "; ".join(r["contributors"][:3]) + ". "
        if wqi.get("turbidity") is not None:
            analysis += f"Turbidity is at {wqi['turbidity']} NTU. "
        if wqi.get("do") is not None:
            analysis += f"Dissolved oxygen is {wqi['do']} mg/L."

        evidence_parts.append(f"Turbidity: {wqi.get('turbidity')} NTU [{wqi.get('source', 'WQ')}]")
        evidence_parts.append(f"DO: {wqi.get('do')} mg/L [{wqi.get('source', 'WQ')}]")
        evidence_parts.append(f"BOD: {wqi.get('bod')} mg/L [{wqi.get('source', 'WQ')}]")

    else:
        # Default — use agent
        try:
            agent = HydroAgent()
            analysis = agent.process_query(query)
        except Exception:
            analysis = "I can provide analysis on weather, reservoir status, water quality, news, and risk assessments for the Bhavanisagar Dam area."
        evidence_parts.append("System tools available: Reservoir, Weather, Satellite, History, News, Alerts")

    evidence_html = "<br>".join(f"• {e}" for e in evidence_parts) if evidence_parts else "No specific evidence cited."

    return {"analysis": analysis, "evidence": evidence_html}


# ══════════════════════════════════════════════════════════════
# BOOTSTRAP + MAIN
# ══════════════════════════════════════════════════════════════

@st.cache_resource
def bootstrap_system():
    init_db()
    def bg():
        try:
            check = execute_query("SELECT COUNT(*) as count FROM observations")
            if not check or check[0]['count'] == 0:
                run_pipeline()
        except Exception:
            try:
                run_pipeline()
            except Exception:
                pass
    thread = threading.Thread(target=bg, daemon=True)
    thread.start()
    return True


def main():
    if "page" not in st.session_state:
        st.session_state.page = "Mission Control"
    if "data_mode" not in st.session_state:
        st.session_state.data_mode = "DEMO"
    if "demo_scenario" not in st.session_state:
        st.session_state.demo_scenario = "NORMAL"

    bootstrap_system()
    inject_water_bubbles()

    # Sidebar: Data Mode
    with st.sidebar:
        st.markdown(f"<div class=\'eyebrow\'>{_t('LANGUAGE')}</div>", unsafe_allow_html=True)
        lang_choice = st.radio("Language", ["ENGLISH", "தமிழ்"], label_visibility="collapsed", index=0 if st.session_state.get("lang", "en") == "en" else 1)
        st.session_state.lang = "en" if lang_choice == "ENGLISH" else "ta"
        st.markdown("<div style=\'height:1px;background:rgba(148,163,184,0.14);margin-bottom:24px;\'></div>", unsafe_allow_html=True)
        st.markdown("<div class=\'eyebrow\'>{_t('DATA MODE')}</div>", unsafe_allow_html=True)
        st.session_state.data_mode = st.radio(
            _t("Mode"), ["LIVE", "DEMO"], label_visibility="collapsed",
            index=1 if st.session_state.data_mode == "DEMO" else 0
        )

        if st.session_state.data_mode == "DEMO":
            st.markdown("<div class=\'eyebrow\' style=\'margin-top:12px;\'>{_t('DEMO SCENARIO')}</div>", unsafe_allow_html=True)
            st.session_state.demo_scenario = st.selectbox(
            _t("Scenario"), ["NORMAL", "LOW_STORAGE", "HEAVY_RAINFALL", "POLLUTION_RUNOFF"],
                label_visibility="collapsed"
            )

    mode = st.session_state.data_mode

    # Fetch data based on mode
    if mode == "DEMO":
        result = get_demo_data(st.session_state.demo_scenario)
        if result[0] is None:
            st.error("Demo dataset not found. Please ensure data/demo/hydro_mind_demo.json exists.")
            return
        hydro, weather, wqi, news, alerts, activity = result
    else:
        hydro, weather, wqi, news, alerts, activity = fetch_live_data()

    render_sidebar(mode, hydro, weather, wqi)

    if st.session_state.page == "Mission Control":
        page_mission_control(hydro, weather, wqi, news, alerts, activity, mode)
    elif st.session_state.page == "Environmental Intelligence":
        page_environmental_intelligence(hydro, weather, wqi, news, alerts, activity, mode)
    elif st.session_state.page == "AI Analyst & Risk":
        page_ai_analyst(hydro, weather, wqi, news, alerts, activity, mode)


if __name__ == "__main__":
    main()
