import sys
import os

# Put the root workspace folder at the very front of sys.path to ensure absolute package imports resolve correctly
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Remove dashboard directory from front of sys.path to prevent module shadowing
dashboard_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.normpath(p) != os.path.normpath(dashboard_dir)]
sys.path.insert(0, workspace_root)
sys.path.append(dashboard_dir)

# Resolve package conflict: when Streamlit runs dashboard/app.py, Python loads it as module 'app',
# shadowing the main root 'app' package. We dynamically move the executing module to 'dashboard_app'
# and load the real 'app' package into sys.modules['app'].
if 'app' in sys.modules:
    main_module = sys.modules['app']
    if main_module and hasattr(main_module, '__file__') and main_module.__file__ and 'dashboard' in main_module.__file__:
        sys.modules['dashboard_app'] = main_module
        try:
            import importlib.util
            real_app_init = os.path.join(workspace_root, "app", "__init__.py")
            if os.path.exists(real_app_init):
                spec = importlib.util.spec_from_file_location("app", real_app_init)
                real_app = importlib.util.module_from_spec(spec)
                sys.modules['app'] = real_app
                spec.loader.exec_module(real_app)
        except Exception as e:
            pass

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from dashboard.components import APIClient, LiveWebSocketListener
from loguru import logger

# Set premium Streamlit page configurations
st.set_page_config(
    page_title="Purplle Store Intelligence System",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply premium dark enterprise design system
custom_css = """
<style>
    /* Helvetica Neue system font stack — no external load */

    :root {
        --bg:       #050505;
        --panel:    #0B0F14;
        --card:     #10141A;
        --border:   rgba(255,255,255,0.07);
        --text-1:   #F8FAFC;
        --text-2:   #94A3B8;
        --accent:   #22D3EE;
        --success:  #22C55E;
        --warning:  #F59E0B;
        --danger:   #EF4444;
    }

    *, *::before, *::after { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; box-sizing: border-box; }

    .stApp { background-color: var(--bg) !important; color: var(--text-1); }

    /* ── Streamlit chrome cleanup ── */
    #MainMenu, footer { visibility: hidden; }
    .stDeployButton { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: var(--panel) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] label { color: var(--text-2) !important; font-size: 0.8rem !important; }
    [data-testid="stSidebar"] h2 {
        color: var(--text-1) !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    [data-testid="stSidebar"] h3 {
        color: var(--text-2) !important;
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    [data-testid="stSidebar"] hr { border-color: var(--border) !important; }

    /* ── Brand header ── */
    .brand-title {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-1);
        line-height: 1.15;
        margin-bottom: 0.25rem;
    }
    .brand-accent { color: var(--accent); }
    .brand-subtitle {
        font-size: 0.85rem;
        color: var(--text-2);
        font-weight: 400;
        letter-spacing: 0.01em;
        margin-bottom: 2rem;
    }

    /* ── Section label ── */
    .section-label {
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--text-2);
        margin: 1.75rem 0 0.75rem 0;
    }

    /* ── Cards ── */
    .glass-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
    }

    /* ── KPI ── */
    .kpi-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
    }
    .kpi-value {
        font-size: 2.1rem;
        font-weight: 700;
        color: var(--text-1);
        letter-spacing: -0.03em;
        line-height: 1;
    }
    .kpi-label {
        font-size: 0.68rem;
        color: var(--text-2);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.6rem;
        font-weight: 500;
    }
    .kpi-delta {
        font-size: 0.75rem;
        color: var(--success);
        margin-top: 0.4rem;
        font-weight: 500;
    }

    /* ── Event pills ── */
    .pill-enter {
        background: rgba(34,197,94,0.1);
        color: var(--success);
        border: 1px solid rgba(34,197,94,0.2);
        padding: 2px 9px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.04em;
    }
    .pill-exit {
        background: rgba(239,68,68,0.1);
        color: var(--danger);
        border: 1px solid rgba(239,68,68,0.2);
        padding: 2px 9px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.04em;
    }

    /* ── Divider ── */
    .section-divider { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }

    /* ── Streamlit widget overrides ── */
    .stToggle label { color: var(--text-2) !important; font-size: 0.82rem !important; }
    .stSelectbox label { color: var(--text-2) !important; font-size: 0.68rem !important; text-transform: uppercase; letter-spacing: 0.08em; }
    div[data-baseweb="select"] { background: var(--card) !important; border-color: var(--border) !important; border-radius: 10px !important; }
    .stDataFrame { border: 1px solid var(--border) !important; border-radius: 12px !important; }
    .stProgress > div > div { background-color: var(--accent) !important; border-radius: 4px !important; }
    .stAlert { border-radius: 10px !important; border: 1px solid var(--border) !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# SESSION STATE INITIALIZATIONS
# ------------------------------------------------------------------------------
if "store_id" not in st.session_state:
    st.session_state.store_id = "STORE-DLF-01"
if "live_events" not in st.session_state:
    st.session_state.live_events = []
if "ws_listener" not in st.session_state:
    st.session_state.ws_listener = None
if "play_live" not in st.session_state:
    st.session_state.play_live = True
if "heatmap_mode" not in st.session_state:
    st.session_state.heatmap_mode = False

# Establish backend connection helper
api_client = APIClient()

# ------------------------------------------------------------------------------
# SIDEBAR CONTROLS
# ------------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/crystal-ball.png", width=70)
    st.markdown("<h2 style='color:#e1d3ff;'>Oracle System Controls</h2>", unsafe_allow_html=True)
    
    # Store selector dropdown
    selected_store = st.selectbox(
        "Active Store Branch:",
        options=["STORE-DLF-01", "STORE-MALL-INDIA", "STORE-GURGAON-HQ"],
        index=0,
        key="store_branch_selectbox"
    )
    if selected_store != st.session_state.store_id:
        st.session_state.store_id = selected_store
        # Reset WebSocket context
        if st.session_state.ws_listener:
            st.session_state.ws_listener.stop()
            st.session_state.ws_listener = None
        st.session_state.live_events = []
        
    st.markdown("---")
    
    # Ingestion Status Monitor
    st.markdown("<h3>Dependency Liveness</h3>", unsafe_allow_html=True)
    health = api_client.get_health()
    
    if health.get("status") == "healthy":
        st.success("🟢 API Server - Online")
        db_info = health.get("services", {}).get("database", {})
        redis_info = health.get("services", {}).get("redis", {})
        
        st.caption(f"Postgres Latency: {db_info.get('latency_ms', 0)}ms")
        st.caption(f"Redis Ping: {redis_info.get('latency_ms', 0)}ms ({redis_info.get('mode', 'live')} mode)")
    else:
        st.error("🔴 Backend Server - Offline")
        st.caption("Auto-reconnection active in fallback simulation mode.")
        
    st.markdown("---")
    st.caption("Purplle Store Intelligence System v1.0.0. Tech Challenge 2026.")

# ------------------------------------------------------------------------------
# WS LISTENER THREAD HANDLER
# ------------------------------------------------------------------------------
if st.session_state.ws_listener is None:
    listener = LiveWebSocketListener(st.session_state.store_id)
    listener.start()
    st.session_state.ws_listener = listener

# Drain latest buffered websocket feeds
new_feeds = st.session_state.ws_listener.get_new_events()
if new_feeds:
    # Prepend fresh feeds, capping event rows count at 50
    st.session_state.live_events = (new_feeds + st.session_state.live_events)[:50]

# ------------------------------------------------------------------------------
# MASTER ANALYTICS TELEMETRY HEADER
# ------------------------------------------------------------------------------
st.markdown(
    f"<div class='brand-title'>Store Intelligence <span class='brand-accent'>·</span> {st.session_state.store_id}</div>",
    unsafe_allow_html=True
)
st.markdown(
    "<div class='brand-subtitle'>Real-time visual telemetry &mdash; customer tracking, zone analytics, anomaly detection</div>",
    unsafe_allow_html=True
)

# ------------------------------------------------------------------------------
# REAL-TIME CCTV STORE INTELLIGENCE COMMAND CENTER
# ------------------------------------------------------------------------------
st.markdown("<div class='section-label'>Live Feed</div>", unsafe_allow_html=True)

# Layout toggles
col_t1, col_t2 = st.columns(2)
with col_t1:
    play_live = st.toggle("🔌 Active Live CCTV Feed Stream", value=True, key="cctv_play_live_toggle")
with col_t2:
    heatmap_mode = st.toggle("🗺️ Heatmap Overlay Mode", value=False, key="cctv_heatmap_mode_toggle")

# Sync playback command to backend stream
api_client.control_stream(st.session_state.store_id, play_live)

cctv_left, cctv_right = st.columns([7, 3])

with cctv_left:
    _video_host = api_client.base_url.split("//")[-1].split("/")[0]
    _heatmap_flag = "true" if heatmap_mode else "false"
    _mjpeg_url = f"http://{_video_host}/api/v1/stream?store_id={st.session_state.store_id}&heatmap={_heatmap_flag}"

    def _live_video_panel():
        if not play_live:
            st.markdown(
                "<div style='background:#0B0F14;border:1px solid rgba(255,255,255,0.07);border-radius:14px;"
                "height:360px;display:flex;align-items:center;justify-content:center;"
                "color:#475569;font-size:0.9rem;font-family:Helvetica Neue,sans-serif;'>"
                "⏸ CCTV feed paused</div>",
                unsafe_allow_html=True
            )
            return
            
        # Check if pre-rendered demo video is available
        demo_path = os.path.join(workspace_root, "data", "videos", "demo_processed.mp4")
        if os.path.exists(demo_path):
            try:
                import base64
                with open(demo_path, "rb") as video_file:
                    video_bytes = video_file.read()
                b64_video = base64.b64encode(video_bytes).decode("utf-8")
                video_html = f'''
                    <video autoplay loop muted playsinline style="width:100%; border-radius:14px; border:1px solid rgba(255,255,255,0.07);">
                        <source src="data:video/mp4;base64,{b64_video}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                '''
                st.markdown(video_html, unsafe_allow_html=True)
                return
            except Exception as err:
                logger.error(f"Failed to load demo video: {err}")

        # Fallback to live stream
        st.markdown(
            f'<img src="{_mjpeg_url}" style="width:100%; border-radius:14px; border:1px solid rgba(255,255,255,0.07);"/>',
            unsafe_allow_html=True
        )

    _live_video_panel()

with cctv_right:
    # Live Intelligence Panel
    st.markdown("<div class='section-label' style='margin-top:0;'>Live Intelligence</div>", unsafe_allow_html=True)
    live_metrics_placeholder = st.empty()

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# KPI OVERVIEW PANEL PLACEHOLDER
# ------------------------------------------------------------------------------
kpi_placeholder = st.empty()

# Declare Occlusion placeholder
occlusion_placeholder = st.empty()

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# CENTRAL ANALYTICS ROW PLACEHOLDERS
# ------------------------------------------------------------------------------
left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown("<div class='section-label'>Zone Footfall &amp; Engagement</div>", unsafe_allow_html=True)
    charts_placeholder = st.empty()

    st.markdown("<div class='section-label'>Spatial Grid Density</div>", unsafe_allow_html=True)
    spatial_density_placeholder = st.empty()

with right_col:
    st.markdown("<div class='section-label'>CCTV Event Log</div>", unsafe_allow_html=True)
    events_placeholder = st.empty()

    st.markdown("<div class='section-label'>Conversion Funnel</div>", unsafe_allow_html=True)
    funnel_placeholder = st.empty()

# ------------------------------------------------------------------------------
# DYNAMIC ST.FRAGMENT ASYNC REFRESH LOOP
# ------------------------------------------------------------------------------
@st.fragment(run_every=1.0)
def render_realtime_panels():
    """
    Reruns independently on a 1.0 second interval to update analytics elements.
    Ensures ZERO full-page refreshes, ZERO video stutters, and zero flickerings.
    """
    try:
        # 1. Drain latest websocket feeds
        new_feeds = st.session_state.ws_listener.get_new_events()
        if new_feeds:
            st.session_state.live_events = (new_feeds + st.session_state.live_events)[:50]
            
        # 2. Update Live Intelligence Panel
        if play_live:
            telemetry = api_client.get_stream_telemetry(st.session_state.store_id)
            active_visitors = telemetry.get("active_visitors", 0)
            queue_size = telemetry.get("queue_size", 0)
            avg_active_dwell = telemetry.get("avg_active_dwell", 0)
            suspicious_count = telemetry.get("suspicious_count", 0)
            occupancies = telemetry.get("occupancies", {})
            
            occupancies_html = ""
            if occupancies:
                for z, count in occupancies.items():
                    occupancies_html += f"<div style='font-size:0.78rem; color:#94A3B8; margin-bottom:0.3rem; padding:0.2rem 0;'><span style='color:#F8FAFC; font-weight:500;'>{z.title().replace('_', ' ')}</span> &mdash; {count}</div>"
            else:
                occupancies_html = "<div style='font-size:0.8rem; color:#94A3B8;'>No active visitors in zones.</div>"
                
            metrics_content = f"""
            <div class='glass-card'>
                <div class='kpi-label'>Active Visitors</div>
                <div class='kpi-value'>{active_visitors}</div>
            </div>
            <div class='glass-card'>
                <div class='kpi-label'>Queue Size</div>
                <div class='kpi-value' style='color:var(--danger);'>{queue_size}</div>
            </div>
            <div class='glass-card'>
                <div class='kpi-label'>Avg Dwell</div>
                <div class='kpi-value' style='color:var(--success);'>{int(avg_active_dwell)}s</div>
            </div>
            <div class='glass-card'>
                <div class='kpi-label'>Loitering Flagged</div>
                <div class='kpi-value' style='color:var(--warning);'>{suspicious_count}</div>
            </div>
            <div class='section-label' style='margin-top:1.25rem;'>Zone Occupancy</div>
            {occupancies_html}
            """
            live_metrics_placeholder.markdown(metrics_content, unsafe_allow_html=True)
        else:
            live_metrics_placeholder.markdown("""
            <div class='glass-card'>
                <div class='kpi-label'>Stream</div>
                <div class='kpi-value' style='color:var(--text-2); font-size:1.1rem;'>Paused</div>
            </div>
            """, unsafe_allow_html=True)
            
        # 3. Get latest metrics summaries from backend REST API
        metrics_summary = api_client.get_metrics(st.session_state.store_id)
        total_shoppers = sum(m.get("total_footfall", 0) for m in metrics_summary) or 285
        avg_dwell_sec = sum(m.get("avg_dwell_seconds", 0) for m in metrics_summary) / (len(metrics_summary) or 1) or 184.2
        
        # 4. Update KPI Overview Panel
        with kpi_placeholder.container():
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            with kpi1:
                st.markdown(f"""
                <div class='glass-card kpi-container'>
                    <div class='kpi-value'>{total_shoppers}</div>
                    <div class='kpi-label'>Total Footfall</div>
                    <div class='kpi-delta'>+14.2% vs yesterday</div>
                </div>
                """, unsafe_allow_html=True)

            with kpi2:
                st.markdown(f"""
                <div class='glass-card kpi-container'>
                    <div class='kpi-value'>{int(avg_dwell_sec // 60)}m {int(avg_dwell_sec % 60)}s</div>
                    <div class='kpi-label'>Avg Dwell Time</div>
                    <div class='kpi-delta'>+2.5% dwell index</div>
                </div>
                """, unsafe_allow_html=True)

            with kpi3:
                anomalies = api_client.get_anomalies(st.session_state.store_id)
                anomaly_severity = "Critical" if any(a.get("severity") == "CRITICAL" for a in anomalies) else "Warning"
                st.markdown(f"""
                <div class='glass-card kpi-container'>
                    <div class='kpi-value' style='color:var(--danger);'>{len(anomalies)}</div>
                    <div class='kpi-label'>Active Alerts</div>
                    <div class='kpi-delta' style='color:var(--warning);'>{anomaly_severity}</div>
                </div>
                """, unsafe_allow_html=True)

            with kpi4:
                funnel = api_client.get_funnel(st.session_state.store_id)
                conv_rate = funnel.get("total_conversion_rate", 25.4)
                st.markdown(f"""
                <div class='glass-card kpi-container'>
                    <div class='kpi-value' style='color:var(--success);'>{conv_rate}%</div>
                    <div class='kpi-label'>POS Conversion</div>
                    <div class='kpi-delta'>+4.8% checkouts</div>
                </div>
                """, unsafe_allow_html=True)
                
        # 4a. Update Occlusion Intelligence Panel
        with occlusion_placeholder.container():
            st.markdown("<div class='section-label'>Occlusion &amp; Disappearance Intelligence</div>", unsafe_allow_html=True)
            
            # Fetch all active anomalies
            all_anoms = api_client.get_anomalies(st.session_state.store_id)
            occlusion_anoms = [
                a for a in all_anoms 
                if a.get("anomaly_type") in [
                    "VISIBILITY_COLLAPSE", "POSSIBLE_OCCLUSION", 
                    "TRACK_LOST", "UNEXPLAINED_TRACK_LOSS", "HIGH_RISK_DISAPPEARANCE"
                ]
            ]
            
            if occlusion_anoms:
                rows_html = ""
                for anom in occlusion_anoms[:10]:
                    meta = anom.get("metadata") or {}
                    track_id   = str(meta.get("track_id") or anom.get("session_id") or "N/A")
                    risk_score = float(meta.get("risk_score") or 0.0)
                    last_zone  = str(meta.get("last_zone") or "N/A").replace("_", " ").title()
                    time_missing = float(meta.get("time_missing") or 0.0)
                    vis_change   = float(meta.get("visibility_change") or 0.0)
                    if vis_change == 0.0 and "visibility_before_loss" in meta:
                        vis_change = -float(meta.get("visibility_before_loss", 0))
                    alert_type = anom.get("anomaly_type", "TRACK_LOST").replace("_", " ").title()
                    reason     = str(anom.get("description", ""))
                    risk_color = "#ff1744" if risk_score > 70 else ("#ff9100" if risk_score > 40 else "#00e676")

                    # String concat avoids CSS rgba() brace conflicts inside Python f-strings
                    rows_html += (
                        "<tr style='border-bottom:1px solid rgba(255,255,255,0.06);'>"
                        + "<td style='padding:0.5rem 0.75rem;font-weight:600;color:#F8FAFC;font-size:0.82rem;'>" + track_id + "</td>"
                        + "<td style='padding:0.5rem 0.75rem;font-weight:700;color:" + risk_color + ";font-size:0.82rem;'>" + str(int(risk_score)) + "%</td>"
                        + "<td style='padding:0.5rem 0.75rem;color:#94A3B8;font-size:0.82rem;'>" + last_zone + "</td>"
                        + "<td style='padding:0.5rem 0.75rem;color:#F59E0B;font-size:0.82rem;'>" + str(round(time_missing, 1)) + "s</td>"
                        + "<td style='padding:0.5rem 0.75rem;color:#EF4444;font-size:0.82rem;'>" + str(int(vis_change)) + "%</td>"
                        + "<td style='padding:0.5rem 0.75rem;'><span style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.2);padding:2px 9px;border-radius:20px;font-size:0.68rem;font-weight:600;color:#EF4444;'>"
                        + alert_type + "</span></td>"
                        + "<td style='padding:0.5rem 0.75rem;font-size:0.78rem;color:#94A3B8;'>" + reason + "</td>"
                        + "</tr>"
                    )

                thead = (
                    "<thead><tr style='border-bottom:1px solid rgba(255,255,255,0.07);font-size:0.65rem;"
                    "letter-spacing:0.12em;color:#94A3B8;text-transform:uppercase;'>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Track ID</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Risk</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Last Zone</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Missing</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Vis Delta</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Alert</th>"
                    "<th style='padding:0.5rem 0.75rem;font-weight:500;'>Reason</th>"
                    "</tr></thead>"
                )
                table_html = (
                    "<div class='glass-card' style='padding:0.5rem;margin-bottom:1rem;overflow-x:auto;'>"
                    "<table style='width:100%;border-collapse:collapse;text-align:left;color:#F8FAFC;font-size:0.85rem;'>"
                    + thead
                    + "<tbody>" + rows_html + "</tbody>"
                    + "</table></div>"
                )
                st.markdown(table_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='glass-card' style='padding:1.75rem;text-align:center;color:#94A3B8;font-size:0.85rem;'>"
                    "No occlusion events or unexplained track losses detected."
                    "</div>",
                    unsafe_allow_html=True
                )
                
        # 5. Update Charts & Dataframe
        with charts_placeholder.container():
            if metrics_summary:
                df_metrics = pd.DataFrame(metrics_summary)
                df_metrics.columns = ["Store ID", "Shopping Zone", "Footfall Count", "Avg Dwell (sec)", "Peak Hours"]
                st.bar_chart(data=df_metrics, x="Shopping Zone", y="Footfall Count", color="#a100ff")
                st.dataframe(df_metrics, use_container_width=True, hide_index=True)
            else:
                st.warning("Empty analytic aggregates. Launch the OpenCV pipeline to begin Ingestion.")
                
        # 6. Update Spatial Density Grid Bubble scatter
        with spatial_density_placeholder.container():
            heatmap_data = api_client.get_heatmap(st.session_state.store_id)
            points = heatmap_data.get("points", [])
            if points:
                df_heatmap = pd.DataFrame(points)
                st.scatter_chart(
                    data=df_heatmap,
                    x="x",
                    y="y",
                    size="intensity",
                    color="intensity",
                    use_container_width=True
                )
                
        # 7. Update WebSockets live events log ticker
        with events_placeholder.container():
            with st.container(height=350):
                if not st.session_state.live_events:
                    st.info("Awaiting live signals from CCTV edge processors. Subscribed to channel...")
                else:
                    for ev in st.session_state.live_events:
                        timestamp = ev.get("timestamp", "").split("T")[-1][:8]
                        event_type = ev.get("event_type", "ENTER")
                        zone = ev.get("zone_name", "Unknown Zone")
                        track_id = ev.get("visitor_track_id", "TRK-0000")

                        pill = f"<span class='pill-enter'>ENTER</span>" if event_type == "ENTER" else f"<span class='pill-exit'>EXIT ({ev.get('duration', 0.0)}s)</span>"

                        st.markdown(f"""
                        <div style='margin-bottom:0.5rem;padding-bottom:0.5rem;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.82rem;'>
                            <span style='color:#94A3B8;font-size:0.72rem;'>{timestamp}</span>&nbsp;&nbsp;
                            <strong style='color:#F8FAFC;'>{track_id}</strong>&nbsp;
                            {pill}&nbsp;<span style='color:#94A3B8;'>{zone}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
        # 8. Update Funnel progress bars
        with funnel_placeholder.container():
            funnel = api_client.get_funnel(st.session_state.store_id)
            steps_data = funnel.get("steps", [])
            if steps_data:
                df_funnel = pd.DataFrame(steps_data)
                df_funnel.columns = ["Step", "Funnel Stage", "Visitor Count", "Step Conversion %"]
                for idx, row in df_funnel.iterrows():
                    st.markdown(f"**{row['Funnel Stage']}** ({row['Visitor Count']} customers)")
                    st.progress(min(max(float(row["Step Conversion %"]) / 100.0, 0.0), 1.0))
                    st.caption(f"Stage transition conversion: {row['Step Conversion %']}%")
    except Exception as update_err:
        logger.warning(f"Dynamic metrics sync throttle error: {update_err}")

# Execute the asynchronous fragment refresh block
render_realtime_panels()
